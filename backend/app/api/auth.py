"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import bearer_scheme, get_client_ip, get_current_user
from app.config import settings
from app.core.audit import write_audit
from app.core.envelope import envelope, utcnow
from app.core.errors import unauthorized
from app.core.ratelimit import check_rate_limit
from app.core.security import create_access_token, revoke_token, verify_password
from app.database import get_db
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_LIMIT = 10
LOGIN_WINDOW_SECONDS = 60


@router.post("/login")
def login(
    payload: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> dict:
    ip = get_client_ip(request)
    check_rate_limit(f"login:{ip}", LOGIN_LIMIT, LOGIN_WINDOW_SECONDS)

    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        write_audit(
            db,
            action_type="LOGIN_FAILED",
            resource_type="user",
            resource_id=payload.username,
            ip_address=ip,
        )
        db.commit()
        raise unauthorized("Invalid username or password.")
    if not user.is_active:
        raise unauthorized("Account is inactive.")

    user.last_login = utcnow()
    write_audit(
        db,
        action_type="USER_LOGIN",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=ip,
    )
    db.commit()

    token = create_access_token(user.id, user.role, user.affiliated_org_id)
    body = TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )
    return envelope(body.model_dump())


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return envelope(UserOut.model_validate(user).model_dump())


@router.post("/logout")
def logout(
    request: Request,
    user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict:
    # Stateless JWTs: the client discards the token and we also revoke its jti
    # so it cannot be replayed. We record the event either way.
    if credentials is not None and credentials.credentials:
        revoke_token(credentials.credentials)
    write_audit(
        db,
        action_type="USER_LOGOUT",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return envelope({"status": "logged out"})
