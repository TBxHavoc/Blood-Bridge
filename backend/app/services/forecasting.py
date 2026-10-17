"""
Blood Bridge - ML Inventory Depletion & Demand Forecasting Service
IBM Z Datathon 2026 - AI Secured Track (Innovation without Exposure)

Integration:
- Directly loads and evaluates the trained ML model bundle (depletion_model.pkl).
- Models: LightGBM Regressor (predicts continuous hours to depletion) &
          Random Forest Classifier (predicts stockout urgency tier).
- Fallback: Deterministic discrete-event simulation with batch expiry attrition.
"""

from __future__ import annotations

import math
import os
import pickle
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class UsageStatistics:
    blood_group: str
    component_type: str
    total_requests: int
    total_units_consumed: int
    observation_days: float
    avg_usage_per_day: float
    weekly_usage: float
    hourly_burn_rate: float
    peak_24h_demand: int
    recent_trend: str  # 'RISING', 'FALLING', 'STABLE'


@dataclass
class DepletionPrediction:
    blood_bank_id: str
    blood_bank_code: str
    blood_bank_name: str
    blood_group: str
    component_type: str
    units_available: int
    units_reserved: int
    units_unreserved: int
    avg_usage_per_day: float
    weekly_usage: float
    hours_until_depletion: float
    days_until_depletion: float
    predicted_depletion_timestamp: datetime
    stockout_risk: str  # 'IMMEDIATE_EMPTY', 'CRITICAL', 'HIGH', 'MODERATE', 'STABLE', 'EXPIRES_BEFORE_USE'
    confidence_interval_hours: Tuple[float, float]
    earliest_batch_expiry: Optional[date]
    depletion_cause: str  # 'DEMAND_CONSUMPTION', 'BATCH_EXPIRATION', 'ZERO_STOCK'
    model_source: str = "Trained ML (LightGBM/RF)"  # or 'Discrete Simulation'


class BloodDepletionPredictor:
    """
    Predictive analytics and ML depletion forecasting engine.
    Integrates trained LightGBM / Random Forest models with automatic
    deterministic simulation fallback.
    """

    CANDIDATE_MODEL_PATHS = [
        os.path.join("backend", "model", "depletion_model.pkl"),
        os.path.join("backend", "models", "depletion_model.pkl"),
        os.path.join("model", "depletion_model.pkl"),
        os.path.join("models", "depletion_model.pkl"),
        os.path.join("database", "models", "depletion_model.pkl"),
        "depletion_model.pkl",
    ]

    def __init__(self, decay_factor: float = 0.05, min_burn_rate: float = 0.1, model_path: Optional[str] = None, use_ml_model: bool = True):
        self.decay_factor = decay_factor
        self.min_burn_rate = min_burn_rate
        self.ml_bundle: Optional[Dict[str, Any]] = None
        self.has_ml_model: bool = False
        self.model_path: Optional[str] = None

        if use_ml_model and model_path != "disable":
            self._load_ml_model(model_path)

    def _load_ml_model(self, custom_path: Optional[str] = None):
        """Attempts to load trained ML model bundle."""
        paths_to_check = [custom_path] if custom_path else []
        paths_to_check.extend(self.CANDIDATE_MODEL_PATHS)

        # Also check relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = os.path.dirname(current_dir)
        backend_dir = os.path.dirname(app_dir)
        paths_to_check.append(os.path.join(backend_dir, "model", "depletion_model.pkl"))
        paths_to_check.append(os.path.join(backend_dir, "models", "depletion_model.pkl"))

        for p in paths_to_check:
            if p and os.path.exists(p):
                try:
                    with open(p, "rb") as f:
                        bundle = pickle.load(f)
                    if isinstance(bundle, dict) and "regressor" in bundle and "classifier" in bundle:
                        self.ml_bundle = bundle
                        self.has_ml_model = True
                        self.model_path = p
                        print(f"[+] Loaded trained ML depletion model from: {p}")
                        return
                except Exception as e:
                    # Model exists but cannot be unpickled in current environment (e.g. missing lightgbm lib)
                    print(f"[i] Model found at {p} but could not be unpickled in current environment ({e}). Using simulation fallback.")
                    self.has_ml_model = False
                    self.model_path = p
                    return

    def calculate_usage_statistics(
        self,
        requests: List[Dict[str, Any]],
        reference_time: Optional[datetime] = None,
    ) -> Dict[Tuple[str, str], UsageStatistics]:
        """
        Calculates average daily usage, weekly usage, and consumption velocity
        per (blood_group, component_type) from historical requests.
        """
        if not reference_time:
            reference_time = datetime.now(UTC).replace(tzinfo=None)

        grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for req in requests:
            status = req.get("status", "OPEN").upper()
            if status in ("CANCELLED",):
                continue

            bg = req.get("blood_group", "").strip().upper()
            ct = req.get("component_type", "").strip()
            if "RBC" in ct.upper():
                ct = "RBC"
            elif "WHOLE" in ct.upper():
                ct = "WHOLE_BLOOD"

            if not bg or not ct:
                continue

            key = (bg, ct)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(req)

        results: Dict[Tuple[str, str], UsageStatistics] = {}

        for (bg, ct), req_list in grouped.items():
            total_units = 0
            timestamps: List[datetime] = []
            recent_24h_units = 0
            prior_24h_units = 0

            cut_24h = reference_time - timedelta(hours=24)
            cut_48h = reference_time - timedelta(hours=48)

            for r in req_list:
                qty = int(r.get("quantity_units") or r.get("quantity") or 1)
                total_units += qty

                ts_raw = r.get("request_timestamp") or r.get("created_at") or reference_time
                if isinstance(ts_raw, str):
                    try:
                        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        ts = reference_time
                elif isinstance(ts_raw, datetime):
                    ts = ts_raw.replace(tzinfo=None)
                else:
                    ts = reference_time

                timestamps.append(ts)

                if ts >= cut_24h:
                    recent_24h_units += qty
                elif ts >= cut_48h:
                    prior_24h_units += qty

            if timestamps:
                min_time = min(timestamps)
                max_time = max(max(timestamps), reference_time)
                elapsed_seconds = max(3600.0, (max_time - min_time).total_seconds())
                elapsed_days = max(1.0, elapsed_seconds / 86400.0)
            else:
                elapsed_days = 1.0

            avg_per_day = round(total_units / elapsed_days, 2)
            weekly = round(avg_per_day * 7.0, 2)
            hourly = round(avg_per_day / 24.0, 4)

            if recent_24h_units > (prior_24h_units * 1.25):
                trend = "RISING"
            elif recent_24h_units < (prior_24h_units * 0.75):
                trend = "FALLING"
            else:
                trend = "STABLE"

            results[(bg, ct)] = UsageStatistics(
                blood_group=bg,
                component_type=ct,
                total_requests=len(req_list),
                total_units_consumed=total_units,
                observation_days=round(elapsed_days, 2),
                avg_usage_per_day=avg_per_day,
                weekly_usage=weekly,
                hourly_burn_rate=hourly,
                peak_24h_demand=max(recent_24h_units, prior_24h_units),
                recent_trend=trend,
            )

        return results

    def predict_inventory_depletion(
        self,
        inventory_records: List[Dict[str, Any]],
        requests: List[Dict[str, Any]],
        blood_banks_map: Optional[Dict[str, Dict[str, Any]]] = None,
        reference_time: Optional[datetime] = None,
    ) -> List[DepletionPrediction]:
        """
        Predicts when each blood bank will run out of particular blood supplies.
        Uses trained LightGBM / Random Forest model if loaded; otherwise uses
        expiry-aware discrete simulation.
        """
        if not reference_time:
            reference_time = datetime.now(UTC).replace(tzinfo=None)

        usage_map = self.calculate_usage_statistics(requests, reference_time=reference_time)

        # Aggregate inventory by (blood_bank_id, blood_group, component_type)
        grouped_inv: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        for item in inventory_records:
            if not item.get("is_available", True):
                continue

            bb_id = item.get("blood_bank_id") or item.get("blood_bank_code") or "BB_001"
            bg = item.get("blood_group", "").strip().upper()
            ct = item.get("component_type", "").strip()
            if "RBC" in ct.upper():
                ct = "RBC"
            elif "WHOLE" in ct.upper():
                ct = "WHOLE_BLOOD"

            key = (bb_id, bg, ct)
            if key not in grouped_inv:
                grouped_inv[key] = {
                    "blood_bank_id": bb_id,
                    "blood_group": bg,
                    "component_type": ct,
                    "units_available": 0,
                    "units_reserved": 0,
                    "expiries": [],
                }

            avail = int(item.get("units_available") or 0)
            res = int(item.get("units_reserved") or 0)
            grouped_inv[key]["units_available"] += avail
            grouped_inv[key]["units_reserved"] += res

            exp = item.get("expiry_date")
            if isinstance(exp, str):
                try:
                    exp_date = date.fromisoformat(exp.split()[0].replace("Z", ""))
                    grouped_inv[key]["expiries"].append(exp_date)
                except Exception:
                    pass
            elif isinstance(exp, date):
                grouped_inv[key]["expiries"].append(exp)

        predictions: List[DepletionPrediction] = []
        num_banks = max(1, len(set(k[0] for k in grouped_inv.keys())))

        for (bb_id, bg, ct), inv in grouped_inv.items():
            avail = inv["units_available"]
            reserved = inv["units_reserved"]
            unreserved = max(0, avail - reserved)
            expiries = sorted(inv["expiries"])
            earliest_expiry = expiries[0] if expiries else None

            # Usage velocity
            usage = usage_map.get((bg, ct))
            if usage and usage.avg_usage_per_day > 0:
                bank_daily_rate = max(self.min_burn_rate, usage.avg_usage_per_day / num_banks)
            else:
                bank_daily_rate = self.min_burn_rate
            hourly_rate = bank_daily_rate / 24.0
            bank_weekly_rate = round(bank_daily_rate * 7.0, 2)

            # Blood Bank Metadata
            bank_info = (blood_banks_map or {}).get(bb_id, {})
            bank_code = bank_info.get("code", bb_id)
            bank_name = bank_info.get("name", f"Blood Bank ({bank_code})")
            bank_city = bank_info.get("city", "Mumbai")

            # Days to expiry
            days_to_exp = max(0.0, (earliest_expiry - reference_time.date()).days) if earliest_expiry else 30.0

            # Perform Prediction
            if unreserved <= 0:
                hours_left = 0.0
                days_left = 0.0
                depletion_time = reference_time
                risk = "IMMEDIATE_EMPTY"
                cause = "ZERO_STOCK"
                ci = (0.0, 0.0)
                source = "Direct Rule"
            elif self.has_ml_model and self.ml_bundle is not None:
                # Use Trained Machine Learning Model
                try:
                    bundle = self.ml_bundle
                    encoders = bundle.get("encoders", {})
                    
                    # Safe categorical transform
                    def safe_transform(encoder, val, default=0):
                        try:
                            return encoder.transform([val])[0]
                        except Exception:
                            return default

                    bg_idx = safe_transform(encoders.get("bg"), bg, 0)
                    ct_idx = safe_transform(encoders.get("ct"), ct, 0)
                    city_idx = safe_transform(encoders.get("city"), bank_city, 0)

                    # Build feature array
                    import pandas as pd
                    feature_dict = {
                        "feat_bg": bg_idx,
                        "feat_ct": ct_idx,
                        "feat_city": city_idx,
                        "total_unreserved": unreserved,
                        "total_available": avail,
                        "total_reserved": reserved,
                        "days_to_expiry": days_to_exp,
                        "bank_daily_burn": bank_daily_rate,
                        "capacity_units": int(bank_info.get("capacity_units", 500)),
                        "avg_urgency": 3.0,
                    }
                    feat_cols = bundle.get("feature_cols", list(feature_dict.keys()))
                    sample_df = pd.DataFrame([feature_dict])[feat_cols]

                    # ML Inference
                    pred_raw_hours = float(bundle["regressor"].predict(sample_df)[0])
                    # Bound by biological expiry
                    hours_left = round(max(0.0, min(pred_raw_hours, days_to_exp * 24.0)), 1)
                    days_left = round(hours_left / 24.0, 2)
                    depletion_time = reference_time + timedelta(hours=hours_left)

                    pred_tier_idx = int(bundle["classifier"].predict(sample_df)[0])
                    tier_map = {0: "IMMEDIATE_EMPTY", 1: "CRITICAL", 2: "HIGH", 3: "MODERATE", 4: "STABLE"}
                    risk = tier_map.get(pred_tier_idx, "STABLE")

                    cause = "BATCH_EXPIRATION" if hours_left >= (days_to_exp * 24.0) else "DEMAND_CONSUMPTION"
                    std_err = math.sqrt(max(1.0, hours_left * 0.12))
                    ci = (round(max(0.0, hours_left - 1.96 * std_err), 1), round(hours_left + 1.96 * std_err, 1))
                    source = f"Trained ML ({bundle.get('model_type', 'LightGBM/RF')})"
                except Exception as ex:
                    # Fallback to simulation if ML inference encounters unexpected feature shape
                    hours_left = round(min(unreserved / hourly_rate, days_to_exp * 24.0), 1)
                    days_left = round(hours_left / 24.0, 2)
                    depletion_time = reference_time + timedelta(hours=hours_left)
                    risk = "CRITICAL" if hours_left <= 24.0 else ("HIGH" if hours_left <= 72.0 else "STABLE")
                    cause = "DEMAND_CONSUMPTION"
                    ci = (round(max(0.0, hours_left * 0.8), 1), round(hours_left * 1.2, 1))
                    source = "Discrete Simulation Fallback"
            else:
                # Deterministic Discrete Simulation
                sim_hours = 0.0
                current_stock = float(unreserved)
                cause = "DEMAND_CONSUMPTION"

                while sim_hours < 1440.0 and current_stock > 0:
                    sim_hours += 1.0
                    current_stock -= hourly_rate
                    sim_date = (reference_time + timedelta(hours=sim_hours)).date()
                    if earliest_expiry and sim_date >= earliest_expiry:
                        cause = "BATCH_EXPIRATION"
                        current_stock = 0.0
                        break

                hours_left = round(sim_hours, 1)
                days_left = round(hours_left / 24.0, 2)
                depletion_time = reference_time + timedelta(hours=hours_left)

                if hours_left <= 24.0:
                    risk = "CRITICAL"
                elif hours_left <= 72.0:
                    risk = "HIGH"
                elif hours_left <= 168.0:
                    risk = "MODERATE"
                elif cause == "BATCH_EXPIRATION":
                    risk = "EXPIRES_BEFORE_USE"
                else:
                    risk = "STABLE"

                std_err = math.sqrt(max(1.0, hours_left * 0.15))
                ci = (round(max(0.0, hours_left - 1.96 * std_err), 1), round(hours_left + 1.96 * std_err, 1))
                source = "Discrete Simulation"

            predictions.append(
                DepletionPrediction(
                    blood_bank_id=bb_id,
                    blood_bank_code=bank_code,
                    blood_bank_name=bank_name,
                    blood_group=bg,
                    component_type=ct,
                    units_available=avail,
                    units_reserved=reserved,
                    units_unreserved=unreserved,
                    avg_usage_per_day=round(bank_daily_rate, 2),
                    weekly_usage=bank_weekly_rate,
                    hours_until_depletion=hours_left,
                    days_until_depletion=days_left,
                    predicted_depletion_timestamp=depletion_time,
                    stockout_risk=risk,
                    confidence_interval_hours=ci,
                    earliest_batch_expiry=earliest_expiry,
                    depletion_cause=cause,
                    model_source=source,
                )
            )

        predictions.sort(key=lambda p: (p.hours_until_depletion, p.units_unreserved))
        return predictions
