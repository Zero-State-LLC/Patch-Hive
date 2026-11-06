"""Spec 003 FR-031 and decision 40: roll a catalog load back by run ID, against a real Postgres.

The plan is small and hand-written, so this runs in seconds. The full loader goes through the same
record in test_catalog_population.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))
sys.path.insert(0, str(ROOT / "backend"))

import load_runs  # noqa: E402
import population  # noqa: E402
from catalog_rollback import rollback  # noqa: E402
from population import Op, Plan, populate  # noqa: E402
from tests.test_catalog_population import _admin, _migrate, _recreate  # noqa: E402

DB_NAME = "patchhive_rollback_test"
OLD_SLUG, OLD_KEY = "acme-old", "Acme::Old"
NEW_SLUG, NEW_KEY = "acme-new", "Acme::New"
GONE_SLUG = "acme-gone"


def _insert_catalog(slug: str, name: str, hp: int | None = None) -> str:
    return (
        "INSERT INTO module_catalog (slug, brand, name, hp, source, created_at, updated_at) VALUES "
        f"('{slug}', 'Acme', '{name}', {'NULL' if hp is None else hp}, 'test', now(), now())"
    )


def _insert_module(name: str, hp: int = 14) -> str:
    return (
        "INSERT INTO modules (brand, name, hp, module_type, source, status, imported_at, io_ports, tags, created_at, "
        f"updated_at) VALUES ('Acme', '{name}', {hp}, 'VCO', 'test', 'active', now(), '[]', '[]', now(), now())"
    )


def _archive(field: str, action: str, batch: str = "b1") -> str:
    return (
        "INSERT INTO catalog_value_archive (batch, table_name, row_key, brand, name, field, old_value, "
        f"source_tag, action, archived_at) VALUES ('{batch}', 'modules', '{OLD_KEY}', 'Acme', 'Old', "
        f"'{field}', '14', 'test', '{action}', now())"
    )


def _plan() -> Plan:
    plan = Plan()
    for kind, sql in (
        ("insert_catalog", _insert_catalog(NEW_SLUG, "New")),
        ("insert_module", _insert_module("New")),
        ("insert_maker", "INSERT INTO manufacturers (slug, canonical_name, aliases, status, created_at, updated_at) "
         "VALUES ('acme-rollback', 'Acme Rollback', '[]', 'unknown', now(), now())"),
        ("fill_hp", f"UPDATE module_catalog SET hp = 12 WHERE slug = '{OLD_SLUG}'"),
        ("flag", f"UPDATE modules SET needs_reverify = TRUE WHERE brand = 'Acme' AND name = 'Old'"),
        ("archive", _archive("hp", "flag")),
        ("retire", f"UPDATE module_catalog SET tombstoned_at = now(), tombstone_reason = 'wrong' WHERE slug = '{GONE_SLUG}'"),
    ):
        plan.add_insert(kind, Op(kind, sql, {}))
    return plan


@pytest.fixture
def url(monkeypatch: pytest.MonkeyPatch):
    admin = _admin()
    database = _recreate(admin, DB_NAME)
    _migrate(database)
    engine = create_engine(database)
    with engine.begin() as conn:
        conn.execute(text(_insert_catalog(OLD_SLUG, "Old")))
        conn.execute(text(_insert_catalog(GONE_SLUG, "Gone", 8)))
        conn.execute(text(_insert_module("Old")))
    engine.dispose()
    monkeypatch.setattr(population, "build_plan", lambda conn, verification_path=None: _plan())
    monkeypatch.setattr(population, "plan_cases", lambda engine: {"valid": [], "actions": []})
    monkeypatch.setattr(
        population, "case_receipt",
        lambda engine, plan, apply: {"applied": {"inserted": 3}} if apply else {},
    )
    monkeypatch.setenv("GITHUB_RUN_ID", "load-1")
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
    yield database
    with admin.connect() as conn:
        conn.execute(
            text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name"),
            {"name": DB_NAME},
        )
        conn.execute(text(f"DROP DATABASE IF EXISTS {DB_NAME}"))
    admin.dispose()


def _one(database: str, sql: str, **params):
    engine = create_engine(database)
    try:
        with engine.connect() as conn:
            return conn.execute(text(sql), params).one()
    finally:
        engine.dispose()


def _run(database: str, sql: str) -> None:
    engine = create_engine(database)
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    finally:
        engine.dispose()


def _rollback(database: str, run_id: str = "load-1", monkeypatch=None) -> dict:
    planned = rollback(database, run_id, apply=False)
    return rollback(database, run_id, apply=True, expected_plan_hash=planned["plan_hash"], require_plan_hash=True)


def _counts(database: str) -> tuple:
    return _one(
        database,
        "SELECT (SELECT COUNT(*) FROM module_catalog), (SELECT COUNT(*) FROM modules), "
        "(SELECT COUNT(*) FROM manufacturers), (SELECT COUNT(*) FROM catalog_value_archive)",
    )


def test_a_load_records_its_receipt_and_exactly_what_it_changed(url):
    populate(url, apply=True)
    run = _one(url, "SELECT kind, plan_hash, receipt, rolled_back_by FROM catalog_load_runs WHERE run_id = 'load-1'")
    assert run.kind == "apply" and run.rolled_back_by is None
    assert run.receipt["run_id"] == "load-1"
    assert run.receipt["input_files"]
    inserted = _one(
        url, "SELECT array_agg(row_key) FROM catalog_load_changes "
        "WHERE run_id = 'load-1' AND change = 'insert' AND table_name IN ('module_catalog', 'modules')",
    )[0]
    assert set(inserted) == {NEW_KEY, NEW_SLUG}
    fields = _one(
        url, "SELECT array_agg(field ORDER BY field) FROM catalog_load_changes "
        f"WHERE run_id = 'load-1' AND change = 'update' AND row_key = '{OLD_SLUG}'",
    )[0]
    assert fields == ["hp"]  # updated_at moves too, and isn't a change to restore


def test_a_dry_run_records_nothing_and_a_load_can_change_nothing(url, monkeypatch):
    populate(url, apply=False)
    assert _one(url, "SELECT COUNT(*) FROM catalog_load_runs")[0] == 0
    monkeypatch.setattr(population, "build_plan", lambda conn, verification_path=None: Plan())
    populate(url, apply=True)
    assert _one(url, "SELECT COUNT(*) FROM catalog_load_runs")[0] == 1
    assert _one(url, "SELECT COUNT(*) FROM catalog_load_changes")[0] == 0


def test_a_rollback_dry_run_writes_nothing(url):
    populate(url, apply=True)
    before = _counts(url)
    receipt = rollback(url, "load-1", apply=False)
    assert receipt["mode"] == "rollback-dry-run"
    assert receipt["retired"] == {"module_catalog": 1, "modules": 1}
    assert receipt["left_in_place"] == {"manufacturers": 1}
    assert receipt["cases_not_rolled_back"] == {"inserted": 3}
    assert _counts(url) == before
    assert _one(url, f"SELECT hp FROM module_catalog WHERE slug = '{OLD_SLUG}'")[0] == 12
    assert _one(url, "SELECT rolled_back_by FROM catalog_load_runs WHERE run_id = 'load-1'")[0] is None


def test_a_rollback_retires_inserted_rows_restores_values_and_deletes_nothing(url, monkeypatch):
    populate(url, apply=True)
    before = _counts(url)
    monkeypatch.setenv("GITHUB_RUN_ID", "rollback-1")
    receipt = _rollback(url)
    assert receipt["conflicts_total"] == 0
    assert _counts(url) == before  # every row is still there

    catalog = _one(url, f"SELECT tombstoned_at, tombstone_reason FROM module_catalog WHERE slug = '{NEW_SLUG}'")
    assert catalog.tombstoned_at is not None and catalog.tombstone_reason == "rollback of catalog load load-1"
    assert _one(url, "SELECT status FROM modules WHERE name = 'New'")[0] == "tombstoned"

    # A row from before the load gets back what it held, and keeps its own identity.
    old = _one(url, f"SELECT hp, name, tombstoned_at FROM module_catalog WHERE slug = '{OLD_SLUG}'")
    assert old.hp is None and old.name == "Old" and old.tombstoned_at is None
    assert _one(url, "SELECT needs_reverify FROM modules WHERE name = 'Old'")[0] is False
    # A retirement the load made is undone by the operator's rollback, timestamp included.
    gone = _one(url, f"SELECT tombstoned_at, tombstone_reason FROM module_catalog WHERE slug = '{GONE_SLUG}'")
    assert gone.tombstoned_at is None and gone.tombstone_reason is None

    run = _one(url, "SELECT kind, rollback_of FROM catalog_load_runs WHERE run_id = 'rollback-1'")
    assert (run.kind, run.rollback_of) == ("rollback", "load-1")
    assert _one(url, "SELECT rolled_back_by FROM catalog_load_runs WHERE run_id = 'load-1'")[0] == "rollback-1"


def test_a_rolled_back_flag_stops_blocking_placement_but_stays_in_the_archive(url, monkeypatch):
    populate(url, apply=True)
    monkeypatch.setenv("GITHUB_RUN_ID", "rollback-1")
    _rollback(url)
    row = _one(
        url, "SELECT action, rolled_back_run_id FROM catalog_value_archive "
        f"WHERE row_key = '{OLD_KEY}' AND field = 'hp'",
    )
    assert (row.action, row.rolled_back_run_id) == ("flag", "load-1")

    from racks.validation import hp_needs_reverify
    from sqlalchemy.orm import sessionmaker
    from modules.models import Module

    engine = create_engine(url)
    session = sessionmaker(bind=engine)()
    try:
        session.execute(text("UPDATE modules SET needs_reverify = TRUE WHERE name = 'Old'"))
        module = session.query(Module).filter(Module.name == "Old").one()
        assert hp_needs_reverify(session, module) is False  # only the rolled-back flag says otherwise
        session.execute(text(_archive("hp", "flag", batch="b2")))
        assert hp_needs_reverify(session, module) is True  # a later, live flag still blocks
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_a_field_changed_since_the_load_is_left_alone_and_reported(url, monkeypatch):
    populate(url, apply=True)
    _run(url, f"UPDATE module_catalog SET hp = 16 WHERE slug = '{OLD_SLUG}'")
    monkeypatch.setenv("GITHUB_RUN_ID", "rollback-1")
    receipt = _rollback(url)
    assert receipt["conflicts_total"] == 1
    assert receipt["conflicts"] == [
        {"table": "module_catalog", "row_key": OLD_SLUG, "field": "hp", "reason": "changed_since_run"}
    ]
    assert _one(url, f"SELECT hp FROM module_catalog WHERE slug = '{OLD_SLUG}'")[0] == 16
    assert _one(url, "SELECT needs_reverify FROM modules WHERE name = 'Old'")[0] is False


def test_an_apply_must_name_the_reviewed_plan(url):
    populate(url, apply=True)
    with pytest.raises(SystemExit, match="differs from the reviewed dry run"):
        rollback(url, "load-1", apply=True, expected_plan_hash="f" * 64, require_plan_hash=True)
    assert _one(url, f"SELECT hp FROM module_catalog WHERE slug = '{OLD_SLUG}'")[0] == 12
    assert _one(url, "SELECT COUNT(*) FROM catalog_load_runs")[0] == 1


def test_what_cannot_be_rolled_back_is_refused(url, monkeypatch):
    with pytest.raises(SystemExit, match="no record of it"):
        rollback(url, "load-from-before-this-migration")
    populate(url, apply=True)
    monkeypatch.setenv("GITHUB_RUN_ID", "rollback-1")
    _rollback(url)
    with pytest.raises(SystemExit, match="rollback-1 already did"):
        rollback(url, "load-1")
    with pytest.raises(SystemExit, match="it is a rollback"):
        rollback(url, "rollback-1")


def test_a_rerun_of_the_same_actions_run_gets_its_own_record(url, monkeypatch):
    populate(url, apply=True)
    monkeypatch.setattr(population, "build_plan", lambda conn, verification_path=None: Plan())
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    assert populate(url, apply=True)["run_id"] == "load-1-2"


def test_the_job_summary_says_what_a_rollback_will_do(url):
    sys.path.insert(0, str(ROOT / "scripts"))
    import catalog_actions_load

    populate(url, apply=True)
    receipt = rollback(url, "load-1")
    summary = catalog_actions_load._summary({}, None, "dry-run", "staging", receipt)
    assert "rollback of load-1" in summary
    assert receipt["plan_hash"] in summary
    assert "revert or replace the overlay" in summary


def test_a_load_that_deleted_a_row_is_refused():
    row = {"id": 1, "slug": "x"}
    empty = {table: {} for table in load_runs.TRACKED_TABLES}
    with pytest.raises(RuntimeError, match="deleted 1 rows from module_catalog"):
        load_runs.diff({**empty, "module_catalog": {1: row}}, empty)
