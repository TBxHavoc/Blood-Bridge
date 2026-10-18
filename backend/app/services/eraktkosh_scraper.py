"""eRaktKosh Automated Blood Stock Scraper Service for Bengaluru.

Runs automatically as an asynchronous background worker inside the FastAPI backend.
- Scrapes all 14 blood components across Bangalore Urban and Rural districts.
- Extracts per-blood-group inventories (A+, A-, B+, B-, O+, O-, AB+, AB-).
- Atomically overwrites separate data files for each blood group every 10 minutes.
- Also exposes on-demand single scrape triggering.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scrapling import Fetcher

logger = logging.getLogger("bloodbridge.eraktkosh")

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
    {"key": "A_positive", "label": "A+", "canonical": "A+Ve"},
    {"key": "A_negative", "label": "A-", "canonical": "A-Ve"},
    {"key": "B_positive", "label": "B+", "canonical": "B+Ve"},
    {"key": "B_negative", "label": "B-", "canonical": "B-Ve"},
    {"key": "O_positive", "label": "O+", "canonical": "O+Ve"},
    {"key": "O_negative", "label": "O-", "canonical": "O-Ve"},
    {"key": "AB_positive", "label": "AB+", "canonical": "AB+Ve"},
    {"key": "AB_negative", "label": "AB-", "canonical": "AB-Ve"},
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_DIRS = [
    PROJECT_ROOT / "data" / "eraktkosh",
    PROJECT_ROOT / "frontend" / "public" / "data" / "eraktkosh",
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
            if char == "\\":
                out.append(char)
                escaped = True
                continue
            if char == '"':
                out.append(char)
                in_string = False
                continue
            code = ord(char)
            if code < 0x20:
                if code == 0x0A:
                    out.append("\\n")
                elif code == 0x0D:
                    out.append("\\r")
                elif code == 0x09:
                    out.append("\\t")
                else:
                    out.append(f"\\u{code:04x}")
                continue
            out.append(char)
            continue
        if char == '"':
            in_string = True
        out.append(char)
    return "".join(out)


def strip_tags(text: str) -> str:
    text = re.sub(r"<br\s*/?>", " | ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text, flags=re.I)
    text = re.sub(r"&amp;", "&", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_contact(contact_raw: str) -> dict[str, str]:
    parts = [p.strip() for p in contact_raw.split("<br/>") if p.strip()]
    name = parts[0] if len(parts) > 0 else ""
    address = parts[1] if len(parts) > 1 else ""
    contact_info = parts[2] if len(parts) > 2 else ""

    phone, email, fax = "", "", ""
    m_phone = re.search(r"Phone:\s*([^,]+)", contact_info, re.I)
    if m_phone:
        p = m_phone.group(1).strip()
        if p not in ["-", "N/A", "NA"]:
            phone = p

    m_fax = re.search(r"Fax:\s*([^,]+)", contact_info, re.I)
    if m_fax:
        f = m_fax.group(1).strip()
        if f not in ["-", "N/A", "NA"]:
            fax = f

    m_email = re.search(r"Email:\s*([^\s,]+)", contact_info, re.I)
    if m_email:
        e = m_email.group(1).strip()
        if e not in ["-", "N/A", "NA"]:
            email = e

    return {
        "name": name,
        "address": address,
        "phone": phone,
        "fax": fax,
        "email": email,
    }


def parse_stock_cell(avail_html: str) -> dict[str, Any]:
    is_available = "Available" in avail_html and "Not Available" not in avail_html
    groups = {}
    for match in re.finditer(r"([A-Za-z0-9+-]+Ve)\s*:\s*(\d+)", avail_html, re.I):
        label = match.group(1).upper()
        if label.endswith("VE"):
            label = label[:-2] + "Ve"
        groups[label] = int(match.group(2))
    return {
        "is_available": is_available,
        "groups": groups,
        "raw_status": strip_tags(avail_html),
    }


def scrape_bangalore_snapshot() -> list[dict[str, Any]]:
    """Crawls eRaktKosh endpoints for Bangalore Urban and Rural."""
    raw_records = []
    logger.info("Starting eRaktKosh crawl for Bengaluru stock...")

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
                        "type": row[5],
                    })
            except Exception as e:
                logger.warning("Error scraping %s comp %s (%d): %s", dist_name, comp_name, comp_code, e)

    logger.info("Crawl complete: fetched %d component records for Bengaluru.", len(raw_records))
    return raw_records


def write_data_files(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Generates per-blood-group files and overall summary."""
    now_iso = datetime.now(timezone.utc).isoformat()
    now_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for out_dir in OUTPUT_DIRS:
        out_dir.mkdir(parents=True, exist_ok=True)

    summary_stats: dict[str, Any] = {
        "last_updated": now_local,
        "last_updated_iso": now_iso,
        "total_records_scanned": len(records),
        "blood_groups": {},
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
        "type",
    ]

    for bg in BLOOD_GROUPS:
        key = bg["key"]
        label = bg["label"]
        canonical_label = bg["canonical"]

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
                    "all_groups": r["groups"],
                }
                group_rows.append(row_copy)

        group_rows.sort(key=lambda x: x["units"], reverse=True)
        total_units = sum(r["units"] for r in group_rows)
        unique_banks = len(set(r["blood_bank_name"] for r in group_rows))

        summary_stats["blood_groups"][label] = {
            "key": key,
            "total_units": total_units,
            "unique_banks": unique_banks,
            "record_count": len(group_rows),
            "file_json": f"{key}.json",
            "file_csv": f"{key}.csv",
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
            "data": group_rows,
        }

        for out_dir in OUTPUT_DIRS:
            json_file = out_dir / f"{key}.json"
            csv_file = out_dir / f"{key}.csv"

            temp_json = out_dir / f"{key}.tmp.json"
            with open(temp_json, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            temp_json.replace(json_file)

            temp_csv = out_dir / f"{key}.tmp.csv"
            with open(temp_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for gr in group_rows:
                    writer.writerow(gr)
            temp_csv.replace(csv_file)

    for out_dir in OUTPUT_DIRS:
        summary_file = out_dir / "summary.json"
        temp_summary = out_dir / "summary.tmp.json"
        with open(temp_summary, "w", encoding="utf-8") as f:
            json.dump(summary_stats, f, indent=2)
        temp_summary.replace(summary_file)

    logger.info("Successfully updated eRaktKosh Bengaluru files for all 8 blood groups.")
    return summary_stats


def run_single_scrape() -> dict[str, Any]:
    """Runs a single scraping cycle and returns the summary."""
    records = scrape_bangalore_snapshot()
    if records:
        return write_data_files(records)
    return {"error": "No records fetched from eRaktKosh"}


async def eraktkosh_background_loop(interval_seconds: int = 600) -> None:
    """Automatic background worker: scrapes immediately on startup and repeats every interval_seconds."""
    logger.info(
        "Starting eRaktKosh automated background loop (every %d seconds / %d minutes)...",
        interval_seconds,
        interval_seconds // 60,
    )
    # Small initial pause so app startup finishes cleanly
    await asyncio.sleep(2)

    while True:
        start_time = time.time()
        try:
            logger.info("Triggering scheduled eRaktKosh Bengaluru scrape...")
            summary = await asyncio.to_thread(run_single_scrape)
            elapsed = time.time() - start_time
            logger.info("Scheduled scrape finished in %.1fs.", elapsed)
        except asyncio.CancelledError:
            logger.info("eRaktKosh background worker cancelled; shutting down.")
            break
        except Exception:
            logger.exception("Unexpected error in eRaktKosh background worker.")

        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("eRaktKosh background worker sleep interrupted; exiting.")
            break


_worker_task: asyncio.Task | None = None


def start_eraktkosh_background_worker(interval_seconds: int = 600) -> asyncio.Task:
    """Spawns the background scraper task inside the current asyncio event loop."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(
            eraktkosh_background_loop(interval_seconds=interval_seconds),
            name="eraktkosh_background_worker"
        )
    return _worker_task


async def stop_eraktkosh_background_worker() -> None:
    """Cancels and awaits the background scraper task."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="eRaktKosh Scraper Service")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=600, help="Interval in seconds (default 600)")
    args = parser.parse_args()

    if args.once:
        run_single_scrape()
    else:
        asyncio.run(eraktkosh_background_loop(interval_seconds=args.interval))


if __name__ == "__main__":
    main()
