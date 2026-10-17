"""Human-readable code generation (Db2/Postgres portable: max-suffix + 1)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Base


def next_code(db: Session, model: type[Base], prefix: str, width: int = 6) -> str:
    """Return the next `<prefix><n>` code, where n is max existing numeric suffix + 1.

    Non-numeric suffixes (e.g. seeded `REQ_SEED_001`) are ignored.
    """
    codes = db.scalars(select(model.code).where(model.code.like(f"{prefix}%"))).all()  # type: ignore[attr-defined]
    highest = 0
    for code in codes:
        suffix = code[len(prefix):]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:0{width}d}"
