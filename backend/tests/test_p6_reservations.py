"""P6: reservation holds, confirm/release/fulfil, TTL expiry, oversell guard."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.conftest import auth_header


def _new_inventory(client: TestClient, token: str, units: int, group: str = "B+") -> str:
    resp = client.post(
        "/api/v1/inventory",
        json={
            "blood_group": group,
            "component_type": "RBC",
            "units_available": units,
            "collection_date": str(date.today() - timedelta(days=2)),
            "expiry_date": str(date.today() + timedelta(days=20)),
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _request_with_match(client: TestClient, token: str, inventory_id: str) -> dict:
    resp = client.post(
        "/api/v1/requests",
        json={"blood_group": "B+", "component_type": "RBC", "quantity_units": 1, "urgency": 4},
        headers=auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert any(m["inventory_id"] == inventory_id for m in data["matches"])
    return data


def test_full_hold_confirm_fulfil(client: TestClient, world: dict) -> None:
    inv_id = _new_inventory(client, world["bank_token"], 5)
    req = _request_with_match(client, world["hospital_token"], inv_id)

    hold = client.post(
        f"/api/v1/requests/{req['id']}/hold",
        json={"inventory_id": inv_id, "quantity": 2},
        headers=auth_header(world["hospital_token"]),
    )
    assert hold.status_code == 200, hold.text
    reservation = hold.json()["data"]
    assert reservation["status"] == "ACTIVE"

    confirmed = client.post(
        f"/api/v1/reservations/{reservation['id']}/confirm",
        headers=auth_header(world["hospital_token"]),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "CONFIRMED"

    inv = client.get(f"/api/v1/inventory/{inv_id}", headers=auth_header(world["bank_token"]))
    assert inv.json()["data"]["units_available"] == 3
    assert inv.json()["data"]["units_reserved"] == 0

    fulfilled = client.post(
        f"/api/v1/requests/{req['id']}/fulfil",
        headers=auth_header(world["hospital_token"]),
    )
    assert fulfilled.status_code == 200
    assert fulfilled.json()["data"]["status"] == "FULFILLED"


def test_oversell_is_rejected(client: TestClient, world: dict) -> None:
    inv_id = _new_inventory(client, world["bank_token"], 3)
    req = _request_with_match(client, world["hospital_token"], inv_id)

    first = client.post(
        f"/api/v1/requests/{req['id']}/hold",
        json={"inventory_id": inv_id, "quantity": 3},
        headers=auth_header(world["hospital_token"]),
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/requests/{req['id']}/hold",
        json={"inventory_id": inv_id, "quantity": 1},
        headers=auth_header(world["hospital_token"]),
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CONFLICT"


def test_double_confirm_rejected(client: TestClient, world: dict) -> None:
    inv_id = _new_inventory(client, world["bank_token"], 3)
    req = _request_with_match(client, world["hospital_token"], inv_id)
    reservation = client.post(
        f"/api/v1/requests/{req['id']}/hold",
        json={"inventory_id": inv_id, "quantity": 1},
        headers=auth_header(world["hospital_token"]),
    ).json()["data"]

    assert (
        client.post(
            f"/api/v1/reservations/{reservation['id']}/confirm",
            headers=auth_header(world["hospital_token"]),
        ).status_code
        == 200
    )
    again = client.post(
        f"/api/v1/reservations/{reservation['id']}/confirm",
        headers=auth_header(world["hospital_token"]),
    )
    assert again.status_code == 409


def test_release_returns_units_and_reopens_request(client: TestClient, world: dict) -> None:
    inv_id = _new_inventory(client, world["bank_token"], 4)
    req = _request_with_match(client, world["hospital_token"], inv_id)
    reservation = client.post(
        f"/api/v1/requests/{req['id']}/hold",
        json={"inventory_id": inv_id, "quantity": 2},
        headers=auth_header(world["hospital_token"]),
    ).json()["data"]

    released = client.post(
        f"/api/v1/reservations/{reservation['id']}/release",
        headers=auth_header(world["hospital_token"]),
    )
    assert released.status_code == 200
    assert released.json()["data"]["status"] == "RELEASED"

    inv = client.get(f"/api/v1/inventory/{inv_id}", headers=auth_header(world["bank_token"]))
    assert inv.json()["data"]["units_reserved"] == 0

    reloaded = client.get(
        f"/api/v1/requests/{req['id']}", headers=auth_header(world["hospital_token"])
    )
    assert reloaded.json()["data"]["status"] == "OPEN"

    # release-once: releasing again is a no-op, not an error
    again = client.post(
        f"/api/v1/reservations/{reservation['id']}/release",
        headers=auth_header(world["hospital_token"]),
    )
    assert again.status_code == 200
    assert again.json()["data"]["status"] == "RELEASED"


def test_expired_hold_cannot_be_confirmed(client: TestClient, world: dict) -> None:
    from app.database import SessionLocal
    from app.models import Reservation

    inv_id = _new_inventory(client, world["bank_token"], 3)
    req = _request_with_match(client, world["hospital_token"], inv_id)
    reservation = client.post(
        f"/api/v1/requests/{req['id']}/hold",
        json={"inventory_id": inv_id, "quantity": 1},
        headers=auth_header(world["hospital_token"]),
    ).json()["data"]

    session = SessionLocal()
    try:
        row = session.get(Reservation, reservation["id"])
        row.expires_at = row.expires_at - timedelta(minutes=30)
        session.commit()
    finally:
        session.close()

    confirm = client.post(
        f"/api/v1/reservations/{reservation['id']}/confirm",
        headers=auth_header(world["hospital_token"]),
    )
    assert confirm.status_code == 409

    check = SessionLocal()
    try:
        row = check.get(Reservation, reservation["id"])
        assert row.status == "EXPIRED"
    finally:
        check.close()


def test_cancel_releases_holds(client: TestClient, world: dict) -> None:
    inv_id = _new_inventory(client, world["bank_token"], 4)
    req = _request_with_match(client, world["hospital_token"], inv_id)
    client.post(
        f"/api/v1/requests/{req['id']}/hold",
        json={"inventory_id": inv_id, "quantity": 2},
        headers=auth_header(world["hospital_token"]),
    )

    cancelled = client.post(
        f"/api/v1/requests/{req['id']}/cancel",
        headers=auth_header(world["hospital_token"]),
    )
    assert cancelled.status_code == 200
    inv = client.get(f"/api/v1/inventory/{inv_id}", headers=auth_header(world["bank_token"]))
    assert inv.json()["data"]["units_reserved"] == 0
