"""Transfert d'une image vers une NetDIMM — exécuté dans un sous-processus.

Remplace `netdimm_send <ip> <rom> [--disable-crc]` de WiPi. Émet des événements
JSON (un par ligne) sur stdout :

    {"event": "phase", "phase": "decompress" | "connecting" | "uploading" | "verifying" | "rebooting"}
    {"event": "progress", "phase": "...", "done": n, "total": n}
    {"event": "done", "crc": "0x...", "size": n}
    {"event": "error", "kind": "...", "message": "..."}

Code de sortie : 0 succès, 2 erreur NetDIMM, 3 erreur fichier, 1 autre.
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import json
import os
import signal
import sys
import tempfile
import time
import zlib
from collections.abc import Callable
from typing import Any, BinaryIO

GZIP_MAGIC = b"\x1f\x8b"


class Emitter:
    def __init__(self, out: Any = None, min_interval: float = 0.25) -> None:
        self.out = out or sys.stdout
        self.min_interval = min_interval
        self._last = 0.0
        self._last_pct = -1

    def emit(self, event: str, **data: Any) -> None:
        self.out.write(json.dumps({"event": event, **data}) + "\n")
        self.out.flush()

    def progress(self, phase: str, done: int, total: int, force: bool = False) -> None:
        pct = int(done * 100 / total) if total else 100
        now = time.monotonic()
        if force or done >= total or (pct != self._last_pct and now - self._last >= self.min_interval):
            self._last, self._last_pct = now, pct
            self.emit("progress", phase=phase, done=done, total=total)


def classify(exc: BaseException) -> str:
    """Type d'erreur à partir des messages de NetDimmException (et de leur cause)."""
    msg = str(exc).lower()
    cause = exc.__cause__
    if "could not connect" in msg:
        return "refused" if isinstance(cause, ConnectionRefusedError) else "unreachable"
    if "could not receive" in msg or isinstance(cause, TimeoutError):
        return "timeout"
    if "could not send" in msg:
        return "disconnected"
    return "protocol"


def open_image(path: str, tmpdir: str, emitter: Emitter) -> tuple[BinaryIO, str | None]:
    """Ouvre l'image ; si elle est gzippée, la décompresse dans un fichier temporaire
    (les ROMs Chihiro/Triforce dépassent la RAM du conteneur)."""
    with open(path, "rb") as fh:
        magic = fh.read(2)
    if magic != GZIP_MAGIC:
        return open(path, "rb"), None

    emitter.emit("phase", phase="decompress")
    os.makedirs(tmpdir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=tmpdir, prefix="naomox-", suffix=".bin")
    total = os.path.getsize(path)
    try:
        with open(path, "rb") as raw, gzip.GzipFile(fileobj=raw) as gz, os.fdopen(fd, "wb") as out:
            while True:
                chunk = gz.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                emitter.progress("decompress", raw.tell(), total)
        emitter.progress("decompress", total, total, force=True)
        return open(tmp, "rb"), tmp
    except BaseException:
        os.unlink(tmp)
        raise


def image_crc(fh: BinaryIO) -> int:
    fh.seek(0)
    crc = 0
    while True:
        chunk = fh.read(1 << 20)
        if not chunk:
            break
        crc = zlib.crc32(chunk, crc)
    fh.seek(0)
    return (~crc) & 0xFFFFFFFF


def run(
    ip: str,
    image: str,
    *,
    port: int = 10703,
    target: str = "naomi",
    disable_crc: bool = False,
    reboot: bool = True,
    verify: bool = True,
    socket_timeout: int | None = None,
    tmpdir: str | None = None,
    emitter: Emitter | None = None,
    netdimm_factory: Callable[..., Any] | None = None,
) -> int:
    emitter = emitter or Emitter()
    from arcadeutils import FileBytes

    from netdimm import NetDimm, NetDimmException, NetDimmTargetEnum

    tmpdir = tmpdir or tempfile.gettempdir()
    try:
        fh, tmp = open_image(image, tmpdir, emitter)
    except FileNotFoundError:
        emitter.emit("error", kind="rom_missing", message=f"fichier introuvable : {image}")
        return 3
    except (OSError, EOFError, gzip.BadGzipFile) as e:
        emitter.emit("error", kind="file", message=f"lecture impossible : {e}")
        return 3

    try:
        data = FileBytes(fh)
        total = len(data)
        crc = image_crc(fh)
        factory = netdimm_factory or NetDimm
        netdimm = factory(ip, target=NetDimmTargetEnum(target), timeout=socket_timeout, port=port)

        emitter.emit("phase", phase="connecting")
        started = False

        def on_progress(done: int, tot: int) -> None:
            nonlocal started
            if not started:
                started = True
                emitter.emit("phase", phase="uploading")
            emitter.progress("uploading", done, tot)

        try:
            netdimm.send(data, None, disable_crc_check=disable_crc, progress_callback=on_progress)
            if verify:
                # La NetDIMM n'acquitte pas les blocs : une coupure en cours d'envoi peut passer
                # inaperçue. On relit la taille et le CRC enregistrés (requête « information »,
                # comme le mode serveur de DragonMinded) avant de redémarrer sur le jeu.
                emitter.emit("phase", phase="verifying")
                info = netdimm.info()
                if info.current_game_size != total or info.current_game_crc != crc:
                    # Laisser à la carte le temps de finir d'enregistrer, puis relire une fois.
                    time.sleep(1.0)
                    info = netdimm.info()
                if info.current_game_size != total or info.current_game_crc != crc:
                    emitter.emit(
                        "error",
                        kind="verify",
                        message=(
                            f"la NetDIMM indique {info.current_game_size} octets / CRC "
                            f"0x{info.current_game_crc:08x}, attendu {total} / 0x{crc:08x}"
                        ),
                        started=True,
                    )
                    return 2
            if reboot:
                emitter.emit("phase", phase="rebooting")
                netdimm.reboot()
        except NetDimmException as e:
            kind = classify(e)
            if kind == "unreachable" and started:
                kind = "disconnected"
            emitter.emit("error", kind=kind, message=str(e), cause=str(e.__cause__ or ""), started=started)
            return 2
        emitter.emit("done", crc=f"0x{crc:08x}", size=total)
        return 0
    finally:
        fh.close()
        if tmp:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp)


def main(argv: list[str] | None = None) -> int:
    # Annulation / arrêt du service (SIGTERM) : sortir proprement pour supprimer le fichier temporaire.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    p = argparse.ArgumentParser(prog="python -m naomox.transfer", description=__doc__.split("\n")[0])
    p.add_argument("--ip", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--port", type=int, default=10703)
    p.add_argument("--target", default="naomi", choices=["naomi", "chihiro", "triforce"])
    p.add_argument("--disable-crc", action="store_true")
    p.add_argument("--no-reboot", action="store_true")
    p.add_argument("--no-verify", action="store_true", help="ne pas relire taille/CRC après envoi")
    p.add_argument("--socket-timeout", type=int, default=None)
    p.add_argument("--tmpdir", default=None)
    a = p.parse_args(argv)
    try:
        return run(
            a.ip,
            a.file,
            port=a.port,
            target=a.target,
            disable_crc=a.disable_crc,
            reboot=not a.no_reboot,
            verify=not a.no_verify,
            socket_timeout=a.socket_timeout,
            tmpdir=a.tmpdir,
        )
    except Exception as e:  # garde-fou : toujours un événement exploitable
        Emitter().emit("error", kind="internal", message=f"{type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
