"""eRaktKosh live blood stock API endpoints for Bangalore."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.envelope import envelope

router = APIRouter(prefix="/eraktkosh", tags=["eRaktKosh"])

# Path to the scraped data folder
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "eraktkosh"

BLOOD_GROUP_KEY_MAP = {
    "A+": "A_positive",
    "A-": "A_negative",
    "B+": "B_positive",
    "B-": "B_negative",
    "O+": "O_positive",
    "O-": "O_negative",
    "AB+": "AB_positive",
    "AB-": "AB_negative",
    "A_POS": "A_positive",
    "A_NEG": "A_negative",
    "B_POS": "B_positive",
    "B_NEG": "B_negative",
    "O_POS": "O_positive",
    "O_NEG": "O_negative",
    "AB_POS": "AB_positive",
    "AB_NEG": "AB_negative",
    "A_POSITIVE": "A_positive",
    "A_NEGATIVE": "A_negative",
    "B_POSITIVE": "B_positive",
    "B_NEGATIVE": "B_negative",
    "O_POSITIVE": "O_positive",
    "O_NEGATIVE": "O_negative",
    "AB_POSITIVE": "AB_positive",
    "AB_NEGATIVE": "AB_negative",
}

@router.get("/summary")
async def get_eraktkosh_summary() -> dict[str, Any]:
    """Returns the latest eRaktKosh scrape summary for Bengaluru."""
    summary_file = DATA_DIR / "summary.json"
    if not summary_file.exists():
        raise HTTPException(
            status_code=404,
            detail="eRaktKosh scraped data not found. Please ensure the automation scraper has run."
        )
    try:
        with open(summary_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return envelope(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read summary data: {e}")

@router.get("/bangalore/{blood_group}")
async def get_bangalore_blood_stock(
    blood_group: str,
    component: str | None = Query(None, description="Optional filter by component type")
) -> dict[str, Any]:
    """Returns the live scraped eRaktKosh blood stock for a specific blood group in Bengaluru."""
    clean_group = blood_group.strip().upper().replace(" ", "_")
    key = BLOOD_GROUP_KEY_MAP.get(clean_group)
    if not key:
        # Try direct key
        key = clean_group.lower()

    target_file = DATA_DIR / f"{key}.json"
    if not target_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No scraped data found for blood group '{blood_group}' (key: {key})."
        )

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if component:
            comp_lower = component.lower()
            data["data"] = [
                r for r in data.get("data", [])
                if comp_lower in r.get("component", "").lower()
            ]
            data["filtered_record_count"] = len(data["data"])
            data["filtered_units"] = sum(r.get("units", 0) for r in data["data"])

        return envelope(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read blood group data: {e}")
