import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_eraktkosh_summary():
    response = client.get("/api/v1/eraktkosh/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "blood_groups" in data["data"]
    assert "O+" in data["data"]["blood_groups"]

def test_eraktkosh_bangalore_blood_group():
    response = client.get("/api/v1/eraktkosh/bangalore/O+")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["blood_group"] == "O+"
    assert "data" in data["data"]
    assert len(data["data"]["data"]) > 0

def test_eraktkosh_bangalore_component_filter():
    response = client.get("/api/v1/eraktkosh/bangalore/O+?component=Packed")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    for item in data["data"]["data"]:
        assert "packed" in item["component"].lower()

def test_eraktkosh_unknown_blood_group():
    response = client.get("/api/v1/eraktkosh/bangalore/INVALID_BG")
    assert response.status_code == 404
