"""Bout en bout : vrai serveur HTTP (uvicorn) + mock NetDIMM + flux SSE.

Scénario de l'interface : déclarer une borne, lancer un jeu fictif, suivre les
événements SSE jusqu'à « done », vérifier que la NetDIMM a reçu la ROM et redémarré.
"""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path

import httpx
import uvicorn

from naomox.api import create_app
from naomox.config import Config
from naomox.mock import MockNetDimm
from tests.conftest import make_rom

H = {"X-Requested-With": "naomox"}
ROM = "n1-crazy_taxi-[840-0002].bin.gz"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def test_launch_from_api_until_done_over_sse(tmp_path: Path, mock_dimm: MockNetDimm):
    cfg = Config.model_validate(
        {
            "paths": {"data": str(tmp_path / "data")},
            "http": {"host": "127.0.0.1", "port": free_port()},
            "netdimm": {"port": mock_dimm.port, "probe_interval": 0.2},
        }
    )
    cfg.ensure_dirs()
    raw = make_rom(cfg.paths.roms / ROM, 1_500_000)

    server = uvicorn.Server(uvicorn.Config(create_app(cfg), host="127.0.0.1", port=cfg.http.port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    base = f"http://127.0.0.1:{cfg.http.port}"
    try:
        async with httpx.AsyncClient(base_url=base, timeout=10) as c:
            async with asyncio.timeout(10):
                while not server.started:
                    await asyncio.sleep(0.05)

            cab = (await c.post("/api/v1/cabinets", json={"name": "Borne virtuelle", "ip": "127.0.0.1"}, headers=H)).json()
            async with asyncio.timeout(5):
                while not (await c.get(f"/api/v1/cabinets/{cab['id']}")).json()["status"]["online"]:
                    await asyncio.sleep(0.1)

            states: list[str] = []
            async with c.stream("GET", "/api/v1/events", timeout=None) as sse:
                lines = sse.aiter_lines()
                assert (await anext(lines)).startswith("retry:")
                r = await c.post("/api/v1/launch", json={"rom": ROM}, headers=H)
                assert r.status_code == 202, r.text
                job_id = r.json()["id"]
                event = None
                async with asyncio.timeout(30):
                    async for line in lines:
                        if line.startswith("event: "):
                            event = line[7:]
                        elif line.startswith("data: ") and event == "job":
                            job = json.loads(line[6:])
                            if job["id"] == job_id and (not states or states[-1] != job["state"]):
                                states.append(job["state"])
                            if job["id"] == job_id and job["state"] in ("done", "error", "cancelled"):
                                break

            assert states[-1] == "done", states
            for expected in ("decompress", "connecting", "uploading", "verifying", "rebooting"):
                assert expected in states
            assert bytes(mock_dimm.state.data) == raw
            assert mock_dimm.state.restarts == 1
            status = (await c.get(f"/api/v1/cabinets/{cab['id']}")).json()["status"]
            assert status["game"] == ROM and status["busy"] is False
            assert (await c.get("/api/v1/history")).json()[0]["state"] == "done"
            # Le frontend n'est pas compilé dans ce test : la racine renvoie l'identité de l'API.
            assert (await c.get("/")).json()["name"] == "NAOMOX"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 10)
