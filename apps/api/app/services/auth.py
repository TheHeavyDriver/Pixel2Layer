from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError

_PBKDF2_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 with a random per-password salt.

    Stored as `pbkdf2_sha256$<iterations>$<salt hex>$<digest hex>`.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iterations, salt_hex, digest_hex = stored.split("$")
        digest = bytes.fromhex(digest_hex)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, candidate)


def create_access_token(
    user_id: str,
    *,
    secret: str,
    expires_minutes: int,
    algorithm: str = "HS256",
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(token: str, *, secret: str, algorithm: str = "HS256") -> str | None:
    """Return the token subject (user id) or None if invalid/expired."""
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
    except (InvalidTokenError, ValueError):
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None