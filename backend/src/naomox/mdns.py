"""Nom réseau de NAOMOX (mDNS / Bonjour) modifiable depuis l'interface.

Le hostname du conteneur appartient à Proxmox (réécrit au démarrage du CT) et le changer
demande root. NAOMOX, qui tourne sans privilège, annonce donc lui-même un nom supplémentaire
`<nom>.local` via avahi (D-Bus, autorisé aux utilisateurs locaux) : `avahi-publish -a`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import shutil
import socket

log = logging.getLogger("naomox.mdns")

_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_name(name: str) -> str:
    """« NAOMOX salon.local » → « naomox-salon » ; lève ValueError si invalide."""
    n = name.strip().lower().removesuffix(".local")
    n = re.sub(r"[\s_]+", "-", n)
    if not _LABEL.match(n):
        raise ValueError("nom réseau invalide : lettres, chiffres et tirets (1 à 63 caractères)")
    return n


def system_hostname() -> str:
    return socket.gethostname().split(".")[0].lower()


def primary_ipv4() -> str | None:
    """Adresse IPv4 de l'interface utilisée pour sortir (aucun paquet envoyé)."""
    with contextlib.suppress(OSError), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    return None


class MdnsPublisher:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("avahi-publish")
        self._proc: asyncio.subprocess.Process | None = None
        self.name: str | None = None
        self.error: str | None = None

    @property
    def available(self) -> bool:
        return self.executable is not None

    @property
    def active(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def apply(self, name: str | None) -> None:
        """Annonce `name`.local (rien si vide ou identique au hostname, déjà annoncé par avahi)."""
        await self.stop()
        self.name, self.error = name, None
        if not name or name == system_hostname():
            return
        if not self.available:
            self.error = "avahi-publish absent (paquet avahi-utils)"
            log.warning("nom réseau %s non annoncé : %s", name, self.error)
            return
        ip = primary_ipv4()
        if not ip:
            self.error = "adresse IPv4 introuvable"
            return
        assert self.executable is not None
        self._proc = await asyncio.create_subprocess_exec(
            self.executable, "-a", "-R", f"{name}.local", ip,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )  # fmt: skip
        # Un conflit de nom ou un démon absent fait échouer avahi-publish immédiatement.
        try:
            await asyncio.wait_for(self._proc.wait(), 1.5)
        except TimeoutError:
            log.info("nom réseau annoncé : %s.local → %s", name, ip)
            return
        err = (await self._proc.stderr.read()).decode(errors="replace").strip() if self._proc.stderr else ""
        self.error = err or f"avahi-publish s'est arrêté (code {self._proc.returncode})"
        self._proc = None
        log.warning("nom réseau %s non annoncé : %s", name, self.error)

    async def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.terminate()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(proc.wait(), 3)
