"""API routers, mounted under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import admin, auth, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
