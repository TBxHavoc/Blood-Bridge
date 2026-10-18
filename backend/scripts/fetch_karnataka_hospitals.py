#!/usr/bin/env python3
"""Fetch the Karnataka district-wise hospital registries from data.gov.in.

Pulls three Open Government Data (OGD) datasets and writes them as CSV beside
the other seed data:

    datasets/karnataka/private_hospitals.csv
    datasets/karnataka/public_district_hospitals.csv
    datasets/karnataka/public_general_hospitals.csv

The three sets do not share a schema: the private set uses "hospital_" and
"sl_no" where the public sets use "hospital" and "sl_no_". Column order is
pinned in DATASETS below.

The API key is read from the DATAGOVIN_API_KEY environment variable (or
--api-key) and is never written to disk or committed. Request one from
https://data.gov.in (account menu -> API key).

Usage, from backend/:

    python scripts/fetch_karnataka_hospitals.py
    python scripts/fetch_karnataka_hospitals.py --out-dir datasets/karnataka

The files are reference/seed data, not model inputs: train_model.py reads
datasets/*.csv by exact filename, which is why these live in a sub-directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_ROOT = "https://api.data.gov.in/resource/"
# The OGD API is slow and flaky at large page sizes -- limit=1000 regularly
# times out mid-read -- so default low and page more often. Raise with
# --page-size if your connection is fast.
DEFAULT_PAGE_SIZE = 500
RETRIES = 4
TIMEOUT_SECONDS = 60

# data.gov.in silently drops requests whose User-Agent is the urllib default --
# the connection opens and then never responds, surfacing as a read timeout.
# Any custom agent works, so identify the script honestly.
USER_AGENT = "bloodbridge-fetch/1.0 (+https://github.com/TBxHavoc/Blood-Bridge)"

# filename -> (OGD resource id, columns). The column order is pinned rather
# than taken from the response so re-fetches produce stable diffs, and because
# the three datasets disagree on field names ("hospital_" vs "hospital",
# "sl_no" vs "sl_no_") -- do not assume a shared schema when merging them.
DATASETS: dict[str, tuple[str, list[str]]] = {
    "private_hospitals.csv": (
        "c58188bb-aa22-42b2-8030-8b82f4f008b4",
        ["sl_no", "hospital_", "taluk", "district"],
    ),
    "public_district_hospitals.csv": (
        "6333b313-93f1-4dfc-a73c-10b029ad71b0",
        ["sl_no", "district_name", "hospital", "type_of_facility"],
    ),
    "public_general_hospitals.csv": (
        "380a2699-9106-4fed-9e62-92c0d1439625",
        ["sl_no_", "district_name", "hospital", "type_of_facility"],
    ),
}


def clean(value: object) -> str:
    """Trim and collapse internal whitespace.

    data.gov.in stores a handful of hospital names with embedded newlines and
    doubled spaces. Left as-is they push the file's line count above its row
    count (the private set is 1549 lines for 1543 records) and break any
    line-oriented tooling.
    """
    if value is None:
        return ""
    return " ".join(str(value).split())


def fetch_page(resource_id: str, api_key: str, offset: int, page_size: int) -> dict:
    """One page of a resource, retried on transient network/JSON failures."""
    url = (
        f"{API_ROOT}{resource_id}"
        f"?api-key={api_key}&format=json&limit={page_size}&offset={offset}"
    )
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
            )
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < RETRIES:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"failed after {RETRIES} attempts ({last_error})")


def fetch_dataset(
    resource_id: str, columns: list[str], api_key: str, page_size: int
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    offset = 0
    total: int | None = None

    while True:
        payload = fetch_page(resource_id, api_key, offset, page_size)
        if total is None:
            total = int(payload.get("total", 0))

        records = payload.get("records") or []
        if not records:
            break

        if offset == 0:
            returned = set(records[0])
            extra = sorted(returned - set(columns))
            missing = sorted(set(columns) - returned)
            if extra or missing:
                print(f"    note: schema drift extra={extra} missing={missing}")

        for record in records:
            rows.append({column: clean(record.get(column, "")) for column in columns})

        offset += page_size
        print(f"    {len(rows):>5}/{total} rows", flush=True)
        if len(records) < page_size or (total and offset >= total):
            break
        time.sleep(0.5)  # be gentle with a public API

    return rows


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, restval="", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("DATAGOVIN_API_KEY", ""),
        help="data.gov.in API key (default: $DATAGOVIN_API_KEY)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "datasets" / "karnataka",
        help="directory for the CSVs (default: backend/datasets/karnataka)",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"records per API request (default: {DEFAULT_PAGE_SIZE})",
    )
    args = parser.parse_args(argv)

    api_key = args.api_key.strip()
    if not api_key:
        print(
            "error: no data.gov.in API key.\n"
            "Set DATAGOVIN_API_KEY in the environment, or pass --api-key.\n"
            "Get one from https://data.gov.in (account menu -> API key).",
            file=sys.stderr,
        )
        return 2

    failures = 0
    for filename, (resource_id, columns) in DATASETS.items():
        print(f"{filename} ...", flush=True)
        try:
            rows = fetch_dataset(resource_id, columns, api_key, args.page_size)
        except RuntimeError as exc:
            print(f"    FAILED: {exc}", file=sys.stderr)
            failures += 1
            continue

        path = args.out_dir / filename
        write_csv(path, columns, rows)
        print(f"    {len(rows):>5} rows -> {path}")

    if failures:
        print(f"{failures} dataset(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
