from __future__ import annotations

from pathlib import Path

import pytest

from naomox.storage import (
    GAME_COLUMNS,
    CabinetIn,
    CabinetsStore,
    GamesStore,
    HistoryStore,
    RuntimeStore,
    resolve_in,
    safe_filename,
)
from naomox.systems import guess_system, is_compatible

HEADER = ",".join(GAME_COLUMNS)
ROW = "Sega Naomi,n1-crazy_taxi-[840-0002].bin.gz,crazytax.png,,Crazy Taxi,,Sega,1999,Driving,,Horizontal,,Yes,No,generic,none,AAA0,x"


@pytest.mark.parametrize(
    "name",
    [
        "n1-burning_casino_{moeru_casino}-[GDL-0013].bin.gz",
        "n1-jambo!_safari-[840-0013].bin.gz",
        "tf-fzeroax_SBGG.bin.gz",
    ],
)
def test_safe_filename_accepts_real_rom_names(name: str):
    assert safe_filename(name) == name


@pytest.mark.parametrize(
    "name", ["", ".", "..", "../etc/passwd", "a/b", "a\\b", ".hidden", "bad\x00name", "x\nz"]
)
def test_safe_filename_rejects(name: str):
    with pytest.raises(ValueError):
        safe_filename(name)


def test_resolve_in_stays_inside(tmp_path: Path):
    assert resolve_in(tmp_path, "rom.bin").parent == tmp_path.resolve()
    with pytest.raises(ValueError):
        resolve_in(tmp_path, "../x")


def test_games_seed_roundtrip_and_update(tmp_path: Path):
    seed = tmp_path / "seed.csv"
    seed.write_text(f"{HEADER}\n{ROW}\n", encoding="utf-8")
    store = GamesStore(tmp_path / "state" / "games.csv", seed=seed)
    g = store.get("n1-crazy_taxi-[840-0002].bin.gz")
    assert g is not None and g["description"] == "Crazy Taxi"
    store.update(g["romname"], {"favourite": True, "enabled": "No"})
    again = GamesStore(tmp_path / "state" / "games.csv")
    g2 = again.get(g["romname"])
    assert g2 is not None and g2["favourite"] == "Yes" and g2["enabled"] == "No"
    with pytest.raises(ValueError):
        store.update(g["romname"], {"romname": "evil"})
    # Export compatible romsinfo.csv (même en-tête, même ordre de colonnes).
    assert store.export_csv().splitlines()[0] == HEADER


def test_games_add_unknown_guesses_system(tmp_path: Path):
    store = GamesStore(tmp_path / "games.csv")
    row = store.add_unknown("ch-outrun2_512_SGBZ.bin.gz")
    assert row["system"] == "Sega Chihiro" and row["enabled"] == "Yes"
    assert row["description"] == "ch-outrun2_512_SGBZ"


def test_cabinets_crud_and_validation(tmp_path: Path):
    store = CabinetsStore(tmp_path / "cabinets.yaml")
    a = store.create(CabinetIn(name="Naomi 1", ip="192.168.1.50", type="Sega Naomi"))
    with pytest.raises(ValueError, match="IP"):
        store.create(CabinetIn(name="Autre", ip="192.168.1.50"))
    with pytest.raises(ValueError):
        CabinetIn(name="X", ip="not-an-ip")
    with pytest.raises(ValueError):
        CabinetIn(name="X", ip="10.0.0.2", type="Sega Saturn")
    b = store.update(a.id, {"time_hack": True, "default_game": "none"})
    assert b.time_hack is True and b.default_game is None
    reloaded = CabinetsStore(tmp_path / "cabinets.yaml")
    assert reloaded.get(a.id) == b
    store.delete(a.id)
    assert store.all() == []


def test_runtime_and_history(tmp_path: Path):
    rt = RuntimeStore(tmp_path / "runtime.json")
    rt.set("c1", game="g.bin.gz", crc="0x1")
    assert RuntimeStore(tmp_path / "runtime.json").get("c1")["crc"] == "0x1"
    h = HistoryStore(tmp_path / "history.jsonl", keep=3)
    for i in range(10):
        h.append({"i": i})
    recent = h.recent(2)
    assert [e["i"] for e in recent] == [9, 8]


def test_compatibility_rules():
    assert is_compatible("Sega Naomi2", "Sega Naomi")
    assert is_compatible("Sega Naomi", "Sammy Atomiswave")
    assert not is_compatible("Sega Naomi", "Sega Naomi2")
    assert not is_compatible("Sega Chihiro", "Sega Triforce")
    assert guess_system("n2-virtua_fighter_4-[GDS-0012].bin.gz") == "Sega Naomi2"
    assert guess_system("weird.bin") is None
