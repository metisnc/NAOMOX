"""Systèmes arcade, types de NetDIMM et règles de compatibilité (reprises de WiPi)."""

from __future__ import annotations

SYSTEMS: tuple[str, ...] = (
    "Sega Naomi",
    "Sega Naomi2",
    "Sammy Atomiswave",
    "Sega Chihiro",
    "Sega Triforce",
)

# Types de borne (carte hôte de la NetDIMM).
DIMM_TYPES: tuple[str, ...] = ("Sega Naomi", "Sega Naomi2", "Sega Chihiro", "Sega Triforce")

# Jeux acceptés par type de borne — supported_systems() de launcher/api/lib.php.
COMPATIBILITY: dict[str, tuple[str, ...]] = {
    "Sega Naomi": ("Sega Naomi", "Sammy Atomiswave"),
    "Sega Naomi2": ("Sega Naomi", "Sega Naomi2", "Sammy Atomiswave"),
    "Sega Chihiro": ("Sega Chihiro",),
    "Sega Triforce": ("Sega Triforce",),
}

# Cible netdimm (influence les timeouts par défaut de la bibliothèque).
NETDIMM_TARGET: dict[str, str] = {
    "Sega Naomi": "naomi",
    "Sega Naomi2": "naomi",
    "Sega Chihiro": "chihiro",
    "Sega Triforce": "triforce",
}

# Préfixe des noms de fichiers ROM (convention du pack WiPi) → système.
ROM_PREFIXES: dict[str, str] = {
    "n1": "Sega Naomi",
    "n2": "Sega Naomi2",
    "aw": "Sammy Atomiswave",
    "ch": "Sega Chihiro",
    "tf": "Sega Triforce",
}


def is_compatible(dimm_type: str, system: str, overrides: dict[str, list[str]] | None = None) -> bool:
    table = overrides or COMPATIBILITY
    return system in table.get(dimm_type, ())


def guess_system(filename: str) -> str | None:
    prefix = filename.split("-", 1)[0].lower()
    return ROM_PREFIXES.get(prefix)


def netdimm_target(dimm_type: str) -> str:
    return NETDIMM_TARGET.get(dimm_type, "naomi")
