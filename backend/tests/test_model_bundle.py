"""
Unit and Integration Tests for trained depletion_model.pkl artifact and BloodDepletionPredictor.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
import pytest

from app.services.forecasting import BloodDepletionPredictor, DepletionPrediction


def test_predictor_model_discovery():
    predictor = BloodDepletionPredictor()
    # Check that predictor discovers the candidate model path
    assert predictor.model_path is not None
    assert os.path.exists(predictor.model_path)


def test_predictor_depletion_inference_pipeline():
    predictor = BloodDepletionPredictor()
    now = datetime.now(UTC).replace(tzinfo=None)

    inventory = [
        {
            "blood_bank_id": "BB_001",
            "blood_group": "O+",
            "component_type": "RBC",
            "units_available": 10,
            "units_reserved": 2,
            "expiry_date": (now + timedelta(days=20)).date(),
            "is_available": True,
        },
        {
            "blood_bank_id": "BB_002",
            "blood_group": "AB-",
            "component_type": "WHOLE_BLOOD",
            "units_available": 2,
            "units_reserved": 2,
            "expiry_date": (now + timedelta(days=5)).date(),
            "is_available": True,
        },
    ]

    requests = [
        {
            "blood_group": "O+",
            "component_type": "RBC",
            "quantity_units": 10,
            "status": "FULFILLED",
            "request_timestamp": (now - timedelta(days=2)).isoformat(),
        }
    ]

    predictions = predictor.predict_inventory_depletion(inventory, requests, reference_time=now)
    assert len(predictions) == 2

    # Check AB- (0 unreserved)
    ab_neg = next(p for p in predictions if p.blood_group == "AB-")
    assert ab_neg.units_unreserved == 0
    assert ab_neg.stockout_risk == "IMMEDIATE_EMPTY"
    assert ab_neg.hours_until_depletion == 0.0

    # Check O+
    o_pos = next(p for p in predictions if p.blood_group == "O+")
    assert o_pos.units_unreserved == 8
    assert o_pos.hours_until_depletion > 0.0
    assert o_pos.stockout_risk in ("CRITICAL", "HIGH", "MODERATE", "STABLE")
    assert o_pos.model_source is not None
