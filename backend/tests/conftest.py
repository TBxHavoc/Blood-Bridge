"""Shared pytest fixtures."""

from __future__ import annotations

import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.core import ratelimit
from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.main import app

# Generated per run so no credential is committed in the source tree.
TEST_PASSWORD = secrets.token_urlsafe(18)

# `app.seed.seed` refuses to run with an empty password; supply one at test time.
if not settings.seed_password:
    settings.seed_password = TEST_PASSWORD


@pytest.fixture(scope="session")
def db_ready() -> bool:
    """Skip DB-dependent tests when no database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Database not available: {exc}")
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return True


@pytest.fixture
def db(db_ready: bool) -> Session:
    """A session whose work is rolled back at the end of each test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    ratelimit.reset()
    yield
    ratelimit.reset()


@pytest.fixture
def client(db_ready: bool) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _ensure_user(username: str, role: str, org_id: str | None = None) -> None:
    from app.models import User

    session = SessionLocal()
    try:
        if session.query(User).filter(User.username == username).first() is None:
            session.add(
                User(
                    username=username,
                    email=f"{username}@pytest.test",
                    password_hash=hash_password(TEST_PASSWORD),
                    role=role,
                    affiliated_org_id=org_id,
                )
            )
            session.commit()
    finally:
        session.close()


@pytest.fixture
def admin_token(client: TestClient) -> str:
    _ensure_user("pytest_admin", "admin")
    resp = client.post(
        "/api/v1/auth/login", json={"username": "pytest_admin", "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


@pytest.fixture
def hospital_token(client: TestClient) -> str:
    _ensure_user("pytest_hospital", "hospital_user")
    resp = client.post(
        "/api/v1/auth/login", json={"username": "pytest_hospital", "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


@pytest.fixture
def auditor_token(client: TestClient) -> str:
    _ensure_user("pytest_auditor", "auditor")
    resp = client.post(
        "/api/v1/auth/login", json={"username": "pytest_auditor", "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def world(db_ready: bool, client: TestClient) -> dict:
    """A committed test world: one bank with B+ RBC stock + linked users."""
    from datetime import date, timedelta

    from app.models import BloodBank, BloodInventory, Hospital, User

    session = SessionLocal()
    try:
        bank = session.query(BloodBank).filter(BloodBank.code == "BB_TEST").first()
        if bank is None:
            bank = BloodBank(
                code="BB_TEST",
                name="Test Blood Bank",
                city="Testville",
                latitude=19.0,
                longitude=72.0,
                capacity_units=100,
            )
            session.add(bank)
            session.flush()
        hospital = session.query(Hospital).filter(Hospital.code == "H_TEST").first()
        if hospital is None:
            hospital = Hospital(
                code="H_TEST",
                name="Test Hospital",
                city="Testville",
                latitude=19.05,
                longitude=72.05,
                emergency_dept_capacity="large",
            )
            session.add(hospital)
            session.flush()
        inventory = session.query(BloodInventory).filter(BloodInventory.code == "INV_TEST").first()
        if inventory is None:
            inventory = BloodInventory(
                code="INV_TEST",
                blood_bank_id=bank.id,
                blood_group="B+",
                component_type="RBC",
                units_available=10,
                units_reserved=0,
                collection_date=date.today() - timedelta(days=5),
                expiry_date=date.today() + timedelta(days=10),
                is_available=True,
            )
            session.add(inventory)
        for username, role, org in (
            ("pytest_hosp", "hospital_user", hospital.id),
            ("pytest_bank", "bloodbank_user", bank.id),
        ):
            if session.query(User).filter(User.username == username).first() is None:
                session.add(
                    User(
                        username=username,
                        email=f"{username}@pytest.test",
                        password_hash=hash_password(TEST_PASSWORD),
                        role=role,
                        affiliated_org_id=org,
                    )
                )
        session.commit()
        ids = {
            "bank_id": bank.id,
            "hospital_id": hospital.id,
            "inventory_id": inventory.id,
        }
    finally:
        session.close()

    def _token(username: str) -> str:
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]["access_token"]

    ids["hospital_token"] = _token("pytest_hosp")
    ids["bank_token"] = _token("pytest_bank")
    return ids
