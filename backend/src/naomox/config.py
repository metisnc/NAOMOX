"""Configuration statique (config.yaml) — chemins, réseau, timeouts, authentification."""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

DEFAULT_CONFIG_PATH = "/etc/naomox/config.yaml"


class PathsConfig(BaseModel):
    data: Path = Path("/srv/naomox")
    # Frontend compilé (Vite). Optionnel : l'API fonctionne sans.
    frontend: Path | None = None

    @property
    def roms(self) -> Path:
        return self.data / "roms"

    @property
    def media(self) -> Path:
        return self.data / "media"

    @property
    def firmware(self) -> Path:
        return self.data / "firmware"

    @property
    def homebrew(self) -> Path:
        return self.data / "homebrew"

    @property
    def state(self) -> Path:
        return self.data / "state"

    @property
    def tmp(self) -> Path:
        return self.data / "tmp"


class HttpConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 80


class AuthConfig(BaseModel):
    enabled: bool = False
    # Généré par `naomox set-password` (scrypt).
    password_hash: str = ""
    session_hours: int = 720


class NetworkConfig(BaseModel):
    cabinet_subnet: str = "10.185.10.0/24"

    @field_validator("cabinet_subnet")
    @classmethod
    def _valid_subnet(cls, v: str) -> str:
        net = ipaddress.ip_network(v, strict=False)
        if net.num_addresses > 4096:
            raise ValueError("sous-réseau trop large pour la découverte (max /20)")
        return str(net)


class NetdimmConfig(BaseModel):
    port: int = 10703
    # Timeout socket de la bibliothèque netdimm (s). None = défaut par cible (15 s / 40 s).
    socket_timeout: int | None = None
    # Durée maximale d'un transfert complet (décompression + envoi + reboot).
    send_timeout: int = 900
    # Nouvelles tentatives automatiques si la borne est injoignable à la connexion.
    retries: int = 2
    retry_delay: float = 3.0
    # Relit taille et CRC sur la NetDIMM après l'envoi (détecte une coupure silencieuse).
    verify_upload: bool = True
    # Sonde de présence (connexion TCP au port NetDIMM).
    probe_interval: float = 5.0
    probe_timeout: float = 1.5


class TimehackConfig(BaseModel):
    # Paquet 0x17 (set_time_limit) envoyé périodiquement — reprend timehack.py.
    interval_seconds: float = 30.0
    minutes: int = 10


class Config(BaseModel):
    paths: PathsConfig = Field(default_factory=PathsConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    netdimm: NetdimmConfig = Field(default_factory=NetdimmConfig)
    timehack: TimehackConfig = Field(default_factory=TimehackConfig)
    # Surcharge optionnelle de la table de compatibilité type de borne → systèmes.
    compatibility: dict[str, list[str]] | None = None

    def ensure_dirs(self) -> None:
        p = self.paths
        for d in (
            p.roms,
            p.media / "images",
            p.media / "videos",
            p.media / "systems",
            p.firmware,
            p.homebrew,
            p.state,
            p.tmp,
        ):
            d.mkdir(parents=True, exist_ok=True)


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    path = path or os.environ.get("NAOMOX_CONFIG") or DEFAULT_CONFIG_PATH
    p = Path(path)
    if not p.exists():
        return Config()
    with p.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return Config.model_validate(raw)
