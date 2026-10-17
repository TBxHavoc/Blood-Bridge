"""Standard response envelope (PRD section 9.2 / planning doc section 9.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app import __version__


def utcnow() -> datetime:
    """Timezone-aware UTC now (naive-UTC columns are normalised on write)."""
    return datetime.now(UTC)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _meta() -> dict[str, Any]:
    return {"timestamp": iso(utcnow()), "version": f"v1 ({__version__})"}


def envelope(data: Any = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": True, "data": data, "meta": {**_meta(), **(meta or {})}}


def error_envelope(
    code: str, message: str, details: Any = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return {"success": False, "error": payload, "meta": _meta()}
