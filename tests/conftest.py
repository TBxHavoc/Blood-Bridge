"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.main import app

TEST_PASSWORD = "Password123!"


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


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
