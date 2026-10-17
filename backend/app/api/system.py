"""System endpoints: health (public) and configuration (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import require_roles
from app.config import settings
from app.core.config_store import get_all
from app.core.envelope import envelope, utcnow
from app.database import get_db
from app.models import User

router = APIRouter(tags=["system"])

admin_only = require_roles("admin")


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


@router.get("/config")
def get_config(
    _: User = Depends(admin_only), db: Session = Depends(get_db)
) -> dict:
    """Current matching weights and thresholds (admin only, PRD section 8.3)."""
    return envelope(get_all(db))
