"""FastAPI application factory for Blood Bridge.

Run locally:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.database import Base, engine

configure_logging()
logger = logging.getLogger("bloodbridge")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # create_all() is acceptable for the hackathon MVP (PRD section 8.7).
    import app.models  # noqa: F401  (register tables on Base.metadata)

    Base.metadata.create_all(bind=engine)
    logger.info("Schema ensured (%d tables).", len(Base.metadata.tables))

    # Guarantee the temporary admin and dedicated hospital logins exist, sourced from the environment
    # (git-ignored .env). Never let this block startup.
    from app.seed.bootstrap import ensure_bootstrap_admin, ensure_bootstrap_hospital

    try:
        ensure_bootstrap_admin()
        ensure_bootstrap_hospital()
    except Exception:  # noqa: BLE001 - bootstrap is best-effort
        logger.exception("Bootstrap accounts step failed; continuing startup.")

    # Start eRaktKosh 10-minute automated background scraper if enabled and dependencies available
    if settings.eraktkosh_auto_sync_enabled:
        try:
            from app.services.eraktkosh_scraper import (
                start_eraktkosh_background_worker,
                stop_eraktkosh_background_worker,
            )

            start_eraktkosh_background_worker(
                interval_seconds=settings.eraktkosh_sync_interval_seconds
            )
            logger.info(
                "eRaktKosh automated background scraper started (every %ds).",
                settings.eraktkosh_sync_interval_seconds,
            )
        except Exception as exc:
            logger.warning(
                "eRaktKosh automated background scraper skipped (%s).", exc
            )

    try:
        yield
    finally:
        if settings.eraktkosh_auto_sync_enabled:
            from app.services.eraktkosh_scraper import stop_eraktkosh_background_worker

            await stop_eraktkosh_background_worker()


def create_app() -> FastAPI:
    # Interactive docs and the OpenAPI schema are exposed in development only.
    expose_docs = not settings.is_production
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Privacy-first emergency blood-supply coordination. No patient or "
            "donor identifiers are ever stored, logged or returned."
        ),
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
