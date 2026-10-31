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
    # 88 after v3; v4 (the T039 remainder) re-sources 26 more.
    assert first["updates"]["hp_source_legacy_marked"] == 62
    engine = create_engine(fresh_population_url)
    try:
        with engine.connect() as conn:
            marked = dict(conn.execute(text(
                "SELECT slug, hp FROM module_catalog WHERE hp_source = 'legacy_unsourced'"
            )).all())
            fresh = dict(conn.execute(text(
                "SELECT slug, hp FROM module_catalog WHERE slug IN ('make-noise-dpo', 'make-noise-morphagene', "
                "'bastl-instruments-knit-rider', 'intellijel-mems-mic-1u')"
            )).all())
        # A fresh load takes the maker value from v3; no re-sourced value is marked.
        assert fresh == {"make-noise-dpo": 28, "make-noise-morphagene": 20,
                         "bastl-instruments-knit-rider": 16, "intellijel-mems-mic-1u": 10}
        assert len(marked) == 62 and marked["make-noise-mysteron"] == 14
        assert marked["addac-system-addac200pi"] == 2
        # A citation the page check could not confirm stays marked.
        assert marked["cwejman-d-lfo"] == 12 and marked["befaco-bandit"] == 8
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


def test_jumper_settings_load_once_as_power_configs(fresh_population_url, tmp_path):
    """Spec 003 D8 / T034 on Postgres: the clean T035 settings load once; the rest wait."""
    missing = tmp_path / "none.json"
    applied = populate(fresh_population_url, apply=True, verification_path=missing)
    assert applied["inserts"].get("power_configs") == 19
    stats = applied["power_configs"]["t035-jumper-power"]
    assert stats["skipped_by_reason"] == {"label_not_on_page": 1, "unit_not_stated": 1}
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
    assert per_module["4ms VCA Matrix"] == per_module["Spectral Multiband Resonator"] == 1
    assert sum(per_module.values()) == 19 and len(per_module) == 11
    assert [tuple(row) for row in vca] == [("with jumper selecting internal 5V", 110, 110, 0)]
    assert [tuple(row) for row in recommended] == [("A-Envelope", "The +5V jumper selected (Recommended)")]

    again = populate(fresh_population_url, apply=True, verification_path=missing)
    assert "power_configs" not in again["inserts"]
    assert again["power_configs"]["t035-jumper-power"]["already_stored"] == 19
    engine = create_engine(fresh_population_url)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM power_configs")).scalar_one() == 19
            singles_after = conn.execute(text(
                "SELECT name, power_12v_ma, power_neg12v_ma, power_5v_ma FROM modules "
                "WHERE id IN (SELECT module_id FROM power_configs) ORDER BY name"
            )).all()
    finally:
        engine.dispose()
    # The single draw columns are never written by this action (D8: they stay unknown).
    assert singles_after == singles_before
