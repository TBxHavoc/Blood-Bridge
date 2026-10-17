"""Auth / RBAC dependencies."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import forbidden, unauthorized
from app.core.security import decode_access_token
from app.database import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


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
