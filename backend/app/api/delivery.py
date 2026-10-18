"""Delivery tracking endpoints for hospital-side ETA monitoring.

When a blood bank approves a request, a delivery record is created. The hospital
can poll GET /delivery to see all active deliveries and their current status/ETA.

Flow:
1. Request approved → delivery record created with status DISPATCHED.
2. Immediately: "Blood is on the way!" message.
3. After 5 minutes: ETA is computed based on distance_km and shown to hospital.
4. On simulated arrival: status moves to DELIVERED.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.envelope import envelope
from app.core.errors import not_found
from app.database import get_db
from app.models import (
    BloodBank,
    BloodRequest,
    Delivery,
    Hospital,
    User,
)

router = APIRouter(prefix="/delivery", tags=["delivery"])

hospital_or_admin = require_roles("hospital_user", "admin")


def _compute_eta_minutes(distance_km: float) -> int:
    """Estimate delivery ETA in minutes from distance.

    Assumes average urban speed of 30 km/h with a 5-minute dispatch buffer.
    """
    if distance_km <= 0:
        return 5  # minimum dispatch time
    travel_minutes = (distance_km / 30.0) * 60
    return max(5, math.ceil(travel_minutes + 5))


def _delivery_out(delivery, db: Session) -> dict:
    """Format a Delivery row into an API response dict."""
    request = db.get(BloodRequest, delivery.request_id)
    blood_bank = db.get(BloodBank, delivery.blood_bank_id) if delivery.blood_bank_id else None
    hospital = db.get(Hospital, delivery.hospital_id) if delivery.hospital_id else None

    now = datetime.now(UTC).replace(tzinfo=None)
    dispatched_at = delivery.dispatched_at or delivery.created_at
    elapsed_minutes = (now - dispatched_at).total_seconds() / 60

    # ETA phase logic:
    # Before 5 minutes: show "Blood is on the way!" with no ETA yet
    # After 5 minutes: compute and show remaining ETA
    eta_total = delivery.eta_minutes or _compute_eta_minutes(delivery.distance_km or 0)
    eta_remaining = max(0, eta_total - elapsed_minutes)
    show_eta = elapsed_minutes >= 5

    # Auto-compute phase
    if delivery.status == "DISPATCHED" and eta_remaining <= 0:
        phase = "ARRIVING"
    elif delivery.status == "DELIVERED":
        phase = "DELIVERED"
    elif show_eta:
        phase = "IN_TRANSIT"
    else:
        phase = "DISPATCHED"

    return {
        "id": delivery.id,
        "request_id": delivery.request_id,
        "request_code": request.code if request else None,
        "blood_bank_id": delivery.blood_bank_id,
        "blood_bank_name": blood_bank.name if blood_bank else "Unknown",
        "hospital_id": delivery.hospital_id,
        "hospital_name": hospital.name if hospital else "Unknown",
        "blood_group": request.blood_group if request else None,
        "component_type": request.component_type if request else None,
        "quantity_units": request.quantity_units if request else None,
        "distance_km": round(delivery.distance_km or 0, 1),
        "eta_total_minutes": eta_total,
        "eta_remaining_minutes": round(max(0, eta_remaining), 1),
        "show_eta": show_eta,
        "phase": phase,
        "status": delivery.status,
        "dispatched_at": delivery.dispatched_at.isoformat() if delivery.dispatched_at else None,
        "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None,
        "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
        "elapsed_minutes": round(elapsed_minutes, 1),
        "message": _phase_message(phase, delivery, blood_bank, eta_remaining, show_eta),
    }


def _phase_message(
    phase: str, delivery, blood_bank, eta_remaining: float, show_eta: bool
) -> str:
    bank_name = blood_bank.name if blood_bank else "the blood bank"
    if phase == "DELIVERED":
        return f"Delivery from {bank_name} has arrived! ✅"
    if phase == "ARRIVING":
        return f"Delivery from {bank_name} is arriving now! 🏥"
    if phase == "IN_TRANSIT" and show_eta:
        mins = math.ceil(eta_remaining)
        return f"Blood is in transit from {bank_name}. Estimated arrival in {mins} min 🚑"
    # DISPATCHED phase (first 5 minutes)
    return f"Blood is on the way from {bank_name}! Delivery partner dispatched 🩸"


@router.get("")
def list_deliveries(
    status: str | None = Query(default=None),
    user: User = Depends(hospital_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    """List deliveries visible to the current user.

    Hospital users see only their own deliveries.
    """
    stmt = select(Delivery)

    if user.role == "hospital_user" and user.affiliated_org_id:
        stmt = stmt.where(Delivery.hospital_id == user.affiliated_org_id)

    if status:
        stmt = stmt.where(Delivery.status == status)

    stmt = stmt.order_by(Delivery.created_at.desc())
    rows = db.scalars(stmt).all()
    return envelope([_delivery_out(row, db) for row in rows])


@router.get("/{delivery_id}")
def get_delivery(
    delivery_id: str,
    user: User = Depends(hospital_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(Delivery, delivery_id)
    if row is None:
        raise not_found("Delivery not found.")

    # Access control
    if user.role == "hospital_user" and user.affiliated_org_id != row.hospital_id:
        raise not_found("Delivery not found.")

    return envelope(_delivery_out(row, db))


@router.post("/{delivery_id}/confirm-arrival")
def confirm_arrival(
    delivery_id: str,
    user: User = Depends(hospital_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Hospital confirms the delivery has physically arrived."""
    row = db.get(Delivery, delivery_id)
    if row is None:
        raise not_found("Delivery not found.")
    if user.role == "hospital_user" and user.affiliated_org_id != row.hospital_id:
        raise not_found("Delivery not found.")

    row.status = "DELIVERED"
    row.delivered_at = datetime.now(UTC).replace(tzinfo=None)

    # Also mark the request as FULFILLED
    request = db.get(BloodRequest, row.request_id)
    if request and request.status == "CONFIRMED":
        request.status = "FULFILLED"

    db.commit()
    return envelope(_delivery_out(row, db))
