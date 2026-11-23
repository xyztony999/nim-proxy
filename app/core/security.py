"""Security helpers: secret masking, bearer extraction, constant-time compare,
password hashing and session-token hashing (stdlib only)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from secrets import compare_digest

from fastapi import Request

_PBKDF2_ROUNDS = 120_000


def _pbkdf2_sha256(password: bytes, salt: bytes, rounds: int) -> bytes:
    """Pure-Python PBKDF2-HMAC-SHA256 (single 32-byte block).

    Pyodide's hashlib lacks pbkdf2_hmac, so implement it with hmac + sha256,
    which are available on both the server and Workers runtimes.
    """
    u = hmac.new(password, salt + b"\x00\x00\x00\x01", hashlib.sha256).digest()
    result = bytearray(u)
    for _ in range(rounds - 1):
        u = hmac.new(password, u, hashlib.sha256).digest()
        for i in range(32):
            result[i] ^= u[i]
    return bytes(result)


def mask_secret(value: str, keep: int = 4) -> str:
    """Mask a secret, keeping only the last ``keep`` characters."""
    if not value:
        return ""
    return "****" + value[-keep:] if len(value) > keep else "****"


def bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def secrets_equal(a: str, b: str) -> bool:
    """Constant-time comparison of two secrets."""
    return compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def hash_password(password: str) -> str:
    """Salted PBKDF2-HMAC-SHA256; stored as ``salt_hex$hash_hex``."""
    salt = secrets.token_bytes(16)
    digest = _pbkdf2_sha256(password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification against a ``salt_hex$hash_hex`` record."""
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    digest = _pbkdf2_sha256(password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return hmac.compare_digest(digest, expected)


def hash_token(token: str) -> str:
    """SHA-256 of a session token (store the hash, never the raw token)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(32)
