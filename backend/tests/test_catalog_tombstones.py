"""Catalog tombstones: misattributed rows are hidden, never deleted (2026-10-28)."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import build_maker_overlays as B  # noqa: E402
import population as P  # noqa: E402
from core.database import get_db  # noqa: E402
from main import app  # noqa: E402
from modules.catalog import ModuleCatalog  # noqa: E402
from modules.catalog_routes import materialize_catalog_entry  # noqa: E402
from registry.models import Manufacturer  # noqa: E402

OVERLAYS = ROOT / "data" / "synth-catalog" / "overlays"


# --- crawl guard -----------------------------------------------------------------


def test_shared_homepage_keeps_the_brand_named_in_the_host() -> None:
    brands = [
        {"brand": "Make Noise", "homepage": "https://www.makenoisemusic.com/"},
        {"brand": "Mental Noise", "homepage": "https://www.makenoisemusic.com/"},
        {"brand": "Bastl Instruments", "homepage": "https://bastl-instruments.com/"},
    ]
    assert B.shared_homepage_skips(brands) == {"Mental Noise": "Make Noise"}


def test_shared_homepage_skips_nothing_without_a_single_owner() -> None:
    brands = [
        {"brand": "Alpha", "homepage": "https://synthshop.example/"},
        {"brand": "Beta", "homepage": "https://synthshop.example/"},
    ]
    assert B.shared_homepage_skips(brands) == {}


# --- loader ----------------------------------------------------------------------


def _state():
    catalog = {"mental-noise-maths": {"brand": "Mental Noise", "name": "Maths", "hp": 20, "category": "ENV", "tombstoned": False}}
    modules = {("Mental Noise", "Maths"): {"brand": "Mental Noise", "name": "Maths", "status": "active"}}
    return catalog, modules


ENTRY = {"slug": "mental-noise-maths", "brand": "Mental Noise", "name": "Maths", "reason": "filed under the wrong brand"}


def test_retirement_tombstones_catalog_and_module_rows_once() -> None:
    catalog, modules = _state()
    plan = P.Plan()
    P._schedule_retirement(plan, catalog, modules, ENTRY)
    assert plan.updates == {"catalog_retire": 1, "module_retire": 1}
    assert all("tombstoned_at IS NULL" in op.sql or "IS DISTINCT FROM 'tombstoned'" in op.sql for op in plan.ops)
    assert not any("DELETE" in op.sql.upper() for op in plan.ops)

    again = P.Plan()
    P._schedule_retirement(again, catalog, modules, ENTRY)
    assert again.ops == []


def test_retirement_needs_a_reason_and_matching_identity() -> None:
    catalog, modules = _state()
    plan = P.Plan()
    P._schedule_retirement(plan, catalog, modules, {**ENTRY, "reason": ""})
    P._schedule_retirement(plan, catalog, modules, {**ENTRY, "name": "Other"})
    assert [c["reason"] for c in plan.conflicts] == [
        "retirement_missing_identity_or_reason",
        "retirement_identity_mismatch",
    ]
    assert plan.ops == []


def test_retirement_counts_rows_it_cannot_find() -> None:
    plan = P.Plan()
    P._schedule_retirement(plan, {}, {}, ENTRY)
    assert plan.unmatched == {"retire_catalog": 1, "retire_module": 1}


def test_plan_hash_ignores_the_tombstone_clock() -> None:
    catalog, modules = _state()
    first, second = P.Plan(), P.Plan()
    P._schedule_retirement(first, *_state(), ENTRY)
    for op in first.ops:
        op.params["tombstoned_at"] = "2026-01-01T00:00:00+00:00"
    P._schedule_retirement(second, catalog, modules, ENTRY)
    assert P.plan_hash(first) == P.plan_hash(second)


# --- committed manifest ------------------------------------------------------------


def _load(name: str) -> dict:
    return json.loads((OVERLAYS / name).read_text())


def test_every_retirement_cites_the_real_makers_page() -> None:
    manifest = _load("catalog-retirements-v1.json")
    hosts = {
        "Make Noise": "makenoisemusic.com", "Noise Engineering": "noiseengineering.us",
        "ARC": "analogueresearch.com", "Infinite Machinery": "infinitemachinery.com",
        "Winter Modular": "winter-modular.com",
    }
    rows = manifest["rows"]
    assert manifest["count"] == len(rows) == len({r["slug"] for r in rows})
    for row in rows:
        assert row["reason"] and row["evidence_url"], row
        if row.get("owner"):
            assert hosts[row["owner"]] in row["evidence_url"], row


def test_every_manifest_retirement_renders_as_safe_sql() -> None:
    """Each row as if it exists (staging and prod hold rows a fresh database does not)."""
    rows = _load("catalog-retirements-v1.json")["rows"]
    catalog = {
        r["slug"]: {"brand": r["brand"], "name": r["name"], "hp": None, "category": None, "tombstoned": False}
        for r in rows
    }
    modules = {(r["brand"], r["name"]): {"brand": r["brand"], "name": r["name"], "status": "active"} for r in rows}
    plan = P.Plan()
    for row in rows:
        P._schedule_retirement(plan, catalog, modules, row)
    assert plan.conflicts == []
    assert plan.updates == {"catalog_retire": len(rows), "module_retire": len(rows)}
    P.assert_safe_sql(P.render_plan(plan))


def test_modules_held_only_by_a_retired_row_are_re_added_under_their_owner() -> None:
    manifest = _load("catalog-retirements-v1.json")
    added = {(r["brand"], B.norm(r["brand"], r["name"])) for r in _load("catalog-additions-v5.json")["rows"]}
    power = {(e["brand"], e["name"]) for e in _load("module-power-depth-v13.json")["entries"]}
    readded = [r for r in manifest["rows"] if r.get("kept_as", "").startswith("re-added")]
    assert readded
    for row in readded:
        owner = row["owner"]
        assert (owner, B.norm(owner, B.clean_name(owner, row["name"]))) in added, row
    assert len(power) == len(added)


# --- read paths --------------------------------------------------------------------


@pytest.fixture
def catalog_client(db_session: Session):
    db_session.add_all([
        ModuleCatalog(slug="make-noise-maths", brand="Make Noise", name="Maths", hp=20, category="ENV"),
        ModuleCatalog(
            slug="mental-noise-maths", brand="Mental Noise", name="Maths", hp=20, category="ENV",
            tombstoned_at=datetime(2026, 10, 28), tombstone_reason="filed under the wrong brand",
        ),
        Manufacturer(slug="mental-noise", canonical_name="Mental Noise", status="unknown", provenance={}),
    ])
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_tombstoned_rows_leave_browse_counts_and_search(catalog_client: TestClient) -> None:
    browse = catalog_client.get("/api/modules/catalog", params={"search": "maths"}).json()
    assert [m["brand"] for m in browse["modules"]] == ["Make Noise"]
    assert browse["total"] == 1
    brands = catalog_client.get("/api/modules/catalog/brands").json()["brands"]
    assert [b["name"] for b in brands] == ["Make Noise"]
    assert catalog_client.get("/api/modules/catalog/stats").json()["total_modules"] == 1
    search = catalog_client.get("/api/registry/search", params={"q": "maths"}).json()["results"]
    assert [r["brand"] for r in search] == ["Make Noise"]
    maker = catalog_client.get("/api/registry/manufacturers/mental-noise").json()
    assert maker["model_count"] == 0


def test_a_tombstoned_row_still_answers_by_slug_but_is_not_materialized(
    catalog_client: TestClient, db_session: Session
) -> None:
    row = catalog_client.get("/api/modules/catalog/mental-noise-maths").json()
    assert row["tombstone_reason"] == "filed under the wrong brand"
    with pytest.raises(HTTPException) as exc:
        materialize_catalog_entry(db_session, "mental-noise-maths")
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "CATALOG_ROW_TOMBSTONED"


# --- manifest v2 (brands found by the crawl-time guard, spec 003 T030) -------------


def test_manifest_v2_retires_only_what_v1_did_not() -> None:
    v1 = {r["slug"] for r in _load("catalog-retirements-v1.json")["rows"]}
    v2 = _load("catalog-retirements-v2.json")
    rows = v2["rows"]
    assert v2["count"] == len(rows) == len({r["slug"] for r in rows})
    assert not v1 & {r["slug"] for r in rows}
    hosts = {
        "ALM Busy Circuits": "busycircuits.com", "Instruo": "instruomodular.com",
        "Jasmine & Olive Trees": "jasmineandolivetrees.com", None: "modularsynthlab.com",
    }
    for row in rows:
        assert row["reason"] and ";" not in row["reason"], row
        assert hosts[row["owner"]] in row["evidence_url"], row
        assert row["kept_as"] in {
            "existing row under owner",
            "not re-added: no maker owns that host",
            "not re-added: no page for it in the current crawl",
        }, row


def test_manifest_v2_renders_as_safe_sql() -> None:
    rows = _load("catalog-retirements-v2.json")["rows"]
    catalog = {r["slug"]: {"brand": r["brand"], "name": r["name"], "hp": None, "category": None, "tombstoned": False} for r in rows}
    modules = {(r["brand"], r["name"]): {"brand": r["brand"], "name": r["name"], "status": "active"} for r in rows}
    plan = P.Plan()
    for row in rows:
        P._schedule_retirement(plan, catalog, modules, row)
    assert plan.conflicts == []
    P.assert_safe_sql(P.render_plan(plan))


def test_the_builder_never_rewrites_an_applied_manifest() -> None:
    import build_reattribution as R

    assert R.main(["--version", "1"]) == 2
