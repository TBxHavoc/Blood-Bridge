"""Inventory endpoints. Blood-bank users manage their own bank; admin manages all."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user, require_roles
from app.core.audit import write_audit
from app.core.envelope import envelope
from app.core.errors import bad_request, forbidden, not_found
from app.database import get_db
from app.models import BloodBank, BloodInventory, User
from app.schemas.inventory import InventoryCreate, InventoryOut, InventoryUpdate
from app.services.codes import next_code

router = APIRouter(prefix="/inventory", tags=["inventory"])

manager_only = require_roles("bloodbank_user", "admin")


@router.get("")
def list_inventory(
    blood_group: str | None = None,
    component_type: str | None = None,
    blood_bank_id: str | None = None,
    only_available: bool = True,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(BloodInventory)
    if blood_group:
        stmt = stmt.where(BloodInventory.blood_group == blood_group)
    if component_type:
        stmt = stmt.where(BloodInventory.component_type == component_type)
    if blood_bank_id:
        stmt = stmt.where(BloodInventory.blood_bank_id == blood_bank_id)
    if only_available:
        stmt = stmt.where(BloodInventory.is_available.is_(True))
    rows = db.scalars(stmt.order_by(BloodInventory.expiry_date.asc())).all()
    return envelope([InventoryOut.model_validate(row).model_dump() for row in rows])


@router.get("/{inventory_id}")
def get_inventory(
    inventory_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(BloodInventory, inventory_id)
    if row is None:
        raise not_found("Inventory item not found.")
    return envelope(InventoryOut.model_validate(row).model_dump())


def _resolve_bank_id(user: User, payload_bank_id: str | None, db: Session) -> str:
    if user.role == "bloodbank_user":
        if not user.affiliated_org_id:
            raise forbidden("Your account is not linked to a blood bank.")
        return user.affiliated_org_id
    if not payload_bank_id:
        raise bad_request("blood_bank_id is required for admins.")
    if db.get(BloodBank, payload_bank_id) is None:
        raise bad_request("Unknown blood_bank_id.")
    return payload_bank_id


def _assert_can_edit(user: User, row: BloodInventory) -> None:
    if user.role == "admin":
        return
    if user.affiliated_org_id != row.blood_bank_id:
        raise forbidden("You can only manage inventory for your own blood bank.")


@router.post("")
def create_inventory(
    payload: InventoryCreate,
    request: Request,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
) -> dict:
    bank_id = _resolve_bank_id(user, payload.blood_bank_id, db)
    row = BloodInventory(
        code=next_code(db, BloodInventory, "INV_", 3),
        blood_bank_id=bank_id,
        blood_group=payload.blood_group,
        component_type=payload.component_type,
        units_available=payload.units_available,
        units_reserved=0,
        collection_date=payload.collection_date,
        expiry_date=payload.expiry_date,
        storage_location_code=payload.storage_location_code,
        is_available=True,
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        action_type="CREATE_INVENTORY",
        user_id=user.id,
        resource_type="blood_inventory",
        resource_id=row.id,
        new_value={"code": row.code, "units_available": row.units_available},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return envelope(InventoryOut.model_validate(row).model_dump())


@router.patch("/{inventory_id}")
def update_inventory(
    inventory_id: str,
    payload: InventoryUpdate,
    request: Request,
    user: User = Depends(manager_only),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(BloodInventory, inventory_id)
    if row is None:
        raise not_found("Inventory item not found.")
    _assert_can_edit(user, row)

    old_value = {
        "units_available": row.units_available,
        "is_available": row.is_available,
        "storage_location_code": row.storage_location_code,
        "expiry_date": str(row.expiry_date),
    }
    if payload.units_available is not None:
        if payload.units_available < row.units_reserved:
            raise bad_request("units_available cannot be below units_reserved.")
        row.units_available = payload.units_available
    if payload.is_available is not None:
        row.is_available = payload.is_available
    if payload.storage_location_code is not None:
        row.storage_location_code = payload.storage_location_code
    if payload.expiry_date is not None:
        if payload.expiry_date <= row.collection_date:
            raise bad_request("expiry_date must be after collection_date.")
        row.expiry_date = payload.expiry_date

    write_audit(
        db,
        action_type="UPDATE_INVENTORY",
        user_id=user.id,
        resource_type="blood_inventory",
        resource_id=row.id,
        old_value=old_value,
        new_value=payload.model_dump(exclude_none=True),
        ip_address=get_client_ip(request),
    )
    db.commit()
    return envelope(InventoryOut.model_validate(row).model_dump())
