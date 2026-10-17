"""System endpoints: health (public) and configuration (admin)."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.config import settings
from app.core.envelope import envelope, utcnow

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    """Liveness probe. Public, no auth (PRD section 8.3)."""
    return envelope(
        {
            "status": "ok",
            "version": __version__,
            "environment": settings.environment,
            "time": utcnow().isoformat(),
        }
    )
