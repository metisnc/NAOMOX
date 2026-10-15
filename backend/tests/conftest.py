from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from naomox.mock import MockNetDimm


@pytest.fixture
async def mock_dimm():
    async with MockNetDimm() as m:
        yield m


def make_rom(path: Path, size: int = 300_000, compress: bool = True, seed: int = 1) -> bytes:
    """Fichier ROM factice (contenu déterministe), gzippé par défaut comme les ROMs WiPi."""
    block = bytes((i * 31 + seed) & 0xFF for i in range(256))
    data = (block * (size // 256 + 1))[:size]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(data, compresslevel=1) if compress else data)
    return data


@pytest.fixture
def rom_factory(tmp_path: Path):
    def _make(
        name: str = "n1-test_game-[000-0000].bin.gz", size: int = 300_000, compress: bool = True
    ) -> tuple[Path, bytes]:
        p = tmp_path / "roms" / name
        return p, make_rom(p, size, compress)

    return _make
