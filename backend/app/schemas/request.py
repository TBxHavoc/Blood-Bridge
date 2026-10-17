"""Request and matching-result schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants import BLOOD_GROUPS, COMPONENT_TYPES


class RequestCreate(BaseModel):
    blood_group: str
    component_type: str
    quantity_units: int = Field(gt=0, le=100)
    urgency: int = Field(ge=1, le=5)
    required_by_timestamp: datetime | None = None

    @field_validator("blood_group")
    @classmethod
    def _group(cls, value: str) -> str:
        if value not in BLOOD_GROUPS:
            raise ValueError(f"blood_group must be one of {BLOOD_GROUPS}")
        return value

    @field_validator("component_type")
    @classmethod
    def _component(cls, value: str) -> str:
        if value not in COMPONENT_TYPES:
            raise ValueError(f"component_type must be one of {COMPONENT_TYPES}")
        return value


class MatchOut(BaseModel):
    inventory_id: str
    inventory_code: str
    blood_bank_id: str
    blood_bank_name: str
    blood_group: str
    component_type: str
    expiry_date: date
    units_available: int
    units_reserved: int
    ranking: int
    match_score: float
    distance_km: float
    eta_minutes: int
    explanation: str


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    hospital_id: str
    blood_group: str
    component_type: str
    quantity_units: int
    urgency: int
    status: str
    shortage_type: str | None = None
    priority_score: float | None = None
    required_by_timestamp: datetime | None = None
    request_timestamp: datetime
    created_by_user_id: str
    matches: list[MatchOut] = Field(default_factory=list)
