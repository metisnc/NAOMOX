"""Sous-processus de transfert : événements JSON, décompression, erreurs typées."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from naomox.mock import MockNetDimm


async def run_transfer(*args: str) -> tuple[int, list[dict]]:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "naomox.transfer",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await asyncio.wait_for(proc.communicate(), 60)
    events = [json.loads(line) for line in out.decode().splitlines() if line.strip()]
    assert proc.returncode is not None
    return proc.returncode, events


async def test_gz_rom_is_decompressed_and_sent(mock_dimm: MockNetDimm, rom_factory, tmp_path: Path):
    rom, raw = rom_factory(size=500_000)
    code, events = await run_transfer(
        "--ip",
        "127.0.0.1",
        "--port",
        str(mock_dimm.port),
        "--file",
        str(rom),
        "--disable-crc",
        "--tmpdir",
        str(tmp_path / "tmp"),
    )
    assert code == 0, events
    phases = [e["phase"] for e in events if e["event"] == "phase"]
    assert phases == ["decompress", "connecting", "uploading", "rebooting"]
    assert events[-1]["event"] == "done" and events[-1]["size"] == len(raw)
    assert bytes(mock_dimm.state.data) == raw
    assert mock_dimm.state.restarts == 1
    # Fichier temporaire supprimé.
    assert list((tmp_path / "tmp").iterdir()) == []
    ups = [e for e in events if e["event"] == "progress" and e["phase"] == "uploading"]
    assert ups[-1]["done"] == ups[-1]["total"] == len(raw)


async def test_uncompressed_rom(mock_dimm: MockNetDimm, rom_factory):
    rom, raw = rom_factory(name="n1-raw.bin", compress=False, size=70_000)
    code, events = await run_transfer("--ip", "127.0.0.1", "--port", str(mock_dimm.port), "--file", str(rom))
    assert code == 0
    assert "decompress" not in [e.get("phase") for e in events]
    assert bytes(mock_dimm.state.data) == raw
    assert mock_dimm.state.crc_status == 2  # CRC vérifié


async def test_unreachable(rom_factory):
    rom, _ = rom_factory(size=10_000)
    code, events = await run_transfer(
        "--ip", "127.0.0.1", "--port", "1", "--file", str(rom), "--socket-timeout", "2"
    )
    assert code == 2
    assert events[-1]["event"] == "error"
    assert events[-1]["kind"] in {"refused", "unreachable"}
    assert events[-1]["started"] is False


async def test_missing_file():
    code, events = await run_transfer("--ip", "127.0.0.1", "--file", "/nonexistent/x.bin.gz")
    assert code == 3 and events[-1]["kind"] == "rom_missing"


async def test_disconnect_mid_upload(mock_dimm: MockNetDimm, rom_factory):
    rom, _ = rom_factory(size=400_000, compress=False)
    mock_dimm.faults.disconnect_after_bytes = 100_000
    code, events = await run_transfer(
        "--ip", "127.0.0.1", "--port", str(mock_dimm.port), "--file", str(rom), "--socket-timeout", "3"
    )
    assert code == 2
    assert events[-1]["kind"] in {"disconnected", "timeout", "protocol"}
    assert events[-1]["started"] is True
