"""Reservation (hold/confirm/release/fulfil) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user, require_roles
from app.core.audit import write_audit
from app.core.envelope import envelope
from app.core.errors import forbidden, not_found
from app.database import get_db
from app.models import BloodInventory, BloodRequest, Reservation, User
from app.schemas.reservation import HoldCreate, ReservationOut
from app.services import reservations as svc

router = APIRouter(tags=["reservations"])

hospital_or_admin = require_roles("hospital_user", "admin")


def _own_request(db: Session, user: User, request_id: str) -> BloodRequest:
    row = db.get(BloodRequest, request_id)
    if row is None:
        raise not_found("Request not found.")
    if user.role == "hospital_user" and user.affiliated_org_id != row.hospital_id:
        raise forbidden("You do not have access to this request.")
    return row


@router.post("/requests/{request_id}/hold")
def create_hold(
    request_id: str,
    payload: HoldCreate,
    request: Request,
    user: User = Depends(hospital_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    svc.expire_stale_reservations(db)
    db.commit()
    req_row = _own_request(db, user, request_id)
    reservation = svc.create_hold(db, req_row, payload.inventory_id, payload.quantity)
    write_audit(
        db,
        action_type="HOLD_UNITS",
        user_id=user.id,
        resource_type="reservation",
        resource_id=reservation.id,
        new_value={
            "request_id": req_row.id,
            "inventory_id": reservation.inventory_id,
            "quantity": reservation.quantity,
        },
        ip_address=get_client_ip(request),
    )
    db.commit()
    return envelope(ReservationOut.model_validate(reservation).model_dump())


def _load_reservation(db: Session, user: User, reservation_id: str) -> Reservation:
    row = db.get(Reservation, reservation_id)
    if row is None:
        raise not_found("Reservation not found.")
    req_row = db.get(BloodRequest, row.request_id)
    if req_row is None:
        raise not_found("Reservation's request is missing.")
    if user.role == "hospital_user" and user.affiliated_org_id != req_row.hospital_id:
        raise forbidden("You do not have access to this reservation.")
    if user.role == "bloodbank_user":
        inventory = db.get(BloodInventory, row.inventory_id)
        if inventory is None or inventory.blood_bank_id != user.affiliated_org_id:
            raise forbidden("This reservation is not for your blood bank.")
    return row


@router.post("/reservations/{reservation_id}/confirm")
def confirm_reservation(
    reservation_id: str,
    request: Request,
    user: User = Depends(hospital_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    svc.expire_stale_reservations(db)
    db.commit()
    reservation = _load_reservation(db, user, reservation_id)
    svc.confirm_reservation(db, reservation)
    write_audit(
        db,
        action_type="CONFIRM_RESERVATION",
        user_id=user.id,
        resource_type="reservation",
        resource_id=reservation.id,
        new_value={"quantity": reservation.quantity},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return envelope(ReservationOut.model_validate(reservation).model_dump())


@router.post("/reservations/{reservation_id}/release")
def release_reservation(
    reservation_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    reservation = _load_reservation(db, user, reservation_id)
    old_status = reservation.status
    svc.release_reservation(db, reservation)
    write_audit(
        db,
        action_type="RELEASE_RESERVATION",
        user_id=user.id,
        resource_type="reservation",
        resource_id=reservation.id,
        old_value={"status": old_status},
        new_value={"status": reservation.status},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return envelope(ReservationOut.model_validate(reservation).model_dump())


@router.post("/requests/{request_id}/fulfil")
def fulfil_request(
    request_id: str,
    request: Request,
    user: User = Depends(hospital_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    req_row = _own_request(db, user, request_id)
    svc.fulfil_request(db, req_row)
    write_audit(
        db,
        action_type="FULFIL_REQUEST",
        user_id=user.id,
        resource_type="blood_request",
        resource_id=req_row.id,
        new_value={"status": "FULFILLED"},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return envelope({"id": req_row.id, "code": req_row.code, "status": req_row.status})


@router.get("/reservations")
def list_reservations(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    svc.expire_stale_reservations(db)
    db.commit()
    stmt = select(Reservation)
    if user.role == "hospital_user":
        request_ids = db.scalars(
            select(BloodRequest.id).where(BloodRequest.hospital_id == user.affiliated_org_id)
        ).all()
        stmt = stmt.where(Reservation.request_id.in_(request_ids or ["-"]))
    elif user.role == "bloodbank_user":
        inventory_ids = db.scalars(
            select(BloodInventory.id).where(
                BloodInventory.blood_bank_id == user.affiliated_org_id
            )
        ).all()
        stmt = stmt.where(Reservation.inventory_id.in_(inventory_ids or ["-"]))
    rows = db.scalars(stmt.order_by(Reservation.created_at.desc())).all()
    return envelope([ReservationOut.model_validate(row).model_dump() for row in rows])
