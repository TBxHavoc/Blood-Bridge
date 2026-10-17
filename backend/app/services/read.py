"""Read helpers that join rows into API response shapes."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BloodBank, BloodInventory, BloodRequest, MatchingResult
from app.schemas.request import MatchOut, RequestOut


def active_matches(db: Session, request_id: str) -> list[MatchOut]:
    rows = db.execute(
        select(MatchingResult, BloodInventory, BloodBank)
        .join(BloodInventory, MatchingResult.inventory_id == BloodInventory.id)
        .join(BloodBank, BloodInventory.blood_bank_id == BloodBank.id)
        .where(
            MatchingResult.request_id == request_id,
            MatchingResult.is_active.is_(True),
        )
        .order_by(MatchingResult.ranking.asc())
    ).all()
    return [
        MatchOut(
            inventory_id=inventory.id,
            inventory_code=inventory.code,
            blood_bank_id=bank.id,
            blood_bank_name=bank.name,
            blood_group=inventory.blood_group,
            component_type=inventory.component_type,
            expiry_date=inventory.expiry_date,
            units_available=inventory.units_available,
            units_reserved=inventory.units_reserved,
            ranking=result.ranking,
            match_score=result.match_score,
            distance_km=result.distance_km,
            eta_minutes=result.eta_minutes,
            explanation=result.explanation,
        )
        for result, inventory, bank in rows
    ]


def request_out(db: Session, request: BloodRequest, with_matches: bool = True) -> RequestOut:
    out = RequestOut.model_validate(request)
    if with_matches:
        out.matches = active_matches(db, request.id)
    return out
