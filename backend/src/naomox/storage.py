"""Persistance en fichiers : jeux (CSV compatible romsinfo.csv), bornes (YAML),
état d'exécution (JSON) et historique (JSON lines). Écritures atomiques sous verrou."""

from __future__ import annotations

import contextlib
import csv
import io
import ipaddress
import json
import os
import tempfile
import threading
import time
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from .systems import DIMM_TYPES, SYSTEMS, guess_system

# Colonnes de romsinfo.csv (WiPi), dans l'ordre.
GAME_COLUMNS: tuple[str, ...] = (
    "system",
    "romname",
    "image",
    "video",
    "description",
    "lcd_description",
    "manufacturer",
    "year",
    "genre",
    "rating",
    "orientation",
    "controls",
    "enabled",
    "favourite",
    "openjvs",
    "openffb",
    "game_id",
    "audit_name",
)
# Champs modifiables depuis l'API.
GAME_EDITABLE: frozenset[str] = frozenset(
    {
        "system",
        "image",
        "video",
        "description",
        "manufacturer",
        "year",
        "genre",
        "rating",
        "orientation",
        "controls",
        "enabled",
        "favourite",
    }
)


def safe_filename(name: str) -> str:
    """Valide un nom de fichier simple : pas de chemin, pas de traversée, pas de fichier caché,
    pas de caractère de contrôle."""
    if (
        not name
        or len(name) > 255
        or name.startswith(".")
        or "/" in name
        or "\\" in name
        or not name.isprintable()
    ):
        raise ValueError(f"nom de fichier invalide : {name!r}")
    return name


def resolve_in(base: Path, name: str) -> Path:
    """Résout `name` sous `base` et refuse toute sortie du répertoire."""
    safe_filename(name)
    path = (base / name).resolve()
    if path.parent != base.resolve():
        raise ValueError(f"chemin hors de {base}")
    return path


def atomic_write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(
            fd, mode, **({} if isinstance(data, bytes) else {"encoding": "utf-8", "newline": ""})
        ) as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def _yes(v: Any) -> bool:
    return str(v).strip().lower() in {"yes", "true", "1", "on"}


# --------------------------------------------------------------------------- jeux


class GamesStore:
    """Métadonnées des jeux, au format CSV de WiPi (romsinfo.csv)."""

    def __init__(self, path: Path, seed: Path | None = None) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._rows: dict[str, dict[str, str]] = {}
        if not path.exists() and seed is not None and seed.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._rows = self._parse(seed.read_text(encoding="utf-8-sig"))
            self._save()
        else:
            self.reload()

    @staticmethod
    def _parse(text: str) -> dict[str, dict[str, str]]:
        rows: dict[str, dict[str, str]] = {}
        reader = csv.DictReader(io.StringIO(text))
        missing = {"system", "romname"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"colonnes manquantes : {', '.join(sorted(missing))}")
        for raw in reader:
            rom = (raw.get("romname") or "").strip()
            if not rom:
                continue
            rows[rom] = {c: (raw.get(c) or "").strip() for c in GAME_COLUMNS}
        return rows

    def _dump(self, rows: Iterable[dict[str, str]]) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=GAME_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in GAME_COLUMNS})
        return buf.getvalue()

    def _save(self) -> None:
        atomic_write(self.path, self._dump(sorted(self._rows.values(), key=lambda r: r["romname"].lower())))

    def reload(self) -> None:
        with self._lock:
            self._rows = self._parse(self.path.read_text(encoding="utf-8-sig")) if self.path.exists() else {}

    def all(self) -> list[dict[str, str]]:
        with self._lock:
            return [dict(r) for r in self._rows.values()]

    def get(self, rom: str) -> dict[str, str] | None:
        with self._lock:
            r = self._rows.get(rom)
            return dict(r) if r else None

    def update(self, rom: str, changes: dict[str, Any]) -> dict[str, str]:
        with self._lock:
            row = self._rows.get(rom)
            if row is None:
                raise KeyError(rom)
            for k, v in changes.items():
                if k not in GAME_EDITABLE:
                    raise ValueError(f"champ non modifiable : {k}")
                if k in {"enabled", "favourite"}:
                    v = "Yes" if (v if isinstance(v, bool) else _yes(v)) else "No"
                if k == "system" and v not in SYSTEMS:
                    raise ValueError(f"système inconnu : {v}")
                row[k] = str(v)
            self._save()
            return dict(row)

    def add_unknown(self, rom: str) -> dict[str, str]:
        with self._lock:
            if rom in self._rows:
                return dict(self._rows[rom])
            base = rom
            for ext in (".gz", ".bin"):
                base = base.removesuffix(ext)
            row = {c: "" for c in GAME_COLUMNS}
            row.update(
                system=guess_system(rom) or "Sega Naomi",
                romname=rom,
                description=base,
                enabled="Yes",
                favourite="No",
            )
            self._rows[rom] = row
            self._save()
            return dict(row)

    def export_csv(self) -> str:
        with self._lock:
            return self._dump(sorted(self._rows.values(), key=lambda r: r["romname"].lower()))

    def import_csv(self, text: str, replace: bool = False) -> int:
        rows = self._parse(text)
        with self._lock:
            if replace:
                self._rows = rows
            else:
                self._rows.update(rows)
            self._save()
        return len(rows)


# --------------------------------------------------------------------------- bornes


class CabinetIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    ip: str
    type: str = "Sega Naomi"
    enabled: bool = True
    # Nom de fichier ROM, "menu" (menu OSM) ou None.
    default_game: str | None = None
    time_hack: bool = False
    server_mode: bool = False
    osm_theme: Literal["dark", "light"] = "dark"
    osm_mode: Literal["once", "replay"] = "once"

    @field_validator("ip")
    @classmethod
    def _ip(cls, v: str) -> str:
        return str(ipaddress.IPv4Address(v.strip()))

    @field_validator("type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in DIMM_TYPES:
            raise ValueError(f"type inconnu (attendu : {', '.join(DIMM_TYPES)})")
        return v

    @field_validator("default_game")
    @classmethod
    def _default_game(cls, v: str | None) -> str | None:
        if v in (None, "", "none"):
            return None
        return v if v == "menu" else safe_filename(v)


class Cabinet(CabinetIn):
    id: str


class CabinetsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._items: dict[str, Cabinet] = {}
        self.reload()

    def reload(self) -> None:
        with self._lock:
            self._items = {}
            if self.path.exists():
                data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
                for item in data.get("cabinets", []):
                    cab = Cabinet.model_validate(item)
                    self._items[cab.id] = cab

    def _save(self) -> None:
        doc = {"cabinets": [c.model_dump() for c in self._items.values()]}
        atomic_write(self.path, yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))

    def all(self) -> list[Cabinet]:
        with self._lock:
            return list(self._items.values())

    def get(self, cab_id: str) -> Cabinet | None:
        with self._lock:
            return self._items.get(cab_id)

    def _check_unique(self, data: CabinetIn, exclude: str | None = None) -> None:
        for c in self._items.values():
            if c.id == exclude:
                continue
            if c.ip == data.ip:
                raise ValueError(f"l'IP {data.ip} est déjà utilisée par « {c.name} »")
            if c.name.lower() == data.name.lower():
                raise ValueError(f"le nom « {data.name} » est déjà utilisé")

    def create(self, data: CabinetIn) -> Cabinet:
        with self._lock:
            self._check_unique(data)
            cab = Cabinet(id=uuid.uuid4().hex[:8], **data.model_dump())
            self._items[cab.id] = cab
            self._save()
            return cab

    def update(self, cab_id: str, changes: dict[str, Any]) -> Cabinet:
        with self._lock:
            cur = self._items.get(cab_id)
            if cur is None:
                raise KeyError(cab_id)
            merged = CabinetIn.model_validate({**cur.model_dump(exclude={"id"}), **changes})
            self._check_unique(merged, exclude=cab_id)
            cab = Cabinet(id=cab_id, **merged.model_dump())
            self._items[cab_id] = cab
            self._save()
            return cab

    def delete(self, cab_id: str) -> None:
        with self._lock:
            if self._items.pop(cab_id, None) is None:
                raise KeyError(cab_id)
            self._save()


# --------------------------------------------------------------------------- état / historique


class RuntimeStore:
    """Dernier jeu envoyé par borne (rom + CRC), pour le mode serveur et l'affichage."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        try:
            self._data: dict[str, dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            self._data = {}

    def get(self, cab_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._data.get(cab_id, {}))

    def set(self, cab_id: str, **values: Any) -> None:
        with self._lock:
            self._data.setdefault(cab_id, {}).update(values)
            atomic_write(self.path, json.dumps(self._data, indent=1))

    def forget(self, cab_id: str) -> None:
        with self._lock:
            if self._data.pop(cab_id, None) is not None:
                atomic_write(self.path, json.dumps(self._data, indent=1))


class HistoryStore:
    def __init__(self, path: Path, keep: int = 500) -> None:
        self.path = path
        self.keep = keep
        self._lock = threading.Lock()

    def append(self, entry: dict[str, Any]) -> None:
        entry = {"ts": time.time(), **entry}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if len(lines) > self.keep * 2:
                atomic_write(self.path, "\n".join(lines[-self.keep :]) + "\n")

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            if not self.path.exists():
                return []
            lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        out = []
        for line in reversed(lines):
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    def play_stats(self) -> dict[str, tuple[int, float]]:
        """Nombre de lancements réussis et date du dernier, par ROM."""
        stats: dict[str, tuple[int, float]] = {}
        with self._lock:
            if not self.path.exists():
                return stats
            lines = self.path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("kind") != "launch" or e.get("state") != "done" or not e.get("rom"):
                continue
            count, last = stats.get(e["rom"], (0, 0.0))
            stats[e["rom"]] = (count + 1, max(last, float(e.get("ts", 0))))
        return stats


class SettingsStore:
    """Réglages modifiables depuis l'interface (surcouche de config.yaml)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return {}
            return yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}

    def save(self, values: dict[str, Any]) -> None:
        with self._lock:
            atomic_write(self.path, yaml.safe_dump(values, sort_keys=True))
