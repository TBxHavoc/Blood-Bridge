"""Matching orchestration: load config, run the engine, persist results/alerts."""

from __future__ import annotations

import json

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.constants import ALGORITHM_VERSION
from app.core.config_store import get_int, get_json
from app.matching.engine import MatchingSettings, MatchOutcome, match_request
from app.models import Alert, BloodInventory, BloodRequest, MatchingResult, utcnow
from app.services import adapter


def load_settings(db: Session) -> MatchingSettings:
    """Read all weights/thresholds/bands from system_config (never hard-coded)."""
    return MatchingSettings(
        weight_eta=get_int(db, "matching.weight_eta"),
        weight_expiry=get_int(db, "matching.weight_expiry"),
        weight_freshness=get_int(db, "matching.weight_freshness"),
        max_eta_minutes=get_int(db, "matching.max_eta_minutes"),
        score_threshold=get_int(db, "matching.score_threshold"),
        eta_speed_kmph=get_int(db, "matching.eta_speed_kmph"),
        expiry_bands=get_json(db, "matching.expiry_bands"),
        freshness_bands=get_json(db, "matching.freshness_bands"),
        algorithm_version=ALGORITHM_VERSION,
    )


def run_matching(db: Session, request_row: BloodRequest, persist: bool = True) -> MatchOutcome:
    settings = load_settings(db)
    lookup = adapter.build_lookup(db, settings.eta_speed_kmph)
    inventory_rows = db.scalars(
        select(BloodInventory).where(BloodInventory.is_available.is_(True))
    ).all()
    units = adapter.to_supply_units(db, list(inventory_rows))
    request_input = adapter.to_request_input(db, request_row)
    outcome = match_request(request_input, units, lookup, settings, utcnow())
    if persist:
        persist_results(db, request_row, outcome, settings)
    return outcome


def persist_results(
    db: Session,
    request_row: BloodRequest,
    outcome: MatchOutcome,
    settings: MatchingSettings,
) -> None:
    db.execute(
        update(MatchingResult)
        .where(
            MatchingResult.request_id == request_row.id,
            MatchingResult.is_active.is_(True),
        )
        .values(is_active=False)
    )
    weights_json = json.dumps(settings.weights_snapshot())
    for candidate in outcome.matches:
        db.add(
            MatchingResult(
                request_id=request_row.id,
                inventory_id=candidate.inventory.inventory_id,
                match_score=candidate.match_score,
                ranking=candidate.ranking,
                distance_km=candidate.distance_km,
                eta_minutes=candidate.eta_minutes,
                explanation=candidate.explanation,
                algorithm_version=settings.algorithm_version,
                weights_json=weights_json,
            )
        )
    request_row.shortage_type = outcome.shortage_type
    request_row.priority_score = float(request_row.urgency)
    _sync_alert(db, request_row, outcome)
    db.flush()


def _sync_alert(db: Session, request_row: BloodRequest, outcome: MatchOutcome) -> None:
    recipient = request_row.created_by_user_id
    if outcome.shortage_type:
        alert_type = "SHORTAGE_DETECTED"
        message = (
            f"Request {request_row.code}: {outcome.shortage_type.lower()} shortage "
            f"({outcome.eligible_count} eligible unit source(s))."
        )
    elif outcome.matches:
        alert_type = "MATCH_FOUND"
        message = (
            f"Request {request_row.code}: {len(outcome.matches)} matching source(s); "
            f"best score {outcome.matches[0].match_score:.1f}."
        )
    else:
        return

    existing = db.scalar(
        select(Alert).where(
            Alert.request_id == request_row.id,
            Alert.alert_type == alert_type,
            Alert.is_read.is_(False),
        )
    )
    if existing is not None:
        existing.message = message
    else:
        db.add(
            Alert(
                request_id=request_row.id,
                alert_type=alert_type,
                message=message,
                recipient_user_id=recipient,
            )
        )


def priority_ordered_query():
    """Open/held requests ordered by priority: urgency desc, time asc, id asc."""
    return (
        select(BloodRequest)
        .where(BloodRequest.status.in_(("OPEN", "HELD")))
        .order_by(
            BloodRequest.urgency.desc(),
            BloodRequest.request_timestamp.asc(),
            BloodRequest.id.asc(),
        )
    )
