"""Authentification optionnelle : mot de passe unique (scrypt) et cookie de session signé."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from pathlib import Path

COOKIE = "naomox_session"
_N, _R, _P = 2**14, 8, 1


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, n, r, p, salt, digest = encoded.split("$")
        if algo != "scrypt":
            return False
        test = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(test, _unb64(digest))
    except (ValueError, TypeError):
        return False


class SessionSigner:
    def __init__(self, secret_file: Path) -> None:
        if secret_file.exists():
            self._key = secret_file.read_bytes()
        else:
            secret_file.parent.mkdir(parents=True, exist_ok=True)
            self._key = secrets.token_bytes(32)
            secret_file.write_bytes(self._key)
            secret_file.chmod(0o600)

    def issue(self, hours: int) -> str:
        expiry = str(int(time.time()) + hours * 3600)
        sig = hmac.new(self._key, expiry.encode(), hashlib.sha256).digest()
        return f"{expiry}.{_b64(sig)}"

    def valid(self, token: str | None) -> bool:
        if not token or "." not in token:
            return False
        expiry, sig = token.split(".", 1)
        good = hmac.new(self._key, expiry.encode(), hashlib.sha256).digest()
        try:
            return hmac.compare_digest(good, _unb64(sig)) and int(expiry) > time.time()
        except ValueError:
            return False
