"""Create an administrator-readable JSON snapshot without credential hashes."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401  Ensures every mapped table is registered in Base.metadata.
from app.database.database import Base


EXCLUDED_COLUMNS: dict[str, set[str]] = {
    "users": {"password_hash"},
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def export_database(db: Session) -> dict[str, Any]:
    """Export every application table while omitting stored password hashes."""
    tables: dict[str, dict[str, Any]] = {}
    for table in Base.metadata.sorted_tables:
        excluded = EXCLUDED_COLUMNS.get(table.name, set())
        rows = db.execute(select(table)).mappings().all()
        exported_rows = [
            {column.name: _json_safe(row[column.name]) for column in table.columns if column.name not in excluded}
            for row in rows
        ]
        tables[table.name] = {
            "row_count": len(exported_rows),
            "excluded_columns": sorted(excluded),
            "rows": exported_rows,
        }

    return {
        "metadata": {
            "format": "AI Nurse Scheduling database export",
            "format_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database_engine": "PostgreSQL",
            "security_note": "Password hashes are intentionally excluded from this export.",
        },
        "tables": tables,
    }
