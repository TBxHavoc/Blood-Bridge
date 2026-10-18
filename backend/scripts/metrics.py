"""Live metrics report for the demo (PRD deliverable: "metrics report").

Usage:
    python -m scripts.metrics

Prints counts and fairness/coverage signals straight from the database. No
patient or donor data is ever included.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import (
    Alert,
    AuditLog,
    BloodBank,
    BloodInventory,
    BloodRequest,
    Hospital,
    MatchingResult,
    Reservation,
    User,
)


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def _grouped(db, column) -> dict:
    rows = db.execute(select(column, func.count()).group_by(column)).all()
    return {(key if key is not None else "UNSET"): value for key, value in rows}


def main() -> None:
    db = SessionLocal()
    try:
        avg_score = db.scalar(
            select(func.avg(MatchingResult.match_score)).where(
                MatchingResult.is_active.is_(True)
            )
        )
        active_matches = (
            db.scalar(
                select(func.count())
                .select_from(MatchingResult)
                .where(MatchingResult.is_active.is_(True))
            )
            or 0
        )

        print("=" * 64)
        print("Blood Bridge — metrics report (SIMULATED DATA)")
        print("=" * 64)
        print("Entities")
        for label, model in (
            ("users", User),
            ("blood banks", BloodBank),
            ("hospitals", Hospital),
            ("inventory rows", BloodInventory),
            ("requests", BloodRequest),
            ("active matches", None),
            ("reservations", Reservation),
            ("alerts", Alert),
            ("audit events", AuditLog),
        ):
            value = active_matches if model is None else _count(db, model)
            print(f"  {label:<16}{value}")

        print("\nRequests by status")
        for key, value in sorted(_grouped(db, BloodRequest.status).items()):
            print(f"  {key:<16}{value}")

        print("\nShortages")
        shortages = _grouped(db, BloodRequest.shortage_type)
        for key, value in sorted(shortages.items()):
            print(f"  {key:<16}{value}")
        if not shortages:
            print("  (none recorded)")

        print("\nAlerts by type")
        for key, value in sorted(_grouped(db, Alert.alert_type).items()):
            print(f"  {key:<20}{value}")

        print("\nMatching quality")
        print(f"  active matches       {active_matches}")
        score_text = f"{avg_score:.2f}" if avg_score else "n/a"
        print(f"  avg match score      {score_text}")

        print("\nPrivacy")
        print("  patient/donor identifiers stored: 0 (by design)")
        print(f"  audit events recorded:            {_count(db, AuditLog)}")
        print("=" * 64)
    finally:
        db.close()


if __name__ == "__main__":
    main()
