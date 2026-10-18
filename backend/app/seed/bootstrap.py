"""Idempotent bootstrap of a temporary admin account.

The credential is never written in code. It is read from the environment
(`ADMIN_USERNAME` / `ADMIN_PASSWORD`, e.g. via the git-ignored `backend/.env`)
and persisted only as a bcrypt hash. Because the environment is the source of
truth, re-running with a changed password in `.env` rotates the account's
password — which is what a *temporary* login should do.

The password is never logged and never returned to a client.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_password, verify_password
from app.database import SessionLocal
from app.models import Hospital, User

logger = logging.getLogger("bloodbridge")


def ensure_bootstrap_admin(db: Session | None = None) -> bool:
    """Create/refresh the temp admin from the environment.

    Returns ``True`` when an account is present afterwards, ``False`` when the
    feature is not configured (both env values empty).
    """
    username = settings.admin_username.strip()
    password = settings.admin_password
    if not username or not password:
        logger.info(
            "Bootstrap admin not configured (set ADMIN_USERNAME and "
            "ADMIN_PASSWORD in backend/.env); skipping."
        )
        return False

    owns_session = db is None
    session = db or SessionLocal()
    try:
        user = session.scalar(select(User).where(User.username == username))
        if user is None:
            session.add(
                User(
                    username=username,
                    email=f"{username}@bloodbridge.local",
                    password_hash=hash_password(password),
                    role="admin",
                    affiliated_org_id=None,
                    is_active=True,
                )
            )
            session.commit()
            logger.info("Bootstrap admin %r created (role=admin).", username)
            return True

        changed = False
        if user.role != "admin":
            user.role = "admin"
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if not verify_password(password, user.password_hash):
            user.password_hash = hash_password(password)
            changed = True
        if changed:
            session.commit()
            logger.info(
                "Bootstrap admin %r refreshed to match the environment.", username
            )
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def ensure_bootstrap_hospital(db: Session | None = None) -> bool:
    """Create/refresh the dedicated single hospital account and deactivate others."""
    username = settings.hospital_username.strip()
    password = settings.hospital_password
    if not username or not password:
        return False

    owns_session = db is None
    session = db or SessionLocal()
    try:
        # Find primary hospital (H_001 or first available hospital)
        hospital = session.scalar(select(Hospital).where(Hospital.code == "H_001"))
        if hospital is None:
            hospital = session.scalar(select(Hospital))

        hospital_id = hospital.id if hospital else None

        user = session.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(
                username=username,
                email=f"{username}@hospital.test",
                password_hash=hash_password(password),
                role="hospital_user",
                affiliated_org_id=hospital_id,
                is_active=True,
            )
            session.add(user)
            logger.info("Bootstrap hospital user %r created (role=hospital_user).", username)
        else:
            user.password_hash = hash_password(password)
            user.role = "hospital_user"
            user.affiliated_org_id = hospital_id
            user.is_active = True
            logger.info("Bootstrap hospital user %r refreshed.", username)

        # Ensure this is the ONLY active hospital account
        other_hospitals = session.scalars(
            select(User).where(User.role == "hospital_user", User.username != username)
        ).all()
        for other in other_hospitals:
            other.is_active = False

        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()
