"""Ligne de commande : `naomox serve | mock | hash-password`."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import getpass
import logging
import sys

from . import __version__


def _logging(level: str) -> None:
    # stdout → journald (le service systemd ajoute horodatage et unité).
    logging.basicConfig(level=level.upper(), format="%(levelname)s %(name)s: %(message)s", stream=sys.stdout)


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .api import create_app
    from .config import load_config

    _logging(args.log_level)
    config = load_config(args.config)
    if args.port:
        config.http.port = args.port
    app = create_app(config)
    uvicorn.run(
        app,
        host=args.host or config.http.host,
        port=config.http.port,
        log_level=args.log_level.lower(),
        access_log=args.access_log,
        proxy_headers=True,
    )
    return 0


def cmd_mock(args: argparse.Namespace) -> int:
    from .mock import serve_forever

    _logging(args.log_level)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(serve_forever(args.host, args.port, firmware=args.firmware))
    return 0


def cmd_hash_password(args: argparse.Namespace) -> int:
    from .auth import hash_password

    pw = args.password or getpass.getpass("Mot de passe : ")
    if not args.password and pw != getpass.getpass("Confirmation : "):
        print("Les mots de passe ne correspondent pas.", file=sys.stderr)
        return 1
    print(hash_password(pw))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="naomox", description=f"NAOMOX {__version__} — netbooter NetDIMM")
    p.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="lance l'API et l'interface web")
    s.add_argument("--config", default=None, help="chemin de config.yaml (défaut : /etc/naomox/config.yaml)")
    s.add_argument("--host", default=None)
    s.add_argument("--port", type=int, default=None)
    s.add_argument("--access-log", action="store_true")
    s.set_defaults(func=cmd_serve)

    m = sub.add_parser("mock", help="lance une NetDIMM virtuelle (tests, démo)")
    m.add_argument("--host", default="127.0.0.1")
    m.add_argument("--port", type=int, default=10703)
    m.add_argument("--firmware", default="4.03")
    m.set_defaults(func=cmd_mock)

    h = sub.add_parser("hash-password", help="génère auth.password_hash pour config.yaml")
    h.add_argument("--password", default=None, help="(déconseillé : visible dans l'historique du shell)")
    h.set_defaults(func=cmd_hash_password)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
