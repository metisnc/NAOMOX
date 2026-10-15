"""API HTTP (client ASGI en mémoire) : jeux, bornes, lancement, sécurité."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from naomox.api import create_app
from naomox.auth import hash_password
from naomox.config import Config
from naomox.mock import MockNetDimm
from tests.conftest import make_rom

H = {"X-Requested-With": "naomox"}
GAME = "n1-crazy_taxi-[840-0002].bin.gz"


def config(tmp_path: Path, port: int = 10703, **extra) -> Config:
    cfg = Config.model_validate(
        {"paths": {"data": str(tmp_path / "data")}, "netdimm": {"port": port, "probe_interval": 0.2}, **extra}
    )
    cfg.ensure_dirs()
    return cfg


@pytest.fixture
async def api(tmp_path: Path, mock_dimm: MockNetDimm):
    app = create_app(config(tmp_path, mock_dimm.port))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            c.app = app  # type: ignore[attr-defined]
            yield c


async def wait_online(c: httpx.AsyncClient, cab_id: str) -> None:
    async with asyncio.timeout(5):
        while not (await c.get(f"/api/v1/cabinets/{cab_id}")).json()["status"]["online"]:
            await asyncio.sleep(0.05)


async def wait_job(c: httpx.AsyncClient, job_id: str) -> dict:
    async with asyncio.timeout(30):
        while True:
            j = (await c.get(f"/api/v1/jobs/{job_id}")).json()
            if j["state"] in ("done", "error", "cancelled"):
                return j
            await asyncio.sleep(0.05)


async def test_health_and_seeded_games(api: httpx.AsyncClient):
    assert (await api.get("/api/v1/health")).json()["status"] == "ok"
    games = (await api.get("/api/v1/games")).json()
    assert len(games) > 150  # romsinfo.csv de WiPi embarqué
    taxi = next(g for g in games if g["rom"] == GAME)
    assert taxi["system"] == "Sega Naomi" and taxi["present"] is False


async def test_csrf_header_required(api: httpx.AsyncClient):
    r = await api.post("/api/v1/cabinets", json={"name": "B", "ip": "10.0.0.2"})
    assert r.status_code == 403


async def test_cabinet_crud_and_validation(api: httpx.AsyncClient):
    r = await api.post("/api/v1/cabinets", json={"name": "B", "ip": "10.0.0.300"}, headers=H)
    assert r.status_code == 422
    r = await api.post(
        "/api/v1/cabinets", json={"name": "B", "ip": "10.0.0.2", "type": "Sega Chihiro"}, headers=H
    )
    assert r.status_code == 201
    cab = r.json()
    r = await api.patch(f"/api/v1/cabinets/{cab['id']}", json={"ip": "10.0.0.3"}, headers=H)
    assert r.json()["ip"] == "10.0.0.3"
    r = await api.post("/api/v1/cabinets", json={"name": "C", "ip": "10.0.0.3"}, headers=H)
    assert r.status_code == 400
    assert (await api.delete(f"/api/v1/cabinets/{cab['id']}", headers=H)).status_code == 204
    assert (await api.get(f"/api/v1/cabinets/{cab['id']}")).status_code == 404


async def test_launch_flow_auto_cabinet(api: httpx.AsyncClient, mock_dimm: MockNetDimm):
    app_cfg = api.app.state.naomox.config  # type: ignore[attr-defined]
    raw = make_rom(app_cfg.paths.roms / GAME, 150_000)
    r = await api.post("/api/v1/launch", json={"rom": GAME}, headers=H)
    assert r.status_code == 409 and r.json()["detail"]["error"] == "nodimm"

    cab = (await api.post("/api/v1/cabinets", json={"name": "Naomi", "ip": "127.0.0.1"}, headers=H)).json()
    await wait_online(api, cab["id"])
    r = await api.post("/api/v1/launch", json={"rom": GAME}, headers=H)
    assert r.status_code == 202, r.text
    job = await wait_job(api, r.json()["id"])
    assert job["state"] == "done" and job["cabinet_id"] == cab["id"]
    assert bytes(mock_dimm.state.data) == raw
    assert (await api.get("/api/v1/history")).json()[0]["rom"] == GAME
    status = (await api.get(f"/api/v1/cabinets/{cab['id']}")).json()["status"]
    assert status["game"] == GAME


async def test_launch_rejects_incompatible_and_choose(api: httpx.AsyncClient, mock_dimm: MockNetDimm):
    app_cfg = api.app.state.naomox.config  # type: ignore[attr-defined]
    make_rom(app_cfg.paths.roms / GAME, 1000)
    chi = (
        await api.post(
            "/api/v1/cabinets", json={"name": "Chihiro", "ip": "127.0.0.2", "type": "Sega Chihiro"}, headers=H
        )
    ).json()
    r = await api.post("/api/v1/launch", json={"rom": GAME, "cabinet_id": chi["id"]}, headers=H)
    assert r.status_code == 400 and r.json()["detail"]["error"] == "incompatible"
    a = (await api.post("/api/v1/cabinets", json={"name": "N1", "ip": "127.0.0.1"}, headers=H)).json()
    sup = api.app.state.naomox.supervisor  # type: ignore[attr-defined]
    b = (await api.post("/api/v1/cabinets", json={"name": "N2", "ip": "127.0.0.3"}, headers=H)).json()
    await wait_online(api, a["id"])
    sup.status(b["id"]).online = True  # simule une 2e borne en ligne
    r = await api.post("/api/v1/launch", json={"rom": GAME}, headers=H)
    assert r.status_code == 409 and r.json()["detail"]["error"] == "choose"
    assert {c["name"] for c in r.json()["detail"]["choices"]} == {"N1", "N2"}


async def test_launch_unknown_or_missing_rom(api: httpx.AsyncClient):
    assert (await api.post("/api/v1/launch", json={"rom": "nope.bin.gz"}, headers=H)).status_code == 404
    r = await api.post("/api/v1/launch", json={"rom": GAME}, headers=H)
    assert r.status_code == 404 and r.json()["detail"]["error"] == "rom_missing"


async def test_game_patch_and_scan(api: httpx.AsyncClient):
    r = await api.patch(f"/api/v1/games/{GAME}", json={"favourite": True}, headers=H)
    assert r.json()["favourite"] is True
    r = await api.patch(f"/api/v1/games/{GAME}", json={"romname": "x"}, headers=H)
    assert r.status_code == 400
    app_cfg = api.app.state.naomox.config  # type: ignore[attr-defined]
    make_rom(app_cfg.paths.roms / "tf-new_game_SBZZ.bin.gz", 100)
    scan = (await api.post("/api/v1/games/scan", headers=H)).json()
    assert scan["added"] == ["tf-new_game_SBZZ.bin.gz"]
    g = next(g for g in (await api.get("/api/v1/games")).json() if g["rom"] == "tf-new_game_SBZZ.bin.gz")
    assert g["system"] == "Sega Triforce" and g["present"]
    csv = (await api.get("/api/v1/games/export.csv")).text
    assert csv.startswith("system,romname,")


async def test_upload_and_path_traversal(api: httpx.AsyncClient):
    r = await api.post("/api/v1/files/roms", files={"file": ("n1-up.bin.gz", b"\x1f\x8bdata")}, headers=H)
    assert r.status_code == 201
    names = [f["name"] for f in (await api.get("/api/v1/files/roms")).json()]
    assert "n1-up.bin.gz" in names
    r = await api.post("/api/v1/files/roms", files={"file": ("evil.sh", b"x")}, headers=H)
    assert r.status_code == 400
    r = await api.get("/api/v1/media/images/..%2F..%2Fstate%2Fcabinets.yaml")
    assert r.status_code == 404
    assert (await api.delete("/api/v1/files/roms/n1-up.bin.gz", headers=H)).status_code == 204


async def test_info_endpoint(api: httpx.AsyncClient, mock_dimm: MockNetDimm):
    cab = (await api.post("/api/v1/cabinets", json={"name": "N", "ip": "127.0.0.1"}, headers=H)).json()
    info = (await api.get(f"/api/v1/cabinets/{cab['id']}/info")).json()
    assert info["firmware"] == "4.01" and info["memory_mb"] == 512


async def test_firmware_requires_confirmation_and_file(api: httpx.AsyncClient):
    cab = (await api.post("/api/v1/cabinets", json={"name": "N", "ip": "127.0.0.1"}, headers=H)).json()
    url = f"/api/v1/cabinets/{cab['id']}/firmware"
    assert (await api.post(url, json={"version": "4.03"}, headers=H)).status_code == 400
    r = await api.post(url, json={"version": "4.03", "confirm": True}, headers=H)
    assert r.status_code == 404 and r.json()["detail"]["error"] == "firmware_missing"


async def test_auth_enabled(tmp_path: Path):
    app = create_app(config(tmp_path, auth={"enabled": True, "password_hash": hash_password("s3cret")}))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            assert (await c.get("/api/v1/games")).status_code == 401
            assert (await c.get("/api/v1/health")).status_code == 200
            bad = await c.post("/api/v1/auth/login", json={"password": "nope"}, headers=H)
            assert bad.status_code == 401
            ok = await c.post("/api/v1/auth/login", json={"password": "s3cret"}, headers=H)
            assert ok.status_code == 200
            assert (await c.get("/api/v1/games")).status_code == 200
