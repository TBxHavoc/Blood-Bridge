#!/usr/bin/env python3
"""
Blood Bridge - ML Supply Depletion & Usage Prediction Engine
IBM Z Datathon 2026 - AI Secured Track (Innovation without Exposure)

Usage:
    python scripts/predict_depletion.py
    python scripts/predict_depletion.py --csv datasets/
    python scripts/predict_depletion.py --filter-bank BB_001

Outputs:
1. Average Daily & Weekly Usage per Blood Group and Component.
2. Predicted Runout Times & Hours to Stockout per Blood Bank.
3. Risk Tier Alerts: IMMEDIATE_EMPTY, CRITICAL (<=24h), HIGH (<=72h), MODERATE (<=7d), STABLE.
"""

import sys
import os
import csv
import math
from datetime import datetime, date, timedelta, timezone

# Ensure project paths are resolved
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_dataset_dir():
    candidates = [
        os.path.join(BASE_DIR, "datasets"),
        os.path.join(BASE_DIR, "..", "datasets"),
        "datasets",
    ]
    for c in candidates:
        if os.path.exists(os.path.join(c, "blood_inventory.csv")):
            return c
    return os.path.join(BASE_DIR, "datasets")


def load_csv_data(data_dir):
    inv_file = os.path.join(data_dir, "blood_inventory.csv")
    req_file = os.path.join(data_dir, "blood_requests.csv")
    bank_file = os.path.join(data_dir, "blood_banks.csv")

    inventory = []
    if os.path.exists(inv_file):
        with open(inv_file, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                inventory.append({
                    "code": row.get("code"),
                    "blood_bank_code": row.get("blood_bank_code"),
                    "blood_group": row.get("blood_group", "").strip(),
                    "component_type": "RBC" if "RBC" in row.get("component_type", "").upper() else "WHOLE_BLOOD",
                    "units_available": int(row.get("units_available", 0)),
                    "units_reserved": int(row.get("units_reserved", 0)),
                    "collection_date": row.get("collection_date"),
                    "expiry_date": row.get("expiry_date"),
                    "is_available": row.get("is_available", "True").lower() in ("true", "1", "yes"),
                })

    requests = []
    if os.path.exists(req_file):
        with open(req_file, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                requests.append({
                    "code": row.get("code"),
                    "hospital_code": row.get("hospital_code"),
                    "blood_group": row.get("blood_group", "").strip(),
                    "component_type": "RBC" if "RBC" in row.get("component_type", "").upper() else "WHOLE_BLOOD",
                    "quantity_units": int(row.get("quantity_units", 1)),
                    "status": row.get("status", "OPEN").upper(),
                    "request_timestamp": row.get("request_timestamp"),
                })

    banks = {}
    if os.path.exists(bank_file):
        with open(bank_file, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get("code")
                banks[code] = {
                    "code": code,
                    "name": row.get("name", f"Blood Bank {code}"),
                    "city": row.get("city", "Metro"),
                }

    return inventory, requests, banks


def parse_timestamp(ts_val, default_time):
    if not ts_val:
        return default_time
    try:
        clean = ts_val.strip().replace("Z", "").split(".")[0]
        return datetime.fromisoformat(clean)
    except Exception:
        return default_time


def calculate_usage(requests, ref_time):
    grouped = {}
    for r in requests:
        if r.get("status") in ("CANCELLED",):
            continue
        key = (r["blood_group"], r["component_type"])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(r)

    stats = {}
    for (bg, ct), reqs in grouped.items():
        total_qty = sum(r["quantity_units"] for r in reqs)
        timestamps = [parse_timestamp(r["request_timestamp"], ref_time) for r in reqs]
        if timestamps:
            t_min = min(timestamps)
            t_max = max(max(timestamps), ref_time)
            elapsed_days = max(1.0, (t_max - t_min).total_seconds() / 86400.0)
        else:
            elapsed_days = 1.0

        daily_rate = round(total_qty / elapsed_days, 2)
        weekly_rate = round(daily_rate * 7.0, 2)

        stats[(bg, ct)] = {
            "blood_group": bg,
            "component_type": ct,
            "total_requests": len(reqs),
            "total_units": total_qty,
            "observation_days": round(elapsed_days, 1),
            "daily_usage": daily_rate,
            "weekly_usage": weekly_rate,
            "hourly_burn_rate": round(daily_rate / 24.0, 4),
        }
    return stats


def predict_depletion(inventory, usage_stats, banks, ref_time):
    grouped_inv = {}
    for item in inventory:
        if not item.get("is_available"):
            continue
        bank_code = item.get("blood_bank_code", "BB_001")
        bg = item["blood_group"]
        ct = item["component_type"]
        key = (bank_code, bg, ct)
        if key not in grouped_inv:
            grouped_inv[key] = {
                "bank_code": bank_code,
                "blood_group": bg,
                "component_type": ct,
                "units_available": 0,
                "units_reserved": 0,
                "expiries": [],
            }
        grouped_inv[key]["units_available"] += item["units_available"]
        grouped_inv[key]["units_reserved"] += item["units_reserved"]
        if item.get("expiry_date"):
            try:
                exp = date.fromisoformat(item["expiry_date"].strip())
                grouped_inv[key]["expiries"].append(exp)
            except Exception:
                pass

    num_banks = max(1, len(set(k[0] for k in grouped_inv.keys())))
    predictions = []

    for (bank_code, bg, ct), inv in grouped_inv.items():
        avail = inv["units_available"]
        res = inv["units_reserved"]
        unreserved = max(0, avail - res)
        expiries = sorted(inv["expiries"])
        earliest_expiry = expiries[0] if expiries else None

        usage = usage_stats.get((bg, ct))
        if usage and usage["daily_usage"] > 0:
            bank_daily_rate = max(0.1, usage["daily_usage"] / num_banks)
        else:
            bank_daily_rate = 0.1
        hourly_rate = bank_daily_rate / 24.0
        weekly_rate = round(bank_daily_rate * 7.0, 2)

        bank_name = banks.get(bank_code, {}).get("name", f"Blood Bank ({bank_code})")

        if unreserved <= 0:
            hours_left = 0.0
            depletion_time = ref_time
            risk = "IMMEDIATE_EMPTY"
            cause = "ZERO_STOCK"
        else:
            current_stock = float(unreserved)
            sim_hours = 0.0
            max_sim_hours = 24.0 * 60.0
            cause = "DEMAND_CONSUMPTION"

            while sim_hours < max_sim_hours and current_stock > 0:
                sim_hours += 1.0
                current_stock -= hourly_rate
                sim_date = (ref_time + timedelta(hours=sim_hours)).date()
                if earliest_expiry and sim_date >= earliest_expiry:
                    cause = "BATCH_EXPIRATION"
                    current_stock = 0.0
                    break

            hours_left = round(sim_hours, 1)
            depletion_time = ref_time + timedelta(hours=hours_left)

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

        predictions.append({
            "bank_code": bank_code,
            "bank_name": bank_name,
            "blood_group": bg,
            "component_type": ct,
            "unreserved": unreserved,
            "daily_rate": round(bank_daily_rate, 2),
            "weekly_rate": weekly_rate,
            "hours_left": hours_left,
            "days_left": round(hours_left / 24.0, 2),
            "depletion_time": depletion_time.strftime("%Y-%m-%d %H:%M UTC"),
            "risk": risk,
            "cause": cause,
            "earliest_expiry": str(earliest_expiry) if earliest_expiry else "N/A",
        })

    predictions.sort(key=lambda p: (p["hours_left"], p["unreserved"]))
    return predictions


def main():
    data_dir = find_dataset_dir()
    ref_time = datetime.now(timezone.utc).replace(tzinfo=None)

    print("=" * 88)
    print(" BLOOD BRIDGE: MACHINE LEARNING SUPPLY DEPLETION & DEMAND FORECASTING")
    print(" IBM Z Datathon 2026 · AI Secured Track (Innovation without Exposure)")
    print(f" Reference Evaluation Timestamp: {ref_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f" Dataset Directory: {data_dir}")
    print("=" * 88)

    inventory, requests, banks = load_csv_data(data_dir)
    print(f"\n[+] Loaded {len(inventory)} inventory rows, {len(requests)} historical requests, {len(banks)} blood banks.\n")

    # 1. Historical Usage Analysis
    usage_stats = calculate_usage(requests, ref_time)
    print("[-] 1. HISTORICAL CONSUMPTION ANALYSIS (Usage per Day & Weekly):")
    print("-" * 88)
    print(f"{'Blood Group':<12} {'Component':<14} {'Total Reqs':<12} {'Units Used':<12} {'Avg Units/Day':<16} {'Weekly Usage':<14}")
    print("-" * 88)
    for key in sorted(usage_stats.keys()):
        stat = usage_stats[key]
        print(
            f"{stat['blood_group']:<12} "
            f"{stat['component_type']:<14} "
            f"{str(stat['total_requests']):<12} "
            f"{str(stat['total_units']):<12} "
            f"{str(stat['daily_usage']) + ' u/day':<16} "
            f"{str(stat['weekly_usage']) + ' u/wk':<14}"
        )
    print("-" * 88)

    # 2. Stockout Depletion Predictions
    predictions = predict_depletion(inventory, usage_stats, banks, ref_time)
    print("\n[-] 2. PREDICTED TIME TO DEPLETION & STOCKOUT RISK FORECAST:")
    print("-" * 105)
    print(f"{'Bank Code':<10} {'Blood':<6} {'Component':<12} {'Stock':<8} {'Daily Burn':<12} {'Runout Time':<18} {'Days Left':<12} {'Risk Tier':<14} {'Cause'}")
    print("-" * 105)

    critical_count = 0
    high_count = 0
    for p in predictions:
        if p["risk"] in ("CRITICAL", "IMMEDIATE_EMPTY"):
            critical_count += 1
            risk_tag = f"!! {p['risk']}"
        elif p["risk"] == "HIGH":
            high_count += 1
            risk_tag = f"!  {p['risk']}"
        else:
            risk_tag = f"   {p['risk']}"

        # Display first 25 or all high-risk items
        print(
            f"{p['bank_code']:<10} "
            f"{p['blood_group']:<6} "
            f"{p['component_type']:<12} "
            f"{str(p['unreserved']) + ' u':<8} "
            f"{str(p['daily_rate']) + ' u/d':<12} "
            f"{p['depletion_time']:<18} "
            f"{str(p['days_left']) + ' days':<12} "
            f"{risk_tag:<14} "
            f"{p['cause']}"
        )

    print("-" * 105)
    print(f"\n[SUMMARY] Evaluated {len(predictions)} blood bank supply lines.")
    print(f"          - Immediate / Critical Stockouts (< 24h): {critical_count}")
    print(f"          - High Risk Stockouts (24h - 72h):       {high_count}")
    print("=" * 88 + "\n")


if __name__ == "__main__":
    main()
