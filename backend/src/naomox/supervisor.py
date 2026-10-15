"""Tâches de fond par borne : présence, time hack, mode serveur, démarrage automatique.

- Présence : connexion TCP au port NetDIMM (comme `port_check` de singleboot.py),
  avec anti-rebond (2 sondes concordantes), suspendue pendant un transfert.
- Time hack : paquet 0x17 périodique (timehack.py de WiPi) quand la borne est en ligne.
- Mise sous tension détectée (hors ligne → en ligne) :
    * mode serveur : renvoie le dernier jeu (logique de netdimm_ensure) ;
    * sinon, une seule fois après le démarrage du service : `default_game`
      (logique de singleboot.py).
  Dans les deux cas, rien n'est envoyé si la NetDIMM contient déjà ce jeu (CRC identique).
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import logging
import time
from dataclasses import dataclass
from typing import Any

from netdimm import CRCStatusEnum, NetDimm, NetDimmInfo, NetDimmTargetEnum

from .config import Config
from .events import EventBroker
from .jobs import JobManager
from .storage import Cabinet, CabinetsStore, GamesStore, RuntimeStore, resolve_in
from .systems import netdimm_target

log = logging.getLogger("naomox.supervisor")

RUNNING_STATUSES = {CRCStatusEnum.STATUS_VALID, CRCStatusEnum.STATUS_CHECKING, CRCStatusEnum.STATUS_DISABLED}


@dataclass
class CabinetStatus:
    online: bool | None = None
    since: float | None = None
    ok: int = 0
    fail: int = 0
    last_probe: float | None = None
    timehack_last: float = 0.0
    timehack_ok: bool | None = None
    autoboot_done: bool = False
    last_error: str | None = None


async def probe(ip: str, port: int, limit: float) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), limit)
    except (OSError, TimeoutError):
        return False
    writer.close()
    with contextlib.suppress(Exception):
        await writer.wait_closed()
    return True


async def discover(subnet: str, port: int, probe_timeout: float = 0.8, concurrency: int = 128) -> list[str]:
    """Balaye le sous-réseau à la recherche du port NetDIMM ouvert (remplace nmap)."""
    net = ipaddress.ip_network(subnet, strict=False)
    sem = asyncio.Semaphore(concurrency)

    async def one(ip: str) -> str | None:
        async with sem:
            return ip if await probe(ip, port, probe_timeout) else None

    results = await asyncio.gather(*(one(str(h)) for h in net.hosts()))
    return [ip for ip in results if ip]


def info_to_dict(info: NetDimmInfo) -> dict[str, Any]:
    return {
        "firmware": info.firmware_version.value,
        "memory_mb": info.memory_size,
        "game_memory_bytes": info.available_game_memory,
        "current_game_crc": f"0x{info.current_game_crc:08x}",
        "current_game_size": info.current_game_size,
        "crc_status": info.game_crc_status.name.removeprefix("STATUS_").lower(),
        "control_address": f"0x{info.control_address:08x}",
    }


class Supervisor:
    def __init__(
        self,
        config: Config,
        cabinets: CabinetsStore,
        games: GamesStore,
        jobs: JobManager,
        runtime: RuntimeStore,
        events: EventBroker,
    ) -> None:
        self.config = config
        self.cabinets = cabinets
        self.games = games
        self.jobs = jobs
        self.runtime = runtime
        self.events = events
        self._status: dict[str, CabinetStatus] = {}
        self._task: asyncio.Task[None] | None = None

    # -- cycle de vie --------------------------------------------------------------

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="supervisor")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _loop(self) -> None:
        while True:
            cabs = [c for c in self.cabinets.all() if c.enabled]
            for stale in set(self._status) - {c.id for c in self.cabinets.all()}:
                self._status.pop(stale, None)
            await asyncio.gather(*(self._safe_tick(c) for c in cabs))
            await asyncio.sleep(self.config.netdimm.probe_interval)

    async def _safe_tick(self, cab: Cabinet) -> None:
        try:
            await self.tick(cab)
        except Exception:
            log.exception("supervision de %s", cab.name)

    # -- état ----------------------------------------------------------------------

    def status(self, cab_id: str) -> CabinetStatus:
        return self._status.setdefault(cab_id, CabinetStatus())

    def is_online(self, cab_id: str) -> bool:
        return bool(self.status(cab_id).online) or self.jobs.lock(cab_id).locked()

    def status_dict(self, cab: Cabinet) -> dict[str, Any]:
        st = self.status(cab.id)
        cur = self.jobs.current(cab.id)
        rt = self.runtime.get(cab.id)
        return {
            "id": cab.id,
            # None tant que la première sonde n'a pas eu lieu.
            "online": True if cur else st.online,
            "since": st.since,
            "last_probe": st.last_probe,
            "busy": cur is not None,
            "current_job": cur.to_dict() if cur else None,
            "queued": len(self.jobs.active(cab.id)) - (1 if cur else 0),
            "game": rt.get("game"),
            "launched_at": rt.get("launched_at"),
            "time_hack": {"enabled": cab.time_hack, "last": st.timehack_last or None, "ok": st.timehack_ok},
        }

    # -- tick --------------------------------------------------------------------------

    async def tick(self, cab: Cabinet) -> None:
        st = self.status(cab.id)
        nd = self.config.netdimm
        busy = self.jobs.lock(cab.id).locked()
        alive = True if busy else await probe(cab.ip, nd.port, nd.probe_timeout)
        st.last_probe = time.time()
        if alive:
            st.ok, st.fail = st.ok + 1, 0
        else:
            st.ok, st.fail = 0, st.fail + 1
        previous = st.online
        if (alive and (st.ok >= 2 or previous is None)) or (not alive and (st.fail >= 2 or previous is None)):
            st.online = alive
        if st.online != previous:
            st.since = time.time()
            log.info("%s (%s) %s", cab.name, cab.ip, "en ligne" if st.online else "hors ligne")
            self.events.publish("cabinet", self.status_dict(cab))
            if st.online:
                await self.on_power_on(cab)
        if st.online and cab.time_hack and not busy:
            await self._time_hack(cab, st)

    async def _time_hack(self, cab: Cabinet, st: CabinetStatus) -> None:
        th = self.config.timehack
        if time.monotonic() - st.timehack_last < th.interval_seconds:
            return
        lock = self.jobs.lock(cab.id)
        if lock.locked() or self.jobs.active(cab.id):
            return
        async with lock:
            client = self._client(cab, timeout=5)
            try:
                await asyncio.to_thread(client.set_time_hack, th.minutes)
                st.timehack_ok = True
            except Exception as e:
                st.timehack_ok = False
                st.last_error = f"time hack : {e}"
                log.warning("time hack %s : %s", cab.name, e)
        st.timehack_last = time.monotonic()

    async def on_power_on(self, cab: Cabinet) -> None:
        st = self.status(cab.id)
        first = not st.autoboot_done
        st.autoboot_done = True
        if self.jobs.active(cab.id):
            return
        rt = self.runtime.get(cab.id)
        if cab.server_mode:
            wanted, source = (rt.get("game") or cab.default_game), "server"
        elif first and cab.default_game:
            wanted, source = cab.default_game, "autoboot"
        else:
            return
        if not wanted:
            return
        if wanted == "menu":
            log.warning("%s : démarrage sur le menu OSM non disponible dans cette version", cab.name)
            return
        try:
            path = resolve_in(self.config.paths.roms, wanted)
        except ValueError:
            return
        if not path.exists():
            log.warning("%s : %s introuvable, rien n'est envoyé", cab.name, wanted)
            return
        if rt.get("game") == wanted and rt.get("crc"):
            info = await self.info(cab, quiet=True)
            if (
                info is not None
                and f"0x{info.current_game_crc:08x}" == rt["crc"]
                and info.game_crc_status in RUNNING_STATUSES
            ):
                log.info("%s exécute déjà %s, rien à envoyer", cab.name, wanted)
                return
        log.info("%s : envoi de %s (%s)", cab.name, wanted, source)
        self.jobs.submit(cab, "launch", path, wanted, disable_crc=not cab.server_mode, source=source)

    # -- opérations directes --------------------------------------------------------------

    def _client(self, cab: Cabinet, timeout: int | None = None) -> NetDimm:
        return NetDimm(
            cab.ip,
            target=NetDimmTargetEnum(netdimm_target(cab.type)),
            timeout=timeout or self.config.netdimm.socket_timeout,
            port=self.config.netdimm.port,
        )

    async def info(self, cab: Cabinet, quiet: bool = False) -> NetDimmInfo | None:
        lock = self.jobs.lock(cab.id)
        if lock.locked():
            if quiet:
                return None
            raise BusyError(f"{cab.name} est occupée (transfert en cours)")
        async with lock:
            try:
                return await asyncio.to_thread(self._client(cab, timeout=5).info)
            except Exception as e:
                if quiet:
                    return None
                raise UnreachableError(f"{cab.name} ({cab.ip}) ne répond pas : {e}") from e

    async def reboot(self, cab: Cabinet) -> None:
        lock = self.jobs.lock(cab.id)
        if lock.locked():
            raise BusyError(f"{cab.name} est occupée (transfert en cours)")
        async with lock:
            try:
                await asyncio.to_thread(self._client(cab, timeout=5).reboot)
            except Exception as e:
                raise UnreachableError(f"{cab.name} ({cab.ip}) ne répond pas : {e}") from e


class BusyError(RuntimeError):
    pass


class UnreachableError(RuntimeError):
    pass
