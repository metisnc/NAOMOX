"""La bibliothèque netdimm (vendorisée) contre le mock : on vérifie les échanges."""

from __future__ import annotations

import asyncio
import zlib

import pytest

from naomox.mock import MockNetDimm
from netdimm import CRCStatusEnum, NetDimm, NetDimmException, NetDimmVersionEnum


def client(mock: MockNetDimm, **kw) -> NetDimm:
    return NetDimm("127.0.0.1", port=mock.port, timeout=5, **kw)


async def settle(cond, limit: float = 2.0) -> None:
    """reboot()/set_time_hack() n'attendent pas de réponse : laisser le mock traiter."""
    loop = asyncio.get_running_loop()
    end = loop.time() + limit
    while not cond():
        if loop.time() > end:
            raise AssertionError("condition jamais atteinte")
        await asyncio.sleep(0.01)


async def test_info_parses_firmware_and_memory(mock_dimm: MockNetDimm):
    mock_dimm.state.firmware = "4.02"
    info = await asyncio.to_thread(client(mock_dimm).info)
    assert info.firmware_version == NetDimmVersionEnum.VERSION_4_02
    assert info.memory_size == 512
    assert info.available_game_memory == 512 << 20
    assert info.current_game_size == 0
    # Le client envoie toujours le paquet de démarrage 0x01 en premier.
    assert mock_dimm.state.packets[0][0] == 0x01


async def test_send_without_crc_check_uploads_exact_bytes(mock_dimm: MockNetDimm):
    payload = bytes(range(256)) * 400  # 102 400 octets → 4 blocs de 0x8000
    progress: list[tuple[int, int]] = []

    def go():
        nd = client(mock_dimm)
        nd.send(payload, None, disable_crc_check=True, progress_callback=lambda a, b: progress.append((a, b)))
        nd.reboot()

    await asyncio.to_thread(go)
    s = mock_dimm.state
    await settle(lambda: s.restarts == 1 and s.time_limits)
    assert bytes(s.data) == payload
    assert s.key == b"\x00" * 8  # zero-key : pas de chiffrement
    assert s.crc_check_disabled is True
    assert s.host_mode == 0 and s.restarts == 1
    assert s.info_length == len(payload)
    assert s.info_crc == (~zlib.crc32(payload)) & 0xFFFFFFFF
    assert s.crc_status == 5  # CRC désactivé
    assert progress[0] == (0, len(payload)) and progress[-1] == (len(payload), len(payload))
    # Ordre des paquets : startup, host mode (now loading), key, crc disable, wipe info, upload…, set info
    ids = [p[0] for p in s.packets]
    assert ids[:4] == [0x01, 0x07, 0x7F, 0x04]
    assert 0x19 in ids and 0x0A in ids and 0x17 in ids
    uploads = [p for p in s.packets if p[0] == 0x04]
    assert uploads[-1][1] == 0x81  # dernier bloc marqué


async def test_send_with_crc_check_is_valid_after_reboot(mock_dimm: MockNetDimm):
    payload = b"NAOMI" * 10000

    def go():
        nd = client(mock_dimm)
        nd.send(payload, None, disable_crc_check=False)
        nd.reboot()
        return nd.info()

    info = await asyncio.to_thread(go)
    assert info.game_crc_status == CRCStatusEnum.STATUS_VALID
    assert info.current_game_size == len(payload)
    assert info.current_game_crc == NetDimm.crc(payload)


async def test_time_hack_packet(mock_dimm: MockNetDimm):
    await asyncio.to_thread(client(mock_dimm).set_time_hack, 10)
    await settle(lambda: mock_dimm.state.time_limits)
    assert mock_dimm.state.time_limits == [10]


async def test_refused_connection_raises(mock_dimm: MockNetDimm):
    mock_dimm.faults.refuse = True
    with pytest.raises(NetDimmException):
        await asyncio.to_thread(client(mock_dimm).info)


async def test_unreachable_port_raises():
    nd = NetDimm("127.0.0.1", port=1, timeout=2)
    with pytest.raises(NetDimmException, match="Could not connect"):
        await asyncio.to_thread(nd.info)
