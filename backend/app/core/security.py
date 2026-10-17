"""Password hashing and JWT helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import settings

# In-process revocation list for logged-out tokens (single-worker MVP, same
# trade-off as the rate limiter). Keyed by the JWT `jti` claim.
_revoked_jtis: set[str] = set()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    role: str,
    affiliated_org_id: str | None,
    expires_minutes: int | None = None,
) -> str:
    expire = datetime.now(UTC) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "org": affiliated_org_id,
        "jti": uuid.uuid4().hex,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def revoke_token(token: str) -> None:
    """Add a token's jti to the in-process revocation list (best-effort)."""
    try:
        payload = decode_access_token(token)
    except Exception:  # noqa: BLE001 - an invalid token is already unusable
        return
    jti = payload.get("jti")
    if jti:
        _revoked_jtis.add(jti)


def is_token_revoked(payload: dict[str, Any]) -> bool:
    jti = payload.get("jti")
    return bool(jti) and jti in _revoked_jtis

