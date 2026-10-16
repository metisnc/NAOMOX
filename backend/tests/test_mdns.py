"""Nom réseau (mDNS) : validation et annonce via avahi-publish (simulé)."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from naomox.mdns import MdnsPublisher, normalize_name, system_hostname


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("naomox", "naomox"),
        ("NAOMOX Salon.local", "naomox-salon"),
        ("borne_2", "borne-2"),
        ("  arcade ", "arcade"),
    ],
)
def test_normalize(raw: str, expected: str):
    assert normalize_name(raw) == expected


@pytest.mark.parametrize("raw", ["", "-abc", "abc-", "a.b", "é", "x" * 64])
def test_normalize_rejects(raw: str):
    with pytest.raises(ValueError):
        normalize_name(raw)


def fake_avahi(tmp_path: Path, body: str) -> str:
    exe = tmp_path / "avahi-publish"
    exe.write_text(f'#!/bin/sh\necho "$@" > {tmp_path}/args\n{body}\n')
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return str(exe)


async def test_publishes_alias_and_stops(tmp_path: Path):
    pub = MdnsPublisher(fake_avahi(tmp_path, "sleep 30"))
    await pub.apply("borne-salon")
    assert pub.active and pub.error is None
    args = (tmp_path / "args").read_text().split()
    assert args[:3] == ["-a", "-R", "borne-salon.local"]
    await pub.stop()
    assert not pub.active


async def test_reports_failure(tmp_path: Path):
    pub = MdnsPublisher(fake_avahi(tmp_path, "echo 'Local name collision' >&2; exit 1"))
    await pub.apply("borne-salon")
    assert not pub.active and "collision" in (pub.error or "")


async def test_hostname_needs_no_alias(tmp_path: Path):
    pub = MdnsPublisher(fake_avahi(tmp_path, "sleep 30"))
    await pub.apply(system_hostname())
    assert not pub.active and pub.error is None and not (tmp_path / "args").exists()


async def test_missing_avahi():
    pub = MdnsPublisher.__new__(MdnsPublisher)
    pub.__init__()
    pub.executable = None
    await pub.apply("borne-salon")
    assert "avahi" in (pub.error or "")
