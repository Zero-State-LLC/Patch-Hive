"""Read-only startup check: warn when the database schema is behind Alembic head.

The container entrypoint (docker-entrypoint.sh) runs this when startup migrations are disabled. It never
writes to the database and never fails startup: it only logs a warning so an
operator knows to run the db-migrate workflow.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def code_heads() -> set[str]:
    """Alembic head revision(s) shipped with this code."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return set(ScriptDirectory.from_config(config).get_heads())


def database_revisions(database_url: str) -> set[str]:
    """Revision(s) recorded in the database's alembic_version table (read only)."""
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    connect_args = {"connect_timeout": 5} if database_url.startswith("postgres") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    try:
        with engine.connect() as conn:
            return set(MigrationContext.configure(conn).get_current_heads())
    finally:
        engine.dispose()


def check(database_url: str | None) -> str | None:
    """Return a warning message when the database is not at head, else None."""
    if not database_url:
        return None
    heads = code_heads()
    current = database_revisions(database_url)
    if current == heads:
        return None
    return (
        "WARNING: database schema is not at Alembic head "
        f"(database: {', '.join(sorted(current)) or 'none'}; code: {', '.join(sorted(heads))}). "
        "Startup migrations are disabled; run the db-migrate workflow for this environment."
    )


def main() -> int:
    try:
        message = check(os.environ.get("DATABASE_URL"))
    except Exception as exc:  # never block startup on a diagnostic
        print(
            f"WARNING: could not compare schema revision to head: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 0
    if message:
        print(message, file=sys.stderr)
    else:
        print("Database schema is at Alembic head.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
