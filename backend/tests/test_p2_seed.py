"""P2: synthetic data generation and config seeding."""

from __future__ import annotations

import random
from datetime import date, datetime

from app.constants import BLOOD_GROUPS, COMPONENT_TYPES
from app.core.config_store import CONFIG_DEFAULTS, get_all, seed_defaults
from app.seed import generate


def test_generate_blood_banks() -> None:
    random.seed(1)
    banks = generate.generate_blood_banks(20)
    assert len(banks) == 20
    assert banks[0]["code"] == "BB_001"
    assert len({b["code"] for b in banks}) == 20


def test_generate_inventory_satisfies_constraints() -> None:
    random.seed(2)
    banks = generate.generate_blood_banks(20)
    inventory = generate.generate_inventory(banks, today=date(2026, 10, 17))
    assert 100 <= len(inventory) <= 160
    for row in inventory:
        assert row["blood_group"] in BLOOD_GROUPS
        assert row["component_type"] in COMPONENT_TYPES
        assert row["units_available"] >= row["units_reserved"] >= 0
        assert row["expiry_date"] > row["collection_date"]


def test_haversine_known_distance() -> None:
    # Mumbai -> Delhi straight line is ~1150 km.
    km = generate.haversine_km(19.0760, 72.8777, 28.6139, 77.2090)
    assert 1100 <= km <= 1250


def test_generate_distances_covers_all_pairs() -> None:
    random.seed(3)
    hospitals = generate.generate_hospitals(10)
    banks = generate.generate_blood_banks(20)
    distances = generate.generate_distances(hospitals, banks)
    assert len(distances) == 200
    assert all(d["eta_minutes"] >= 1 for d in distances)


def test_generate_requests_valid() -> None:
    random.seed(4)
    hospitals = generate.generate_hospitals(10)
    requests = generate.generate_requests(hospitals, 40, now=datetime(2026, 10, 17, 12, 0))
    assert len(requests) == 40
    for row in requests:
        assert 1 <= row["urgency"] <= 5
        assert row["quantity_units"] > 0
        assert row["status"] in {"OPEN", "FULFILLED", "CANCELLED", "EXPIRED"}


def test_config_defaults_seeded(db) -> None:
    seed_defaults(db)
    values = get_all(db)
    for key in CONFIG_DEFAULTS:
        assert key in values
    assert values["matching.weight_eta"] == "50"
