"""Admin endpoints: user management and configuration (admin role only).

There is no public registration (PRD FR-3): users are created here by an admin
or by the seed script. Role and organisation are validated server-side.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_roles
from app.core.audit import write_audit
from app.core.envelope import envelope
from app.core.errors import bad_request, conflict, not_found
from app.core.security import hash_password
from app.database import get_db
from app.models import BloodBank, Hospital, User
from app.schemas.user import UserCreate, UserOut, UserPatch

router = APIRouter(prefix="/admin", tags=["admin"])

admin_only = require_roles("admin")


def _validate_org(db: Session, role: str, org_id: str | None) -> None:
    if role == "hospital_user":
        if not org_id or db.get(Hospital, org_id) is None:
            raise bad_request("hospital_user requires a valid affiliated hospital id.")
    elif role == "bloodbank_user":
        if not org_id or db.get(BloodBank, org_id) is None:
            raise bad_request("bloodbank_user requires a valid affiliated blood bank id.")
    elif org_id is not None:
        raise bad_request(f"role '{role}' must not have an affiliated organisation.")


@router.post("/users")
def create_user(
    payload: UserCreate,
    request: Request,
    admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
) -> dict:
    _validate_org(db, payload.role, payload.affiliated_org_id)

    if db.scalar(select(User).where(User.username == payload.username)):
        raise conflict("Username already exists.")
    if db.scalar(select(User).where(User.email == payload.email)):
        raise conflict("Email already exists.")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        affiliated_org_id=payload.affiliated_org_id,
    )
    db.add(user)
    db.flush()
    write_audit(
        db,
        action_type="CREATE_USER",
        user_id=admin.id,
        resource_type="user",
        resource_id=user.id,
        new_value={"username": user.username, "role": user.role},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return envelope(UserOut.model_validate(user).model_dump())


@router.get("/users")
def list_users(
    _: User = Depends(admin_only), db: Session = Depends(get_db)
) -> dict:
    users = db.scalars(select(User).order_by(User.username)).all()
    return envelope([UserOut.model_validate(u).model_dump() for u in users])


@router.patch("/users/{user_id}")
def patch_user(
    user_id: str,
    payload: UserPatch,
    request: Request,
    admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User not found.")
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.affiliated_org_id is not None:
        _validate_org(db, user.role, payload.affiliated_org_id)
        user.affiliated_org_id = payload.affiliated_org_id
    write_audit(
        db,
        action_type="UPDATE_USER",
        user_id=admin.id,
        resource_type="user",
        resource_id=user.id,
        new_value=payload.model_dump(exclude_none=True),
        ip_address=get_client_ip(request),
    )
    db.commit()
    return envelope(UserOut.model_validate(user).model_dump())
