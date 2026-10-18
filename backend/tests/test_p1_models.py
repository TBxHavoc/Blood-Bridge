"""P1: data model — structure, Db2 portability, and DB-enforced constraints."""

from __future__ import annotations

import pytest
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, text
from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401  (registers tables)
from app.database import Base

EXPECTED_TABLES = {
    "users",
    "blood_banks",
    "hospitals",
    "blood_inventory",
    "blood_requests",
    "matching_results",
    "reservations",
    "alerts",
    "audit_logs",
    "location_distances",
    "system_config",
}


def test_all_tables_registered() -> None:
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables.keys()))


def test_no_db2_hostile_types() -> None:
    """No inline ENUM types (Db2 portability invariant)."""
    for table in Base.metadata.tables.values():
        for column in table.columns:
            assert not isinstance(column.type, SAEnum), (
                f"{table.name}.{column.name} uses an inline ENUM; use CHECK-validated text"
            )


def test_primary_keys_are_char36() -> None:
    for name in EXPECTED_TABLES - {"location_distances", "system_config"}:
        pk = list(Base.metadata.tables[name].primary_key.columns)[0]
        assert isinstance(pk.type, String)
        assert pk.type.length == 36, f"{name} PK should be String(36)"


def test_inventory_blood_group_check(db) -> None:
    db.execute(
        text(
            "INSERT INTO blood_banks (id, code, name, city, latitude, longitude, "
            "is_active, created_at, updated_at) VALUES "
            "('bb-x','BB_X','X','Mumbai',19.0,72.8,true, now(), now())"
        )
    )
    with pytest.raises(IntegrityError):
        db.execute(
            text(
                "INSERT INTO blood_inventory (id, code, blood_bank_id, blood_group, "
                "component_type, units_available, units_reserved, collection_date, "
                "expiry_date, is_available, last_updated) VALUES "
                "('inv-x','INV_X','bb-x','XX','RBC',5,0,current_date,"
                "current_date + 10,true, now())"
            )
        )
        db.flush()
    db.rollback()


def test_inventory_available_ge_reserved_check(db) -> None:
    db.execute(
        text(
            "INSERT INTO blood_banks (id, code, name, city, latitude, longitude, "
            "is_active, created_at, updated_at) VALUES "
            "('bb-y','BB_Y','Y','Pune',18.5,73.8,true, now(), now())"
        )
    )
    with pytest.raises(IntegrityError):
        db.execute(
            text(
                "INSERT INTO blood_inventory (id, code, blood_bank_id, blood_group, "
                "component_type, units_available, units_reserved, collection_date, "
                "expiry_date, is_available, last_updated) VALUES "
                "('inv-y','INV_Y','bb-y','O+','RBC',2,5,current_date,"
                "current_date + 10,true, now())"
            )
        )
        db.flush()
    db.rollback()
