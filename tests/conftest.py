"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine


@pytest.fixture(scope="session")
def db_ready() -> bool:
    """Skip DB-dependent tests when no database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Database not available: {exc}")
    return True


@pytest.fixture
def db(db_ready: bool) -> Session:
    """A session whose work is rolled back at the end of each test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
