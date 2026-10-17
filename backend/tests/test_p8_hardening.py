"""P8: hardening — DB portability, indexes, append-only audit surface, seed CLI."""

from __future__ import annotations

from sqlalchemy import DateTime, Enum, String

import app.models  # noqa: F401  (register tables on Base.metadata)
from app.database import Base


def test_no_nonportable_column_types() -> None:
    """Db2-safe: no inline ENUM, no SERIAL, no INET anywhere in the schema."""
    for table in Base.metadata.tables.values():
        for column in table.columns:
            assert not isinstance(column.type, Enum), f"{table.name}.{column.name} uses Enum"
            type_name = type(column.type).__name__.upper()
            for forbidden in ("ENUM", "INET", "SERIAL"):
                assert forbidden not in type_name, f"{table.name}.{column.name} -> {type_name}"


def test_primary_keys_are_portable_strings() -> None:
    for table in Base.metadata.tables.values():
        assert table.primary_key is not None, f"{table.name} has no PK"
        for column in table.primary_key.columns:
            assert isinstance(column.type, String), f"{table.name}.{column.name} PK is not String"
            assert column.type.length in (36, 50, 100), (
                f"{table.name}.{column.name} PK length {column.type.length}"
            )


def test_timestamps_are_plain_datetime() -> None:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            name = column.name.lower()
            if name.endswith("_at") or name.endswith("timestamp") or name == "last_updated":
                assert isinstance(column.type, DateTime), f"{table.name}.{column.name} not DateTime"


def test_required_indexes_present() -> None:
    def index_names(table_name: str) -> set[str]:
        table = Base.metadata.tables[table_name]
        return {index.name for index in table.indexes}

    assert "ix_inventory_expiry" in index_names("blood_inventory")
    assert "ix_inventory_group_component" in index_names("blood_inventory")
    assert "ix_requests_hospital_status" in index_names("blood_requests")
    assert "ix_requests_status_urgency_time" in index_names("blood_requests")
    assert "ix_reservations_status_expires" in index_names("reservations")
    assert "ix_alerts_user_read" in index_names("alerts")
    assert "ix_audit_resource" in index_names("audit_logs")


def test_audit_api_surface_is_read_only() -> None:
    from app.main import app

    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if path.startswith("/api/v1/audit"):
            assert methods <= {"GET", "HEAD"}, f"{path} exposes {methods}"


def test_seed_cli_function(db_ready: bool) -> None:
    from app.seed.seed import seed

    counts = seed(banks=2, hospitals=1, requests=3, write_csv=False, reset=True)
    assert counts["blood_banks"] == 2
    assert counts["hospitals"] == 1
    assert counts["blood_requests"] == 3
    assert counts["users"] >= 4
    assert counts["config_keys_added"] == 9

    # Restore the standard demo dataset so the local DB is left in a usable state.
    restored = seed(write_csv=False, reset=True)
    assert restored["blood_requests"] == 40
