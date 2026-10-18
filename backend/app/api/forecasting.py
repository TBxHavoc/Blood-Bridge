"""
Forecasting and Depletion API Router.
Predicts blood supply stockouts, runout times, and daily/weekly consumption velocities.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.envelope import envelope
from app.database import get_db
from app.models import BloodBank, BloodInventory, BloodRequest, User
from app.schemas.forecasting import (
    DepletionPredictionOut,
    ForecastingDashboardOut,
    UsageStatisticsOut,
)
from app.services.forecasting import BloodDepletionPredictor

router = APIRouter(prefix="/forecasting", tags=["forecasting"])

_predictor = BloodDepletionPredictor()


def _load_db_state(db: Session):
    """Fetches inventory, requests, and blood bank metadata from the database."""
    # Blood Requests
    req_rows = db.scalars(select(BloodRequest)).all()
    requests_data = [
        {
            "id": r.id,
            "blood_group": r.blood_group,
            "component_type": r.component_type,
            "quantity_units": r.quantity_units,
            "status": r.status,
            "request_timestamp": r.request_timestamp,
        }
        for r in req_rows
    ]

    # Inventory
    inv_rows = db.scalars(select(BloodInventory)).all()
    inventory_data = [
        {
            "id": i.id,
            "blood_bank_id": i.blood_bank_id,
            "blood_group": i.blood_group,
            "component_type": i.component_type,
            "units_available": i.units_available,
            "units_reserved": i.units_reserved,
            "collection_date": i.collection_date,
            "expiry_date": i.expiry_date,
            "is_available": i.is_available,
        }
        for i in inv_rows
    ]

    # Blood Banks mapping
    bank_rows = db.scalars(select(BloodBank)).all()
    banks_map = {
        b.id: {"code": b.code, "name": b.name, "city": b.city}
        for b in bank_rows
    }

    return requests_data, inventory_data, banks_map


@router.get("/usage")
def get_usage_statistics(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Returns average daily usage and weekly usage per blood group and component.
    Derived from historical clinical blood request records.
    """
    requests_data, _, _ = _load_db_state(db)
    now = datetime.now(UTC).replace(tzinfo=None)
    usage_map = _predictor.calculate_usage_statistics(requests_data, reference_time=now)

    out = [
        UsageStatisticsOut(
            blood_group=stat.blood_group,
            component_type=stat.component_type,
            total_requests=stat.total_requests,
            total_units_consumed=stat.total_units_consumed,
            observation_days=stat.observation_days,
            avg_usage_per_day=stat.avg_usage_per_day,
            weekly_usage=stat.weekly_usage,
            hourly_burn_rate=stat.hourly_burn_rate,
            peak_24h_demand=stat.peak_24h_demand,
            recent_trend=stat.recent_trend,
        ).model_dump()
        for stat in usage_map.values()
    ]
    return envelope(out)


@router.get("/depletion")
def get_depletion_forecast(
    blood_group: Optional[str] = None,
    component_type: Optional[str] = None,
    blood_bank_id: Optional[str] = None,
    risk_tier: Optional[str] = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Predicts the exact time when blood banks might run out of particular blood type supplies.
    Simulates inventory burn rates and flags critical stockout risks.
    """
    requests_data, inventory_data, banks_map = _load_db_state(db)
    now = datetime.now(UTC).replace(tzinfo=None)

    predictions = _predictor.predict_inventory_depletion(
        inventory_records=inventory_data,
        requests=requests_data,
        blood_banks_map=banks_map,
        reference_time=now,
    )

    # Apply filters
    filtered = predictions
    if blood_group:
        filtered = [p for p in filtered if p.blood_group == blood_group.upper()]
    if component_type:
        filtered = [p for p in filtered if component_type.upper() in p.component_type.upper()]
    if blood_bank_id:
        filtered = [p for p in filtered if p.blood_bank_id == blood_bank_id or p.blood_bank_code == blood_bank_id]
    if risk_tier:
        filtered = [p for p in filtered if p.stockout_risk == risk_tier.upper()]

    out = [
        DepletionPredictionOut(
            blood_bank_id=p.blood_bank_id,
            blood_bank_code=p.blood_bank_code,
            blood_bank_name=p.blood_bank_name,
            blood_group=p.blood_group,
            component_type=p.component_type,
            units_available=p.units_available,
            units_reserved=p.units_reserved,
            units_unreserved=p.units_unreserved,
            avg_usage_per_day=p.avg_usage_per_day,
            weekly_usage=p.weekly_usage,
            hours_until_depletion=p.hours_until_depletion,
            days_until_depletion=p.days_until_depletion,
            predicted_depletion_timestamp=p.predicted_depletion_timestamp,
            stockout_risk=p.stockout_risk,
            confidence_interval_hours=p.confidence_interval_hours,
            earliest_batch_expiry=p.earliest_batch_expiry,
            depletion_cause=p.depletion_cause,
            model_source=getattr(p, "model_source", "Heuristic Simulation"),
        ).model_dump()
        for p in filtered
    ]
    return envelope(out)


@router.get("/summary")
def get_forecasting_summary(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Returns an executive dashboard view with overall usage statistics
    and high-priority stockout depletion alerts.
    """
    requests_data, inventory_data, banks_map = _load_db_state(db)
    now = datetime.now(UTC).replace(tzinfo=None)

    usage_map = _predictor.calculate_usage_statistics(requests_data, reference_time=now)
    predictions = _predictor.predict_inventory_depletion(
        inventory_records=inventory_data,
        requests=requests_data,
        blood_banks_map=banks_map,
        reference_time=now,
    )

    critical_count = sum(1 for p in predictions if p.stockout_risk in ("CRITICAL", "IMMEDIATE_EMPTY"))
    high_count = sum(1 for p in predictions if p.stockout_risk == "HIGH")

    dashboard = ForecastingDashboardOut(
        generated_at=now,
        ml_model_loaded=_predictor.has_ml_model,
        model_path=_predictor.model_path,
        total_inventory_items_monitored=len(predictions),
        critical_stockouts_count=critical_count,
        high_risk_stockouts_count=high_count,
        usage_statistics=[
            UsageStatisticsOut(
                blood_group=s.blood_group,
                component_type=s.component_type,
                total_requests=s.total_requests,
                total_units_consumed=s.total_units_consumed,
                observation_days=s.observation_days,
                avg_usage_per_day=s.avg_usage_per_day,
                weekly_usage=s.weekly_usage,
                hourly_burn_rate=s.hourly_burn_rate,
                peak_24h_demand=s.peak_24h_demand,
                recent_trend=s.recent_trend,
            )
            for s in usage_map.values()
        ],
        depletion_predictions=[
            DepletionPredictionOut(
                blood_bank_id=p.blood_bank_id,
                blood_bank_code=p.blood_bank_code,
                blood_bank_name=p.blood_bank_name,
                blood_group=p.blood_group,
                component_type=p.component_type,
                units_available=p.units_available,
                units_reserved=p.units_reserved,
                units_unreserved=p.units_unreserved,
                avg_usage_per_day=p.avg_usage_per_day,
                weekly_usage=p.weekly_usage,
                hours_until_depletion=p.hours_until_depletion,
                days_until_depletion=p.days_until_depletion,
                predicted_depletion_timestamp=p.predicted_depletion_timestamp,
                stockout_risk=p.stockout_risk,
                confidence_interval_hours=p.confidence_interval_hours,
                earliest_batch_expiry=p.earliest_batch_expiry,
                depletion_cause=p.depletion_cause,
                model_source=getattr(p, "model_source", "Heuristic Simulation"),
            )
            for p in predictions[:10]  # Top 10 most imminent stockouts
        ],
    )
    return envelope(dashboard.model_dump())

