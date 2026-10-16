"""API REST (/api/v1), flux SSE et service du frontend compilé."""

from __future__ import annotations

import contextlib
import logging
import os
import uuid
from collections.abc import AsyncIterator
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .auth import COOKIE, SessionSigner, verify_password
from .config import Config, NetworkConfig
from .events import EventBroker
from .jobs import JobManager
from .storage import (
    Cabinet,
    CabinetIn,
    CabinetsStore,
    GamesStore,
    HistoryStore,
    RuntimeStore,
    SettingsStore,
    resolve_in,
    safe_filename,
)
from .supervisor import BusyError, Supervisor, UnreachableError, discover, info_to_dict
from .systems import COMPATIBILITY, DIMM_TYPES, SYSTEMS, is_compatible

log = logging.getLogger("naomox.api")

API = "/api/v1"
FILE_KINDS: dict[str, tuple[str, ...]] = {
    "roms": (".bin.gz", ".bin", ".gz"),
    "images": (".png", ".jpg", ".jpeg", ".webp", ".gif"),
    "videos": (".mp4", ".webm"),
    # Logos des systèmes (marques Sega / Sammy, non fournis) : « Sega Naomi.png », etc.
    "systems": (".png", ".svg", ".webp"),
    "firmware": (".bin.gz", ".bin"),
}
FIRMWARE_FILES = {
    "4.01": "FW_Netdimm_401.bin.gz",
    "4.02": "FW_Netdimm_402.bin.gz",
    "4.03": "FW_Netdimm_403.bin.gz",
}
DIAG_FILE = "naomidiag.bin.gz"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class Naomox:
    """Conteneur des services de l'application."""

    def __init__(self, config: Config) -> None:
        self.config = config
        config.ensure_dirs()
        state = config.paths.state
        seed = resources.files("naomox") / "data" / "romsinfo.csv"
        with resources.as_file(seed) as seed_path:
            self.games = GamesStore(state / "games.csv", seed=seed_path)
        self.cabinets = CabinetsStore(state / "cabinets.yaml")
        self.runtime = RuntimeStore(state / "runtime.json")
        self.history = HistoryStore(state / "history.jsonl")
        self.settings = SettingsStore(state / "settings.yaml")
        self.events = EventBroker()
        self.jobs = JobManager(config, self.events, self.runtime, self.history)
        self.supervisor = Supervisor(config, self.cabinets, self.games, self.jobs, self.runtime, self.events)
        self.signer = SessionSigner(state / "session.key")

    @property
    def subnet(self) -> str:
        return self.settings.load().get("cabinet_subnet") or self.config.network.cabinet_subnet

    def compat(self) -> dict[str, list[str]] | None:
        return self.config.compatibility

    def path_for(self, kind: str) -> Path:
        p = self.config.paths
        return {
            "roms": p.roms,
            "images": p.media / "images",
            "videos": p.media / "videos",
            "systems": p.media / "systems",
            "firmware": p.firmware,
        }[kind]


class FrontendFiles(StaticFiles):
    """Frontend compilé : index.html revalidé à chaque visite (sinon Safari / la PWA gardent
    une ancienne version), fichiers versionnés de Vite (assets/*-<hash>.*) en cache long."""

    async def get_response(self, path: str, scope: Any) -> Response:
        response = await super().get_response(path, scope)
        if path.startswith("assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response


# --------------------------------------------------------------------------- schémas


class LaunchIn(BaseModel):
    rom: str
    cabinet_id: str | None = None


class FirmwareIn(BaseModel):
    version: Literal["4.01", "4.02", "4.03"]
    confirm: bool = False


class LoginIn(BaseModel):
    password: str


class SettingsIn(BaseModel):
    cabinet_subnet: str | None = None


# --------------------------------------------------------------------------- helpers


def _err(status: int, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"message": message, **extra})


def _cab_or_404(app: Naomox, cab_id: str) -> Cabinet:
    cab = app.cabinets.get(cab_id)
    if cab is None:
        raise _err(404, "borne inconnue")
    return cab


def _game_view(
    app: Naomox, row: dict[str, str], stats: dict[str, tuple[int, float]] | None = None
) -> dict[str, Any]:
    rom = row["romname"]
    media = app.config.paths.media

    def media_url(kind: str, name: str) -> str | None:
        if not name:
            return None
        try:
            return f"{API}/media/{kind}/{name}" if resolve_in(media / kind, name).exists() else None
        except ValueError:
            return None

    try:
        path = resolve_in(app.config.paths.roms, rom)
        size = path.stat().st_size if path.exists() else None
    except (ValueError, OSError):
        size = None
    plays, last = (stats or {}).get(rom, (0, None))
    return {
        "rom": rom,
        "name": row.get("description") or rom,
        "system": row.get("system"),
        "manufacturer": row.get("manufacturer"),
        "year": row.get("year"),
        "genre": row.get("genre"),
        "rating": row.get("rating"),
        "orientation": row.get("orientation"),
        "controls": row.get("controls"),
        "enabled": row.get("enabled", "").lower() == "yes",
        "favourite": row.get("favourite", "").lower() == "yes",
        "game_id": row.get("game_id"),
        "image": media_url("images", row.get("image", "")),
        "video": media_url("videos", row.get("video", "")),
        "present": size is not None,
        "size": size,
        "plays": plays,
        "last_played": last,
    }


def _system_logo(app: Naomox, system: str) -> str | None:
    base = app.path_for("systems")
    for ext in FILE_KINDS["systems"]:
        try:
            if resolve_in(base, system + ext).exists():
                return f"{API}/media/systems/{system}{ext}"
        except ValueError:
            return None
    return None


def _cab_view(app: Naomox, cab: Cabinet) -> dict[str, Any]:
    return {**cab.model_dump(), "status": app.supervisor.status_dict(cab)}


# --------------------------------------------------------------------------- application


def create_app(config: Config) -> FastAPI:
    app_state = Naomox(config)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        app_state.supervisor.start()
        log.info("NAOMOX %s prêt — données dans %s", __version__, config.paths.data)
        yield
        await app_state.supervisor.stop()
        await app_state.jobs.shutdown()

    app = FastAPI(
        title="NAOMOX",
        version=__version__,
        lifespan=lifespan,
        docs_url=f"{API}/docs",
        openapi_url=f"{API}/openapi.json",
    )
    app.state.naomox = app_state

    @app.middleware("http")
    async def guard(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        if path.startswith("/api/"):
            # CSRF : toute écriture doit porter l'en-tête (impossible depuis un formulaire tiers).
            if request.method not in SAFE_METHODS and request.headers.get("x-requested-with") != "naomox":
                return JSONResponse(
                    {"detail": {"message": "en-tête X-Requested-With manquant"}}, status_code=403
                )
            open_paths = (f"{API}/health", f"{API}/auth")
            if (
                config.auth.enabled
                and not path.startswith(open_paths)
                and not app_state.signer.valid(request.cookies.get(COOKIE))
            ):
                return JSONResponse({"detail": {"message": "authentification requise"}}, status_code=401)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def value_error(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse({"detail": {"message": str(exc)}}, status_code=400)

    r = APIRouter(prefix=API)

    # -- système ---------------------------------------------------------------------

    @r.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__}

    @r.get("/auth")
    async def auth_status(request: Request) -> dict[str, Any]:
        return {
            "enabled": config.auth.enabled,
            "authenticated": (not config.auth.enabled) or app_state.signer.valid(request.cookies.get(COOKIE)),
        }

    @r.post("/auth/login")
    async def login(body: LoginIn, response: Response) -> dict[str, Any]:
        if not config.auth.enabled:
            return {"authenticated": True}
        if not verify_password(body.password, config.auth.password_hash):
            raise _err(401, "mot de passe incorrect")
        response.set_cookie(
            COOKIE, app_state.signer.issue(config.auth.session_hours), httponly=True, samesite="strict",
            max_age=config.auth.session_hours * 3600,
        )  # fmt: skip
        return {"authenticated": True}

    @r.post("/auth/logout")
    async def logout(response: Response) -> dict[str, Any]:
        response.delete_cookie(COOKIE)
        return {"authenticated": False}

    @r.get("/systems")
    async def systems() -> dict[str, Any]:
        return {
            "systems": SYSTEMS,
            "dimm_types": DIMM_TYPES,
            "compatibility": app_state.compat() or COMPATIBILITY,
            "firmware_versions": list(FIRMWARE_FILES),
            "logos": {s: _system_logo(app_state, s) for s in SYSTEMS},
        }

    @r.get("/settings")
    async def get_settings() -> dict[str, Any]:
        return {
            "cabinet_subnet": app_state.subnet,
            "netdimm_port": config.netdimm.port,
            "timehack_interval": config.timehack.interval_seconds,
            "auth_enabled": config.auth.enabled,
            "version": __version__,
        }

    @r.put("/settings")
    async def put_settings(body: SettingsIn) -> dict[str, Any]:
        values = app_state.settings.load()
        if body.cabinet_subnet is not None:
            values["cabinet_subnet"] = NetworkConfig(cabinet_subnet=body.cabinet_subnet).cabinet_subnet
        app_state.settings.save(values)
        return await get_settings()

    # -- jeux ---------------------------------------------------------------------------

    @r.get("/games")
    async def list_games() -> list[dict[str, Any]]:
        stats = app_state.history.play_stats()
        games = [_game_view(app_state, row, stats) for row in app_state.games.all()]
        games.sort(key=lambda g: g["name"].lower())
        return games

    @r.patch("/games/{rom}")
    async def patch_game(rom: str, changes: dict[str, Any]) -> dict[str, Any]:
        try:
            row = app_state.games.update(rom, changes)
        except KeyError:
            raise _err(404, "jeu inconnu") from None
        return _game_view(app_state, row, app_state.history.play_stats())

    @r.post("/games/scan")
    async def scan_games() -> dict[str, Any]:
        roms_dir = config.paths.roms
        files = sorted(
            f.name for f in roms_dir.iterdir() if f.is_file() and f.name.lower().endswith(FILE_KINDS["roms"])
        )
        known = {g["romname"] for g in app_state.games.all()}
        added = []
        for name in files:
            if name not in known:
                try:
                    app_state.games.add_unknown(safe_filename(name))
                    added.append(name)
                except ValueError:
                    log.warning("nom de ROM ignoré : %r", name)
        missing = sorted(known - set(files))
        return {"present": len(files), "added": added, "missing": len(missing)}

    @r.get("/games/export.csv")
    async def export_games() -> PlainTextResponse:
        return PlainTextResponse(
            app_state.games.export_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="romsinfo.csv"'},
        )

    @r.post("/games/import")
    async def import_games(file: UploadFile = File(...), replace: bool = Query(False)) -> dict[str, Any]:
        text = (await file.read()).decode("utf-8-sig")
        count = app_state.games.import_csv(text, replace=replace)
        return {"imported": count}

    # -- lancement ------------------------------------------------------------------------

    @r.post("/launch", status_code=202)
    async def launch(body: LaunchIn) -> dict[str, Any]:
        game = app_state.games.get(body.rom)
        if game is None:
            raise _err(404, "jeu inconnu")
        if game.get("enabled", "").lower() != "yes":
            raise _err(400, "ce jeu est désactivé")
        path = resolve_in(config.paths.roms, body.rom)
        if not path.exists():
            raise _err(404, "fichier ROM absent du serveur", error="rom_missing")
        system = game["system"]
        compatible = [
            c
            for c in app_state.cabinets.all()
            if c.enabled and is_compatible(c.type, system, app_state.compat())
        ]

        def brief(c: Cabinet) -> dict[str, Any]:
            return {
                "id": c.id,
                "name": c.name,
                "ip": c.ip,
                "type": c.type,
                "online": app_state.supervisor.is_online(c.id),
            }

        if body.cabinet_id:
            cab = _cab_or_404(app_state, body.cabinet_id)
            if cab not in compatible:
                raise _err(
                    400, f"{cab.name} ({cab.type}) ne peut pas lancer un jeu {system}", error="incompatible"
                )
        else:
            online = [c for c in compatible if app_state.supervisor.is_online(c.id)]
            if not compatible:
                raise _err(
                    409, f"aucune borne compatible {system} n'est configurée", error="nodimm", choices=[]
                )
            if not online:
                raise _err(409, "aucune borne compatible n'est en ligne", error="nodimm",
                           choices=[brief(c) for c in compatible])  # fmt: skip
            if len(online) > 1:
                raise _err(
                    409, "plusieurs bornes possibles", error="choose", choices=[brief(c) for c in online]
                )
            cab = online[0]
        job = app_state.jobs.submit(cab, "launch", path, body.rom, disable_crc=True)
        return job.to_dict()

    # -- jobs / historique ---------------------------------------------------------------------

    @r.get("/jobs")
    async def list_jobs(cabinet_id: str | None = None, active: bool = False) -> list[dict[str, Any]]:
        return [j.to_dict() for j in app_state.jobs.list(cabinet_id, active_only=active)]

    @r.get("/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        job = app_state.jobs.get(job_id)
        if job is None:
            raise _err(404, "job inconnu")
        return job.to_dict(with_log=True)

    @r.post("/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str) -> dict[str, Any]:
        if app_state.jobs.get(job_id) is None:
            raise _err(404, "job inconnu")
        return (await app_state.jobs.cancel(job_id)).to_dict()

    @r.post("/jobs/{job_id}/retry", status_code=202)
    async def retry_job(job_id: str) -> dict[str, Any]:
        job = app_state.jobs.get(job_id)
        if job is None:
            raise _err(404, "job inconnu")
        return app_state.jobs.retry(job_id, _cab_or_404(app_state, job.cabinet_id)).to_dict()

    @r.get("/history")
    async def history(limit: int = Query(50, ge=1, le=500)) -> list[dict[str, Any]]:
        return app_state.history.recent(limit)

    @r.get("/events")
    async def events() -> StreamingResponse:
        return StreamingResponse(
            app_state.events.stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # -- bornes ------------------------------------------------------------------------------

    @r.get("/cabinets")
    async def list_cabinets() -> list[dict[str, Any]]:
        return [_cab_view(app_state, c) for c in app_state.cabinets.all()]

    @r.post("/cabinets", status_code=201)
    async def create_cabinet(body: CabinetIn) -> dict[str, Any]:
        return _cab_view(app_state, app_state.cabinets.create(body))

    @r.get("/cabinets/{cab_id}")
    async def get_cabinet(cab_id: str) -> dict[str, Any]:
        return _cab_view(app_state, _cab_or_404(app_state, cab_id))

    @r.patch("/cabinets/{cab_id}")
    async def patch_cabinet(cab_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        changes.pop("id", None)
        try:
            cab = app_state.cabinets.update(cab_id, changes)
        except KeyError:
            raise _err(404, "borne inconnue") from None
        return _cab_view(app_state, cab)

    @r.delete("/cabinets/{cab_id}", status_code=204)
    async def delete_cabinet(cab_id: str) -> Response:
        if app_state.jobs.active(cab_id):
            raise _err(409, "transfert en cours sur cette borne")
        try:
            app_state.cabinets.delete(cab_id)
        except KeyError:
            raise _err(404, "borne inconnue") from None
        app_state.runtime.forget(cab_id)
        return Response(status_code=204)

    @r.get("/cabinets/{cab_id}/info")
    async def cabinet_info(cab_id: str) -> dict[str, Any]:
        cab = _cab_or_404(app_state, cab_id)
        try:
            info = await app_state.supervisor.info(cab)
        except BusyError as e:
            raise _err(409, str(e), error="busy") from None
        except UnreachableError as e:
            raise _err(504, str(e), error="unreachable") from None
        assert info is not None
        return info_to_dict(info)

    @r.post("/cabinets/{cab_id}/reboot")
    async def cabinet_reboot(cab_id: str) -> dict[str, Any]:
        cab = _cab_or_404(app_state, cab_id)
        try:
            await app_state.supervisor.reboot(cab)
        except BusyError as e:
            raise _err(409, str(e), error="busy") from None
        except UnreachableError as e:
            raise _err(504, str(e), error="unreachable") from None
        return {"ok": True}

    @r.post("/cabinets/{cab_id}/firmware", status_code=202)
    async def cabinet_firmware(cab_id: str, body: FirmwareIn) -> dict[str, Any]:
        cab = _cab_or_404(app_state, cab_id)
        if not body.confirm:
            raise _err(400, "confirmation requise pour la mise à jour du firmware")
        path = resolve_in(config.paths.firmware, FIRMWARE_FILES[body.version])
        if not path.exists():
            raise _err(404, f"{path.name} absent de {config.paths.firmware}", error="firmware_missing")
        return app_state.jobs.submit(cab, "firmware", path, f"Firmware NetDIMM {body.version}").to_dict()

    @r.post("/cabinets/{cab_id}/diag", status_code=202)
    async def cabinet_diag(cab_id: str) -> dict[str, Any]:
        cab = _cab_or_404(app_state, cab_id)
        if cab.type not in ("Sega Naomi", "Sega Naomi2"):
            raise _err(400, "le diagnostic n'existe que pour Naomi / Naomi 2")
        path = resolve_in(config.paths.homebrew, DIAG_FILE)
        if not path.exists():
            raise _err(404, f"{DIAG_FILE} absent de {config.paths.homebrew}")
        return app_state.jobs.submit(cab, "diag", path, "Naomi diagnostic").to_dict()

    @r.post("/cabinets/discover")
    async def cabinets_discover() -> dict[str, Any]:
        subnet = app_state.subnet
        found = await discover(subnet, config.netdimm.port)
        by_ip = {c.ip: c for c in app_state.cabinets.all()}
        return {
            "subnet": subnet,
            "found": [{"ip": ip, "cabinet_id": by_ip[ip].id if ip in by_ip else None} for ip in found],
        }

    # -- fichiers / médias -----------------------------------------------------------------------

    @r.get("/firmware")
    async def firmware_available() -> list[dict[str, Any]]:
        return [
            {"version": v, "file": f, "present": (config.paths.firmware / f).exists()}
            for v, f in FIRMWARE_FILES.items()
        ]

    @r.get("/files/{kind}")
    async def list_files(
        kind: Literal["roms", "images", "videos", "systems", "firmware"],
    ) -> list[dict[str, Any]]:
        base = app_state.path_for(kind)
        out = []
        for f in sorted(base.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                st = f.stat()
                out.append({"name": f.name, "size": st.st_size, "mtime": st.st_mtime})
        return out

    @r.post("/files/{kind}", status_code=201)
    async def upload_file(
        kind: Literal["roms", "images", "videos", "systems", "firmware"], file: UploadFile = File(...)
    ) -> dict[str, Any]:
        name = safe_filename(os.path.basename(file.filename or ""))
        if not name.lower().endswith(FILE_KINDS[kind]):
            raise _err(400, f"extension non acceptée pour {kind} : {', '.join(FILE_KINDS[kind])}")
        base = app_state.path_for(kind)
        dest = resolve_in(base, name)
        tmp = base / f".upload-{uuid.uuid4().hex}"
        size = 0
        try:
            with tmp.open("wb") as out:
                while chunk := await file.read(1 << 20):
                    out.write(chunk)
                    size += len(chunk)
            os.replace(tmp, dest)
        finally:
            with contextlib.suppress(FileNotFoundError):
                tmp.unlink()
        if kind == "roms":
            app_state.games.add_unknown(name)
        return {"name": name, "size": size}

    @r.delete("/files/{kind}/{name}", status_code=204)
    async def delete_file(
        kind: Literal["roms", "images", "videos", "systems", "firmware"], name: str
    ) -> Response:
        path = resolve_in(app_state.path_for(kind), name)
        if not path.exists():
            raise _err(404, "fichier introuvable")
        path.unlink()
        return Response(status_code=204)

    @r.get("/media/{kind}/{name}")
    async def media(kind: Literal["images", "videos", "systems"], name: str) -> FileResponse:
        try:
            path = resolve_in(app_state.path_for(kind), name)
        except ValueError:
            raise _err(404, "fichier introuvable") from None
        if not path.exists():
            raise _err(404, "fichier introuvable")
        return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})

    app.include_router(r)

    # Frontend compilé (Vite) servi à la racine ; routage côté client par hash (#/…).
    if config.paths.frontend and Path(config.paths.frontend, "index.html").exists():
        app.mount("/", FrontendFiles(directory=config.paths.frontend, html=True), name="frontend")
    else:

        @app.get("/", include_in_schema=False)
        async def root() -> dict[str, Any]:
            return {"name": "NAOMOX", "version": __version__, "api": API, "frontend": None}

    return app
