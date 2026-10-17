#!/usr/bin/env python3
"""
Blood Bridge - ML Supply Depletion & Demand Forecasting Model Trainer
IBM Z Datathon 2026 - AI Secured Track (Innovation without Exposure)

Model: Hybrid Gradient Boosted Decision Tree (LightGBM / Random Forest) + Discrete Expiry Simulation
Targets:
  1. Regression: Predict continuous Daily Usage (units/day) and Hours to Depletion.
  2. Multi-Class Classification: Predict Stockout Risk Tier (CRITICAL, HIGH, MODERATE, STABLE).
"""

import os
import sys
import json
import math
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta, timezone

# Optional imports with fallbacks
try:
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, GradientBoostingRegressor
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import mean_absolute_error, r2_score, classification_report, accuracy_score
    from sklearn.preprocessing import LabelEncoder
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import lightgbm as lgb
    LGBM_AVAILABLE = True
except ImportError:
    LGBM_AVAILABLE = False


def load_datasets(dataset_dir="datasets"):
    """Loads CSV datasets into pandas DataFrames."""
    inv_df = pd.read_csv(os.path.join(dataset_dir, "blood_inventory.csv"))
    req_df = pd.read_csv(os.path.join(dataset_dir, "blood_requests.csv"))
    banks_df = pd.read_csv(os.path.join(dataset_dir, "blood_banks.csv"))
    hosp_df = pd.read_csv(os.path.join(dataset_dir, "hospitals.csv"))
    dist_df = pd.read_csv(os.path.join(dataset_dir, "location_distances.csv"))

    # Normalize component types
    inv_df["component_type"] = inv_df["component_type"].apply(
        lambda x: "RBC" if "RBC" in str(x).upper() else "WHOLE_BLOOD"
    )
    req_df["component_type"] = req_df["component_type"].apply(
        lambda x: "RBC" if "RBC" in str(x).upper() else "WHOLE_BLOOD"
    )

    # Parse timestamps
    req_df["request_timestamp"] = pd.to_datetime(req_df["request_timestamp"])
    inv_df["expiry_date"] = pd.to_datetime(inv_df["expiry_date"]).dt.date
    inv_df["collection_date"] = pd.to_datetime(inv_df["collection_date"]).dt.date

    return inv_df, req_df, banks_df, hosp_df, dist_df


def engineer_features(inv_df, req_df, banks_df, hosp_df, dist_df, ref_time=None):
    """
    Builds structured feature vectors from raw clinical requests and inventory records.
    Calculates historical usage per day and weekly usage.
    """
    if ref_time is None:
        ref_time = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Historical Usage Features (Excluding cancelled requests)
    valid_reqs = req_df[req_df["status"] != "CANCELLED"].copy()
    
    # Calculate observation window
    t_min = valid_reqs["request_timestamp"].min()
    t_max = max(valid_reqs["request_timestamp"].max(), pd.to_datetime(ref_time))
    elapsed_days = max(1.0, (t_max - t_min).total_seconds() / 86400.0)

    # Group by blood group & component
    usage_summary = (
        valid_reqs.groupby(["blood_group", "component_type"])
        .agg(
            total_units=("quantity_units", "sum"),
            request_count=("code", "count"),
            avg_urgency=("urgency", "mean"),
            high_urgency_ratio=("urgency", lambda u: (u >= 4).mean()),
        )
        .reset_index()
    )

    usage_summary["avg_usage_per_day"] = (usage_summary["total_units"] / elapsed_days).round(2)
    usage_summary["weekly_usage"] = (usage_summary["avg_usage_per_day"] * 7.0).round(2)
    usage_summary["hourly_burn_rate"] = (usage_summary["avg_usage_per_day"] / 24.0).round(4)

    # 2. Inventory Aggregation by (blood_bank_code, blood_group, component_type)
    active_inv = inv_df[inv_df["is_available"] == True].copy()
    active_inv["unreserved_units"] = np.maximum(
        0, active_inv["units_available"] - active_inv["units_reserved"]
    )

    bank_inv = (
        active_inv.groupby(["blood_bank_code", "blood_group", "component_type"])
        .agg(
            total_available=("units_available", "sum"),
            total_reserved=("units_reserved", "sum"),
            total_unreserved=("unreserved_units", "sum"),
            earliest_expiry=("expiry_date", "min"),
            batch_count=("code", "count"),
        )
        .reset_index()
    )

    # Merge inventory with usage summary
    merged = pd.merge(
        bank_inv,
        usage_summary,
        on=["blood_group", "component_type"],
        how="left"
    )

    # Fill defaults for blood types without observed requests
    merged["avg_usage_per_day"] = merged["avg_usage_per_day"].fillna(0.1)
    merged["weekly_usage"] = merged["weekly_usage"].fillna(0.7)
    merged["hourly_burn_rate"] = merged["hourly_burn_rate"].fillna(0.004)
    merged["avg_urgency"] = merged["avg_urgency"].fillna(2.5)
    merged["high_urgency_ratio"] = merged["high_urgency_ratio"].fillna(0.2)

    # Merge Blood Bank metadata
    merged = pd.merge(
        merged,
        banks_df[["code", "city", "capacity_units"]],
        left_on="blood_bank_code",
        right_on="code",
        how="left"
    )

    # Calculate days until earliest batch expiry
    ref_date = pd.to_datetime(ref_time).date()
    merged["days_to_expiry"] = merged["earliest_expiry"].apply(
        lambda exp: max(0.0, (exp - ref_date).days) if pd.notnull(exp) else 30.0
    )

    # Apportion daily burn rate by bank share
    num_banks = len(banks_df["code"].unique())
    merged["bank_daily_burn"] = np.maximum(0.1, merged["avg_usage_per_day"] / num_banks)
    merged["bank_hourly_burn"] = merged["bank_daily_burn"] / 24.0

    # 3. Target Variable Calculation (Ground Truth Simulation)
    # Continuous Target: Hours until Depletion
    # Categorical Target: Risk Tier (0=IMMEDIATE_EMPTY, 1=CRITICAL, 2=HIGH, 3=MODERATE, 4=STABLE)
    hours_to_depletion = []
    risk_tiers = []
    risk_labels = []

    for _, row in merged.iterrows():
        unres = row["total_unreserved"]
        burn = row["bank_hourly_burn"]
        exp_days = row["days_to_expiry"]
        exp_hours = exp_days * 24.0

        if unres <= 0:
            h = 0.0
            tier = 0
            label = "IMMEDIATE_EMPTY"
        else:
            # Consumption time
            h_consumption = unres / burn
            # Expiry time cutoff
            h = min(h_consumption, exp_hours)

            if h <= 24.0:
                tier = 1
                label = "CRITICAL"
            elif h <= 72.0:
                tier = 2
                label = "HIGH"
            elif h <= 168.0:
                tier = 3
                label = "MODERATE"
            else:
                tier = 4
                label = "STABLE"

        hours_to_depletion.append(round(h, 2))
        risk_tiers.append(tier)
        risk_labels.append(label)

    merged["target_hours_to_depletion"] = hours_to_depletion
    merged["target_risk_tier"] = risk_tiers
    merged["target_risk_label"] = risk_labels

    return merged, usage_summary


def train_models(dataset_dir="datasets", model_output_path="models/depletion_model.pkl"):
    """
    Trains the LightGBM / Random Forest forecasting models.
    """
    print("=" * 80)
    print(" BLOOD BRIDGE: TRAINING ML SUPPLY DEPLETION & DEMAND MODEL")
    print("=" * 80)

    inv_df, req_df, banks_df, hosp_df, dist_df = load_datasets(dataset_dir)
    print(f"[+] Loaded {len(inv_df)} inventory items and {len(req_df)} historical requests.")

    data, usage_summary = engineer_features(inv_df, req_df, banks_df, hosp_df, dist_df)
    print(f"[+] Feature matrix constructed: {data.shape[0]} supply lines with {data.shape[1]} features.")

    # Display Usage Statistics
    print("\n[-] Computed Historical Usage Rates:")
    print("-" * 65)
    print(f"{'Blood Group':<12} {'Component':<14} {'Avg Units/Day':<16} {'Weekly Usage':<14}")
    print("-" * 65)
    for _, r in usage_summary.iterrows():
        print(f"{r['blood_group']:<12} {r['component_type']:<14} {str(r['avg_usage_per_day']) + ' u/d':<16} {str(r['weekly_usage']) + ' u/wk':<14}")
    print("-" * 65)

    if not SKLEARN_AVAILABLE:
        print("[!] scikit-learn is not installed in this environment.")
        print("    Run: pip install scikit-learn lightgbm pandas numpy")
        return data, usage_summary, None

    # Feature Encoding
    le_bg = LabelEncoder()
    le_ct = LabelEncoder()
    le_city = LabelEncoder()

    data["feat_bg"] = le_bg.fit_transform(data["blood_group"])
    data["feat_ct"] = le_ct.fit_transform(data["component_type"])
    data["feat_city"] = le_city.fit_transform(data["city"].fillna("Unknown"))

    feature_cols = [
        "feat_bg",
        "feat_ct",
        "feat_city",
        "total_unreserved",
        "total_available",
        "total_reserved",
        "days_to_expiry",
        "bank_daily_burn",
        "capacity_units",
        "avg_urgency",
        "high_urgency_ratio"
    ]

    X = data[feature_cols].fillna(0)
    y_reg = data["target_hours_to_depletion"]
    y_clf = data["target_risk_tier"]

    # Train / Test Split
    X_train, X_test, y_reg_train, y_reg_test, y_clf_train, y_clf_test = train_test_split(
        X, y_reg, y_clf, test_size=0.2, random_state=42
    )

    # 1. Regressor Training (Predict Hours to Depletion)
    print("\n[-] 1. Training Regressor (Predicting Hours until Depletion):")
    if LGBM_AVAILABLE:
        print("    Model: LightGBM Regressor (LGBMRegressor)")
        reg_model = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.05, max_depth=5, random_state=42)
    else:
        print("    Model: Random Forest Regressor (RandomForestRegressor)")
        reg_model = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)

    reg_model.fit(X_train, y_reg_train)
    reg_preds = reg_model.predict(X_test)

    mae = mean_absolute_error(y_reg_test, reg_preds)
    r2 = r2_score(y_reg_test, reg_preds)
    print(f"    [OK] Regressor Evaluation:")
    print(f"         - Mean Absolute Error (MAE): {mae:.2f} hours")
    print(f"         - R-squared (R2 Score):       {r2:.4f}")

    # 2. Classifier Training (Predicting Stockout Risk Tier)
    print("\n[-] 2. Training Classifier (Predicting Stockout Risk Tier):")
    clf_model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    clf_model.fit(X_train, y_clf_train)
    clf_preds = clf_model.predict(X_test)

    acc = accuracy_score(y_clf_test, clf_preds)
    print(f"    [OK] Classifier Accuracy: {acc * 100:.2f}%")

    # Feature Importance
    importances = reg_model.feature_importances_
    print("\n[-] 3. Top Feature Importances (Explainability):")
    feat_imp = sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)
    for col, imp in feat_imp[:6]:
        print(f"    - {col:<22}: {imp:.4f}")

    # Save Model Artifacts
    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
    bundle = {
        "reg_model": reg_model,
        "clf_model": clf_model,
        "feature_cols": feature_cols,
        "encoders": {"bg": le_bg, "ct": le_ct, "city": le_city},
        "usage_summary": usage_summary.to_dict(orient="records"),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "LightGBM/RandomForest-Hybrid",
    }
    with open(model_output_path, "wb") as f:
        pickle.dump(bundle, f)

    print(f"\n[SUCCESS] Trained model successfully exported to: {model_output_path}")
    print("=" * 80)
    return data, usage_summary, bundle


if __name__ == "__main__":
    ds_dir = "datasets" if os.path.exists("datasets") else "../datasets"
    train_models(dataset_dir=ds_dir)
