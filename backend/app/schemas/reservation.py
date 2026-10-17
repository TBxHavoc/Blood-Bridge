"""Reservation schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HoldCreate(BaseModel):
    inventory_id: str
    quantity: int = Field(gt=0, le=100)


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str
    inventory_id: str
    quantity: int
    status: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
