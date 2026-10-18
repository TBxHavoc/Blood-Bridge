"""system_config access helpers.

Weights and thresholds are read from the DB, never hard-coded (FR-11). Each key
has a default so the engine works even on a fresh database, but the seeded
values are the source of truth.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SystemConfig

# key -> (default_value, data_type, description)
CONFIG_DEFAULTS: dict[str, tuple[str, str, str]] = {
    "matching.weight_eta": ("50", "integer", "Max points for ETA factor"),
    "matching.weight_expiry": ("30", "integer", "Max points for expiry-suitability factor"),
    "matching.weight_freshness": ("20", "integer", "Max points for data-freshness factor"),
    "matching.max_eta_minutes": ("180", "integer", "ETA (min) at which the ETA factor scores 0"),
    "matching.score_threshold": ("50", "integer", "Best score below this -> PARTIAL shortage"),
    "matching.eta_speed_kmph": ("60", "integer", "Assumed speed to derive ETA from distance"),
    # Bands are ordered, ascending by threshold; the last entry has a null bound.
    "matching.expiry_bands": (
        '[{"max_days": 3, "points": 30}, '
        '{"max_days": 7, "points": 25}, '
        '{"max_days": 30, "points": 15}, '
        '{"max_days": null, "points": 5}]',
        "json",
        "Expiry-suitability points by days-until-expiry",
    ),
    "matching.freshness_bands": (
        '[{"max_hours": 1, "points": 20}, '
        '{"max_hours": 6, "points": 10}, '
        '{"max_hours": 24, "points": 5}, '
        '{"max_hours": null, "points": 0}]',
        "json",
        "Data-freshness points by hours since inventory update",
    ),
    "lifecycle.hold_ttl_minutes": ("10", "integer", "Minutes a reservation stays ACTIVE"),
}


def seed_defaults(db: Session) -> int:
    """Insert any missing config keys. Existing values are left untouched."""
    existing = {row.key for row in db.scalars(select(SystemConfig)).all()}
    added = 0
    for key, (value, data_type, description) in CONFIG_DEFAULTS.items():
        if key in existing:
            continue
        db.add(
            SystemConfig(key=key, value=value, data_type=data_type, description=description)
        )
        added += 1
    db.flush()
    return added


def get_all(db: Session) -> dict[str, str]:
    return {row.key: row.value for row in db.scalars(select(SystemConfig)).all()}


def _raw(db: Session, key: str) -> str | None:
    row = db.get(SystemConfig, key)
    if row is not None:
        return row.value
    default = CONFIG_DEFAULTS.get(key)
    return default[0] if default else None


def get_int(db: Session, key: str, fallback: int | None = None) -> int:
    raw = _raw(db, key)
    if raw is None:
        if fallback is None:
            raise KeyError(f"Unknown config key: {key}")
        return fallback
    return int(raw)


def get_json(db: Session, key: str, fallback: Any = None) -> Any:
    raw = _raw(db, key)
    if raw is None:
        return fallback
    return json.loads(raw)


def set_value(
    db: Session, key: str, value: str, updated_by_user_id: str | None = None
) -> SystemConfig:
    row = db.get(SystemConfig, key)
    if row is None:
        default = CONFIG_DEFAULTS.get(key)
        row = SystemConfig(
            key=key,
            value=value,
            data_type=default[1] if default else "string",
            description=default[2] if default else None,
        )
        db.add(row)
    else:
        row.value = value
        if updated_by_user_id:
            row.updated_by_user_id = updated_by_user_id
    db.flush()
    return row
