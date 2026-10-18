"""Alert endpoints (FR-17). The frontend polls GET /alerts every 5-10 s."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.envelope import envelope
from app.core.errors import forbidden, not_found
from app.database import get_db
from app.models import Alert, User, utcnow
from app.schemas.alert import AlertOut, AlertPatch

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    is_read: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Alert).where(Alert.recipient_user_id == user.id)
    if is_read is not None:
        stmt = stmt.where(Alert.is_read.is_(is_read))
    stmt = stmt.order_by(Alert.created_at.desc()).limit(limit)
    rows = db.scalars(stmt).all()
    return envelope([AlertOut.model_validate(row).model_dump() for row in rows])


@router.patch("/{alert_id}")
def patch_alert(
    alert_id: str,
    payload: AlertPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise not_found("Alert not found.")
    if alert.recipient_user_id != user.id and user.role != "admin":
        raise forbidden("This alert is not addressed to you.")
    alert.is_read = payload.is_read
    alert.read_at = utcnow() if payload.is_read else None
    db.commit()
    return envelope(AlertOut.model_validate(alert).model_dump())
