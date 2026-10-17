"""Adapters: ORM rows -> matching-engine dataclasses and distance lookups.

The engine is storage-agnostic, so every DB read is funnelled through here.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.matching.engine import DistanceLookup, RequestInput, SupplyUnit
from app.models import BloodBank, BloodInventory, BloodRequest, Hospital, LocationDistance


def _coords(db: Session) -> dict[str, tuple[float, float]]:
    coords: dict[str, tuple[float, float]] = {}
    for bank in db.scalars(select(BloodBank)).all():
        coords[bank.code] = (float(bank.latitude), float(bank.longitude))
    for hospital in db.scalars(select(Hospital)).all():
        coords[hospital.code] = (float(hospital.latitude), float(hospital.longitude))
    return coords


def build_lookup(db: Session, speed_kmph: float) -> DistanceLookup:
    distances = {
        (row.origin_id, row.destination_id): (row.distance_km, row.eta_minutes)
        for row in db.scalars(select(LocationDistance)).all()
    }
    return DistanceLookup(distances, _coords(db), speed_kmph)


def to_supply_units(db: Session, rows: list[BloodInventory]) -> list[SupplyUnit]:
    bank_ids = {row.blood_bank_id for row in rows}
    banks: dict[str, BloodBank] = {}
    if bank_ids:
        banks = {
            bank.id: bank
            for bank in db.scalars(
                select(BloodBank).where(BloodBank.id.in_(bank_ids))
            ).all()
        }
    units: list[SupplyUnit] = []
    for row in rows:
        bank = banks.get(row.blood_bank_id)
        units.append(
            SupplyUnit(
                inventory_id=row.id,
                inventory_code=row.code,
                blood_bank_id=row.blood_bank_id,
                blood_bank_code=bank.code if bank else "",
                blood_bank_name=bank.name if bank else "",
                blood_group=row.blood_group,
                component_type=row.component_type,
                units_available=row.units_available,
                units_reserved=row.units_reserved,
                expiry_date=row.expiry_date,
                is_available=row.is_available,
                last_updated=row.last_updated,
            )
        )
    return units


def to_request_input(db: Session, request: BloodRequest) -> RequestInput:
    hospital = db.get(Hospital, request.hospital_id)
    return RequestInput(
        request_id=request.id,
        request_code=request.code,
        hospital_id=request.hospital_id,
        hospital_code=hospital.code if hospital else "",
        blood_group=request.blood_group,
        component_type=request.component_type,
        quantity_units=request.quantity_units,
        urgency=request.urgency,
        request_timestamp=request.request_timestamp,
        required_by_timestamp=request.required_by_timestamp,
    )
