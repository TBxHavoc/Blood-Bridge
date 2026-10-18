"""Audit logging.

Every sensitive action appends a row. We deliberately provide only an INSERT
path — there is no update or delete helper anywhere in the codebase, matching
the append-only invariant.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit(
    db: Session,
    *,
    action_type: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
    reason_notes: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Add an audit row to the current transaction (caller must commit)."""

    def _dump(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json.dumps(value, default=str)

    row = AuditLog(
        action_type=action_type,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=_dump(old_value),
        new_value=_dump(new_value),
        reason_notes=reason_notes,
        ip_address=ip_address,
    )
    db.add(row)
    db.flush()
    return row
