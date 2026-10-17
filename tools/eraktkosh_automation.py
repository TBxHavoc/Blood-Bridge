#!/usr/bin/env python3
"""
Automated eRaktKosh Scraper for Bangalore (All Blood Groups).

Features:
- Scrapes all 14 blood components across Bangalore Urban and Rural districts.
- Extracts details for all 8 standard blood groups (A+, A-, B+, B-, O+, O-, AB+, AB-).
- Produces separate JSON & CSV files for each blood group immediately upon completion.
- Replaces previous data files atomically with fresh data.
- Writes to both `data/eraktkosh/` and `frontend/public/data/eraktkosh/` for instant UI reflection.
- Runs on a recurring 10-minute schedule (600s).
- Supports single-run mode via `--once` flag.
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from scrapling import Fetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("eraktkosh_automation")

DISTRICTS = {
    572: "Bangalore Urban",
    583: "Bangalore Rural"
}

COMPONENTS = {
    11: "Whole Blood",
    12: "Packed Red Blood Cells",
    13: "Fresh Frozen Plasma",
    14: "Single Donor Platelet",
    16: "Platelet Rich Plasma",
    17: "Cryoprecipitate",
    18: "Single Donor Plasma",
    19: "Plasma",
    20: "Platelet Concentrate",
    21: "Cryo Poor Plasma",
    23: "Random Donor Platelets",
    28: "Sagm Packed Red Blood Cells",
    29: "Irradiated RBC",
    30: "Leukoreduced Rbc"
}

BLOOD_GROUPS = [
    {"key": "A_positive", "label": "A+", "regex": r'A\+Ve\s*:\s*(\d+)'},
    {"key": "A_negative", "label": "A-", "regex": r'A\-Ve\s*:\s*(\d+)'},
    {"key": "B_positive", "label": "B+", "regex": r'B\+Ve\s*:\s*(\d+)'},
    {"key": "B_negative", "label": "B-", "regex": r'B\-Ve\s*:\s*(\d+)'},
    {"key": "O_positive", "label": "O+", "regex": r'O\+Ve\s*:\s*(\d+)'},
    {"key": "O_negative", "label": "O-", "regex": r'O\-Ve\s*:\s*(\d+)'},
    {"key": "AB_positive", "label": "AB+", "regex": r'AB\+Ve\s*:\s*(\d+)'},
    {"key": "AB_negative", "label": "AB-", "regex": r'AB\-Ve\s*:\s*(\d+)'},
]

# Destination folders
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRS = [
    WORKSPACE_ROOT / "data" / "eraktkosh",
    WORKSPACE_ROOT / "frontend" / "public" / "data" / "eraktkosh"
]

def clean_json_str(text: str) -> str:
    """Escapes raw control characters that appear inside JSON string literals."""
    out = []
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                out.append(char)
                escaped = False
                continue
            if char == '\\':
                out.append(char)
                escaped = True
                continue
            if char == '"':
                out.append(char)
                in_string = False
                continue
            code = ord(char)
            if code < 0x20:
                if code == 0x0a:
                    out.append('\\n')
                elif code == 0x0d:
                    out.append('\\r')
                elif code == 0x09:
                    out.append('\\t')
                else:
                    out.append(f'\\u{code:04x}')
                continue
            out.append(char)
            continue
        if char == '"':
            in_string = True
        out.append(char)
    return "".join(out)

def strip_tags(text: str) -> str:
    text = re.sub(r'<br\s*/?>', ' | ', text, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text, flags=re.I)
    text = re.sub(r'&amp;', '&', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def parse_contact(contact_raw: str):
    parts = [p.strip() for p in contact_raw.split('<br/>') if p.strip()]
    name = parts[0] if len(parts) > 0 else ""
    address = parts[1] if len(parts) > 1 else ""
    contact_info = parts[2] if len(parts) > 2 else ""
    
    phone, email, fax = "", "", ""
    m_phone = re.search(r'Phone:\s*([^,]+)', contact_info, re.I)
    if m_phone:
        p = m_phone.group(1).strip()
        if p not in ['-', 'N/A', 'NA']: phone = p
        
    m_fax = re.search(r'Fax:\s*([^,]+)', contact_info, re.I)
    if m_fax:
        f = m_fax.group(1).strip()
        if f not in ['-', 'N/A', 'NA']: fax = f
        
    m_email = re.search(r'Email:\s*([^\s,]+)', contact_info, re.I)
    if m_email:
        e = m_email.group(1).strip()
        if e not in ['-', 'N/A', 'NA']: email = e

    return {
        "name": name,
        "address": address,
        "phone": phone,
        "fax": fax,
        "email": email
    }

def parse_stock_cell(avail_html: str):
    is_available = "Available" in avail_html and "Not Available" not in avail_html
    groups = {}
    for match in re.finditer(r'([A-Za-z0-9+-]+Ve)\s*:\s*(\d+)', avail_html, re.I):
        label = match.group(1).upper()
        # Canonicalize label
        if label.endswith("VE"):
            label = label[:-2] + "Ve"
        groups[label] = int(match.group(2))
    return {
        "is_available": is_available,
        "groups": groups,
        "raw_status": strip_tags(avail_html)
    }

def scrape_bangalore_snapshot():
    """Scrapes all blood banks and components for Bangalore Urban & Rural."""
    raw_records = []
    logger.info("Starting scrape of eRaktKosh for Bangalore...")

    for dist_code, dist_name in DISTRICTS.items():
        for comp_code, comp_name in COMPONENTS.items():
            url = (
                f"https://eraktkosh.mohfw.gov.in/BLDAHIMS/bloodbank/nearbyBB.cnt"
                f"?hmode=GETNEARBYSTOCKDETAILS&stateCode=29&districtCode={dist_code}"
                f"&bloodGroup=all&bloodComponent={comp_code}&lang=0"
            )
            try:
                resp = Fetcher.get(url, timeout=20)
                raw = resp.body.decode("utf-8", errors="ignore")
                cleaned = clean_json_str(raw)
                data = json.loads(cleaned)
                rows = data.get("data", [])
                
                for row in rows:
                    if len(row) < 6:
                        continue
                    contact = parse_contact(row[1])
                    if contact["name"] == "-" or not contact["name"]:
                        continue
                    stock = parse_stock_cell(row[3])
                    
                    raw_records.append({
                        "district": dist_name,
                        "district_code": dist_code,
                        "component": comp_name,
                        "component_code": comp_code,
                        "blood_bank_name": contact["name"],
                        "address": contact["address"],
                        "category": row[2] or "Private",
                        "phone": contact["phone"],
                        "email": contact["email"],
                        "fax": contact["fax"],
                        "is_available": stock["is_available"],
                        "groups": stock["groups"],
                        "status_text": stock["raw_status"],
                        "last_updated": row[4],
                        "type": row[5]
                    })
            except Exception as e:
                logger.warning(f"Error fetching {dist_name} component {comp_name} ({comp_code}): {e}")

    logger.info(f"Fetched {len(raw_records)} component records across Bangalore.")
    return raw_records

def write_data_files(records: list):
    """Processes scraped records and writes individual blood group files and summary."""
    now_iso = datetime.now(timezone.utc).isoformat()
    now_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Ensure directories exist
    for out_dir in OUTPUT_DIRS:
        out_dir.mkdir(parents=True, exist_ok=True)

    summary_stats = {
        "last_updated": now_local,
        "last_updated_iso": now_iso,
        "total_records_scanned": len(records),
        "blood_groups": {}
    }

    fieldnames = [
        "blood_bank_name",
        "category",
        "district",
        "component",
        "units",
        "phone",
        "email",
        "address",
        "last_updated",
        "type"
    ]

    for bg in BLOOD_GROUPS:
        key = bg["key"]
        label = bg["label"]
        canonical_label = f"{label}Ve"

        # Find all records where this blood group has units available
        group_rows = []
        for r in records:
            units = r["groups"].get(canonical_label, 0)
            if units > 0:
                row_copy = {
                    "blood_bank_name": r["blood_bank_name"],
                    "category": r["category"],
                    "district": r["district"],
                    "component": r["component"],
                    "units": units,
                    "phone": r["phone"],
                    "email": r["email"],
                    "address": r["address"],
                    "last_updated": r["last_updated"],
                    "type": r["type"],
                    "all_groups": r["groups"]
                }
                group_rows.append(row_copy)

        # Sort descending by units available
        group_rows.sort(key=lambda x: x["units"], reverse=True)

        total_units = sum(r["units"] for r in group_rows)
        unique_banks = len(set(r["blood_bank_name"] for r in group_rows))

        summary_stats["blood_groups"][label] = {
            "key": key,
            "total_units": total_units,
            "unique_banks": unique_banks,
            "record_count": len(group_rows),
            "file_json": f"{key}.json",
            "file_csv": f"{key}.csv"
        }

        payload = {
            "blood_group": label,
            "key": key,
            "city": "Bengaluru",
            "last_updated": now_local,
            "last_updated_iso": now_iso,
            "total_units": total_units,
            "unique_banks": unique_banks,
            "record_count": len(group_rows),
            "data": group_rows
        }

        # Write to both target directories
        for out_dir in OUTPUT_DIRS:
            json_file = out_dir / f"{key}.json"
            csv_file = out_dir / f"{key}.csv"
            
            # Atomic JSON write
            temp_json = out_dir / f"{key}.tmp.json"
            with open(temp_json, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            temp_json.replace(json_file)

            # Atomic CSV write
            temp_csv = out_dir / f"{key}.tmp.csv"
            with open(temp_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for gr in group_rows:
                    writer.writerow(gr)
            temp_csv.replace(csv_file)

        logger.info(f"Updated {label} ({key}): {total_units} units across {unique_banks} banks.")

    # Write overall summary
    for out_dir in OUTPUT_DIRS:
        summary_file = out_dir / "summary.json"
        temp_summary = out_dir / "summary.tmp.json"
        with open(temp_summary, "w", encoding="utf-8") as f:
            json.dump(summary_stats, f, indent=2)
        temp_summary.replace(summary_file)

    logger.info("Summary file written successfully to all destinations.")
    return summary_stats

def run_automation_loop(interval_seconds=600):
    """Runs the scraper immediately and then repeats every interval_seconds (default 10 min)."""
    logger.info(f"Starting eRaktKosh Bangalore Scraping Automation (Cycle: every {interval_seconds // 60} minutes)...")
    while True:
        start_time = time.time()
        try:
            records = scrape_bangalore_snapshot()
            if records:
                write_data_files(records)
            else:
                logger.warning("No records returned from eRaktKosh; skipping file update.")
        except Exception as e:
            logger.error(f"Error in scraping cycle: {e}", exc_info=True)

        elapsed = time.time() - start_time
        sleep_time = max(10, interval_seconds - elapsed)
        next_run = datetime.fromtimestamp(time.time() + sleep_time).strftime("%H:%M:%S")
        logger.info(f"Scraping cycle completed in {elapsed:.1f}s. Next run scheduled at {next_run} (in {int(sleep_time)}s).")
        time.sleep(sleep_time)

def main():
    parser = argparse.ArgumentParser(description="eRaktKosh Bangalore Blood Stock Automated Scraper")
    parser.add_argument("--once", action="store_true", help="Run once and exit immediately (no loop)")
    parser.add_argument("--interval", type=int, default=600, help="Interval between runs in seconds (default: 600 = 10 min)")
    args = parser.parse_args()

    if args.once:
        records = scrape_bangalore_snapshot()
        if records:
            write_data_files(records)
        logger.info("Single scrape completed successfully.")
    else:
        run_automation_loop(interval_seconds=args.interval)

if __name__ == "__main__":
    main()
