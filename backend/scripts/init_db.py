#!/usr/bin/env python3
"""
Create all database tables from the ORM models.

Run this once against a fresh database (e.g. right after provisioning an
Aiven PostgreSQL service) before starting the API server:

    python scripts/init_db.py

This project uses `Base.metadata.create_all()` rather than Alembic
migrations for now — deliberately: it's the right amount of tooling for a
single-schema, pre-1.0 project. It is NOT a migration tool: running it again
after the schema already exists is safe (it only creates missing tables,
never alters or drops existing ones), but it cannot evolve an existing
table's columns. If this project outgrows that — multiple environments that
need to be kept in sync through schema changes over time — introduce
Alembic at that point rather than before it's needed.
"""
import sys
from pathlib import Path

# Allow running as `python scripts/init_db.py` from the backend/ directory
# (or any directory) without requiring PYTHONPATH or `-m` flags — Python
# only auto-adds the script's own directory (scripts/) to sys.path, not its
# parent, so the `app` package import would otherwise fail.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.db.postgres.models import Base  # noqa: E402
from app.db.postgres.session import get_engine  # noqa: E402


def main() -> None:
    settings = get_settings()
    print(f"Connecting to: {_redact(settings.DATABASE_URL)}")

    engine = get_engine(settings.DATABASE_URL)
    try:
        Base.metadata.create_all(engine)
    except Exception as exc:
        print(f"Failed to create tables: {exc}", file=sys.stderr)
        sys.exit(1)

    table_names = sorted(Base.metadata.tables.keys())
    print(f"Done. {len(table_names)} tables ensured:")
    for name in table_names:
        print(f"  - {name}")


def _redact(database_url: str) -> str:
    """Don't print the password when this runs in a deploy log."""
    if "@" not in database_url:
        return database_url
    scheme_and_creds, host_part = database_url.rsplit("@", 1)
    scheme, _, _ = scheme_and_creds.partition("://")
    return f"{scheme}://***:***@{host_part}"


if __name__ == "__main__":
    main()
