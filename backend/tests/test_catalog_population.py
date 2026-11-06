"""Full catalog population against a throwaway Postgres database.

Uses the local superuser credentials from CI. Refuses to touch patchhive_test.
"""

from __future__ import annotations

import json
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
    ACCESS_BASIS_OVERLAY,
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
            # Both HP overlays carry these; the maker-cited v2 value wins over v1 (D3).
            overlap_hp = dict(
                conn.execute(
                    text("SELECT slug, hp FROM module_catalog WHERE slug IN ('acid-rain-technology-junction', 'doepfer-a-101-3', 'doepfer-a-137-2')")
                ).all()
            )
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
    assert overlap_hp == {"acid-rain-technology-junction": 4, "doepfer-a-101-3": 30, "doepfer-a-137-2": 14}
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


def test_an_apply_must_name_the_reviewed_inputs(fresh_population_url, tmp_path, monkeypatch):
    """Spec 003 OQ-9: with require_inputs_hash, the reviewed dry run's inputs_hash must match too,
    so an apply refuses when the committed inputs changed even though the planned writes did not."""
    import population

    population_url = fresh_population_url
    missing = tmp_path / "none.json"
    dry = populate(population_url, apply=False, verification_path=missing)
    before = _counts(population_url)
    reviewed = {"expected_plan_hash": dry["plan_hash"], "require_plan_hash": True, "require_inputs_hash": True}

    with pytest.raises(SystemExit, match="catalog inputs differ from the reviewed dry run"):
        populate(population_url, apply=True, verification_path=missing, **reviewed)
    with pytest.raises(SystemExit, match="catalog inputs differ from the reviewed dry run"):
        populate(population_url, apply=True, verification_path=missing,
                 expected_inputs_hash="0" * 64, **reviewed)
    # A committed input that changes without changing a single planned write still refuses.
    real_inputs_hash = population.inputs_hash
    monkeypatch.setattr(population, "inputs_hash", lambda: "f" * 64)
    with pytest.raises(SystemExit, match="catalog inputs differ from the reviewed dry run"):
        populate(population_url, apply=True, verification_path=missing,
                 expected_inputs_hash=dry["inputs_hash"], **reviewed)
    monkeypatch.setattr(population, "inputs_hash", real_inputs_hash)
    assert _counts(population_url) == before  # nothing written

    applied = populate(population_url, apply=True, verification_path=missing,
                       expected_inputs_hash=dry["inputs_hash"], **reviewed)
    assert (applied["plan_hash"], applied["inputs_hash"]) == (dry["plan_hash"], dry["inputs_hash"])
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


V2_PAGES = {
    "acid-rain-technology-junction": "https://acidraintechnology.com/products/junction",
    "doepfer-a-101-3": "https://doepfer.de/A1013.htm",
    "doepfer-a-137-2": "https://doepfer.de/a1372.htm",
}


def test_maker_corrections_v2_replace_the_v1_overlay_hp(fresh_population_url, tmp_path):
    """Spec 003 FR-038: rows still holding the unsourced v1 HP take the maker value once."""
    missing = tmp_path / "none.json"
    populate(fresh_population_url, apply=True, verification_path=missing)
    engine = create_engine(fresh_population_url)
    try:
        with engine.begin() as conn:
            # The values a database loaded before #152 holds (v1 filled before v2).
            conn.execute(text(
                "UPDATE module_catalog SET hp = CASE slug "
                "WHEN 'acid-rain-technology-junction' THEN 6 WHEN 'doepfer-a-101-3' THEN 10 "
                "WHEN 'doepfer-a-137-2' THEN 12 END "
                "WHERE slug IN ('acid-rain-technology-junction', 'doepfer-a-101-3', 'doepfer-a-137-2')"
            ))
            conn.execute(text(
                "UPDATE modules SET hp = CASE name WHEN 'Junction' THEN 6 WHEN 'A-101-3' THEN 10 END "
                "WHERE (brand, name) IN (('Acid Rain Technology', 'Junction'), ('Doepfer', 'A-101-3'))"
            ))
            # The fresh load marked these rows processed while they were still missing.
            conn.execute(text("DELETE FROM catalog_value_archive WHERE batch = 'maker-corrections-v2'"))
        receipt = populate(fresh_population_url, apply=True, verification_path=missing)
        # A-137-2 holds 12, not the reviewed 10, so it is left alone.
        assert receipt["updates"] == {"module_catalog_correct": 2, "modules_correct": 2}
        assert receipt["provenance"]["maker-corrections-v2"]["value_not_matched"] == 1
        with engine.connect() as conn:
            catalog = dict(conn.execute(text(
                "SELECT slug, hp FROM module_catalog WHERE slug IN "
                "('acid-rain-technology-junction', 'doepfer-a-101-3', 'doepfer-a-137-2')"
            )).all())
            modules = dict(conn.execute(text(
                "SELECT name, hp FROM modules WHERE (brand, name) IN "
                "(('Acid Rain Technology', 'Junction'), ('Doepfer', 'A-101-3'))"
            )).all())
            archived = conn.execute(text(
                "SELECT table_name, row_key, old_value, source_tag FROM catalog_value_archive "
                "WHERE batch = 'maker-corrections-v2' AND field = 'hp' AND action = 'correct' "
                "ORDER BY table_name, row_key"
            )).all()
        assert catalog == {"acid-rain-technology-junction": 4, "doepfer-a-101-3": 30, "doepfer-a-137-2": 12}
        assert modules == {"Junction": 4, "A-101-3": 30}
        assert [(a.table_name, a.row_key, a.old_value) for a in archived] == [
            ("module_catalog", "acid-rain-technology-junction", "6"),
            ("module_catalog", "doepfer-a-101-3", "10"),
            ("modules", "Acid Rain Technology::Junction", "6"),
            ("modules", "Doepfer::A-101-3", "10"),
        ]
        pages = {**V2_PAGES, "Acid Rain Technology::Junction": V2_PAGES["acid-rain-technology-junction"],
                 "Doepfer::A-101-3": V2_PAGES["doepfer-a-101-3"]}
        assert all(pages[a.row_key] in a.source_tag for a in archived)

        again = populate(fresh_population_url, apply=True, verification_path=missing)
        assert again["inserts"] == {} and again["updates"] == {}
        with engine.connect() as conn:
            assert conn.execute(text(
                "SELECT hp FROM module_catalog WHERE slug = 'doepfer-a-137-2'"
            )).scalar_one() == 12
    finally:
        engine.dispose()


V3_PAGES = {
    "make-noise-dpo": "https://www.makenoisemusic.com/modules/dpo/",
    "make-noise-morphagene": "https://www.makenoisemusic.com/modules/morphagene/",
}


def test_maker_corrections_v3_and_the_legacy_hp_marker(fresh_population_url, tmp_path):
    """Spec 003 T039 on Postgres: the hand-checked v1 values are corrected once, and
    hp_source marks exactly the rows whose HP is still an uncited v1 value."""
    missing = tmp_path / "none.json"
    first = populate(fresh_population_url, apply=True, verification_path=missing)
    # 88 after v3; v4 (the T039 remainder) re-sources 26 more and v5 4 more. On a fresh
    # load the A-155 stays marked at v1's 4 (maker-corrections-v5 needs a stored value).
    # Of the 58, the 40 whose HP a retailer page states read retailer_observed (FR-039).
    # The free reads of 2026-11-05 re-source 8 of the other 18 (the ADDAC rows).
    assert first["updates"]["hp_source_legacy_marked"] == 10
    assert first["updates"]["hp_source_retailer_marked"] == 40
    engine = create_engine(fresh_population_url)
    try:
        with engine.connect() as conn:
            marked = dict(conn.execute(text(
                "SELECT slug, hp FROM module_catalog WHERE hp_source = 'legacy_unsourced'"
            )).all())
            retailer = dict(conn.execute(text(
                "SELECT slug, hp FROM module_catalog WHERE hp_source = 'retailer_observed'"
            )).all())
            fresh = dict(conn.execute(text(
                "SELECT slug, hp FROM module_catalog WHERE slug IN ('make-noise-dpo', 'make-noise-morphagene', "
                "'bastl-instruments-knit-rider', 'intellijel-mems-mic-1u')"
            )).all())
        # A fresh load takes the maker value from v3; no re-sourced value is marked.
        assert fresh == {"make-noise-dpo": 28, "make-noise-morphagene": 20,
                         "bastl-instruments-knit-rider": 16, "intellijel-mems-mic-1u": 10}
        assert len(marked) == 10 and marked["make-noise-mysteron"] == 14
        # A retailer page that disagrees leaves the v1 value marked (Befaco Mixer: 5, retailer 4).
        assert marked["befaco-mixer"] == 5
        # A citation the page check could not confirm stays marked.
        assert marked["cwejman-d-lfo"] == 12
        assert len(retailer) == 40 and retailer["befaco-bandit"] == 8
        assert not set(marked) & {"make-noise-dpo", "doepfer-a-110", "mutable-instruments-grids",
                                  "make-noise-maths", "make-noise-rene"}

        with engine.begin() as conn:
            # The values a database loaded before v3 holds (v1 filled DPO and Morphagene),
            # with no marker yet on Mysteron, and a stale marker on a re-sourced row.
            conn.execute(text(
                "UPDATE module_catalog SET hp = CASE slug WHEN 'make-noise-dpo' THEN 30 "
                "WHEN 'make-noise-morphagene' THEN 18 END "
                "WHERE slug IN ('make-noise-dpo', 'make-noise-morphagene')"
            ))
            conn.execute(text(
                "UPDATE modules SET hp = CASE name WHEN 'DPO' THEN 30 WHEN 'Morphagene' THEN 18 END "
                "WHERE brand = 'Make Noise' AND name IN ('DPO', 'Morphagene')"
            ))
            conn.execute(text("UPDATE module_catalog SET hp_source = NULL WHERE slug = 'make-noise-mysteron'"))
            conn.execute(text(
                "UPDATE module_catalog SET hp_source = 'legacy_unsourced' WHERE slug = 'doepfer-a-110'"
            ))
            conn.execute(text("DELETE FROM catalog_value_archive WHERE batch = 'maker-corrections-v3'"))
        receipt = populate(fresh_population_url, apply=True, verification_path=missing)
        assert receipt["updates"] == {
            "module_catalog_correct": 2,
            "modules_correct": 2,
            "hp_source_legacy_marked": 1,
            "hp_source_legacy_cleared": 1,
        }
        assert receipt["conflicts_total"] == 0
        with engine.connect() as conn:
            catalog = dict(conn.execute(text(
                "SELECT slug, hp FROM module_catalog WHERE slug IN ('make-noise-dpo', 'make-noise-morphagene')"
            )).all())
            modules = dict(conn.execute(text(
                "SELECT name, hp FROM modules WHERE brand = 'Make Noise' AND name IN ('DPO', 'Morphagene')"
            )).all())
            sources = dict(conn.execute(text(
                "SELECT slug, hp_source FROM module_catalog WHERE slug IN "
                "('make-noise-dpo', 'make-noise-mysteron', 'doepfer-a-110')"
            )).all())
            archived = conn.execute(text(
                "SELECT table_name, row_key, old_value, source_tag FROM catalog_value_archive "
                "WHERE batch = 'maker-corrections-v3' AND field = 'hp' AND action = 'correct' "
                "ORDER BY table_name, row_key"
            )).all()
        assert catalog == {"make-noise-dpo": 28, "make-noise-morphagene": 20}
        assert modules == {"DPO": 28, "Morphagene": 20}
        assert sources == {"make-noise-dpo": None, "make-noise-mysteron": "legacy_unsourced", "doepfer-a-110": None}
        assert [(a.table_name, a.row_key, a.old_value) for a in archived] == [
            ("module_catalog", "make-noise-dpo", "30"),
            ("module_catalog", "make-noise-morphagene", "18"),
            ("modules", "Make Noise::DPO", "30"),
            ("modules", "Make Noise::Morphagene", "18"),
        ]
        pages = {**V3_PAGES, "Make Noise::DPO": V3_PAGES["make-noise-dpo"],
                 "Make Noise::Morphagene": V3_PAGES["make-noise-morphagene"]}
        assert all(pages[a.row_key] in a.source_tag for a in archived)

        again = populate(fresh_population_url, apply=True, verification_path=missing)
        assert again["inserts"] == {} and again["updates"] == {}
    finally:
        engine.dispose()


def test_maker_corrections_v4_clear_the_re_sourced_markers(fresh_population_url, tmp_path):
    """Spec 003 T039 remainder on Postgres: a database loaded before v4 holds v1's 8 HP
    for Doepfer A-106-1 and A-138m and the marker on every v4 slug. The reload corrects
    the two values once, clears the markers, and a rerun plans nothing."""
    missing = tmp_path / "none.json"
    populate(fresh_population_url, apply=True, verification_path=missing)
    engine = create_engine(fresh_population_url)
    try:
        with engine.connect() as conn:
            fresh = dict(conn.execute(text(
                "SELECT slug, hp FROM module_catalog WHERE slug IN ('doepfer-a-106-1', 'doepfer-a-138m')"
            )).all())
            unmarked = conn.execute(text(
                "SELECT count(*) FROM module_catalog WHERE hp_source IS NULL AND slug IN "
                "('doepfer-a-106-1', 'doepfer-a-138m', 'make-noise-maths', 'acid-rain-technology-chainsaw')"
            )).scalar_one()
        assert fresh == {"doepfer-a-106-1": 14, "doepfer-a-138m": 20} and unmarked == 4

        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE module_catalog SET hp = 8, hp_source = 'legacy_unsourced' "
                "WHERE slug IN ('doepfer-a-106-1', 'doepfer-a-138m')"
            ))
            conn.execute(text(
                "UPDATE module_catalog SET hp_source = 'legacy_unsourced' WHERE slug = 'make-noise-maths'"
            ))
            conn.execute(text("DELETE FROM catalog_value_archive WHERE batch = 'maker-corrections-v4'"))
        receipt = populate(fresh_population_url, apply=True, verification_path=missing)
        assert receipt["updates"] == {"module_catalog_correct": 2, "hp_source_legacy_cleared": 3}
        assert receipt["conflicts_total"] == 0
        with engine.connect() as conn:
            rows = {r.slug: (r.hp, r.hp_source) for r in conn.execute(text(
                "SELECT slug, hp, hp_source FROM module_catalog WHERE slug IN "
                "('doepfer-a-106-1', 'doepfer-a-138m', 'make-noise-maths')"
            ))}
            archived = conn.execute(text(
                "SELECT table_name, row_key, old_value, source_tag FROM catalog_value_archive "
                "WHERE batch = 'maker-corrections-v4' AND field = 'hp' AND action = 'correct' "
                "ORDER BY row_key"
            )).all()
        assert rows == {"doepfer-a-106-1": (14, None), "doepfer-a-138m": (20, None), "make-noise-maths": (20, None)}
        assert [(a.table_name, a.row_key, a.old_value) for a in archived] == [
            ("module_catalog", "doepfer-a-106-1", "8"),
            ("module_catalog", "doepfer-a-138m", "8"),
        ]
        assert "https://doepfer.de/A106.htm" in archived[0].source_tag
        assert "https://doepfer.de/A138m.htm" in archived[1].source_tag

        again = populate(fresh_population_url, apply=True, verification_path=missing)
        assert again["inserts"] == {} and again["updates"] == {}
    finally:
        engine.dispose()


def test_decisions_52_and_53_set_the_basis_and_clear_modulargrid_urls(fresh_population_url, tmp_path):
    """A basis is filled only under its checks, and a cleared URL lands in the archive."""
    missing = tmp_path / "none.json"
    populate(fresh_population_url, apply=True, verification_path=missing)
    overlay = json.loads(ACCESS_BASIS_OVERLAY.read_text(encoding="utf-8"))
    refill, keep, moved = (entry["slug"] for entry in overlay["rows"][:3])
    lead_page = "https://modulargrid.example/e/lead"

    def basis(conn, slug: str):
        return conn.execute(
            text("SELECT access_basis, evidence_status, modulargrid_url FROM module_catalog WHERE slug = :slug"),
            {"slug": slug},
        ).one()

    engine = create_engine(fresh_population_url)
    try:
        with engine.begin() as conn:
            assert basis(conn, refill).access_basis == "official_publication"  # a load from empty tags them
            lead = conn.execute(text(
                "SELECT c.slug, c.brand, c.name FROM module_catalog c "
                "JOIN modules m ON m.brand = c.brand AND m.name = c.name "
                "WHERE c.access_basis = 'unknown' AND c.tombstoned_at IS NULL AND m.status <> 'tombstoned' "
                "ORDER BY c.slug LIMIT 1"
            )).one()
            retired = conn.execute(text(
                "SELECT brand, name FROM modules WHERE status = 'tombstoned' ORDER BY brand, name LIMIT 1"
            )).one()
            conn.execute(text("UPDATE module_catalog SET access_basis = NULL WHERE slug = :s"), {"s": refill})
            conn.execute(text("UPDATE module_catalog SET access_basis = 'maker_permission' WHERE slug = :s"), {"s": keep})
            conn.execute(
                text(
                    "UPDATE module_catalog SET access_basis = NULL, manufacturer_url = 'https://elsewhere.example/x' "
                    "WHERE slug = :s"
                ),
                {"s": moved},
            )
            conn.execute(
                text(
                    "UPDATE module_catalog SET source = 'CatalogCandidate', access_basis = NULL, "
                    "evidence_status = NULL, modulargrid_url = :url WHERE slug = :s"
                ),
                {"url": lead_page, "s": lead.slug},
            )
            conn.execute(
                text(
                    "UPDATE modules SET source_reference = :url, verification_source_url = :url "
                    "WHERE brand = :b AND name = :n"
                ),
                {"url": lead_page, "b": lead.brand, "n": lead.name},
            )
            conn.execute(
                text("UPDATE modules SET source_reference = :url WHERE brand = :b AND name = :n"),
                {"url": lead_page, "b": retired.brand, "n": retired.name},
            )

        receipt = populate(fresh_population_url, apply=True, verification_path=missing)
        assert receipt["access_basis"]["official_publication"] == 1
        assert receipt["access_basis"]["leads_tagged_unknown"] == {"CatalogCandidate": 1}
        assert receipt["access_basis"]["urls_cleared"] == {
            "module_catalog.modulargrid_url": 1,
            "modules.source_reference": 1,
            "modules.verification_source_url": 1,
        }
        assert receipt["access_basis"]["left_alone_retired_with_url"] == 1
        assert [c["slug"] for c in receipt["conflicts"] if c["reason"] == "access_basis_host_changed"] == [moved]

        with engine.connect() as conn:
            assert basis(conn, refill).access_basis == "official_publication"
            assert basis(conn, keep).access_basis == "maker_permission"
            assert basis(conn, moved).access_basis is None
            assert tuple(basis(conn, lead.slug)) == ("unknown", "CATALOG_OBSERVED", None)
            module = conn.execute(
                text("SELECT source_reference, verification_source_url FROM modules WHERE brand = :b AND name = :n"),
                {"b": lead.brand, "n": lead.name},
            ).one()
            assert tuple(module) == (None, None)
            archived = conn.execute(text(
                "SELECT table_name, field, old_value, action FROM catalog_value_archive "
                "WHERE batch = 'modulargrid-clear-v1' ORDER BY table_name, field"
            )).all()
            assert [tuple(row) for row in archived] == [
                ("module_catalog", "modulargrid_url", lead_page, "clear"),
                ("modules", "source_reference", lead_page, "clear"),
                ("modules", "verification_source_url", lead_page, "clear"),
            ]

        again = populate(fresh_population_url, apply=False, verification_path=missing)
        assert again["access_basis"]["official_publication"] == 0
        assert again["access_basis"]["leads_tagged_unknown"] == {}
        assert again["access_basis"]["urls_cleared"] == {"module_catalog.modulargrid_url": 0}
        assert again["conflicts_total"] == 1  # the moved row is still reported and still untagged
    finally:
        engine.dispose()


def test_the_access_basis_overlay_names_no_lead_and_passes_its_own_checks():
    overlay = json.loads(ACCESS_BASIS_OVERLAY.read_text(encoding="utf-8"))
    assert {row["access_basis"] for row in overlay["rows"]} == {"official_publication"}
    assert all(row["checks"] for row in overlay["rows"])
    assert not {row["slug"] for row in overlay["rows"]} & {row["slug"] for row in overlay["left_out"]}
    # The Noise Engineering row is checked at the maker's page its URL correction moves it to.
    hosts = {row["slug"]: row["host"] for row in overlay["rows"]}
    assert hosts["noise-engineering-basimilus-iteritas-alter"] == "noiseengineering.us"
    assert set(hosts.values()).isdisjoint({"manualslib.com"})
    assert {row["reason"] for row in overlay["left_out"]} == {"robots_unavailable_403", "robots_unavailable_0"}


def test_jumper_settings_load_once_as_power_configs(fresh_population_url, tmp_path):
    """Spec 003 D8 / T034 on Postgres: the clean T035 settings load once; the rest wait."""
    missing = tmp_path / "none.json"
    applied = populate(fresh_population_url, apply=True, verification_path=missing)
    assert applied["inserts"].get("power_configs") == 21
    stats = applied["power_configs"]["t035-jumper-power"]
    assert stats["skipped_by_reason"] == {}
    engine = create_engine(fresh_population_url)
    try:
        with engine.connect() as conn:
            per_module = dict(conn.execute(text(
                "SELECT m.name, COUNT(*) FROM power_configs p JOIN modules m ON m.id = p.module_id "
                "GROUP BY m.name"
            )).all())
            vca = conn.execute(text(
                "SELECT p.label, p.power_12v_ma, p.power_neg12v_ma, p.power_5v_ma FROM power_configs p "
                "JOIN modules m ON m.id = p.module_id WHERE m.name = '4ms VCA Matrix'"
            )).all()
            smr = conn.execute(text(
                "SELECT p.label, p.power_12v_ma, p.power_neg12v_ma, p.power_5v_ma FROM power_configs p "
                "JOIN modules m ON m.id = p.module_id WHERE m.name = 'Spectral Multiband Resonator' ORDER BY p.label"
            )).all()
            otool = conn.execute(text(
                "SELECT p.label, p.power_12v_ma, p.power_neg12v_ma, p.power_5v_ma, p.quote FROM power_configs p "
                "JOIN modules m ON m.id = p.module_id WHERE m.name = 'Otool Scope and Audio Tools' ORDER BY p.label"
            )).all()
            recommended = conn.execute(text("SELECT name, label FROM power_configs WHERE is_recommended")).all()
            singles_before = conn.execute(text(
                "SELECT name, power_12v_ma, power_neg12v_ma, power_5v_ma FROM modules "
                "WHERE id IN (SELECT module_id FROM power_configs) ORDER BY name"
            )).all()
    finally:
        engine.dispose()
    # Otool's page leaves both settings unnamed; the maker's manual names them (t034-manual-labels).
    assert [tuple(row[:4]) for row in otool] == [
        ("With rear jumper set to External 5v", 12, 22, 70),
        ("With rear jumper set to Internal 5v", 80, 22, None),
    ]
    assert all("Otool_Plus_UserManual.pdf" in row[4] for row in otool)
    assert per_module["4ms VCA Matrix"] == per_module["Spectral Multiband Resonator"] == 2
    assert sum(per_module.values()) == 21 and len(per_module) == 11
    # Owner decisions (t034-owner-decisions): the VCA Matrix's unit-less "80 max" is left unknown,
    # and the SMR base setting takes the negation of the page's own label.
    assert sorted(tuple(row) for row in vca) == [
        ("with jumper selecting external 5V", None, 110, 40),
        ("with jumper selecting internal 5V", 110, 110, 0),
    ]
    assert [tuple(row) for row in smr] == [("jumper not set to +12V", 86, 28, 25), ("when jumper set to +12V", 110, 28, 0)]
    assert [tuple(row) for row in recommended] == [("A-Envelope", "The +5V jumper selected (Recommended)")]

    again = populate(fresh_population_url, apply=True, verification_path=missing)
    assert "power_configs" not in again["inserts"]
    assert again["power_configs"]["t035-jumper-power"]["already_stored"] == 21
    engine = create_engine(fresh_population_url)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM power_configs")).scalar_one() == 21
            singles_after = conn.execute(text(
                "SELECT name, power_12v_ma, power_neg12v_ma, power_5v_ma FROM modules "
                "WHERE id IN (SELECT module_id FROM power_configs) ORDER BY name"
            )).all()
    finally:
        engine.dispose()
    # The single draw columns are never written by this action (D8: they stay unknown).
    assert singles_after == singles_before


def test_a_category_reaches_module_type_on_a_loaded_database(fresh_population_url, tmp_path):
    """Owner decision 51: a module row older than its category holds the loader's placeholder."""
    missing = tmp_path / "none.json"
    populate(fresh_population_url, apply=True, verification_path=missing)

    def types(conn) -> dict[str, str]:
        rows = conn.execute(text(
            "SELECT name, module_type FROM modules WHERE (brand, name) IN ("
            "('ACL', 'M/S-MATRIX'), ('Hive Mind Synthesis', 'Video Gate 1U 10HP'), ('Eowave', 'SOURCE MK3'), "
            "('Melted Electronics', 'Glitch Boy'), ('Feedback', 'RESET'), ('Jolin', 'GETREKT ⇝ touch waveshaper'), "
            "('Bela', 'Pepper'))"
        )).all()
        return {row.name: row.module_type for row in rows}

    engine = create_engine(fresh_population_url)
    try:
        with engine.begin() as conn:
            # Filled by this load: the catalog row has no category yet, and the module row predates it.
            conn.execute(text("UPDATE module_catalog SET category = NULL WHERE slug = 'acl-m-s-matrix'"))
            conn.execute(text("UPDATE modules SET module_type = 'UNKNOWN' WHERE name = 'M/S-MATRIX'"))
            # Filled or corrected by an earlier load, and the module row never caught up.
            conn.execute(text("UPDATE modules SET module_type = 'UNKNOWN' WHERE name = 'Video Gate 1U 10HP'"))
            # A value someone set, which differs from the catalog's SYSTEM. It stays.
            conn.execute(text("UPDATE modules SET module_type = 'UTIL' WHERE name = 'SOURCE MK3'"))
            # The placeholder on a row the loader didn't write. It stays.
            conn.execute(text("UPDATE modules SET module_type = 'UNKNOWN', source = 'Admin' WHERE name = 'RESET'"))
            # The placeholder on a retired row. It stays.
            conn.execute(text("UPDATE modules SET module_type = 'UNKNOWN' WHERE name = 'GETREKT ⇝ touch waveshaper'"))
            assert types(conn)["Pepper"] == "UNKNOWN"  # no category to copy, so it stays too

        receipt = populate(fresh_population_url, apply=True, verification_path=missing)
        with engine.connect() as conn:
            assert types(conn) == {
                "M/S-MATRIX": "UTIL",
                "Video Gate 1U 10HP": "VIDEO",
                "SOURCE MK3": "UTIL",
                "Glitch Boy": "VIDEO",  # a reviewed correction's value is left alone
                "RESET": "UNKNOWN",
                "GETREKT ⇝ touch waveshaper": "UNKNOWN",
                "Pepper": "UNKNOWN",
            }
            archived = conn.execute(text(
                "SELECT row_key, field, old_value, source_tag, action FROM catalog_value_archive "
                "WHERE batch = 'module-type-sync-v1' ORDER BY row_key"
            )).all()
        assert receipt["updates"]["module_type_from_category"] == 2
        assert receipt["module_type_sync"]["synced"] == 2
        assert receipt["module_type_sync"]["by_category"] == {"UTIL": 1, "VIDEO": 1}
        assert receipt["module_type_sync"]["left_alone_not_loader_row"] == 1
        assert receipt["module_type_sync"]["left_alone_other_value"] >= 1
        assert [tuple(row) for row in archived] == [
            ("ACL::M/S-MATRIX", "module_type", "UNKNOWN", "module_catalog:acl-m-s-matrix", "fill"),
            ("Hive Mind Synthesis::Video Gate 1U 10HP", "module_type", "UNKNOWN",
             "module_catalog:hive-mind-synthesis-video-gate-1u-10hp", "fill"),
        ]

        again = populate(fresh_population_url, apply=False, verification_path=missing)
        assert "module_type_from_category" not in again["updates"]
    finally:
        engine.dispose()


def test_inputs_hash_covers_the_manual_label_receipt(tmp_path, monkeypatch):
    """The fingerprint changes when a T034 manual label changes (it changes the plan)."""
    import population

    copy = tmp_path / "t034-manual-labels.json"
    copy.write_bytes(population.POWER_CONFIG_LABELS.read_bytes())
    monkeypatch.setattr(population, "ROOT", tmp_path.parent)
    monkeypatch.setattr(population, "CATALOG", tmp_path / "none")
    monkeypatch.setattr(population, "POWER_CONFIG_RECEIPT", tmp_path / "missing.json")
    monkeypatch.setattr(population, "POWER_CONFIG_LABELS", copy)
    monkeypatch.setattr(population, "POWER_CONFIG_DECISIONS", tmp_path / "missing-decisions.json")
    before = population.inputs_hash()
    copy.write_text(copy.read_text().replace("Internal 5v", "Internal 5V"))
    assert population.inputs_hash() != before


def test_the_free_reads_reach_both_tables_and_clear_supply_outputs(fresh_population_url, tmp_path):
    missing = tmp_path / "none.json"
    applied = populate(fresh_population_url, apply=True, verification_path=missing)
    assert applied["conflicts_total"] == 0
    engine = create_engine(fresh_population_url)
    try:
        with engine.connect() as conn:
            def module(name):
                return conn.execute(text(
                    "SELECT hp, module_type, status, power_12v_ma, power_neg12v_ma, power_5v_ma "
                    "FROM modules WHERE name = :name ORDER BY id LIMIT 1"
                ), {"name": name}).one()

            assert module("UPWR")[3:] == (None, None, None)
            assert module("POW!")[3:] == (None, None, None)
            assert module("ADDAC200PI").hp == 4
            assert module("Yarns").module_type == "MIDI"
            assert module("STO").module_type == "VCO"
            assert module("Mesa").module_type == "FX"
            assert module("Starlight 8HP").status == "tombstoned"
            assert conn.execute(text(
                "SELECT manufacturer_url, access_basis FROM module_catalog "
                "WHERE slug = 'noise-engineering-basimilus-iteritas-alter'"
            )).one() == ("https://noiseengineering.us/products/basimilus-iteritas-alter", "official_publication")

        # A database loaded before v7 holds the supply's output as a draw.
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM catalog_value_archive WHERE batch = 'maker-corrections-v7'"))
            conn.execute(text(
                "UPDATE modules SET power_12v_ma = 2000, power_neg12v_ma = 1000, power_5v_ma = 500 WHERE name = 'UPWR'"
            ))
        again = populate(fresh_population_url, apply=True, verification_path=missing)
        assert again["conflicts_total"] == 0
        with engine.connect() as conn:
            assert conn.execute(text(
                "SELECT power_12v_ma, power_neg12v_ma, power_5v_ma FROM modules WHERE name = 'UPWR'"
            )).one() == (None, None, None)
            assert conn.execute(text(
                "SELECT old_value FROM catalog_value_archive "
                "WHERE batch = 'maker-corrections-v7' AND field = 'power_12v_ma' AND name = 'UPWR'"
            )).scalar_one() == "2000"
    finally:
        engine.dispose()


def test_a_confirmed_lead_leaves_unknown_and_the_rest_stay_hidden(fresh_population_url, tmp_path):
    """Spec 003 FR-034 on Postgres: confirmation is recorded with its URL, and the old basis is archived."""
    missing = tmp_path / "none.json"
    applied = populate(fresh_population_url, apply=True, verification_path=missing)
    assert applied["conflicts_total"] == 0
    assert applied["lead_promotions"]["promoted"] > 150
    engine = create_engine(fresh_population_url)
    try:
        with engine.connect() as conn:
            yarns = conn.execute(text(
                "SELECT access_basis, evidence_status, manufacturer_url, category FROM module_catalog "
                "WHERE slug = 'mutable-instruments-yarns'"
            )).one()
            assert yarns.access_basis == "official_publication"
            assert yarns.evidence_status == "MANUFACTURER_CONFIRMED"
            assert yarns.manufacturer_url == "https://pichenettes.github.io/mutable-instruments-documentation/modules/yarns/"
            assert yarns.category == "MIDI"
            archived = dict(conn.execute(text(
                "SELECT field, old_value FROM catalog_value_archive "
                "WHERE batch = 'lead-promotions-v1' AND row_key = 'mutable-instruments-yarns'"
            )).all())
            assert archived == {"access_basis": "unknown", "evidence_status": "CATALOG_OBSERVED"}
            # A refused site stays refused, so its lead stays hidden.
            assert conn.execute(text(
                "SELECT access_basis FROM module_catalog WHERE slug = 'befaco-adsr'"
            )).scalar_one() == "unknown"
            still_leads = conn.execute(text(
                "SELECT COUNT(*) FROM module_catalog WHERE access_basis = 'unknown' AND tombstoned_at IS NULL"
            )).scalar_one()
            assert still_leads > 100
            assert conn.execute(text(
                "SELECT hp FROM module_catalog WHERE hp > 84 AND tombstoned_at IS NULL"
            )).all() == []
        again = populate(fresh_population_url, apply=False, verification_path=missing)
        assert again["lead_promotions"]["promoted"] == 0
        assert not again["updates"].get("lead_promoted")
    finally:
        engine.dispose()


def test_noise_first_rows_become_noise_in_both_tables(fresh_population_url, tmp_path):
    """Owner decision 16: the patch engine reads module_type, so a noise source has to say so."""
    missing = tmp_path / "none.json"
    applied = populate(fresh_population_url, apply=True, verification_path=missing)
    assert applied["conflicts_total"] == 0
    engine = create_engine(fresh_population_url)
    try:
        with engine.connect() as conn:
            category, module_type = conn.execute(text(
                "SELECT c.category, m.module_type FROM module_catalog c JOIN modules m "
                "ON m.brand = c.brand AND m.name = c.name WHERE c.slug = 'plum-audio-noise'"
            )).one()
            assert (category, module_type) == ("NOISE", "NOISE")
            archived = conn.execute(text(
                "SELECT old_value FROM catalog_value_archive WHERE batch = 'category-corrections-v6' "
                "AND row_key = 'plum-audio-noise' AND field = 'category'"
            )).scalar_one()
            assert archived == "VCF"
            # Noise among other functions keeps its category.
            assert conn.execute(text(
                "SELECT category FROM module_catalog WHERE slug = 'verbos-electronics-noise-filter'"
            )).scalar_one() == "VCF"
    finally:
        engine.dispose()

