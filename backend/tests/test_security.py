"""Regression tests for the security audit findings (RBAC, auth, hardening)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD, auth_header

# --- #1 fail closed on a weak signing secret in production -----------------


def test_production_rejects_weak_secret() -> None:
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret_key="dev-only-change-me")
    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret_key="too-short")
    # A strong secret is accepted.
    assert Settings(environment="production", jwt_secret_key="a" * 48).is_production


def _inventory(client: TestClient, token: str, units: int = 5) -> dict:
    resp = client.post(
        "/api/v1/inventory",
        json={
            "blood_group": "B+",
            "component_type": "RBC",
            "units_available": units,
            "collection_date": str(date.today() - timedelta(days=2)),
            "expiry_date": str(date.today() + timedelta(days=20)),
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _request(client: TestClient, token: str) -> dict:
    resp = client.post(
        "/api/v1/requests",
        json={"blood_group": "B+", "component_type": "RBC", "quantity_units": 1, "urgency": 4},
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


# --- #2 broken access control on /requests ---------------------------------


def test_bank_cannot_list_requests(client: TestClient, world: dict) -> None:
    resp = client.get("/api/v1/requests", headers=auth_header(world["bank_token"]))
    assert resp.status_code == 403


def test_bank_cannot_read_or_rematch_request(client: TestClient, world: dict) -> None:
    created = _request(client, world["hospital_token"])
    h = auth_header(world["bank_token"])
    assert client.get(f"/api/v1/requests/{created['id']}", headers=h).status_code == 403
    assert (
        client.post(f"/api/v1/requests/{created['id']}/rematch", headers=h).status_code == 403
    )
    assert (
        client.post(f"/api/v1/requests/{created['id']}/cancel", headers=h).status_code == 403
    )


def test_hospital_cannot_read_other_hospitals_request(client: TestClient, world: dict) -> None:
    from app.core.security import hash_password
    from app.database import SessionLocal
    from app.models import Hospital, User

    session = SessionLocal()
    try:
        hosp = session.query(Hospital).filter(Hospital.code == "H_TEST2").first()
        if hosp is None:
            hosp = Hospital(
                code="H_TEST2",
                name="Other Hospital",
                city="Elsewhere",
                latitude=18.0,
                longitude=72.0,
                emergency_dept_capacity="small",
            )
            session.add(hosp)
            session.flush()
        if session.query(User).filter(User.username == "pytest_hosp2").first() is None:
            session.add(
                User(
                    username="pytest_hosp2",
                    email="hosp2@example.com",
                    password_hash=hash_password(TEST_PASSWORD),
                    role="hospital_user",
                    affiliated_org_id=hosp.id,
                )
            )
        session.commit()
    finally:
        session.close()

    created = _request(client, world["hospital_token"])
    token = client.post(
        "/api/v1/auth/login", json={"username": "pytest_hosp2", "password": TEST_PASSWORD}
    ).json()["data"]["access_token"]
    assert (
        client.get(f"/api/v1/requests/{created['id']}", headers=auth_header(token)).status_code
        == 403
    )


# --- #3 match queue restricted ---------------------------------------------


def test_match_queue_forbidden_for_hospital(client: TestClient, world: dict) -> None:
    resp = client.get("/api/v1/match/queue", headers=auth_header(world["hospital_token"]))
    assert resp.status_code == 403


def test_match_queue_allowed_for_auditor(
    client: TestClient, world: dict, auditor_token: str
) -> None:
    resp = client.get("/api/v1/match/queue", headers=auth_header(auditor_token))
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


# --- #4 inventory scoped to blood banks ------------------------------------


def test_inventory_forbidden_for_hospital(client: TestClient, world: dict) -> None:
    assert (
        client.get("/api/v1/inventory", headers=auth_header(world["hospital_token"])).status_code
        == 403
    )


def test_inventory_scoped_to_own_bank(client: TestClient, world: dict) -> None:
    _inventory(client, world["bank_token"], units=3)
    rows = client.get("/api/v1/inventory", headers=auth_header(world["bank_token"])).json()["data"]
    assert rows
    assert all(row["blood_bank_id"] == world["bank_id"] for row in rows)


# --- #5 auditors are read-only ---------------------------------------------


def test_auditor_cannot_release_reservation(
    client: TestClient, world: dict, auditor_token: str
) -> None:
    inv = _inventory(client, world["bank_token"], units=3)
    req = _request(client, world["hospital_token"])
    hold = client.post(
        f"/api/v1/requests/{req['id']}/hold",
        json={"inventory_id": inv["id"], "quantity": 1},
        headers=auth_header(world["hospital_token"]),
    )
    assert hold.status_code == 200, hold.text
    reservation_id = hold.json()["data"]["id"]
    resp = client.post(
        f"/api/v1/reservations/{reservation_id}/release",
        headers=auth_header(auditor_token),
    )
    assert resp.status_code == 403


# --- #6 X-Forwarded-For cannot bypass rate limiting ------------------------


def test_spoofed_xff_does_not_bypass_login_limit(client: TestClient, world: dict) -> None:
    # Each attempt carries a different spoofed X-Forwarded-For; because the
    # header is not trusted, the limiter must still trip on the real peer IP.
    statuses = [
        client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "wrong"},
            headers={"X-Forwarded-For": f"10.0.{i}.{i}"},
        ).status_code
        for i in range(15)
    ]
    assert statuses[0] == 401
    assert 429 in statuses


def test_long_xff_does_not_crash_login(
    client: TestClient, world: dict, monkeypatch
) -> None:
    from app.api import deps

    monkeypatch.setattr(deps.settings, "trust_forwarded_for", True)
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "wrong"},
        headers={"X-Forwarded-For": "1" * 200},
    )
    assert resp.status_code == 401


# --- #7/#8 validation errors are 400, safe, and do not echo input ----------


def test_validation_error_is_400_and_does_not_echo_input(
    client: TestClient, world: dict
) -> None:
    resp = client.post(
        "/api/v1/requests",
        json={"blood_group": "B+", "component_type": "RBC", "quantity_units": 1, "urgency": 99},
        headers=auth_header(world["hospital_token"]),
    )
    assert resp.status_code == 400
    text = resp.text
    assert '"input"' not in text
    assert '"ctx"' not in text
    details = resp.json()["error"]["details"]
    assert details and {"loc", "msg", "type"} <= set(details[0])


def test_validation_error_does_not_leak_password(client: TestClient, admin_token: str) -> None:
    secret = "abcdefghij"  # long enough, but no digit -> custom validator rejects
    resp = client.post(
        "/api/v1/admin/users",
        json={
            "username": "leakcheck",
            "email": "leakcheck@example.com",
            "password": secret,
            "role": "auditor",
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 400
    assert secret not in resp.text


# --- #9 security headers + health does not leak environment ----------------


def test_security_headers_present(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"


def test_health_does_not_leak_environment(client: TestClient) -> None:
    data = client.get("/api/v1/health").json()["data"]
    assert "environment" not in data
    assert data["status"] == "ok"


# --- #11 password policy + logout revocation -------------------------------


def test_password_policy_requires_letter_and_digit(client: TestClient, admin_token: str) -> None:
    weak = client.post(
        "/api/v1/admin/users",
        json={
            "username": "weakpw",
            "email": "weakpw@example.com",
            "password": "abcdefgh",
            "role": "auditor",
        },
        headers=auth_header(admin_token),
    )
    assert weak.status_code == 400

    strong = client.post(
        "/api/v1/admin/users",
        json={
            "username": "strongpw",
            "email": "strongpw@example.com",
            "password": "abcdefg1",
            "role": "auditor",
        },
        headers=auth_header(admin_token),
    )
    assert strong.status_code in (200, 409), strong.text


def test_logout_revokes_token(client: TestClient, admin_token: str) -> None:
    h = auth_header(admin_token)
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 200
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401
