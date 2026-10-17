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
from app.database import Base, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bloodbridge")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # create_all() is acceptable for the hackathon MVP (PRD section 8.7).
    import app.models  # noqa: F401  (register tables on Base.metadata)

    Base.metadata.create_all(bind=engine)
    logger.info("Schema ensured (%d tables).", len(Base.metadata.tables))
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Privacy-first emergency blood-supply coordination. No patient or "
            "donor identifiers are ever stored, logged or returned."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
