"""P4: inventory and request endpoints, matching integration, match queue."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.conftest import auth_header


def _new_request(client: TestClient, token: str, **overrides) -> dict:
    payload = {
        "blood_group": "B+",
        "component_type": "RBC",
        "quantity_units": 2,
        "urgency": 3,
    }
    payload.update(overrides)
    resp = client.post(
        "/api/v1/requests", json=payload, headers=auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_create_request_finds_match(client: TestClient, world: dict) -> None:
    data = _new_request(client, world["hospital_token"], blood_group="B+")
    assert data["status"] == "OPEN"
    assert data["code"].startswith("REQ_")
    assert data["shortage_type"] is None
    assert len(data["matches"]) >= 1
    top = data["matches"][0]
    assert top["ranking"] == 1
    assert top["match_score"] > 0
    assert "/100" in top["explanation"]
    # B+ recipient can only receive B+, B-, O+ or O- red cells.
    assert top["blood_group"] in {"B+", "B-", "O+", "O-"}


def test_create_request_complete_shortage(client: TestClient, world: dict) -> None:
    # No single stock row holds 100 units, so nothing is eligible -> COMPLETE.
    data = _new_request(client, world["hospital_token"], blood_group="O-", quantity_units=100)
    assert data["shortage_type"] == "COMPLETE"
    assert data["matches"] == []


def test_request_persisted_and_readable(client: TestClient, world: dict) -> None:
    created = _new_request(client, world["hospital_token"])
    resp = client.get(
        f"/api/v1/requests/{created['id']}", headers=auth_header(world["hospital_token"])
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]["matches"]) == len(created["matches"])


def test_bloodbank_cannot_create_request(client: TestClient, world: dict) -> None:
    resp = client.post(
        "/api/v1/requests",
        json={"blood_group": "B+", "component_type": "RBC", "quantity_units": 1, "urgency": 1},
        headers=auth_header(world["bank_token"]),
    )
    assert resp.status_code == 403


def test_request_validation_rejects_bad_urgency(client: TestClient, world: dict) -> None:
    resp = client.post(
        "/api/v1/requests",
        json={"blood_group": "B+", "component_type": "RBC", "quantity_units": 1, "urgency": 9},
        headers=auth_header(world["hospital_token"]),
    )
    assert resp.status_code == 400


def test_cancel_request(client: TestClient, world: dict) -> None:
    created = _new_request(client, world["hospital_token"])
    resp = client.post(
        f"/api/v1/requests/{created['id']}/cancel",
        headers=auth_header(world["hospital_token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "CANCELLED"


def test_inventory_list_requires_auth(client: TestClient, world: dict) -> None:
    assert client.get("/api/v1/inventory").status_code == 401


def test_inventory_list_authenticated(client: TestClient, world: dict) -> None:
    resp = client.get("/api/v1/inventory", headers=auth_header(world["hospital_token"]))
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


def test_bloodbank_creates_inventory_for_own_bank(client: TestClient, world: dict) -> None:
    resp = client.post(
        "/api/v1/inventory",
        json={
            "blood_group": "O-",
            "component_type": "RBC",
            "units_available": 4,
            "collection_date": str(date.today() - timedelta(days=2)),
            "expiry_date": str(date.today() + timedelta(days=20)),
        },
        headers=auth_header(world["bank_token"]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["code"].startswith("INV_")
    assert body["blood_bank_id"] == world["bank_id"]


def test_hospital_cannot_create_inventory(client: TestClient, world: dict) -> None:
    resp = client.post(
        "/api/v1/inventory",
        json={
            "blood_group": "O-",
            "component_type": "RBC",
            "units_available": 1,
            "collection_date": str(date.today() - timedelta(days=2)),
            "expiry_date": str(date.today() + timedelta(days=20)),
        },
        headers=auth_header(world["hospital_token"]),
    )
    assert resp.status_code == 403


def test_match_queue_is_priority_ordered(client: TestClient, world: dict) -> None:
    _new_request(client, world["hospital_token"], urgency=1)
    _new_request(client, world["hospital_token"], urgency=5)
    resp = client.get("/api/v1/match/queue", headers=auth_header(world["hospital_token"]))
    assert resp.status_code == 200
    urgencies = [row["urgency"] for row in resp.json()["data"]]
    assert urgencies == sorted(urgencies, reverse=True)
