"""Audit log schemas (auditor view applies PII masking)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action_type: str
    user_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    reason_notes: str | None = None
    ip_address: str | None = None
    created_at: datetime
