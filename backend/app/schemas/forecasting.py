"""
Pydantic Schemas for ML Depletion & Usage Forecasting.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional, Tuple

from pydantic import BaseModel, ConfigDict


class UsageStatisticsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    blood_group: str
    component_type: str
    total_requests: int
    total_units_consumed: int
    observation_days: float
    avg_usage_per_day: float
    weekly_usage: float
    hourly_burn_rate: float
    peak_24h_demand: int
    recent_trend: str


class DepletionPredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    blood_bank_id: str
    blood_bank_code: str
    blood_bank_name: str
    blood_group: str
    component_type: str
    units_available: int
    units_reserved: int
    units_unreserved: int
    avg_usage_per_day: float
    weekly_usage: float
    hours_until_depletion: float
    days_until_depletion: float
    predicted_depletion_timestamp: datetime
    stockout_risk: str
    confidence_interval_hours: Tuple[float, float]
    earliest_batch_expiry: Optional[date] = None
    depletion_cause: str


class ForecastingDashboardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime
    total_inventory_items_monitored: int
    critical_stockouts_count: int
    high_risk_stockouts_count: int
    usage_statistics: List[UsageStatisticsOut]
    depletion_predictions: List[DepletionPredictionOut]
