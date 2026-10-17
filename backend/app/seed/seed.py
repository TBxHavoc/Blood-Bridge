"""Seed script: generates synthetic datasets, writes CSV, loads the database.

Usage:
    python -m app.seed.seed                 # reset + reload with defaults
    python -m app.seed.seed --no-reset      # add without wiping
    python -m app.seed.seed --no-csv        # skip CSV output
    python -m app.seed.seed --requests 60

All data is SIMULATED FOR DEMONSTRATION PURPOSES.
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from sqlalchemy import delete

from app.config import settings
from app.core.config_store import seed_defaults
from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import (
    Alert,
    AuditLog,
    BloodBank,
    BloodInventory,
    BloodRequest,
    Hospital,
    LocationDistance,
    MatchingResult,
    Reservation,
    SystemConfig,
    User,
)
from app.seed import generate

DATASETS_DIR = Path(__file__).resolve().parents[2] / "datasets"

RESET_ORDER = [
    MatchingResult,
    Reservation,
    Alert,
    AuditLog,
    BloodRequest,
    BloodInventory,
    LocationDistance,
    Hospital,
    BloodBank,
    User,
    SystemConfig,
]


def _reset(db) -> None:
    for model in RESET_ORDER:
        db.execute(delete(model))
    db.flush()


def _write_csv(name: str, rows: list[dict]) -> None:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    path = DATASETS_DIR / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def seed(
    *,
    banks: int = 20,
    hospitals: int = 10,
    requests: int = 40,
    random_seed: int = 42,
    reset: bool = True,
    write_csv: bool = True,
) -> dict[str, int]:
    random.seed(random_seed)
    Base.metadata.create_all(bind=engine)

    bank_rows = generate.generate_blood_banks(banks)
    hospital_rows = generate.generate_hospitals(hospitals)
    inventory_rows = generate.generate_inventory(bank_rows)
    request_rows = generate.generate_requests(hospital_rows, requests)
    distance_rows = generate.generate_distances(hospital_rows, bank_rows)

    if write_csv:
        _write_csv("blood_banks", bank_rows)
        _write_csv("hospitals", hospital_rows)
        _write_csv("blood_inventory", inventory_rows)
        _write_csv("blood_requests", request_rows)
        _write_csv("location_distances", distance_rows)

    db = SessionLocal()
    try:
        if reset:
            _reset(db)

        # --- Banks + hospitals (flush to obtain ids) ---
        banks_by_code: dict[str, str] = {}
        for row in bank_rows:
            bank = BloodBank(**row)
            db.add(bank)
            db.flush()
            banks_by_code[row["code"]] = bank.id

        hospitals_by_code: dict[str, str] = {}
        for row in hospital_rows:
            hospital = Hospital(**row)
            db.add(hospital)
            db.flush()
            hospitals_by_code[row["code"]] = hospital.id

        # --- Demo users: admin, auditor, one per hospital, one per bank ---
        pwd = hash_password(settings.seed_password)
        users: list[User] = [
            User(username="_admin", email="admin@bloodbridge.test", password_hash=pwd,
                 role="admin", affiliated_org_id=None),
            User(username="_auditor", email="auditor@bloodbridge.test", password_hash=pwd,
                 role="auditor", affiliated_org_id=None),
        ]
        hospital_user_by_code: dict[str, str] = {}
        for code, org_id in hospitals_by_code.items():
            user = User(
                username=f"hospital_{code.lower()}",
                email=f"{code.lower()}@hospital.test",
                password_hash=pwd,
                role="hospital_user",
                affiliated_org_id=org_id,
            )
            db.add(user)
            db.flush()
            hospital_user_by_code[code] = user.id
            users.append(user)
        for code, org_id in banks_by_code.items():
            user = User(
                username=f"bank_{code.lower()}",
                email=f"{code.lower()}@bank.test",
                password_hash=pwd,
                role="bloodbank_user",
                affiliated_org_id=org_id,
            )
            db.add(user)
            users.append(user)
        db.flush()
        admin = users[0]

        # --- Inventory ---
        for row in inventory_rows:
            data = dict(row)
            data["blood_bank_id"] = banks_by_code[data.pop("blood_bank_code")]
            db.add(BloodInventory(**data))

        # --- Historical requests ---
        for row in request_rows:
            data = dict(row)
            hospital_code = data.pop("hospital_code")
            data["hospital_id"] = hospitals_by_code[hospital_code]
            data["created_by_user_id"] = hospital_user_by_code.get(hospital_code, admin.id)
            db.add(BloodRequest(**data))

        # --- Distances (stored using human codes) ---
        for row in distance_rows:
            db.add(LocationDistance(**row))

        added = seed_defaults(db)
        db.commit()

        counts = {
            "users": len(users),
            "blood_banks": len(bank_rows),
            "hospitals": len(hospital_rows),
            "blood_inventory": len(inventory_rows),
            "blood_requests": len(request_rows),
            "location_distances": len(distance_rows),
            "config_keys_added": added,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Blood Bridge synthetic data.")
    parser.add_argument("--banks", type=int, default=20)
    parser.add_argument("--hospitals", type=int, default=10)
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-reset", action="store_true")
    parser.add_argument("--no-csv", action="store_true")
    args = parser.parse_args()

    counts = seed(
        banks=args.banks,
        hospitals=args.hospitals,
        requests=args.requests,
        random_seed=args.seed,
        reset=not args.no_reset,
        write_csv=not args.no_csv,
    )
    print("Seeded (SIMULATED FOR DEMONSTRATION PURPOSES):")
    for key, value in counts.items():
        print(f"  {key}: {value}")
    print(f"\nDemo password: {settings.seed_password}")
    print("Users: _admin, _auditor, hospital_h_001.., bank_bb_001..")


if __name__ == "__main__":
    main()
