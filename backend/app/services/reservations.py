"""Reservation (hold) lifecycle.

Flow (PRD section 8.4): OPEN -> HELD (hold) -> CONFIRMED (confirm -> units
deducted) -> FULFILLED. A hold that is not confirmed within the TTL expires and
its units are released. Inventory rows are locked (`SELECT ... FOR UPDATE`) so
two concurrent confirms cannot oversell the same units.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import RESERVATION_STATUSES
from app.core.config_store import get_int
from app.core.errors import bad_request, conflict, not_found
from app.models import (
    Alert,
    BloodInventory,
    BloodRequest,
    MatchingResult,
    Reservation,
    utcnow,
)


def _add_alert(db: Session, request: BloodRequest, alert_type: str, message: str) -> None:
    db.add(
        Alert(
            request_id=request.id,
            alert_type=alert_type,
            message=message,
            recipient_user_id=request.created_by_user_id,
        )
    )


def _lock_inventory(db: Session, inventory_id: str) -> BloodInventory:
    row = db.execute(
        select(BloodInventory)
        .where(BloodInventory.id == inventory_id)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise not_found("Inventory item not found.")
    return row


def _lock_request(db: Session, request_id: str) -> BloodRequest:
    row = db.execute(
        select(BloodRequest).where(BloodRequest.id == request_id).with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise not_found("Request not found.")
    return row


def _has_active_match(db: Session, request_id: str, inventory_id: str) -> bool:
    return (
        db.scalar(
            select(MatchingResult.id).where(
                MatchingResult.request_id == request_id,
                MatchingResult.inventory_id == inventory_id,
                MatchingResult.is_active.is_(True),
            )
        )
        is not None
    )


def _open_if_no_holds(db: Session, request: BloodRequest) -> None:
    # Sessions are configured with autoflush=False, so flush the status change
    # we just made before asking whether any ACTIVE holds remain.
    db.flush()
    remaining = db.scalar(
        select(Reservation.id).where(
            Reservation.request_id == request.id,
            Reservation.status == "ACTIVE",
        )
    )
    if remaining is None and request.status == "HELD":
        request.status = "OPEN"


def create_hold(
    db: Session, request: BloodRequest, inventory_id: str, quantity: int
) -> Reservation:
    if request.status not in {"OPEN", "HELD"}:
        raise bad_request(f"Cannot hold units for a request in status {request.status}.")
    if not _has_active_match(db, request.id, inventory_id):
        raise conflict(
            "This source is not a current match for the request. Re-run matching first."
        )

    inventory = _lock_inventory(db, inventory_id)
    now = utcnow()
    if not inventory.is_available or inventory.expiry_date < now.date():
        raise conflict("This inventory is no longer available. Re-run matching.")
    if inventory.units_available - inventory.units_reserved < quantity:
        raise conflict(
            "Not enough unreserved units remain at this source. Re-run matching."
        )

    ttl = get_int(db, "lifecycle.hold_ttl_minutes")
    inventory.units_reserved += quantity
    reservation = Reservation(
        request_id=request.id,
        inventory_id=inventory.id,
        quantity=quantity,
        status="ACTIVE",
        expires_at=now + timedelta(minutes=ttl),
    )
    db.add(reservation)
    request.status = "HELD"
    db.flush()
    return reservation


def confirm_reservation(db: Session, reservation: Reservation) -> Reservation:
    if reservation.status != "ACTIVE":
        raise conflict(f"Reservation is already {reservation.status}.")
    if reservation.expires_at <= utcnow():
        # The caller sweeps stale holds before calling us; if one slipped
        # through, refuse without mutating (the sweep persists the EXPIRED state).
        raise conflict("The hold expired before it could be confirmed.")

    inventory = _lock_inventory(db, reservation.inventory_id)
    if inventory.units_available < reservation.quantity:
        raise conflict("Reserved units are no longer available. Re-run matching.")
    inventory.units_available -= reservation.quantity
    inventory.units_reserved = max(0, inventory.units_reserved - reservation.quantity)
    reservation.status = "CONFIRMED"

    request = _lock_request(db, reservation.request_id)
    request.status = "CONFIRMED"
    _add_alert(
        db,
        request,
        "ALLOCATED",
        f"Units allocated for request {request.code} ({reservation.quantity} unit(s)).",
    )
    db.flush()
    return reservation


def fulfil_request(db: Session, request: BloodRequest) -> BloodRequest:
    if request.status != "CONFIRMED":
        raise bad_request(f"Only a CONFIRMED request can be fulfilled (is {request.status}).")
    request.status = "FULFILLED"
    db.flush()
    return request


def release_reservation(db: Session, reservation: Reservation) -> Reservation:
    if reservation.status != "ACTIVE":
        return reservation  # already terminal: release-once
    inventory = _lock_inventory(db, reservation.inventory_id)
    inventory.units_reserved = max(0, inventory.units_reserved - reservation.quantity)
    reservation.status = "RELEASED"
    request = db.get(BloodRequest, reservation.request_id)
    if request is not None:
        _open_if_no_holds(db, request)
    db.flush()
    return reservation


def release_all_for_request(db: Session, request: BloodRequest) -> int:
    rows = db.scalars(
        select(Reservation).where(
            Reservation.request_id == request.id, Reservation.status == "ACTIVE"
        )
    ).all()
    for reservation in rows:
        release_reservation(db, reservation)
    return len(rows)


def expire_stale_reservations(db: Session, now=None) -> int:
    """Mark overdue ACTIVE holds EXPIRED and release their units."""
    moment = now or utcnow()
    rows = db.scalars(
        select(Reservation).where(
            Reservation.status == "ACTIVE", Reservation.expires_at <= moment
        )
    ).all()
    for reservation in rows:
        inventory = _lock_inventory(db, reservation.inventory_id)
        inventory.units_reserved = max(0, inventory.units_reserved - reservation.quantity)
        reservation.status = "EXPIRED"
        request = db.get(BloodRequest, reservation.request_id)
        if request is not None:
            _add_alert(
                db,
                request,
                "MATCH_EXPIRED",
                f"A held match for request {request.code} expired and was released.",
            )
            _open_if_no_holds(db, request)
    if rows:
        db.flush()
    return len(rows)


__all__ = [
    "RESERVATION_STATUSES",
    "confirm_reservation",
    "create_hold",
    "expire_stale_reservations",
    "fulfil_request",
    "release_all_for_request",
    "release_reservation",
]
