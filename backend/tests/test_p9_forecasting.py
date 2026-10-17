"""
Tests for ML Inventory Depletion & Demand Forecasting (P9).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.forecasting import BloodDepletionPredictor
from tests.conftest import auth_header


def test_usage_statistics_calculation() -> None:
    predictor = BloodDepletionPredictor()
    now = datetime(2026, 10, 17, 12, 0, 0)

    # 4 requests over 2 days = 10 units total -> 5 units/day, 35 units/week
    sample_requests = [
        {
            "blood_group": "O+",
            "component_type": "RBC",
            "quantity_units": 4,
            "status": "OPEN",
            "request_timestamp": (now - timedelta(days=2)).isoformat(),
        },
        {
            "blood_group": "O+",
            "component_type": "RBC",
            "quantity_units": 2,
            "status": "FULFILLED",
            "request_timestamp": (now - timedelta(days=1)).isoformat(),
        },
        {
            "blood_group": "O+",
            "component_type": "RBC",
            "quantity_units": 4,
            "status": "OPEN",
            "request_timestamp": now.isoformat(),
        },
        # Cancelled requests must be ignored
        {
            "blood_group": "O+",
            "component_type": "RBC",
            "quantity_units": 8,
            "status": "CANCELLED",
            "request_timestamp": now.isoformat(),
        },
    ]

    stats = predictor.calculate_usage_statistics(sample_requests, reference_time=now)
    assert ("O+", "RBC") in stats

    stat = stats[("O+", "RBC")]
    assert stat.total_requests == 3
    assert stat.total_units_consumed == 10
    assert stat.avg_usage_per_day == 5.0
    assert stat.weekly_usage == 35.0
    assert stat.hourly_burn_rate == round(5.0 / 24.0, 4)


def test_depletion_prediction_immediate_empty() -> None:
    predictor = BloodDepletionPredictor()
    now = datetime(2026, 10, 17, 12, 0, 0)

    inventory = [
        {
            "blood_bank_id": "BB_001",
            "blood_group": "AB-",
            "component_type": "RBC",
            "units_available": 2,
            "units_reserved": 2,  # 0 unreserved
            "expiry_date": (now + timedelta(days=10)).date(),
            "is_available": True,
        }
    ]

    preds = predictor.predict_inventory_depletion(inventory, requests=[], reference_time=now)
    assert len(preds) == 1
    p = preds[0]
    assert p.units_unreserved == 0
    assert p.stockout_risk == "IMMEDIATE_EMPTY"
    assert p.hours_until_depletion == 0.0


def test_depletion_prediction_rate_and_risk_tiers() -> None:
    predictor = BloodDepletionPredictor(use_ml_model=False)
    now = datetime(2026, 10, 17, 12, 0, 0)

    # 48 units consumed over 2 days = 24 units/day (1 unit/hour)
    requests = [
        {
            "blood_group": "O+",
            "component_type": "RBC",
            "quantity_units": 48,
            "status": "FULFILLED",
            "request_timestamp": (now - timedelta(days=2)).isoformat(),
        }
    ]

    # Inventory with 12 unreserved units -> at 1 unit/hr, depletes in 12 hours (CRITICAL)
    critical_inv = [
        {
            "blood_bank_id": "BB_001",
            "blood_group": "O+",
            "component_type": "RBC",
            "units_available": 12,
            "units_reserved": 0,
            "expiry_date": (now + timedelta(days=20)).date(),
            "is_available": True,
        }
    ]
    preds = predictor.predict_inventory_depletion(critical_inv, requests, reference_time=now)
    assert len(preds) == 1
    assert preds[0].hours_until_depletion == 12.0
    assert preds[0].stockout_risk == "CRITICAL"

    # Inventory with 240 units -> at 1 unit/hr, depletes in 240 hours / 10 days (STABLE)
    stable_inv = [
        {
            "blood_bank_id": "BB_001",
            "blood_group": "O+",
            "component_type": "RBC",
            "units_available": 240,
            "units_reserved": 0,
            "expiry_date": (now + timedelta(days=30)).date(),
            "is_available": True,
        }
    ]
    preds_stable = predictor.predict_inventory_depletion(stable_inv, requests, reference_time=now)
    assert preds_stable[0].days_until_depletion == 10.0
    assert preds_stable[0].stockout_risk == "STABLE"


def test_depletion_due_to_expiry_attrition() -> None:
    predictor = BloodDepletionPredictor(use_ml_model=False)
    now = datetime(2026, 10, 17, 12, 0, 0)

    # Low demand: 1 unit per day (0.0417 u/hr)
    requests = [
        {
            "blood_group": "B-",
            "component_type": "Whole Blood",
            "quantity_units": 2,
            "status": "FULFILLED",
            "request_timestamp": (now - timedelta(days=2)).isoformat(),
        }
    ]

    # 10 units but expires tomorrow (+24h)
    expiring_inv = [
        {
            "blood_bank_id": "BB_002",
            "blood_group": "B-",
            "component_type": "WHOLE_BLOOD",
            "units_available": 10,
            "units_reserved": 0,
            "expiry_date": (now + timedelta(days=1)).date(),
            "is_available": True,
        }
    ]
    preds = predictor.predict_inventory_depletion(expiring_inv, requests, reference_time=now)
    assert len(preds) == 1
    assert preds[0].depletion_cause == "BATCH_EXPIRATION"
    assert preds[0].stockout_risk in ("CRITICAL", "EXPIRES_BEFORE_USE")


def test_forecasting_api_endpoints(client: TestClient, admin_token: str) -> None:
    headers = auth_header(admin_token)

    # 1. Usage Statistics endpoint
    resp_usage = client.get("/api/v1/forecasting/usage", headers=headers)
    assert resp_usage.status_code == 200
    assert resp_usage.json()["success"] is True
    assert isinstance(resp_usage.json()["data"], list)

    # 2. Depletion Forecast endpoint
    resp_dep = client.get("/api/v1/forecasting/depletion", headers=headers)
    assert resp_dep.status_code == 200
    assert resp_dep.json()["success"] is True
    assert isinstance(resp_dep.json()["data"], list)

    # 3. Executive Dashboard Summary endpoint
    resp_sum = client.get("/api/v1/forecasting/summary", headers=headers)
    assert resp_sum.status_code == 200
    body = resp_sum.json()
    assert body["success"] is True
    assert "total_inventory_items_monitored" in body["data"]
    assert "usage_statistics" in body["data"]
    assert "depletion_predictions" in body["data"]
