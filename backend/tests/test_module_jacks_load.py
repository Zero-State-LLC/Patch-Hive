"""Jack lists reach `modules` only from a reviewed overlay and only where empty (spec 003 FR-041)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "synth-catalog"
sys.path.insert(0, str(CATALOG))
sys.path.insert(0, str(ROOT / "backend"))

import population  # noqa: E402
from catalog_rollback import rollback  # noqa: E402
from population import Plan, _schedule_jacks, assert_safe_sql, populate  # noqa: E402
from tests.test_catalog_population import _admin, _migrate, _recreate  # noqa: E402

OVERLAY = json.loads((CATALOG / "overlays" / "module-jacks-v1.json").read_text(encoding="utf-8"))
PORTS = [{"name": "Gate In", "type": "gate_in"}, {"name": "Out", "type": "audio_out"}]
DB_NAME = "patchhive_jacks_test"


def _entry(**changes) -> dict:
    return {
        "brand": "Acme",
        "name": "Env",
        "source_kind": "manual",
        "source_url": "https://acme.example/env.pdf",
        "io_ports": PORTS,
        **changes,
    }


def _row(**changes) -> dict:
    return {"brand": "Acme", "name": "Env", "status": "active", "io_ports": [], **changes}


def _plan_for(entry: dict, row: dict | None) -> Plan:
    plan = Plan()
    _schedule_jacks(plan, {} if row is None else {("Acme", "Env"): row}, entry)
    return plan


# --- the committed overlay ---


def test_the_overlay_has_the_reviewed_lists_and_no_quotes():
    entries = OVERLAY["entries"]
    assert len(entries) == 230
    assert len(OVERLAY["proposal_sha256"]) == 64
    assert len({(e["brand"], e["name"]) for e in entries}) == len(entries)
    assert not any({"quote", "evidence"} & set(e) for e in entries)


def test_every_overlay_entry_passes_the_loaders_checks():
    assert [e["name"] for e in OVERLAY["entries"] if population._jack_problem(e)] == []


def test_every_overlay_list_has_an_output():
    no_output = [
        e["name"]
        for e in OVERLAY["entries"]
        if not any(port["type"].endswith("_out") for port in e["io_ports"])
    ]
    assert no_output == []


# --- the plan ---


def test_an_empty_list_is_filled_with_a_guarded_statement():
    row = _row()
    plan = _plan_for(_entry(), row)
    assert plan.updates == {"modules_io_ports": 1}
    op = plan.ops[0]
    assert_safe_sql(op.sql)
    assert "status <> 'tombstoned'" in op.sql
    assert "CAST(io_ports AS jsonb) = CAST('[]' AS jsonb)" in op.sql
    assert json.loads(op.params["io_ports"]) == PORTS
    assert row["io_ports"] == PORTS


def test_the_same_list_again_writes_nothing():
    plan = _plan_for(_entry(), _row(io_ports=PORTS))
    assert plan.ops == []
    assert plan.conflicts_total == 0


def test_a_different_declared_list_is_a_conflict_and_is_left_alone():
    stored = [{"name": "Trig", "type": "gate_in"}]
    plan = _plan_for(_entry(), _row(io_ports=stored))
    assert plan.ops == []
    assert plan.conflicts[0]["reason"] == "jacks_differ"


@pytest.mark.parametrize("row", [None, _row(status="tombstoned"), _row(_duplicate=True)])
def test_a_missing_retired_or_ambiguous_row_gets_nothing(row):
    plan = _plan_for(_entry(), row)
    assert plan.ops == []
    assert plan.unmatched == {"module_jacks": 1}


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"io_ports": []}, "jacks_empty"),
        ({"source_url": ""}, "jacks_need_source"),
        ({"source_url": "ftp://acme.example/x"}, "jacks_need_source"),
        ({"io_ports": [{"name": "Out", "type": "banana"}]}, "jacks_bad_type"),
        ({"io_ports": [{"name": "", "type": "cv_in"}]}, "jacks_bad_name"),
        ({"io_ports": [PORTS[0], PORTS[0]]}, "jacks_bad_name"),
    ],
)
def test_a_malformed_entry_is_a_conflict_and_writes_nothing(changes, reason):
    plan = _plan_for(_entry(**changes), _row())
    assert plan.ops == []
    assert plan.conflicts[0]["reason"] == reason


# --- against a real Postgres ---


def _insert(name: str, ports: list) -> str:
    return (
        "INSERT INTO modules (brand, name, hp, module_type, source, status, imported_at, io_ports, "
        f"tags, created_at, updated_at) VALUES ('Acme', '{name}', 8, 'ENV', 'test', 'active', now(), "
        f"'{json.dumps(ports)}', '[]', now(), now())"
    )


def _plan_from_database(conn, verification_path=None) -> Plan:
    plan = Plan()
    modules = population._module_state(conn)
    _schedule_jacks(plan, modules, _entry(name="Env"))
    _schedule_jacks(plan, modules, _entry(name="Declared"))
    return plan


@pytest.fixture
def url(monkeypatch: pytest.MonkeyPatch):
    admin = _admin()
    database = _recreate(admin, DB_NAME)
    _migrate(database)
    engine = create_engine(database)
    with engine.begin() as conn:
        conn.execute(text(_insert("Env", [])))
        conn.execute(text(_insert("Declared", [{"name": "Trig", "type": "gate_in"}])))
    engine.dispose()
    monkeypatch.setattr(population, "build_plan", _plan_from_database)
    monkeypatch.setattr(population, "plan_cases", lambda engine: {"valid": [], "actions": []})
    monkeypatch.setattr(population, "case_receipt", lambda engine, plan, apply: {})
    yield database
    with admin.connect() as conn:
        conn.execute(
            text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name"),
            {"name": DB_NAME},
        )
        conn.execute(text(f"DROP DATABASE IF EXISTS {DB_NAME}"))
    admin.dispose()


def _ports(database: str, name: str) -> list:
    engine = create_engine(database)
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT io_ports FROM modules WHERE brand = 'Acme' AND name = :name"),
                {"name": name},
            ).scalar_one()
    finally:
        engine.dispose()


def test_a_load_fills_the_empty_list_once_and_leaves_a_declared_one(url):
    first = populate(url, apply=True, run_id="load-1")
    assert first["updates"] == {"modules_io_ports": 1}
    assert first["conflicts_total"] == 1
    assert _ports(url, "Env") == PORTS
    assert _ports(url, "Declared") == [{"name": "Trig", "type": "gate_in"}]
    second = populate(url, apply=False, run_id="load-2")
    assert second["updates"] == {}


def test_a_rollback_empties_the_list_again(url):
    populate(url, apply=True, run_id="load-1")
    planned = rollback(url, "load-1", apply=False)
    rollback(
        url,
        "load-1",
        apply=True,
        expected_plan_hash=planned["plan_hash"],
        require_plan_hash=True,
        this_run="rollback-1",
    )
    assert _ports(url, "Env") == []
