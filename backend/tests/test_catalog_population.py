"""Full catalog population against a throwaway Postgres database.

Uses the local superuser credentials from CI. Refuses to touch patchhive_test.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

from population import (  # noqa: E402
    Op,
    Plan,
    assert_safe_sql,
    dump_affected_tables,
    plan_hash,
    populate,
)

ADMIN_URL = "postgresql://patchhive:patchhive_test@127.0.0.1:5432/postgres"
DB_NAME = "patchhive_population_test"
SQL_DB_NAME = "patchhive_population_sql"


def _admin():
    engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"throwaway postgres is unavailable ({exc.__class__.__name__})")
    return engine


def _recreate(admin, name: str) -> str:
    with admin.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": name},
        )
        conn.execute(text(f"DROP DATABASE IF EXISTS {name}"))
        conn.execute(text(f"CREATE DATABASE {name} OWNER patchhive"))
    return f"postgresql://patchhive:patchhive_test@127.0.0.1:5432/{name}"


def _migrate(url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT / "backend",
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").replace("patchhive_test", "[redacted]")
        raise RuntimeError(detail[-2000:])


@pytest.fixture(scope="module")
def population_url() -> str:
    admin = _admin()
    try:
        url = _recreate(admin, DB_NAME)
        _migrate(url)
        return url
    finally:
        admin.dispose()


def _counts(url: str) -> dict[str, int]:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            names = ("manufacturers", "module_catalog", "modules", "case_catalog")
            return {name: int(conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar_one()) for name in names}
    finally:
        engine.dispose()


def test_population_dry_run_then_apply_is_idempotent(population_url: str, tmp_path: Path) -> None:
    missing = tmp_path / "no-verification.json"
    before = _counts(population_url)
    assert before == {"manufacturers": 0, "module_catalog": 0, "modules": 0, "case_catalog": 0}

    receipt_path = tmp_path / "receipt.json"
    sql_path = tmp_path / "population.sql"
    dry = populate(
        population_url,
        apply=False,
        receipt_path=receipt_path,
        sql_path=sql_path,
        verification_path=missing,
    )
    assert dry["mode"] == "dry-run"
    assert "patchhive_test" not in dry["database"]
    assert "@" not in dry["database"]
    assert dry["inserts"].get("manufacturers") == 703
    assert dry["cases"]["inserts"] == 50
    assert dry["cases"]["rejected"] == 0
    assert _counts(population_url) == before
    sql = sql_path.read_text(encoding="utf-8")
    assert_safe_sql(sql)
    # Ignore string literals so module names such as "Tin Teardrop VCF" are not
    # mistaken for statements; keywords must still appear as whole words.
    upper = re.sub(r"'(?:[^']|'')*'", "''", sql).upper()
    for forbidden in ("DELETE", "DROP", "TRUNCATE", "ALTER"):
        assert not re.search(rf"\b{forbidden}\s", upper)

    applied = populate(
        population_url,
        apply=True,
        receipt_path=receipt_path,
        sql_path=sql_path,
        verification_path=missing,
    )
    assert applied["mode"] == "apply"
    after = _counts(population_url)
    assert after["manufacturers"] == 703
    assert after["module_catalog"] >= 376
    assert after["modules"] >= 3
    assert after["case_catalog"] == 50

    engine = create_engine(population_url)
    try:
        with engine.connect() as conn:
            chainsaw = conn.execute(
                text("SELECT hp FROM module_catalog WHERE brand = :brand AND name = :name"),
                {"brand": "Acid Rain Technology", "name": "Chainsaw"},
            ).scalar_one()
            bitbox = conn.execute(
                text(
                    "SELECT verification_status, power_12v_ma, power_neg12v_ma, power_5v_ma, depth_mm "
                    "FROM modules WHERE brand = :brand AND name = :name"
                ),
                {"brand": "1010 Music", "name": "Bitbox 2.0"},
            ).mappings().first()
    finally:
        engine.dispose()
    assert chainsaw == 4
    # Bitbox 2.0 power came from ModularGrid overlays (removed 2026-10-17); a fresh
    # load may only carry manufacturer-sourced values for it.
    assert bitbox is None or bitbox["verification_status"] in {"unverified", "verified", "flagged", "corrected"}

    again = populate(population_url, apply=True, verification_path=missing, receipt_path=tmp_path / "again.json", sql_path=tmp_path / "again.sql")
    assert again["inserts"] == {}
    assert again["updates"] == {}
    assert _counts(population_url) == after

    if shutil.which("pg_dump") and shutil.which("pg_restore"):
        dump_path = tmp_path / "pre-apply.dump"
        dump_affected_tables(population_url, dump_path)
        listed = subprocess.run(["pg_restore", "-l", str(dump_path)], check=False, capture_output=True, text=True)
        assert listed.returncode == 0, listed.stderr[-400:]
        listing = listed.stdout
        assert "TABLE DATA manufacturers" in listing or "manufacturers" in listing
        assert "modules" in listing

    if shutil.which("psql"):
        admin = _admin()
        try:
            sql_url = _recreate(admin, SQL_DB_NAME)
        finally:
            admin.dispose()
        _migrate(sql_url)
        env = os.environ.copy()
        env.update(
            {
                "PGHOST": "127.0.0.1",
                "PGPORT": "5432",
                "PGUSER": "patchhive",
                "PGPASSWORD": "patchhive_test",
                "PGDATABASE": SQL_DB_NAME,
            }
        )
        loaded = subprocess.run(["psql", "-v", "ON_ERROR_STOP=1", "-f", str(sql_path)], env=env, check=False, capture_output=True, text=True)
        assert loaded.returncode == 0, (loaded.stderr or "")[-800:].replace("patchhive_test", "[redacted]")
        replayed = _counts(sql_url)
        assert replayed["manufacturers"] == after["manufacturers"]
        assert replayed["module_catalog"] == after["module_catalog"]
        assert replayed["modules"] == after["modules"]
        assert replayed["case_catalog"] == 0


def test_receipts_carry_run_identity_hashes_and_the_full_conflict_count(population_url, tmp_path):
    receipt = populate(population_url, apply=False, verification_path=tmp_path / "none.json")
    for key in ("run_id", "started_at", "finished_at", "plan_hash", "inputs_hash", "conflicts_total"):
        assert key in receipt, key
    assert len(receipt["plan_hash"]) == len(receipt["inputs_hash"]) == 64
    assert receipt["conflicts_total"] >= len(receipt["conflicts"])


@pytest.fixture
def fresh_population_url() -> str:
    admin = _admin()
    try:
        url = _recreate(admin, "patchhive_population_gate")
        _migrate(url)
        return url
    finally:
        admin.dispose()


def test_an_apply_must_name_the_reviewed_plan(fresh_population_url, tmp_path):
    """Spec 003 FR-020: with require_plan_hash, only the reviewed plan is applied."""
    population_url = fresh_population_url
    missing = tmp_path / "none.json"
    dry = populate(population_url, apply=False, verification_path=missing)
    before = _counts(population_url)

    with pytest.raises(SystemExit, match="differs from the reviewed dry run"):
        populate(population_url, apply=True, verification_path=missing,
                 expected_plan_hash="0" * 64, require_plan_hash=True)
    with pytest.raises(SystemExit):
        populate(population_url, apply=True, verification_path=missing, require_plan_hash=True)
    assert _counts(population_url) == before  # nothing written

    applied = populate(population_url, apply=True, verification_path=missing,
                       expected_plan_hash=dry["plan_hash"], require_plan_hash=True)
    assert applied["plan_hash"] == dry["plan_hash"]
    assert _counts(population_url) != before


def test_the_plan_hash_covers_the_case_writes():
    """Spec 003 FR-020: a changed case seed, or a changed case write, is a new plan."""
    plan = Plan(ops=[Op("insert", "INSERT INTO t (a) VALUES (:a)", {"a": 1})])
    record = {"slug": "acme-6u", "manufacturer": "Acme", "model": "6U"}
    cases = {"valid": [record], "actions": [{"slug": "acme-6u", "action": "inserted", "writes": 0}]}
    base = plan_hash(plan, cases)

    assert plan_hash(plan, cases) == base
    assert plan_hash(plan) != base
    seed_changed = {**cases, "valid": [{**record, "model": "7U"}]}
    assert plan_hash(plan, seed_changed) != base
    state_changed = {**cases, "actions": [{"slug": "acme-6u", "action": "updated", "writes": 2}]}
    assert plan_hash(plan, state_changed) != base


def test_a_case_change_after_the_dry_run_refuses_the_apply(fresh_population_url, tmp_path):
    """The reviewed hash stops case writes too: rows changed since the dry run refuse."""
    missing = tmp_path / "none.json"
    dry = populate(fresh_population_url, apply=False, verification_path=missing)
    import json

    from integrations.case_catalog_populator import import_records
    from sqlalchemy.orm import sessionmaker

    seed = json.loads((ROOT / "data" / "cases" / "seed-v1.json").read_text(encoding="utf-8"))
    engine = create_engine(fresh_population_url)
    session = sessionmaker(bind=engine)()
    try:
        assert import_records(session, seed["cases"][:1])["inserted"] == 1
    finally:
        session.close()
        engine.dispose()
    before = _counts(fresh_population_url)
    with pytest.raises(SystemExit, match="differs from the reviewed dry run"):
        populate(fresh_population_url, apply=True, verification_path=missing,
                 expected_plan_hash=dry["plan_hash"], require_plan_hash=True)
    assert _counts(fresh_population_url) == before


def test_a_reviewed_correction_fixes_a_stored_value_once(fresh_population_url, tmp_path):
    """Spec 003 FR-038 on Postgres: put CHICANE's 1U-tile values back, then reload."""
    missing = tmp_path / "none.json"
    populate(fresh_population_url, apply=True, verification_path=missing)
    engine = create_engine(fresh_population_url)
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE modules SET hp = 14, verification_source_url = "
                "'https://www.sovageengineering.com/product-page/chicane-1u' "
                "WHERE brand = 'Sovage Engineering' AND name = 'CHICANE'"
            ))
            conn.execute(text("DELETE FROM catalog_value_archive WHERE batch = 'maker-corrections-v1'"))
        receipt = populate(fresh_population_url, apply=True, verification_path=missing)
        assert receipt["updates"].get("modules_correct") == 1
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT hp, verification_source_url FROM modules "
                "WHERE brand = 'Sovage Engineering' AND name = 'CHICANE'"
            )).one()
            archived = conn.execute(text(
                "SELECT field, old_value FROM catalog_value_archive "
                "WHERE batch = 'maker-corrections-v1' AND action = 'correct' ORDER BY field"
            )).all()
        assert (row.hp, row.verification_source_url) == (4, "https://www.sovageengineering.com/product-page/chicane")
        assert [tuple(a) for a in archived] == [
            ("hp", "14"),
            ("verification_source_url", "https://www.sovageengineering.com/product-page/chicane-1u"),
        ]
        again = populate(fresh_population_url, apply=True, verification_path=missing)
        assert "modules_correct" not in again["updates"]
    finally:
        engine.dispose()
