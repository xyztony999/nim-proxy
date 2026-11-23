"""Security helpers: secret masking, bearer extraction, constant-time compare."""

from __future__ import annotations

from secrets import compare_digest

from fastapi import Request


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
