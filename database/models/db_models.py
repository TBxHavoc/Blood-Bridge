"""
Blood Bridge - SQLAlchemy 2.0 ORM Database Models
IBM Z Datathon 2026 - AI Secured Track (Innovation without Exposure)

Designed for dual runtime compatibility:
- Local PostgreSQL (Docker/Native)
- Production IBM LinuxONE / IBM Db2 LUW (ibm_db_sa dialect)

Complies with PRD v1.0, SRS v1.0, and strict zero-patient/zero-donor privacy.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    Text,
    Date,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    create_engine
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    sessionmaker,
    Session
)

Base = declarative_base()


def generate_uuid() -> str:
    """Generate 36-character UUID string for DB portability (PostgreSQL + Db2)."""
    return str(uuid.uuid4())


class SystemConfig(Base):
    __tablename__ = "system_config"

    config_key = Column(String(50), primary_key=True)
    config_value = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    data_type = Column(String(20), default="string", nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("data_type IN ('string', 'integer', 'float', 'boolean', 'json')", name="chk_cfg_dtype"),
    )


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    hospital_code = Column(String(20), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    address = Column(Text, nullable=False)
    latitude = Column(Numeric(9, 6), nullable=False)
    longitude = Column(Numeric(9, 6), nullable=False)
    delivery_point = Column(String(255), nullable=False)  # Staged disclosure (NFR-P7)
    contact_phone = Column(String(30), nullable=False)
    contact_email = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    requests = relationship("BloodRequest", back_populates="hospital")
    distances = relationship("LocationDistance", back_populates="hospital")


class BloodBank(Base):
    __tablename__ = "blood_banks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    bank_code = Column(String(20), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    address = Column(Text, nullable=False)
    latitude = Column(Numeric(9, 6), nullable=False)
    longitude = Column(Numeric(9, 6), nullable=False)
    contact_phone = Column(String(30), nullable=False)
    contact_email = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    inventory = relationship("BloodInventory", back_populates="blood_bank", cascade="all, delete-orphan")
    distances = relationship("LocationDistance", back_populates="blood_bank")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    affiliated_org_type = Column(String(20), default="none", nullable=False)
    affiliated_org_id = Column(String(36), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('hospital_user', 'bloodbank_user', 'admin', 'auditor')", name="chk_user_role"),
        CheckConstraint("affiliated_org_type IN ('hospital', 'blood_bank', 'none')", name="chk_user_org_type"),
    )


class BloodInventory(Base):
    """
    Blood Inventory metadata contributed by blood banks.
    ZERO DONOR IDENTIFIERS ARE ALLOWED (FR-21, NFR-P1).
    """
    __tablename__ = "blood_inventory"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    inventory_code = Column(String(30), unique=True, nullable=False)
    blood_bank_id = Column(String(36), ForeignKey("blood_banks.id", ondelete="CASCADE"), nullable=False)
    blood_group = Column(String(5), nullable=False)
    component_type = Column(String(20), nullable=False)
    units_available = Column(Integer, nullable=False)
    units_reserved = Column(Integer, default=0, nullable=False)
    collection_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    last_updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    blood_bank = relationship("BloodBank", back_populates="inventory")
    reservations = relationship("Reservation", back_populates="inventory")
    matching_results = relationship("MatchingResult", back_populates="inventory")

    __table_args__ = (
        CheckConstraint("blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')", name="chk_inv_blood_group"),
        CheckConstraint("component_type IN ('Whole Blood', 'RBC')", name="chk_inv_component"),
        CheckConstraint("units_available >= 0", name="chk_inv_units_avail_pos"),
        CheckConstraint("units_reserved >= 0", name="chk_inv_units_res_pos"),
        CheckConstraint("units_reserved <= units_available", name="chk_units_reserved_le_available"),
        CheckConstraint("expiry_date > collection_date", name="chk_expiry_gt_collection"),
    )

    @property
    def units_unreserved(self) -> int:
        return max(0, (self.units_available or 0) - (self.units_reserved or 0))


class BloodRequest(Base):
    """
    Hospital Emergency Blood Request.
    ZERO PATIENT IDENTIFIERS (FR-08, NFR-P1).
    Pseudonymous request code (REQ_ + random alphanumeric suffix, NFR-P2).
    """
    __tablename__ = "blood_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    request_code = Column(String(30), unique=True, nullable=False)
    hospital_id = Column(String(36), ForeignKey("hospitals.id", ondelete="RESTRICT"), nullable=False)
    blood_group = Column(String(5), nullable=False)
    component_type = Column(String(20), nullable=False)
    quantity = Column(Integer, nullable=False)
    clinician_urgency = Column(Integer, nullable=False)
    status = Column(String(20), default="OPEN", nullable=False)  # OPEN, HELD, CONFIRMED, CANCELLED, EXPIRED, FULFILLED
    priority_score = Column(Numeric(5, 2), nullable=True)
    required_by = Column(DateTime(timezone=True), nullable=False)
    request_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    hospital = relationship("Hospital", back_populates="requests")
    reservations = relationship("Reservation", back_populates="request", cascade="all, delete-orphan")
    matching_results = relationship("MatchingResult", back_populates="request", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="request")

    __table_args__ = (
        CheckConstraint("blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')", name="chk_req_blood_group"),
        CheckConstraint("component_type IN ('Whole Blood', 'RBC')", name="chk_req_component"),
        CheckConstraint("quantity > 0", name="chk_req_qty_positive"),
        CheckConstraint("clinician_urgency BETWEEN 1 AND 5", name="chk_req_urgency_range"),
        CheckConstraint("status IN ('OPEN', 'HELD', 'CONFIRMED', 'CANCELLED', 'EXPIRED', 'FULFILLED')", name="chk_req_status_enum"),
    )


class Reservation(Base):
    """
    Transactional hold to prevent double allocation (PRD 8.4, 8.5).
    """
    __tablename__ = "reservations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    reservation_code = Column(String(30), unique=True, nullable=False)
    request_id = Column(String(36), ForeignKey("blood_requests.id", ondelete="CASCADE"), nullable=False)
    inventory_id = Column(String(36), ForeignKey("blood_inventory.id", ondelete="RESTRICT"), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(20), default="ACTIVE", nullable=False)  # ACTIVE, CONFIRMED, RELEASED, EXPIRED
    placed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    released_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    request = relationship("BloodRequest", back_populates="reservations")
    inventory = relationship("BloodInventory", back_populates="reservations")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_res_qty_positive"),
        CheckConstraint("status IN ('ACTIVE', 'CONFIRMED', 'RELEASED', 'EXPIRED')", name="chk_res_status_enum"),
    )


class MatchingResult(Base):
    """
    Explainable matching rank and score breakdown (PRD Section 7).
    """
    __tablename__ = "matching_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    request_id = Column(String(36), ForeignKey("blood_requests.id", ondelete="CASCADE"), nullable=False)
    inventory_id = Column(String(36), ForeignKey("blood_inventory.id", ondelete="RESTRICT"), nullable=False)
    rank = Column(Integer, nullable=False)
    match_score = Column(Numeric(5, 2), nullable=False)
    eta_minutes = Column(Integer, nullable=False)
    distance_km = Column(Numeric(6, 2), nullable=False)
    score_breakdown = Column(Text, nullable=False)  # JSON string
    explanation = Column(Text, nullable=False)      # Human-readable breakdown
    algorithm_version = Column(String(20), default="v1.0", nullable=False)
    weights_used = Column(Text, nullable=False)     # JSON string of weights snapshot
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    request = relationship("BloodRequest", back_populates="matching_results")
    inventory = relationship("BloodInventory", back_populates="matching_results")

    __table_args__ = (
        CheckConstraint("rank >= 1", name="chk_mr_rank_positive"),
        CheckConstraint("match_score BETWEEN 0.00 AND 100.00", name="chk_mr_score_range"),
        CheckConstraint("eta_minutes >= 0", name="chk_mr_eta_positive"),
        CheckConstraint("distance_km >= 0", name="chk_mr_distance_positive"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    recipient_role = Column(String(20), nullable=False)
    recipient_org_id = Column(String(36), nullable=True)
    recipient_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    alert_type = Column(String(30), nullable=False)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    request_id = Column(String(36), ForeignKey("blood_requests.id", ondelete="SET NULL"), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    request = relationship("BloodRequest", back_populates="alerts")

    __table_args__ = (
        CheckConstraint("recipient_role IN ('hospital_user', 'bloodbank_user', 'admin', 'auditor')", name="chk_alt_role"),
        CheckConstraint("alert_type IN ('MATCH_FOUND', 'SHORTAGE_DETECTED', 'MATCH_EXPIRED', 'ALLOCATED')", name="chk_alt_type"),
    )


class LocationDistance(Base):
    __tablename__ = "location_distances"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    hospital_id = Column(String(36), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    blood_bank_id = Column(String(36), ForeignKey("blood_banks.id", ondelete="CASCADE"), nullable=False)
    distance_km = Column(Numeric(6, 2), nullable=False)
    estimated_transit_minutes = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    hospital = relationship("Hospital", back_populates="distances")
    blood_bank = relationship("BloodBank", back_populates="distances")

    __table_args__ = (
        UniqueConstraint("hospital_id", "blood_bank_id", name="uq_hospital_blood_bank"),
        CheckConstraint("distance_km >= 0", name="chk_dist_km_pos"),
        CheckConstraint("estimated_transit_minutes >= 0", name="chk_dist_eta_pos"),
    )


class AuditLog(Base):
    """
    Immutable audit log with cryptographic hash chaining (PRD 6.6, 9).
    """
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    sequence_number = Column(Integer, primary_key=False, autoincrement=True, unique=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(50), nullable=True)
    user_role = Column(String(20), nullable=True)
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(36), nullable=True)
    old_values = Column(Text, nullable=True)
    new_values = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=False)  # Universal text representation
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    prev_hash = Column(String(64), nullable=True)
    current_hash = Column(String(64), nullable=True)


# Database Engine and Session Factory Helper
def get_db_engine(database_url: str):
    """
    Creates an engine compatible with either PostgreSQL or Db2 on LinuxONE.
    - PostgreSQL: postgresql+psycopg2://user:pass@localhost:5432/bloodbridge
    - IBM Db2: ibm_db_sa://db2inst1:pass@linuxone-host:50000/BLDPRD
    """
    return create_engine(database_url, echo=False, pool_pre_ping=True)


def init_db(database_url: str):
    """Initialize schema tables using SQLAlchemy create_all."""
    engine = get_db_engine(database_url)
    Base.metadata.create_all(bind=engine)
    return engine


def get_db(database_url: str):
    """FastAPI Dependency for database session."""
    engine = get_db_engine(database_url)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
