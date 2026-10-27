"""Spec 003 owner decisions D1/D2 (2026-10-27): T020, T021, T022 and Firecrawl proxy tiers."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from cases.models import Case
from main import app
from modules.catalog import ModuleCatalog
from modules.models import Module

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "data" / "synth-catalog"))

from catalog_scrape import CatalogScraper, HttpRequest, HttpResponse  # noqa: E402

_HERMES_SPEC = importlib.util.spec_from_file_location(
    "hermes_hp_enrich", REPO / "scripts" / "hermes_hp_enrich_firecrawl.py"
)
assert _HERMES_SPEC and _HERMES_SPEC.loader
hermes = importlib.util.module_from_spec(_HERMES_SPEC)
_HERMES_SPEC.loader.exec_module(hermes)


def _client(db_session: Session) -> TestClient:
    from core import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


# --- T020: ModularGrid-derived seed rows are tagged leads without scraped descriptions


@pytest.mark.parametrize(
    "seed",
    [
        REPO / "data" / "synth-catalog" / "seed-phase2-v1.json",
        REPO / "backend" / "data" / "synth-catalog" / "seed-phase2-v1.json",
    ],
)
def test_phase2_seed_rows_are_tagged_leads_without_descriptions(seed: Path) -> None:
    rows = json.loads(seed.read_text(encoding="utf-8"))["catalog_modules"]
    assert rows
    assert not any("description" in row for row in rows)
    assert {row["access_basis"] for row in rows} == {"unknown"}
    assert {row["evidence_status"] for row in rows} == {"CATALOG_OBSERVED"}


def test_catalog_api_returns_lead_tags(db_session: Session) -> None:
    db_session.add_all(
        [
            ModuleCatalog(
                slug="lead-osc",
                brand="Lead",
                name="Osc",
                source="SynthCatalogResearch",
                access_basis="unknown",
                evidence_status="CATALOG_OBSERVED",
            ),
            ModuleCatalog(slug="maker-vca", brand="Maker", name="VCA", hp=8, source="Manual"),
        ]
    )
    db_session.commit()
    resp = _client(db_session).get("/api/modules/catalog", params={"sort_by": "brand"})
    app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    by_slug = {row["slug"]: row for row in resp.json()["modules"]}
    assert by_slug["lead-osc"]["evidence_status"] == "CATALOG_OBSERVED"
    assert by_slug["lead-osc"]["access_basis"] == "unknown"
    assert by_slug["maker-vca"]["evidence_status"] is None


def test_population_loader_inserts_lead_tags(db_session: Session) -> None:
    # db-load.yml runs after migrations, so the loader itself must carry the tags.
    import population

    seed = REPO / "data" / "synth-catalog" / "seed-phase2-v1.json"
    row = json.loads(seed.read_text(encoding="utf-8"))["catalog_modules"][0]
    plan = population.Plan()
    population._schedule_catalog(plan, {}, row, modulargrid_url=None)
    (op,) = plan.ops
    db_session.execute(text(op.sql), op.params)
    db_session.commit()

    slug = op.params["slug"]
    stored = db_session.query(ModuleCatalog).filter_by(slug=slug).one()
    assert stored.access_basis == "unknown"
    assert stored.evidence_status == "CATALOG_OBSERVED"


def test_lead_migration_reads_every_seed_slug() -> None:
    spec = importlib.util.spec_from_file_location(
        "lead_tags", REPO / "backend" / "alembic" / "versions" / "20261027_catalog_lead_tags.py"
    )
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    slugs = migration._seed_slugs()
    rows = json.loads(migration.SEED.read_text(encoding="utf-8"))["catalog_modules"]
    assert len(slugs) == len({ModuleCatalog.create_slug(r["brand"], r["name"]) for r in rows})


# --- T021: modules whose HP is still a flagged ModularGrid value cannot be placed


def _archive(db: Session, module: Module, *, field: str, action: str) -> None:
    db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS catalog_value_archive (id INTEGER PRIMARY KEY, "
            "batch TEXT, table_name TEXT, row_key TEXT, brand TEXT, name TEXT, field TEXT, "
            "old_value TEXT, source_tag TEXT, maker_check TEXT, action TEXT, archived_at TEXT)"
        )
    )
    db.execute(
        text(
            "INSERT INTO catalog_value_archive (batch, table_name, row_key, field, source_tag, action) "
            "VALUES ('modulargrid-provenance-v1', 'modules', :key, :field, 'modulargrid:test', :action)"
        ),
        {"key": f"{module.brand}::{module.name}", "field": field, "action": action},
    )
    db.commit()


def _place(db: Session, case: Case, module: Module):
    resp = _client(db).post(
        "/api/racks",
        json={
            "case_id": case.id,
            "modules": [{"module_id": module.id, "row_index": 0, "start_hp": 0}],
        },
    )
    app.dependency_overrides.clear()
    return resp


def test_flagged_hp_module_cannot_be_placed(
    db_session: Session, sample_case: Case, sample_vco: Module
) -> None:
    sample_vco.needs_reverify = True
    db_session.commit()
    _archive(db_session, sample_vco, field="hp", action="flag")

    resp = _place(db_session, sample_case, sample_vco)
    assert resp.status_code == 400, resp.text
    errors = resp.json()["detail"]["errors"]
    assert [e["details"]["code"] for e in errors] == ["MODULE_HP_NEEDS_REVERIFY"]


def test_reverify_for_other_fields_still_places(
    db_session: Session, sample_case: Case, sample_vco: Module
) -> None:
    # HP was confirmed by the maker ("keep"); only power was nulled.
    sample_vco.needs_reverify = True
    db_session.commit()
    _archive(db_session, sample_vco, field="hp", action="keep")
    _archive(db_session, sample_vco, field="power_12v_ma", action="null")

    assert _place(db_session, sample_case, sample_vco).status_code == 201


def test_no_archive_table_means_no_hp_flag(
    db_session: Session, sample_case: Case, sample_vco: Module
) -> None:
    sample_vco.needs_reverify = True
    db_session.commit()
    assert _place(db_session, sample_case, sample_vco).status_code == 201


# --- T022: automated enrichment fetches official manufacturer pages only


@pytest.mark.parametrize(
    "brand,name",
    [
        ("Make Noise", "Maths"),
        ("Intellijel", "Quad VCA"),
        ("Doepfer", "A-110-1 VCO"),
        ("ADDAC System", "ADDAC 101"),
        ("Instruo", "Cs-L"),
        ("Unknown Maker", "Thing"),
    ],
)
def test_candidate_urls_are_official_only(brand: str, name: str) -> None:
    urls = hermes.candidate_urls(brand, name)
    assert all(kind == "official" for _, kind in urls)
    assert not any(
        host in url for url, _ in urls for host in ("perfectcircuit", "thomann", "modulargrid")
    )


def test_found_rows_record_official_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    fetched: list[str] = []

    def fake_scrape(url: str, timeout: int = 60) -> str:
        fetched.append(url)
        return "Maths is a 20 HP analog computer module. " * 4

    monkeypatch.setattr(hermes, "scrape_markdown", fake_scrape)
    row = hermes.process_one({"brand": "Make Noise", "name": "Maths", "slug": "maths"}, 0)
    assert row["status"] == "found"
    assert row["hp"] == 20
    assert row["access_basis"] == "official_publication"
    assert row["source_authority"] == "MANUFACTURER_PRIMARY"
    assert all("perfectcircuit" not in url for url in fetched)


def test_not_found_rows_have_no_access_basis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hermes, "scrape_markdown", lambda url, timeout=60: "")
    row = hermes.process_one({"brand": "Make Noise", "name": "Maths", "slug": "maths"}, 0)
    assert row["status"] == "not_found"
    assert row["access_basis"] is None


# --- Firecrawl managed proxy tiers


class _Transport:
    def __init__(self) -> None:
        self.calls: list[HttpRequest] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.calls.append(request)
        if request.url.endswith("/robots.txt"):
            return HttpResponse(404, b"", {})
        if request.url == "https://api.firecrawl.dev/v1/scrape":
            return HttpResponse(200, json.dumps({"data": {"html": "<p>12 HP</p>"}}).encode(), {})
        return HttpResponse(503, b"nope", {})


def _router(tmp_path: Path, transport: _Transport, **kwargs) -> CatalogScraper:
    return CatalogScraper(
        cache_dir=tmp_path / "cache",
        ledger_path=tmp_path / "ledger.json",
        transport=transport,
        sleeper=lambda _s: None,
        resolve_hosts=False,
        min_interval_s=0,
        max_retries=1,
        max_paid_fetches=1,
        **kwargs,
    )


def _firecrawl_payload(transport: _Transport) -> dict:
    call = next(c for c in transport.calls if c.url == "https://api.firecrawl.dev/v1/scrape")
    return json.loads(call.body or b"{}")


def test_firecrawl_uses_configured_proxy_tier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CONTEXT_DEV_API_KEY", raising=False)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-secret")
    monkeypatch.setenv("PATCHHIVE_FIRECRAWL_PROXY", "stealth")
    transport = _Transport()
    result = _router(tmp_path, transport).fetch("https://maker.example/module")
    assert result.ok
    assert _firecrawl_payload(transport)["proxy"] == "stealth"
    assert result.receipt.get("note") == "proxy=stealth"
    assert "fc-test-secret" not in json.dumps(result.receipt)


def test_firecrawl_proxy_defaults_to_auto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONTEXT_DEV_API_KEY", raising=False)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-secret")
    monkeypatch.delenv("PATCHHIVE_FIRECRAWL_PROXY", raising=False)
    transport = _Transport()
    _router(tmp_path, transport).fetch("https://maker.example/module")
    assert _firecrawl_payload(transport)["proxy"] == "auto"


def test_unknown_proxy_tier_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _router(tmp_path, _Transport(), firecrawl_proxy="residential")
