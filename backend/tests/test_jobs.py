"""File d'attente par borne, annulation, timeout et relance — contre le mock."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from naomox.config import Config
from naomox.events import EventBroker
from naomox.jobs import Job, JobManager
from naomox.mock import MockNetDimm
from naomox.storage import Cabinet, HistoryStore, RuntimeStore


def make_config(tmp_path: Path, port: int, **netdimm) -> Config:
    cfg = Config.model_validate(
        {
            "paths": {"data": str(tmp_path / "data")},
            "netdimm": {"port": port, "retry_delay": 0.2, "socket_timeout": 3, **netdimm},
        }
    )
    cfg.ensure_dirs()
    return cfg


def make_manager(cfg: Config) -> JobManager:
    state = cfg.paths.state
    return JobManager(
        cfg, EventBroker(), RuntimeStore(state / "runtime.json"), HistoryStore(state / "h.jsonl")
    )


CAB = Cabinet(id="cab1", name="Borne 1", ip="127.0.0.1", type="Sega Naomi")


async def wait_final(job: Job, limit: float = 30) -> Job:
    async with asyncio.timeout(limit):
        while not job.final:
            await asyncio.sleep(0.02)
    return job


async def test_launch_done_updates_runtime_and_history(tmp_path, mock_dimm: MockNetDimm, rom_factory):
    cfg = make_config(tmp_path, mock_dimm.port)
    jm = make_manager(cfg)
    rom, raw = rom_factory(size=200_000)
    seen: list[str] = []
    q_events = jm.events.stream()
    await q_events.__anext__()  # "retry:" initial

    job = jm.submit(CAB, "launch", rom, rom.name)
    await wait_final(job)
    assert job.state == "done", job.log
    assert job.total == len(raw) and job.percent == 100
    assert bytes(mock_dimm.state.data) == raw
    rt = jm.runtime.get("cab1")
    assert rt["game"] == rom.name and rt["crc"] == job.crc
    assert jm.history.recent(1)[0]["state"] == "done"
    # Les états sont publiés en SSE.
    while True:
        try:
            chunk = await asyncio.wait_for(q_events.__anext__(), 0.1)
        except TimeoutError:
            break
        seen.append(chunk)
    assert any('"state": "uploading"' in c for c in seen)
    assert any('"state": "done"' in c for c in seen)
    await q_events.aclose()
    await jm.shutdown()


async def test_queue_is_serialised_per_cabinet(tmp_path, mock_dimm: MockNetDimm, rom_factory):
    cfg = make_config(tmp_path, mock_dimm.port)
    jm = make_manager(cfg)
    rom1, _ = rom_factory("n1-a.bin.gz", size=100_000)
    rom2, raw2 = rom_factory("n1-b.bin.gz", size=120_000)
    j1 = jm.submit(CAB, "launch", rom1, rom1.name)
    j2 = jm.submit(CAB, "launch", rom2, rom2.name)
    assert j2.state == "queued"
    await wait_final(j2)
    assert j1.state == j2.state == "done"
    assert j1.ended <= j2.started
    assert bytes(mock_dimm.state.data) == raw2
    await jm.shutdown()


async def test_cancel_running_transfer(tmp_path, mock_dimm: MockNetDimm, rom_factory):
    cfg = make_config(tmp_path, mock_dimm.port, socket_timeout=30)
    jm = make_manager(cfg)
    # Borne qui accepte la connexion mais ne répond plus : le transfert reste bloqué.
    mock_dimm.faults.mute = True
    rom, _ = rom_factory(size=200_000, compress=False)
    job = jm.submit(CAB, "launch", rom, rom.name)
    await asyncio.wait_for(mock_dimm.packet_received.wait(), 10)
    t0 = asyncio.get_running_loop().time()
    await jm.cancel(job.id)
    await wait_final(job, 10)
    assert job.state == "cancelled"
    assert asyncio.get_running_loop().time() - t0 < 5
    assert jm.history.recent(1)[0]["state"] == "cancelled"
    await jm.shutdown()


async def test_cancel_queued_job(tmp_path, mock_dimm: MockNetDimm, rom_factory):
    cfg = make_config(tmp_path, mock_dimm.port, socket_timeout=30)
    jm = make_manager(cfg)
    mock_dimm.faults.mute = True
    rom, _ = rom_factory(size=50_000, compress=False)
    j1 = jm.submit(CAB, "launch", rom, rom.name)
    j2 = jm.submit(CAB, "launch", rom, rom.name)
    await jm.cancel(j2.id)
    assert j2.state == "cancelled"
    await jm.cancel(j1.id)
    await wait_final(j1)
    assert j1.state == "cancelled"
    await jm.shutdown()


async def test_global_timeout(tmp_path, mock_dimm: MockNetDimm, rom_factory):
    # La bibliothèque attendrait 10 s une réponse ; le délai global (2 s) tranche avant.
    cfg = make_config(tmp_path, mock_dimm.port, send_timeout=2, socket_timeout=30)
    jm = make_manager(cfg)
    mock_dimm.faults.mute = True
    rom, _ = rom_factory(size=50_000, compress=False)
    job = jm.submit(CAB, "launch", rom, rom.name)
    await wait_final(job, 15)
    assert job.state == "error" and job.error_kind == "timeout"
    assert "délai maximal" in (job.message or "")
    await jm.shutdown()


async def test_unresponsive_dimm_reports_library_timeout(tmp_path, mock_dimm: MockNetDimm, rom_factory):
    cfg = make_config(tmp_path, mock_dimm.port, send_timeout=60)
    jm = make_manager(cfg)
    mock_dimm.faults.mute = True
    rom, _ = rom_factory(size=50_000, compress=False)
    job = jm.submit(CAB, "launch", rom, rom.name)
    await wait_final(job, 30)
    assert job.state == "error" and job.error_kind == "timeout"
    assert job.attempts == 1  # pas de relance : la connexion avait abouti
    await jm.shutdown()


async def test_retry_when_unreachable_then_error(tmp_path, rom_factory):
    cfg = make_config(tmp_path, 1, retries=2)
    jm = make_manager(cfg)
    rom, _ = rom_factory(size=10_000)
    job = jm.submit(CAB, "launch", rom, rom.name)
    await wait_final(job, 30)
    assert job.state == "error"
    assert job.error_kind in {"refused", "unreachable"}
    assert job.attempts == 3
    await jm.shutdown()


async def test_retry_succeeds_once_dimm_comes_up(tmp_path, rom_factory):
    async with MockNetDimm() as probe_port:
        port = probe_port.port
    cfg = make_config(tmp_path, port, retries=3, retry_delay=1.0)
    jm = make_manager(cfg)
    rom, raw = rom_factory(size=50_000)
    job = jm.submit(CAB, "launch", rom, rom.name)
    await asyncio.sleep(0.5)  # 1re tentative refusée
    async with MockNetDimm(port=port) as m:
        await wait_final(job, 30)
        assert job.state == "done", job.log
        assert job.attempts >= 2
        assert bytes(m.state.data) == raw
    await jm.shutdown()


async def test_manual_retry_creates_new_job(tmp_path, mock_dimm: MockNetDimm, rom_factory):
    cfg = make_config(tmp_path, mock_dimm.port)
    jm = make_manager(cfg)
    rom, _ = rom_factory(size=10_000)
    j1 = jm.submit(CAB, "launch", rom, rom.name)
    with pytest.raises(ValueError):
        jm.retry(j1.id, CAB)
    await wait_final(j1)
    j2 = jm.retry(j1.id, CAB)
    assert j2.id != j1.id
    await wait_final(j2)
    assert j2.state == "done"
    await jm.shutdown()


async def test_cancel_during_decompression_removes_temp_file(tmp_path, mock_dimm: MockNetDimm, rom_factory):
    cfg = make_config(tmp_path, mock_dimm.port, socket_timeout=30)
    jm = make_manager(cfg)
    mock_dimm.faults.mute = True  # le transfert reste bloqué après la décompression
    rom, _ = rom_factory(size=3_000_000)
    job = jm.submit(CAB, "launch", rom, rom.name)
    await asyncio.wait_for(mock_dimm.packet_received.wait(), 15)
    assert list(cfg.paths.tmp.glob("naomox-*.bin"))  # fichier décompressé présent
    await jm.cancel(job.id)
    await wait_final(job, 10)
    assert list(cfg.paths.tmp.glob("naomox-*.bin")) == []
    await jm.shutdown()
