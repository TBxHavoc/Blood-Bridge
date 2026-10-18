"""Auth / RBAC dependencies."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import forbidden, unauthorized
from app.core.security import decode_access_token, is_token_revoked
from app.database import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)

_IP_MAX_LEN = 45  # audit_logs.ip_address is String(45)


def get_client_ip(request: Request) -> str | None:
    """Resolve the client IP for rate limiting / audit.

    A client-supplied ``X-Forwarded-For`` is trusted **only** when
    ``TRUST_FORWARDED_FOR`` is enabled (i.e. the app sits behind a trusted
    proxy); otherwise it is ignored so the header cannot be spoofed to bypass
    IP-based rate limits. The result is clipped to fit the audit column.
    """
    host: str | None = None
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            host = forwarded.split(",")[0].strip()
    if not host:
        host = request.client.host if request.client else None
    return host[:_IP_MAX_LEN] if host else host


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise unauthorized("Missing bearer token.")
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception as exc:  # noqa: BLE001 - any decode failure is a 401
        raise unauthorized("Invalid or expired token.") from exc
    if is_token_revoked(payload):
        raise unauthorized("This token has been revoked.")

    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise unauthorized("User not found or inactive.")
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    """Dependency factory: allow only the given roles (server-side, not UI)."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise forbidden(
                f"This action requires one of: {', '.join(roles)}."
            )
        return user

    return _checker
