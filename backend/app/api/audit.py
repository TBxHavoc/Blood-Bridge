"""Audit log + fairness endpoints (auditor, admin).

Auditors get PII-masked views (FR-21); admins see unmasked values. The audit
store itself is append-only — there is no write/update/delete endpoint here.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.envelope import envelope
from app.core.masking import mask_pii_text
from app.database import get_db
from app.models import AuditLog, User
from app.schemas.audit import AuditLogOut
from app.services.fairness import build_fairness_report

router = APIRouter(prefix="/audit", tags=["audit"])

auditor_only = require_roles("auditor", "admin")


def _maybe_mask(row: AuditLogOut, mask: bool) -> AuditLogOut:
    if not mask:
        return row
    return row.model_copy(
        update={
            "old_value": mask_pii_text(row.old_value),
            "new_value": mask_pii_text(row.new_value),
            "reason_notes": mask_pii_text(row.reason_notes),
        }
    )


@router.get("/logs")
def list_audit_logs(
    action_type: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(auditor_only),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(AuditLog)
    if action_type:
        stmt = stmt.where(AuditLog.action_type == action_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    if since:
        stmt = stmt.where(AuditLog.created_at >= since.replace(tzinfo=None))
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    rows = db.scalars(stmt).all()
    mask = user.role == "auditor"
    return envelope(
        [_maybe_mask(AuditLogOut.model_validate(row), mask).model_dump() for row in rows]
    )


@router.get("/matching-fairness")
def matching_fairness(
    _: User = Depends(auditor_only), db: Session = Depends(get_db)
) -> dict:
    return envelope(build_fairness_report(db))
