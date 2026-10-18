#!/usr/bin/env python3
"""
Blood Bridge - ML Model Integration & Depletion Forecasting Verification Test
IBM Z Datathon 2026 - AI Secured Track (Innovation without Exposure)

Target Model File:
    backend/models/depletion_model.pkl

Usage (from the repository root):
    python backend/scripts/test_trained_model.py
    python backend/scripts/test_trained_model.py --model "backend/models/depletion_model.pkl"
"""

import os
import sys
import math
import pickle
import argparse
from datetime import datetime, date, timedelta, timezone

# Make the backend app package importable so the service layer can be tested.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def find_model_path(explicit_path=None):
    if explicit_path and os.path.exists(explicit_path):
        return explicit_path
    candidates = [
        os.path.join(BASE_DIR, "models", "depletion_model.pkl"),
        os.path.join(BASE_DIR, "..", "models", "depletion_model.pkl"),
        "backend/models/depletion_model.pkl",
        "models/depletion_model.pkl",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


def inspect_model_bundle(model_path):
    print("=" * 88)
    print(f"[*] 1. VERIFYING MODEL ARTIFACT AT: {model_path}")
    print("=" * 88)

    if not os.path.exists(model_path):
        print(f"[!] ERROR: Model file not found at {model_path}")
        return None

    size_bytes = os.path.getsize(model_path)
    print(f"[+] File Size:        {size_bytes:,} bytes ({size_bytes / 1024:.2f} KB)")
    print(f"[+] Last Modified:    {datetime.fromtimestamp(os.path.getmtime(model_path)).strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        with open(model_path, "rb") as f:
            bundle = pickle.load(f)
        print("[+] Unpickle Status:  SUCCESSFULLY LOADED")
    except Exception as e:
        print(f"[!] Warning: Could not unpickle directly in current Python runtime ({e}).")
        print("[i] Note: LightGBM / Scikit-learn might need to be installed in this environment.")
        return None

    print(f"[+] Bundle Keys:      {list(bundle.keys())}")
    print(f"[+] Regressor:        {type(bundle.get('regressor')).__name__}")
    print(f"[+] Classifier:       {type(bundle.get('classifier')).__name__}")
    print(f"[+] Feature Columns:  {bundle.get('feature_cols')}")
    print(f"[+] Timestamp:        {bundle.get('timestamp')}")
    print(f"[+] Model Type:       {bundle.get('model_type')}")

    encoders = bundle.get("encoders", {})
    if "bg" in encoders and hasattr(encoders["bg"], "classes_"):
        print(f"[+] Encoders (Blood): {list(encoders['bg'].classes_)}")
    if "ct" in encoders and hasattr(encoders["ct"], "classes_"):
        print(f"[+] Encoders (Comp):  {list(encoders['ct'].classes_)}")
    if "city" in encoders and hasattr(encoders["city"], "classes_"):
        print(f"[+] Encoders (City):  {list(encoders['city'].classes_)}")

    usage = bundle.get("usage_summary", [])
    if usage:
        print(f"[+] Historical Usage Profiles: {len(usage)} combinations precomputed.")

    return bundle


def run_unit_inference_tests(bundle):
    print("\n" + "=" * 88)
    print("[*] 2. RUNNING MULTI-SCENARIO ML INFERENCE UNIT TESTS")
    print("=" * 88)

    if bundle is None:
        print("[i] Skipping direct bundle inference (bundle not loaded into memory).")
        return

    import pandas as pd

    reg = bundle["regressor"]
    clf = bundle["classifier"]
    encoders = bundle["encoders"]
    feat_cols = bundle["feature_cols"]

    test_scenarios = [
        {
            "name": "Scenario 1: Critical Emergency Shortage (Near Depletion)",
            "bank_code": "BB_001",
            "city": "Mumbai",
            "blood_group": "O+",
            "component_type": "RBC",
            "unreserved": 2,
            "available": 3,
            "reserved": 1,
            "days_to_expiry": 14.0,
            "daily_burn": 1.25,
            "capacity": 800,
            "urgency": 4.5,
        },
        {
            "name": "Scenario 2: High Risk Stockout (< 3 Days Supply)",
            "bank_code": "BB_003",
            "city": "Delhi",
            "blood_group": "A-",
            "component_type": "WHOLE_BLOOD",
            "unreserved": 4,
            "available": 4,
            "reserved": 0,
            "days_to_expiry": 20.0,
            "daily_burn": 0.95,
            "capacity": 600,
            "urgency": 3.0,
        },
        {
            "name": "Scenario 3: Biological Expiry Pre-emption (Short Shelf Life)",
            "bank_code": "BB_005",
            "city": "Bengaluru",
            "blood_group": "B+",
            "component_type": "RBC",
            "unreserved": 15,
            "available": 15,
            "reserved": 0,
            "days_to_expiry": 1.5,  # 36 hours left before expiry
            "daily_burn": 0.40,
            "capacity": 500,
            "urgency": 2.0,
        },
        {
            "name": "Scenario 4: Stable Inventory Buffer (> 7 Days Stock)",
            "bank_code": "BB_007",
            "city": "Pune",
            "blood_group": "O+",
            "component_type": "WHOLE_BLOOD",
            "unreserved": 45,
            "available": 50,
            "reserved": 5,
            "days_to_expiry": 32.0,
            "daily_burn": 0.85,
            "capacity": 1000,
            "urgency": 2.5,
        },
        {
            "name": "Scenario 5: Immediate Stockout (Zero Unreserved Units)",
            "bank_code": "BB_002",
            "city": "Chennai",
            "blood_group": "AB-",
            "component_type": "RBC",
            "unreserved": 0,
            "available": 2,
            "reserved": 2,
            "days_to_expiry": 25.0,
            "daily_burn": 0.30,
            "capacity": 400,
            "urgency": 5.0,
        },
    ]

    tier_names = {
        0: "IMMEDIATE_EMPTY",
        1: "CRITICAL (<24h)",
        2: "HIGH (1-3 days)",
        3: "MODERATE (3-7 days)",
        4: "STABLE (>7 days)",
    }

    for sc in test_scenarios:
        print(f"\n[-] {sc['name']}:")
        print(f"    Target:       {sc['bank_code']} ({sc['city']}) | {sc['blood_group']} {sc['component_type']}")
        print(f"    Inventory:    {sc['unreserved']} units unreserved (Total: {sc['available']}, Reserved: {sc['reserved']})")
        print(f"    Expiry:       {sc['days_to_expiry']} days until batch expiration")
        print(f"    Daily Burn:   {sc['daily_burn']} units/day | Clinical Urgency: {sc['urgency']}/5")

        if sc["unreserved"] <= 0:
            pred_hours = 0.0
            pred_tier_str = "IMMEDIATE_EMPTY (Direct Stockout Rule)"
        else:
            def encode_val(enc, val, default=0):
                try:
                    return enc.transform([val])[0]
                except Exception:
                    return default

            bg_idx = encode_val(encoders["bg"], sc["blood_group"])
            ct_idx = encode_val(encoders["ct"], sc["component_type"])
            city_idx = encode_val(encoders["city"], sc["city"])

            row_data = {
                "feat_bg": bg_idx,
                "feat_ct": ct_idx,
                "feat_city": city_idx,
                "total_unreserved": sc["unreserved"],
                "total_available": sc["available"],
                "total_reserved": sc["reserved"],
                "days_to_expiry": sc["days_to_expiry"],
                "bank_daily_burn": sc["daily_burn"],
                "capacity_units": sc["capacity"],
                "avg_urgency": sc["urgency"],
            }
            sample_df = pd.DataFrame([row_data])[feat_cols]

            raw_pred_hours = float(reg.predict(sample_df)[0])
            # Bound by batch expiry
            pred_hours = max(0.0, min(raw_pred_hours, sc["days_to_expiry"] * 24.0))
            pred_tier = int(clf.predict(sample_df)[0])
            pred_tier_str = tier_names.get(pred_tier, "UNKNOWN")

        print(f"    --> PREDICTION: {pred_hours:.1f} hours ({pred_hours/24.0:.2f} days) until stockout")
        print(f"    --> RISK TIER:  {pred_tier_str}")


def test_service_layer_integration():
    print("\n" + "=" * 88)
    print("[*] 3. TESTING FASTAPI SERVICE LAYER (app.services.forecasting)")
    print("=" * 88)

    try:
        from app.services.forecasting import BloodDepletionPredictor
        predictor = BloodDepletionPredictor()
        print(f"[+] Initialized BloodDepletionPredictor successfully.")
        print(f"[+] ML Model Loaded Flag: {predictor.has_ml_model}")
        print(f"[+] Loaded Model Path:    {predictor.model_path}")

        # Sample test with mock inventory & requests
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        mock_inv = [
            {
                "blood_bank_id": "BB_001",
                "blood_group": "O+",
                "component_type": "RBC",
                "units_available": 6,
                "units_reserved": 1,
                "expiry_date": (now + timedelta(days=15)).date(),
                "is_available": True,
            },
            {
                "blood_bank_id": "BB_002",
                "blood_group": "AB-",
                "component_type": "WHOLE_BLOOD",
                "units_available": 1,
                "units_reserved": 1,
                "expiry_date": (now + timedelta(days=5)).date(),
                "is_available": True,
            },
            {
                "blood_bank_id": "BB_003",
                "blood_group": "B+",
                "component_type": "RBC",
                "units_available": 50,
                "units_reserved": 2,
                "expiry_date": (now + timedelta(days=28)).date(),
                "is_available": True,
            },
        ]
        mock_reqs = [
            {
                "blood_group": "O+",
                "component_type": "RBC",
                "quantity_units": 8,
                "status": "FULFILLED",
                "request_timestamp": (now - timedelta(days=2)).isoformat(),
            },
            {
                "blood_group": "AB-",
                "component_type": "WHOLE_BLOOD",
                "quantity_units": 2,
                "status": "FULFILLED",
                "request_timestamp": (now - timedelta(days=1)).isoformat(),
            },
        ]

        predictions = predictor.predict_inventory_depletion(mock_inv, mock_reqs, reference_time=now)
        print(f"\n[+] Evaluated {len(predictions)} supply line predictions through Service Layer:")
        for p in predictions:
            print(f"    - [{p.stockout_risk:<15}] {p.blood_bank_id} | {p.blood_group} {p.component_type} : "
                  f"{p.hours_until_depletion:.1f} hrs left ({p.days_until_depletion:.1f} days) | Source: {p.model_source}")

    except Exception as e:
        print(f"[!] Service layer test error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Test trained Blood Bridge depletion model")
    parser.add_argument("--model", default=None, help="Path to depletion_model.pkl")
    args = parser.parse_args()

    model_path = find_model_path(args.model)
    bundle = inspect_model_bundle(model_path)
    run_unit_inference_tests(bundle)
    test_service_layer_integration()

    print("\n" + "=" * 88)
    print("[+] Model Integration and Forecasting Test Complete.")
    print("=" * 88 + "\n")


if __name__ == "__main__":
    main()
