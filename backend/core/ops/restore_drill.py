"""Backup/restore drill and acceptance receipts: counts-only facts about a database.

Used by ``scripts/staging/restore_drill.py`` (pg_dump of staging or production, restored
into a Postgres container on the runner) and ``scripts/staging/acceptance_staging.py``.
Every query against a source runs in a ``READ ONLY`` transaction that is rolled back.
Receipts hold table names, row counts, revisions, sizes and hashes; never a URL, host,
user, row value or password, because this repo's Actions artifacts are public.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

BACKEND = Path(__file__).resolve().parents[2]
_TABLE_NAME = re.compile(r"[a-z_][a-z0-9_]{0,62}")


class DrillError(RuntimeError):
    """A drill query failed. The message holds the error class only, never connection details."""


def _read_only(url: str, work):
    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            # The connection begins a transaction on first use; nothing here ever commits.
            conn.execute(text("SET TRANSACTION READ ONLY"))
            try:
                return work(conn)
            finally:
                conn.rollback()
    except SQLAlchemyError as exc:
        raise DrillError(f"database query failed ({exc.__class__.__name__})") from None
    finally:
        engine.dispose()


def server_major(url: str) -> int:
    """The server's Postgres major version (15 for 15.13)."""
    return _read_only(
        url,
        lambda conn: int(conn.execute(text("SHOW server_version_num")).scalar_one()) // 10000,
    )


def public_table_counts(url: str) -> dict[str, int]:
    """Row count of every table in the ``public`` schema, by table name."""

    def work(conn) -> dict[str, int]:
        names = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
        ).scalars()
        counts: dict[str, int] = {}
        for name in names:
            if not _TABLE_NAME.fullmatch(name):
                raise DrillError("refusing to count a table whose name is not a plain identifier")
            # An identifier can't be a bound parameter; _TABLE_NAME checked it above.
            query = text(f'SELECT COUNT(*) FROM public."{name}"')  # nosec B608
            counts[name] = int(conn.execute(query).scalar_one())
        return counts

    return _read_only(url, work)


def alembic_head() -> str:
    """This checkout's single alembic head."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        raise DrillError(f"expected one alembic head, found {len(heads)}")
    return heads[0]


def current_revision(url: str) -> str | None:
    from alembic.runtime.migration import MigrationContext

    return _read_only(url, lambda conn: MigrationContext.configure(conn).get_current_revision())


def head_check(url: str) -> dict[str, Any]:
    head = alembic_head()
    current = current_revision(url)
    return {"head": head, "current": current, "at_head": current == head}


def compare_counts(
    before: dict[str, int], after: dict[str, int], restored: dict[str, int]
) -> dict[str, Any]:
    """Compare the restored copy with the source counted just before and just after the dump.

    If the source did not change while it was dumped, the restored copy must match it
    table for table. If it did change, counts cannot prove anything about the copy, so the
    comparison is reported as not conclusive; every source table must still exist.
    """
    stable = before == after
    tables = sorted(set(before) | set(after) | set(restored))
    missing = sorted(name for name in set(before) | set(after) if name not in restored)
    mismatched = sorted(
        name for name in tables if stable and restored.get(name) != before.get(name)
    )
    return {
        "source_stable_during_dump": stable,
        "conclusive": stable,
        "tables": {
            name: {
                "source_before": before.get(name),
                "source_after": after.get(name),
                "restored": restored.get(name),
            }
            for name in tables
        },
        "missing_tables": missing,
        "mismatched_tables": mismatched,
        "ok": not missing and not mismatched,
    }


def summary_markdown(title: str, receipt: dict[str, Any]) -> str:
    """A short job summary: result, revision and the checks; the counts stay in the artifact."""
    lines = [f"## {title}", "", f"- result: **{receipt.get('result', 'unknown')}**"]
    for key, value in receipt.items():
        if key in {"result", "counts", "tables"} or isinstance(value, (dict, list)):
            continue
        lines.append(f"- {key}: `{value}`")
    for key in ("alembic", "dump", "tests", "reconcile", "teardown"):
        section = receipt.get(key)
        if isinstance(section, dict):
            flat = ", ".join(
                f"{name}={value}"
                for name, value in section.items()
                if not isinstance(value, (dict, list))
            )
            lines.append(f"- {key}: {flat}")
    counts = receipt.get("counts")
    if isinstance(counts, dict):
        lines.append(
            f"- counts: {len(counts.get('tables', {}))} tables, conclusive={counts.get('conclusive')}, "
            f"missing={counts.get('missing_tables')}, mismatched={counts.get('mismatched_tables')}"
        )
    return "\n".join(lines) + "\n"
