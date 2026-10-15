"""Présence, time hack, mode serveur et démarrage automatique."""

from __future__ import annotations

import asyncio
from pathlib import Path

from naomox.config import Config
from naomox.events import EventBroker
from naomox.jobs import JobManager
from naomox.mock import MockNetDimm
from naomox.storage import CabinetIn, CabinetsStore, GamesStore, HistoryStore, RuntimeStore
from naomox.supervisor import Supervisor, discover, probe
from tests.conftest import make_rom


def build(tmp_path: Path, port: int, **timehack) -> tuple[Supervisor, JobManager, CabinetsStore]:
    cfg = Config.model_validate(
        {
            "paths": {"data": str(tmp_path / "data")},
            "netdimm": {"port": port, "probe_timeout": 0.5, "retry_delay": 0.2},
            "timehack": {"interval_seconds": 0.0, **timehack},
        }
    )
    cfg.ensure_dirs()
    st = cfg.paths.state
    events = EventBroker()
    runtime = RuntimeStore(st / "runtime.json")
    jobs = JobManager(cfg, events, runtime, HistoryStore(st / "h.jsonl"))
    cabs = CabinetsStore(st / "cabinets.yaml")
    sup = Supervisor(cfg, cabs, GamesStore(st / "games.csv"), jobs, runtime, events)
    return sup, jobs, cabs


async def settle_jobs(jobs: JobManager, cab_id: str, limit: float = 20) -> None:
    async with asyncio.timeout(limit):
        while jobs.active(cab_id):
            await asyncio.sleep(0.05)


async def test_probe_and_discover(mock_dimm: MockNetDimm):
    assert await probe("127.0.0.1", mock_dimm.port, 1)
    assert not await probe("127.0.0.1", 1, 0.5)
    found = await discover("127.0.0.1/32", mock_dimm.port)
    assert found == [] or found == ["127.0.0.1"]  # /32 : hosts() vide selon la version de Python
    assert await discover("127.0.0.0/30", mock_dimm.port) == ["127.0.0.1"]


async def test_online_debounce_and_time_hack(tmp_path, mock_dimm: MockNetDimm):
    sup, jobs, cabs = build(tmp_path, mock_dimm.port)
    cab = cabs.create(CabinetIn(name="B1", ip="127.0.0.1", time_hack=True))
    await sup.tick(cab)
    assert sup.status(cab.id).online is True  # première sonde : immédiat
    async with asyncio.timeout(3):
        while not mock_dimm.state.time_limits:
            await asyncio.sleep(0.02)
    assert mock_dimm.state.time_limits[0] == 10
    assert sup.status(cab.id).timehack_ok is True

    await mock_dimm.stop()
    await sup.tick(cab)
    assert sup.status(cab.id).online is True  # anti-rebond : une seule sonde négative
    await sup.tick(cab)
    assert sup.status(cab.id).online is False
    await jobs.shutdown()


async def test_autoboot_sends_default_game_once(tmp_path, mock_dimm: MockNetDimm):
    sup, jobs, cabs = build(tmp_path, mock_dimm.port)
    raw = make_rom(sup.config.paths.roms / "n1-auto.bin.gz", 80_000)
    cab = cabs.create(CabinetIn(name="B1", ip="127.0.0.1", default_game="n1-auto.bin.gz"))
    await sup.tick(cab)
    await asyncio.sleep(0.1)
    await settle_jobs(jobs, cab.id)
    assert bytes(mock_dimm.state.data) == raw
    assert jobs.list()[0].source == "autoboot"
    # Coupure puis retour : pas de nouvel envoi hors mode serveur.
    mock_dimm.power_cycle()
    await sup.on_power_on(cab)
    assert jobs.active(cab.id) == []
    await jobs.shutdown()


async def test_server_mode_resends_after_power_cycle_only_when_needed(tmp_path, mock_dimm: MockNetDimm):
    sup, jobs, cabs = build(tmp_path, mock_dimm.port)
    raw = make_rom(sup.config.paths.roms / "n1-srv.bin.gz", 90_000)
    cab = cabs.create(CabinetIn(name="B1", ip="127.0.0.1", default_game="n1-srv.bin.gz", server_mode=True))
    await sup.on_power_on(cab)
    await settle_jobs(jobs, cab.id)
    assert len(jobs.list()) == 1 and jobs.list()[0].state == "done"
    assert mock_dimm.state.crc_check_disabled is False  # mode serveur : CRC vérifié (netdimm_ensure)

    # Borne toujours sous tension avec le bon jeu : rien n'est renvoyé.
    await sup.on_power_on(cab)
    assert jobs.active(cab.id) == []
    assert len(jobs.list()) == 1

    # Coupure secteur : la mémoire est perdue → renvoi automatique.
    mock_dimm.power_cycle()
    await sup.on_power_on(cab)
    await settle_jobs(jobs, cab.id)
    assert len(jobs.list()) == 2 and jobs.list()[0].source == "server"
    assert bytes(mock_dimm.state.data) == raw
    await jobs.shutdown()


async def test_info_and_reboot(tmp_path, mock_dimm: MockNetDimm):
    sup, jobs, cabs = build(tmp_path, mock_dimm.port)
    cab = cabs.create(CabinetIn(name="B1", ip="127.0.0.1"))
    info = await sup.info(cab)
    assert info is not None and info.firmware_version.value == "4.01"
    await sup.reboot(cab)
    async with asyncio.timeout(2):
        while mock_dimm.state.restarts == 0:
            await asyncio.sleep(0.02)
    await jobs.shutdown()
