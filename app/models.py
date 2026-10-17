"""SQLAlchemy ORM models for Blood Bridge.

Design rules (see PROJECT-STATE.md invariants):
- Primary keys are UUIDs stored as 36-char strings; human codes are separate
  unique columns (BB_001, H_001, INV_001, REQ_...).
- No inline ENUM, no SERIAL, no INET — CHECK-validated text instead, so the
  schema is valid on both PostgreSQL and Db2.
- Timestamps are stored naive in UTC (Db2 TIMESTAMP has no zone).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import (
    ALERT_TYPES,
    BLOOD_GROUPS,
    COMPONENT_TYPES,
    REQUEST_STATUSES,
    RESERVATION_STATUSES,
    ROLES,
    SHORTAGE_TYPES,
)
from app.database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Naive UTC now, for storage."""
    return datetime.now(UTC).replace(tzinfo=None)


def _in_clause(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    affiliated_org_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(_in_clause("role", ROLES), name="ck_users_role"),
        Index("ix_users_affiliated_org", "affiliated_org_id"),
    )


class BloodBank(Base):
    __tablename__ = "blood_banks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    capacity_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (Index("ix_blood_banks_city", "city"),)


class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    emergency_dept_capacity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (Index("ix_hospitals_city", "city"),)


class BloodInventory(Base):
    __tablename__ = "blood_inventory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    blood_bank_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("blood_banks.id"), nullable=False
    )
    blood_group: Mapped[str] = mapped_column(String(3), nullable=False)
    component_type: Mapped[str] = mapped_column(String(20), nullable=False)
    units_available: Mapped[int] = mapped_column(Integer, nullable=False)
    units_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    collection_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    storage_location_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Manual "withdrawn/quarantined" flag. Operational availability is computed in
    # the engine as: is_available AND not expired AND (available - reserved) >= qty.
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(_in_clause("blood_group", BLOOD_GROUPS), name="ck_inventory_blood_group"),
        CheckConstraint(
            _in_clause("component_type", COMPONENT_TYPES), name="ck_inventory_component"
        ),
        CheckConstraint("units_available >= 0", name="ck_inventory_available_nonneg"),
        CheckConstraint("units_reserved >= 0", name="ck_inventory_reserved_nonneg"),
        CheckConstraint("units_available >= units_reserved", name="ck_inventory_avail_ge_reserved"),
        CheckConstraint("expiry_date > collection_date", name="ck_inventory_expiry_gt_collection"),
        Index("ix_inventory_blood_group", "blood_group"),
        Index("ix_inventory_expiry", "expiry_date"),
        Index("ix_inventory_blood_bank", "blood_bank_id"),
    )


class BloodRequest(Base):
    __tablename__ = "blood_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hospital_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hospitals.id"), nullable=False
    )
    blood_group: Mapped[str] = mapped_column(String(3), nullable=False)
    component_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity_units: Mapped[int] = mapped_column(Integer, nullable=False)
    urgency: Mapped[int] = mapped_column(Integer, nullable=False)
    required_by_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    shortage_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    request_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(_in_clause("blood_group", BLOOD_GROUPS), name="ck_requests_blood_group"),
        CheckConstraint(
            _in_clause("component_type", COMPONENT_TYPES), name="ck_requests_component"
        ),
        CheckConstraint("quantity_units > 0", name="ck_requests_quantity_positive"),
        CheckConstraint("urgency BETWEEN 1 AND 5", name="ck_requests_urgency_range"),
        CheckConstraint(_in_clause("status", REQUEST_STATUSES), name="ck_requests_status"),
        CheckConstraint(
            "shortage_type IS NULL OR " + _in_clause("shortage_type", SHORTAGE_TYPES),
            name="ck_requests_shortage_type",
        ),
        Index("ix_requests_hospital", "hospital_id"),
        Index("ix_requests_status", "status"),
        Index("ix_requests_blood_group", "blood_group"),
        Index("ix_requests_timestamp", "request_timestamp"),
    )


class MatchingResult(Base):
    __tablename__ = "matching_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("blood_requests.id"), nullable=False
    )
    inventory_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("blood_inventory.id"), nullable=False
    )
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    ranking: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    eta_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(20), nullable=False)
    weights_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    match_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_matching_request", "request_id"),
        Index("ix_matching_inventory", "inventory_id"),
        Index("ix_matching_timestamp", "match_timestamp"),
    )


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("blood_requests.id"), nullable=False
    )
    inventory_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("blood_inventory.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(_in_clause("status", RESERVATION_STATUSES), name="ck_reservations_status"),
        Index("ix_reservations_request", "request_id"),
        Index("ix_reservations_inventory", "inventory_id"),
        Index("ix_reservations_status", "status"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    request_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("blood_requests.id"), nullable=True
    )
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(_in_clause("alert_type", ALERT_TYPES), name="ck_alerts_type"),
        Index("ix_alerts_request", "request_id"),
        Index("ix_alerts_user", "recipient_user_id"),
    )


class AuditLog(Base):
    """Append-only. The application writes rows inside the same transaction as the
    action it records; there is no UPDATE or DELETE path in the code."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_audit_user", "user_id"),
        Index("ix_audit_action", "action_type"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
        Index("ix_audit_timestamp", "created_at"),
    )


class LocationDistance(Base):
    __tablename__ = "location_distances"

    origin_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    destination_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    origin_type: Mapped[str] = mapped_column(String(20), nullable=False)
    destination_type: Mapped[str] = mapped_column(String(20), nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    eta_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (Index("ix_distances_origin", "origin_id"),)


class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
    updated_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
