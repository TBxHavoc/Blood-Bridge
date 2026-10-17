"""API routers, mounted under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    admin,
    alerts,
    audit,
    auth,
    eraktkosh,
    forecasting,
    inventory,
    requests,
    reservations,
    system,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(inventory.router)
api_router.include_router(requests.router)
api_router.include_router(requests.match_router)
api_router.include_router(reservations.router)
api_router.include_router(alerts.router)
api_router.include_router(audit.router)
api_router.include_router(forecasting.router)
api_router.include_router(eraktkosh.router)

