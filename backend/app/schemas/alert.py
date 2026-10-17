"""Alert schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str | None = None
    alert_type: str
    message: str
    recipient_user_id: str
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None


class AlertPatch(BaseModel):
    is_read: bool = True
