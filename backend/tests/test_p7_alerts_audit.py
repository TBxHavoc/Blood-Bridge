"""P7: alerts, audit logs (masked for auditors), fairness report, PII masking."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.masking import mask_email, mask_phone, mask_pii_text
from tests.conftest import TEST_PASSWORD, auth_header


def _create_user(client: TestClient, admin_token: str, username: str, role: str) -> None:
    resp = client.post(
        "/api/v1/admin/users",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": TEST_PASSWORD,
            "role": role,
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code in (200, 409), resp.text


def _login(client: TestClient, username: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"username": username, "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


# --- masking primitives ----------------------------------------------------


def test_mask_helpers() -> None:
    assert mask_email("jane.doe@example.com") == "j***@example.com"
    assert mask_phone("+91-9876543210") == "***210"
    masked = mask_pii_text("contact jane@x.org or +91-9876543210 on 2026-01-01")
    assert "jane@x.org" not in masked
    assert "+91-9876543210" not in masked
    assert "2026-01-01" in masked  # dates are not mistaken for phone numbers


# --- alerts ----------------------------------------------------------------


def test_alerts_generated_and_markable(client: TestClient, world: dict) -> None:
    created = client.post(
        "/api/v1/requests",
        json={"blood_group": "B+", "component_type": "RBC", "quantity_units": 1, "urgency": 4},
        headers=auth_header(world["hospital_token"]),
    )
    assert created.status_code == 200

    me = client.get("/api/v1/auth/me", headers=auth_header(world["hospital_token"])).json()["data"]
    alerts = client.get(
        "/api/v1/alerts", headers=auth_header(world["hospital_token"])
    ).json()["data"]
    assert alerts, "expected at least one alert"
    assert all(a["recipient_user_id"] == me["id"] for a in alerts)

    target = alerts[0]
    patched = client.patch(
        f"/api/v1/alerts/{target['id']}",
        json={"is_read": True},
        headers=auth_header(world["hospital_token"]),
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["is_read"] is True

    unread = client.get(
        "/api/v1/alerts?is_read=false", headers=auth_header(world["hospital_token"])
    ).json()["data"]
    assert all(a["id"] != target["id"] for a in unread)


def test_allocated_alert_after_confirm(client: TestClient, world: dict) -> None:
    from datetime import date, timedelta

    inv = client.post(
        "/api/v1/inventory",
        json={
            "blood_group": "B+",
            "component_type": "RBC",
            "units_available": 3,
            "collection_date": str(date.today() - timedelta(days=2)),
            "expiry_date": str(date.today() + timedelta(days=20)),
        },
        headers=auth_header(world["bank_token"]),
    ).json()["data"]
    req = client.post(
        "/api/v1/requests",
        json={"blood_group": "B+", "component_type": "RBC", "quantity_units": 1, "urgency": 4},
        headers=auth_header(world["hospital_token"]),
    ).json()["data"]
    reservation = client.post(
        f"/api/v1/requests/{req['id']}/hold",
        json={"inventory_id": inv["id"], "quantity": 1},
        headers=auth_header(world["hospital_token"]),
    ).json()["data"]
    client.post(
        f"/api/v1/reservations/{reservation['id']}/confirm",
        headers=auth_header(world["hospital_token"]),
    )
    alerts = client.get(
        "/api/v1/alerts", headers=auth_header(world["hospital_token"])
    ).json()["data"]
    assert any(a["alert_type"] == "ALLOCATED" for a in alerts)


# --- audit logs ------------------------------------------------------------


def test_audit_requires_privileged_role(client: TestClient, world: dict) -> None:
    assert (
        client.get("/api/v1/audit/logs", headers=auth_header(world["hospital_token"])).status_code
        == 403
    )


def test_auditor_sees_masked_admin_sees_plain(client: TestClient, admin_token: str) -> None:
    from app.database import SessionLocal
    from app.models import AuditLog

    _create_user(client, admin_token, "pytest_auditor", "auditor")
    auditor_token = _login(client, "pytest_auditor")

    session = SessionLocal()
    try:
        session.add(
            AuditLog(
                action_type="TEST_MASK",
                resource_type="probe",
                resource_id="probe-1",
                new_value='{"email": "jane.doe@example.com", "phone": "+91-9876543210"}',
            )
        )
        session.commit()
    finally:
        session.close()

    auditor_view = client.get(
        "/api/v1/audit/logs?action_type=TEST_MASK", headers=auth_header(auditor_token)
    ).json()["data"]
    assert auditor_view
    blob = auditor_view[0]["new_value"]
    assert "jane.doe@example.com" not in blob
    assert "***210" in blob

    admin_view = client.get(
        "/api/v1/audit/logs?action_type=TEST_MASK", headers=auth_header(admin_token)
    ).json()["data"]
    assert "jane.doe@example.com" in admin_view[0]["new_value"]


def test_fairness_report(client: TestClient, admin_token: str, world: dict) -> None:
    resp = client.get("/api/v1/audit/matching-fairness", headers=auth_header(admin_token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "totals" in data
    assert "priority_ordering" in data
    assert "scoring_inputs" in data
    assert "eta_minutes" in data["scoring_inputs"]
