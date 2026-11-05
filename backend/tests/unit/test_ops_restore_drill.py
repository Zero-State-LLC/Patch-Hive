"""Restore drill facts: counts-only comparison, alembic head check, read-only source queries."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from core.ops import restore_drill
from core.ops.restore_drill import DrillError, compare_counts, summary_markdown
from core.ops.throwaway_db import create_database, drop_database, with_database

BACKEND = Path(__file__).resolve().parents[2]
ADMIN_URL = os.environ.get("THROWAWAY_ADMIN_URL", "postgresql://patchhive:patchhive_test@127.0.0.1:5432/postgres")


def test_a_faithful_restore_of_a_quiet_source_passes() -> None:
    source = {"users": 3, "canonical_credit_ledger": 7}
    result = compare_counts(source, dict(source), dict(source))
    assert result["ok"] and result["conclusive"] and result["mismatched_tables"] == []
    assert result["tables"]["users"] == {"source_before": 3, "source_after": 3, "restored": 3}


def test_a_lost_row_fails_when_the_source_was_quiet() -> None:
    source = {"users": 3, "canonical_credit_ledger": 7}
    result = compare_counts(source, dict(source), {"users": 3, "canonical_credit_ledger": 6})
    assert not result["ok"] and result["mismatched_tables"] == ["canonical_credit_ledger"]


def test_a_busy_source_is_reported_not_conclusive() -> None:
    result = compare_counts({"users": 3}, {"users": 4}, {"users": 3})
    assert result["ok"] and not result["conclusive"] and not result["source_stable_during_dump"]


def test_a_missing_table_fails_even_when_not_conclusive() -> None:
    result = compare_counts({"users": 3, "exports": 1}, {"users": 4, "exports": 1}, {"users": 3})
    assert not result["ok"] and result["missing_tables"] == ["exports"]


def test_summary_lists_checks_but_not_per_table_counts() -> None:
    receipt = {
        "result": "pass",
        "env": "staging",
        "alembic": {"head": "abc", "current": "abc", "at_head": True},
        "dump": {"bytes": 10, "sha256": "f" * 64},
        "counts": compare_counts({"users": 3}, {"users": 3}, {"users": 3}),
        "reconcile": {"status": "ok", "mismatch_count": 0, "mismatches": []},
    }
    text_out = summary_markdown("Backup/restore drill (staging)", receipt)
    assert "result: **pass**" in text_out and "env: `staging`" in text_out
    assert "at_head=True" in text_out and "mismatch_count=0" in text_out
    assert "1 tables, conclusive=True" in text_out and "users" not in text_out


def test_alembic_head_matches_the_alembic_cli() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"], cwd=BACKEND, capture_output=True, text=True, check=True
    )
    assert completed.stdout.split()[0] == restore_drill.alembic_head()


# Real Postgres (CI service container) ----------------------------------------------------


@pytest.fixture()
def scratch_url():
    engine = create_engine(ADMIN_URL)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        pytest.skip(f"throwaway postgres is unavailable ({exc.__class__.__name__})")
    finally:
        engine.dispose()
    name = "patchhive_acceptance_999998_1"
    drop_database(ADMIN_URL, name)
    create_database(ADMIN_URL, name)
    url = with_database(ADMIN_URL, name)
    seed = create_engine(url)
    with seed.begin() as conn:
        conn.execute(text("CREATE TABLE widgets (id int)"))
        conn.execute(text("INSERT INTO widgets VALUES (1), (2)"))
    seed.dispose()
    yield url
    drop_database(ADMIN_URL, name)


def test_postgres_facts_are_counts_and_versions(scratch_url: str) -> None:
    assert restore_drill.server_major(scratch_url) >= 15
    assert restore_drill.public_table_counts(scratch_url) == {"widgets": 2}
    check = restore_drill.head_check(scratch_url)
    assert check == {"head": restore_drill.alembic_head(), "current": None, "at_head": False}


def test_source_queries_cannot_write(scratch_url: str) -> None:
    with pytest.raises(DrillError, match="database query failed"):
        restore_drill._read_only(scratch_url, lambda conn: conn.execute(text("INSERT INTO widgets VALUES (3)")))
    assert restore_drill.public_table_counts(scratch_url) == {"widgets": 2}
