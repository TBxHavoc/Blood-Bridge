"""Fairness + transparency report (FR-21, success metric 4)."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, BloodRequest, Hospital, utcnow

SCORING_INPUTS = (
    "blood_group_compatibility",
    "component_type",
    "request_urgency",
    "request_wait_time",
    "eta_minutes",
    "expiry_suitability",
    "data_freshness",
)


def _priority_ordering(requests: list[BloodRequest]) -> dict:
    """Among FULFILLED requests of equal urgency, service order should follow wait time."""
    groups: dict[int, list[BloodRequest]] = defaultdict(list)
    for row in requests:
        if row.status == "FULFILLED":
            groups[row.urgency].append(row)
    honored = total = 0
    for group in groups.values():
        ordered = sorted(group, key=lambda r: r.request_timestamp)
        for earlier, later in zip(ordered, ordered[1:], strict=False):
            total += 1
            served_earlier = earlier.updated_at or earlier.request_timestamp
            served_later = later.updated_at or later.request_timestamp
            if served_earlier <= served_later:
                honored += 1
    return {
        "equal_urgency_pairs": total,
        "honored": honored,
        "score": round(honored / total, 3) if total else 1.0,
    }


def build_fairness_report(db: Session) -> dict:
    requests = db.scalars(select(BloodRequest)).all()
    hospitals = {h.id: h for h in db.scalars(select(Hospital)).all()}

    by_status: dict[str, int] = {}
    by_urgency: dict[str, int] = {}
    shortages: dict[str, int] = {}
    per_hospital: dict[str, dict] = defaultdict(
        lambda: {"requests": 0, "fulfilled": 0, "minutes": []}
    )

    for row in requests:
        by_status[row.status] = by_status.get(row.status, 0) + 1
        by_urgency[str(row.urgency)] = by_urgency.get(str(row.urgency), 0) + 1
        if row.shortage_type:
            shortages[row.shortage_type] = shortages.get(row.shortage_type, 0) + 1
        agg = per_hospital[row.hospital_id]
        agg["requests"] += 1
        if row.status == "FULFILLED":
            agg["fulfilled"] += 1
            if row.updated_at and row.request_timestamp:
                agg["minutes"].append(
                    (row.updated_at - row.request_timestamp).total_seconds() / 60
                )

    by_hospital = []
    for hospital_id, agg in per_hospital.items():
        minutes = agg["minutes"]
        by_hospital.append(
            {
                "hospital_id": hospital_id,
                "hospital_code": hospitals[hospital_id].code if hospital_id in hospitals else None,
                "requests": agg["requests"],
                "fulfilled": agg["fulfilled"],
                "avg_minutes_to_fulfil": (
                    round(sum(minutes) / len(minutes), 1) if minutes else None
                ),
            }
        )
    by_hospital.sort(key=lambda row: (-row["requests"], row["hospital_id"]))

    alert_counts: dict[str, int] = {}
    for alert in db.scalars(select(Alert)).all():
        alert_counts[alert.alert_type] = alert_counts.get(alert.alert_type, 0) + 1

    return {
        "generated_at": utcnow().isoformat(),
        "totals": {
            "requests": len(requests),
            "by_status": by_status,
            "by_urgency": by_urgency,
            "shortages": shortages,
        },
        "alerts": alert_counts,
        "by_hospital": by_hospital,
        "priority_ordering": _priority_ordering(requests),
        "scoring_inputs": list(SCORING_INPUTS),
        "note": (
            "Scoring uses clinical inputs only; money, hospital size and influence "
            "are never inputs."
        ),
    }
