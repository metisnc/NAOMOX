"""Jobs de transfert : une file FIFO et un worker par borne, un sous-processus par envoi.

États d'un job : queued → decompress → connecting → uploading → verifying → rebooting → done
                 (retrying entre deux tentatives) ; états finaux : done, error, cancelled.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sys
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Config
from .events import EventBroker
from .storage import Cabinet, HistoryStore, RuntimeStore
from .systems import netdimm_target

log = logging.getLogger("naomox.jobs")

FINAL_STATES = frozenset({"done", "error", "cancelled"})
# Erreurs pour lesquelles une nouvelle tentative a du sens (rien n'a encore été envoyé).
RETRYABLE = frozenset({"unreachable", "refused"})


@dataclass
class Job:
    cabinet_id: str
    cabinet_name: str
    ip: str
    kind: str  # launch | firmware | diag
    rom: str  # nom affiché (fichier ROM, firmware, homebrew)
    file: str
    target: str = "naomi"
    disable_crc: bool = True
    source: str = "user"  # user | autoboot | server
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: str = "queued"
    done: int = 0
    total: int = 0
    error_kind: str | None = None
    message: str | None = None
    crc: str | None = None
    attempts: int = 0
    created: float = field(default_factory=time.time)
    started: float | None = None
    ended: float | None = None
    log: deque[str] = field(default_factory=lambda: deque(maxlen=200))
    cancel_requested: bool = False
    _proc: asyncio.subprocess.Process | None = field(default=None, repr=False)

    @property
    def final(self) -> bool:
        return self.state in FINAL_STATES

    @property
    def percent(self) -> int:
        return int(self.done * 100 / self.total) if self.total else (100 if self.state == "done" else 0)

    def to_dict(self, with_log: bool = False) -> dict[str, Any]:
        d = {
            "id": self.id,
            "cabinet_id": self.cabinet_id,
            "cabinet_name": self.cabinet_name,
            "ip": self.ip,
            "kind": self.kind,
            "rom": self.rom,
            "source": self.source,
            "state": self.state,
            "done": self.done,
            "total": self.total,
            "percent": self.percent,
            "error_kind": self.error_kind,
            "message": self.message,
            "crc": self.crc,
            "attempts": self.attempts,
            "created": self.created,
            "started": self.started,
            "ended": self.ended,
        }
        if with_log:
            d["log"] = list(self.log)
        return d

    def note(self, line: str) -> None:
        self.log.append(f"{time.strftime('%H:%M:%S')} {line}")


class JobManager:
    def __init__(
        self,
        config: Config,
        events: EventBroker,
        runtime: RuntimeStore,
        history: HistoryStore,
        keep: int = 200,
    ) -> None:
        self.config = config
        self.events = events
        self.runtime = runtime
        self.history = history
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._keep = keep
        self._queues: dict[str, asyncio.Queue[Job]] = {}
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._current: dict[str, Job] = {}

    # -- accès -----------------------------------------------------------------

    def lock(self, cab_id: str) -> asyncio.Lock:
        """Verrou TCP par borne : une seule conversation NetDIMM à la fois."""
        return self._locks.setdefault(cab_id, asyncio.Lock())

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self, cabinet_id: str | None = None, active_only: bool = False) -> list[Job]:
        jobs = [j for j in reversed(self._jobs.values()) if cabinet_id in (None, j.cabinet_id)]
        return [j for j in jobs if not j.final] if active_only else jobs

    def current(self, cab_id: str) -> Job | None:
        return self._current.get(cab_id)

    def active(self, cab_id: str) -> list[Job]:
        return [j for j in self._jobs.values() if j.cabinet_id == cab_id and not j.final]

    # -- soumission / annulation -------------------------------------------------

    def submit(
        self,
        cab: Cabinet,
        kind: str,
        file: Path,
        rom: str,
        *,
        disable_crc: bool = True,
        source: str = "user",
    ) -> Job:
        job = Job(
            cabinet_id=cab.id,
            cabinet_name=cab.name,
            ip=cab.ip,
            kind=kind,
            rom=rom,
            file=str(file),
            target=netdimm_target(cab.type),
            disable_crc=disable_crc,
            source=source,
        )
        job.note(f"{kind} {rom} → {cab.name} ({cab.ip}), source={source}")
        self._jobs[job.id] = job
        while len(self._jobs) > self._keep:
            oldest = next(iter(self._jobs.values()))
            if not oldest.final:
                break
            self._jobs.popitem(last=False)
        self._queue(cab.id).put_nowait(job)
        self._publish(job)
        return job

    async def cancel(self, job_id: str) -> Job:
        job = self._jobs[job_id]
        if job.final:
            return job
        job.cancel_requested = True
        job.note("annulation demandée")
        if job.state == "queued":
            self._finish(job, "cancelled", message="annulé avant démarrage")
        elif job._proc is not None:
            await self._stop_proc(job._proc)
        return job

    def retry(self, job_id: str, cab: Cabinet) -> Job:
        old = self._jobs[job_id]
        if not old.final:
            raise ValueError("job encore actif")
        return self.submit(cab, old.kind, Path(old.file), old.rom, disable_crc=old.disable_crc, source="user")

    async def shutdown(self) -> None:
        for job in list(self._jobs.values()):
            if not job.final:
                await self.cancel(job.id)
        for task in self._workers.values():
            task.cancel()
        for task in self._workers.values():
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._workers.clear()

    # -- worker ------------------------------------------------------------------

    def _queue(self, cab_id: str) -> asyncio.Queue[Job]:
        if cab_id not in self._queues:
            self._queues[cab_id] = asyncio.Queue()
            self._workers[cab_id] = asyncio.create_task(self._worker(cab_id), name=f"worker-{cab_id}")
        return self._queues[cab_id]

    async def _worker(self, cab_id: str) -> None:
        queue = self._queues[cab_id]
        while True:
            job = await queue.get()
            try:
                if job.final:
                    continue
                async with self.lock(cab_id):
                    self._current[cab_id] = job
                    try:
                        await self._run(job)
                    finally:
                        self._current.pop(cab_id, None)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # ne jamais tuer le worker
                log.exception("job %s : erreur interne", job.id)
                if not job.final:
                    self._finish(job, "error", kind="internal", message=str(e))
            finally:
                queue.task_done()

    async def _run(self, job: Job) -> None:
        nd = self.config.netdimm
        job.started = time.time()
        deadline = time.monotonic() + nd.send_timeout
        while True:
            job.attempts += 1
            final = await self._attempt(job, deadline)
            if job.cancel_requested:
                self._finish(job, "cancelled", message="annulé")
                return
            if final.get("event") == "done":
                job.crc = final.get("crc")
                self._finish(job, "done", message="jeu envoyé, la borne redémarre")
                return
            kind = final.get("kind", "internal")
            msg = final.get("message", "erreur inconnue")
            can_retry = (
                kind in RETRYABLE
                and not final.get("started")
                and job.attempts <= nd.retries
                and time.monotonic() + nd.retry_delay < deadline
            )
            if not can_retry:
                self._finish(job, "error", kind=kind, message=msg)
                return
            job.state = "retrying"
            job.message = f"tentative {job.attempts}/{nd.retries + 1} échouée ({kind}), nouvel essai…"
            job.note(job.message)
            self._publish(job)
            await asyncio.sleep(nd.retry_delay)
            if job.cancel_requested:
                self._finish(job, "cancelled", message="annulé")
                return

    async def _attempt(self, job: Job, deadline: float) -> dict[str, Any]:
        cfg = self.config
        args = [
            sys.executable, "-m", "naomox.transfer",
            "--ip", job.ip,
            "--port", str(cfg.netdimm.port),
            "--file", job.file,
            "--target", job.target,
            "--tmpdir", str(cfg.paths.tmp),
        ]  # fmt: skip
        if job.disable_crc:
            args.append("--disable-crc")
        if not cfg.netdimm.verify_upload:
            args.append("--no-verify")
        if cfg.netdimm.socket_timeout:
            args += ["--socket-timeout", str(cfg.netdimm.socket_timeout)]

        job.state, job.done, job.total = "connecting", 0, 0
        job.error_kind = job.message = None
        self._publish(job)
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        job._proc = proc
        stderr_task = asyncio.create_task(self._drain_stderr(proc, job))
        final: dict[str, Any] = {}
        try:
            async with asyncio.timeout(max(1.0, deadline - time.monotonic())):
                assert proc.stdout is not None
                async for raw in proc.stdout:
                    try:
                        ev = json.loads(raw)
                    except ValueError:
                        job.note(raw.decode(errors="replace").rstrip())
                        continue
                    if ev.get("event") in ("done", "error"):
                        final = ev
                    self._on_event(job, ev)
                await proc.wait()
        except TimeoutError:
            job.note("délai maximal dépassé, arrêt du transfert")
            await self._stop_proc(proc)
            final = {"event": "error", "kind": "timeout", "message": "délai maximal de transfert dépassé"}
        finally:
            job._proc = None
            with contextlib.suppress(Exception):
                await asyncio.wait_for(stderr_task, 5)
        if not final:
            final = {
                "event": "error",
                "kind": "cancelled" if job.cancel_requested else "internal",
                "message": f"le transfert s'est arrêté (code {proc.returncode})",
            }
        return final

    def _on_event(self, job: Job, ev: dict[str, Any]) -> None:
        kind = ev.get("event")
        if kind == "phase":
            job.state = ev["phase"]
            if job.state in ("decompress", "uploading"):
                # Ces phases ont leur propre progression ; « rebooting » garde la barre à 100 %.
                job.done, job.total = 0, 0
            job.note(f"phase {job.state}")
        elif kind == "progress":
            job.done, job.total = int(ev.get("done", 0)), int(ev.get("total", 0))
        elif kind == "error":
            job.note(f"erreur {ev.get('kind')}: {ev.get('message')} {ev.get('cause', '')}".rstrip())
        elif kind == "done":
            job.note(f"terminé, {ev.get('size')} octets, crc {ev.get('crc')}")
        self._publish(job)

    async def _drain_stderr(self, proc: asyncio.subprocess.Process, job: Job) -> None:
        assert proc.stderr is not None
        async for raw in proc.stderr:
            line = raw.decode(errors="replace").rstrip()
            if line:
                job.note(line)
                log.debug("[%s] %s", job.id, line)

    @staticmethod
    async def _stop_proc(proc: asyncio.subprocess.Process) -> None:
        if proc.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError):
            proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), 3)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()

    def _finish(self, job: Job, state: str, kind: str | None = None, message: str | None = None) -> None:
        job.state = state
        job.error_kind = kind
        job.message = message
        job.ended = time.time()
        job.note(f"état final : {state}" + (f" ({kind})" if kind else ""))
        log.info(
            "job %s %s %s → %s: %s %s", job.id, job.kind, job.rom, job.cabinet_name, state, message or ""
        )
        if state == "done" and job.kind == "launch":
            self.runtime.set(job.cabinet_id, game=job.rom, crc=job.crc, launched_at=job.ended)
        elif state == "done":
            # Firmware / diag : la borne n'exécute plus le jeu précédent.
            self.runtime.set(job.cabinet_id, game=None, crc=None, launched_at=job.ended)
        if job.started is not None or state != "cancelled":
            self.history.append({
                "job": job.id, "kind": job.kind, "rom": job.rom, "cabinet_id": job.cabinet_id,
                "cabinet": job.cabinet_name, "state": state, "error_kind": kind, "message": message,
                "source": job.source, "duration": round(job.ended - (job.started or job.created), 1),
            })  # fmt: skip
        self._publish(job)

    def _publish(self, job: Job) -> None:
        self.events.publish("job", job.to_dict())
