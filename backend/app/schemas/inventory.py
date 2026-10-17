"""Inventory schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.constants import BLOOD_GROUPS, COMPONENT_TYPES


class InventoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    blood_bank_id: str
    blood_group: str
    component_type: str
    units_available: int
    units_reserved: int
    collection_date: date
    expiry_date: date
    storage_location_code: str | None = None
    is_available: bool
    last_updated: datetime


class InventoryCreate(BaseModel):
    blood_bank_id: str | None = None
    blood_group: str
    component_type: str
    units_available: int = Field(ge=0)
    collection_date: date
    expiry_date: date
    storage_location_code: str | None = None

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

    @model_validator(mode="after")
    def _dates(self) -> InventoryCreate:
        if self.expiry_date <= self.collection_date:
            raise ValueError("expiry_date must be after collection_date")
        return self


class InventoryUpdate(BaseModel):
    units_available: int | None = Field(default=None, ge=0)
    is_available: bool | None = None
    storage_location_code: str | None = None
    expiry_date: date | None = None
