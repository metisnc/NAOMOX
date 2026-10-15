"""Faux serveur NetDIMM (TCP) pour les tests et le développement.

Implémente côté « carte » les paquets émis par la bibliothèque netdimm :
0x01 startup, 0x04 upload, 0x05 download, 0x07 host mode, 0x08 dimm mode,
0x09 close, 0x0A restart, 0x10 peek, 0x11 poke, 0x16 control read,
0x17 time limit, 0x18 information, 0x19 set information, 0x7F key code.

Format d'en-tête (little-endian, 32 bits) : AABBCCCC = id, flags, longueur.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import struct
import zlib
from dataclasses import dataclass, field

log = logging.getLogger("naomox.mock")

ADDR_CRC_DISABLE = 0xFFFEFFF0
ADDR_GAME_INFO = 0xFFFF0000
REG_CRC_STATUS = 0xFFFEFFE0
REG_GAME_SIZE = 0xFFFF0004


@dataclass
class MockFaults:
    # Ferme immédiatement toute connexion entrante (borne « refuse »).
    refuse: bool = False
    # Coupe la connexion après réception de N octets de jeu.
    disconnect_after_bytes: int | None = None
    # Délai (s) appliqué à chaque paquet d'upload (transfert lent).
    upload_delay: float = 0.0
    # Ne répond jamais aux requêtes (timeout côté client).
    mute: bool = False


@dataclass
class MockState:
    firmware: str = "4.01"
    dimm_memory_mb: int = 512
    game_memory_mb: int = 512
    host_mode: int = 0
    dimm_mode: int = 0
    key: bytes | None = None
    crc_check_disabled: bool = False
    info_crc: int = 0
    info_length: int = 0
    crc_status: int = 0
    received_crc: int = 0
    received_bytes: int = 0
    store_data: bool = True
    data: bytearray = field(default_factory=bytearray)
    restarts: int = 0
    time_limits: list[int] = field(default_factory=list)
    packets: list[tuple[int, int, int]] = field(default_factory=list)
    connections: int = 0

    @property
    def game_crc(self) -> int:
        return (~self.received_crc) & 0xFFFFFFFF


class MockNetDimm:
    def __init__(self, host: str = "127.0.0.1", port: int = 0, firmware: str = "4.01") -> None:
        self.host = host
        self.port = port
        self.state = MockState(firmware=firmware)
        self.faults = MockFaults()
        self._server: asyncio.base_events.Server | None = None
        self.upload_started = asyncio.Event()
        self.packet_received = asyncio.Event()

    # -- cycle de vie --------------------------------------------------------

    async def start(self) -> MockNetDimm:
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]
        log.info("mock NetDIMM à l'écoute sur %s:%d (firmware %s)", self.host, self.port, self.state.firmware)
        return self

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()
            self._server = None

    async def __aenter__(self) -> MockNetDimm:
        return await self.start()

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()

    def power_cycle(self) -> None:
        """Simule une coupure d'alimentation : la mémoire de jeu est perdue."""
        s = self.state
        s.info_crc = s.info_length = s.crc_status = 0
        s.received_crc = s.received_bytes = 0
        s.data = bytearray()
        s.host_mode = 0

    # -- protocole -------------------------------------------------------------

    @staticmethod
    def _packet(pktid: int, flags: int, data: bytes = b"") -> bytes:
        return (
            struct.pack("<I", ((pktid & 0xFF) << 24) | ((flags & 0xFF) << 16) | (len(data) & 0xFFFF)) + data
        )

    def _version_word(self) -> int:
        major, minor = self.state.firmware.split(".")
        return (int(major, 16) << 8) | int(minor, 16)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.state.connections += 1
        if self.faults.refuse:
            writer.close()
            return
        try:
            while True:
                try:
                    header = await reader.readexactly(4)
                except (asyncio.IncompleteReadError, ConnectionError):
                    break
                (word,) = struct.unpack("<I", header)
                pktid, flags, length = (word >> 24) & 0xFF, (word >> 16) & 0xFF, word & 0xFFFF
                data = await reader.readexactly(length) if length else b""
                self.state.packets.append((pktid, flags, length))
                self.packet_received.set()
                if self.faults.mute:
                    continue
                keep_open = await self._dispatch(pktid, flags, data, writer)
                await writer.drain()
                if not keep_open:
                    break
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _dispatch(self, pktid: int, flags: int, data: bytes, writer: asyncio.StreamWriter) -> bool:
        s = self.state
        if pktid == 0x01:  # startup / NOP
            return True
        if pktid in (0x07, 0x08):  # host / dimm mode
            (v,) = struct.unpack("<I", data[:4])
            mask, setbits = (v >> 8) & 0xFF, v & 0xFF
            if pktid == 0x07:
                s.host_mode = (s.host_mode & mask) | setbits
                mode = s.host_mode
            else:
                s.dimm_mode = (s.dimm_mode & mask) | setbits
                mode = s.dimm_mode
            writer.write(self._packet(pktid, 0, struct.pack("<I", mode)))
            return True
        if pktid == 0x7F:  # key code
            s.key = data
            return True
        if pktid == 0x04:  # upload
            return await self._upload(data)
        if pktid == 0x05:  # download
            addr, size = struct.unpack("<II", data[:8])
            payload = self._read(addr, size)
            seq, off = 1, 0
            while True:
                chunk = payload[off : off + 8192]
                last = off + len(chunk) >= len(payload)
                writer.write(
                    self._packet(
                        0x04, 0x81 if last else 0x80, struct.pack("<IIH", seq, addr + off, 0) + chunk
                    )
                )
                if last:
                    break
                seq += 1
                off += len(chunk)
            return True
        if pktid == 0x09:  # close
            return False
        if pktid == 0x0A:  # restart
            s.restarts += 1
            s.host_mode = 0
            if s.crc_check_disabled:
                s.crc_status = 5
            elif s.info_length and s.info_crc == s.game_crc:
                s.crc_status = 2
            else:
                s.crc_status = 3
            return True
        if pktid in (0x10, 0x16):  # peek / control read
            writer.write(self._packet(0x10, 0, struct.pack("<II", 1, 0)))
            return True
        if pktid == 0x11:  # poke
            return True
        if pktid == 0x17:  # time limit / time hack
            (minutes,) = struct.unpack("<I", data[:4])
            s.time_limits.append(minutes)
            return True
        if pktid == 0x18:  # information
            writer.write(
                self._packet(
                    0x18,
                    0,
                    struct.pack(
                        "<HHHHI", 0xC, self._version_word(), s.game_memory_mb, s.dimm_memory_mb, s.info_crc
                    ),
                )
            )
            return True
        if pktid == 0x19:  # set information
            s.info_crc, s.info_length, _ = struct.unpack("<III", data[:12])
            return True
        log.warning("paquet inconnu 0x%02x", pktid)
        return True

    async def _upload(self, data: bytes) -> bool:
        s = self.state
        _seq, addr, _ = struct.unpack("<IIH", data[:10])
        payload = data[10:]
        if addr == ADDR_CRC_DISABLE:
            s.crc_check_disabled = payload[:4] == b"\xff\xff\xff\xff"
            return True
        if addr == ADDR_GAME_INFO:
            s.info_crc = s.info_length = 0
            s.crc_status = 0
            return True
        if addr == 0:
            s.received_crc = 0
            s.received_bytes = 0
            s.data = bytearray()
        self.upload_started.set()
        if self.faults.upload_delay:
            await asyncio.sleep(self.faults.upload_delay)
        s.received_crc = zlib.crc32(payload, s.received_crc)
        s.received_bytes += len(payload)
        if s.store_data:
            end = addr + len(payload)
            if len(s.data) < end:
                s.data.extend(b"\0" * (end - len(s.data)))
            s.data[addr:end] = payload
        limit = self.faults.disconnect_after_bytes
        return not (limit is not None and s.received_bytes >= limit)

    def _read(self, addr: int, size: int) -> bytes:
        s = self.state
        if addr == REG_CRC_STATUS:
            return struct.pack("<I", s.crc_status)
        if addr == REG_GAME_SIZE:
            return struct.pack("<I", s.info_length)
        chunk = bytes(s.data[addr : addr + size])
        return chunk + b"\0" * (size - len(chunk))


async def serve_forever(host: str, port: int, firmware: str = "4.01") -> None:
    mock = await MockNetDimm(host, port, firmware=firmware).start()
    try:
        await asyncio.Event().wait()
    finally:
        await mock.stop()
