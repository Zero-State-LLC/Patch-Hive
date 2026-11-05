"""Owner decision 39 (spec 003 FR-033): anonymous reads leave out `unknown` access-basis rows.

A row with access_basis NULL was never tagged and stays readable. A signed-in caller reads
every live row. A module someone already placed keeps rendering on their rack.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.models import Case
from community.models import User
from core.database import get_db
from core.security import create_access_token
from integrations.case_catalog_populator import import_records
from main import app
from modules.catalog import ModuleCatalog
from modules.models import Module
from registry import services
from registry.models import Manufacturer
from tests.conftest import bearer_headers, make_user

LEAD_NAMES = ("Lead LFO", "Lead Env")
KNOWN_SLUG = "maker-one-known-osc"
LEAD_SLUG = "lead-only-lead-lfo"
LEAD_NO_HP_SLUG = "maker-one-lead-env"
RETIRED_LEAD_SLUG = "maker-one-retired-lead"


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _catalog_row(slug: str, brand: str, name: str, **fields) -> ModuleCatalog:
    return ModuleCatalog(slug=slug, brand=brand, name=name, is_available="available", **fields)


def _module(brand: str, name: str, hp: int) -> Module:
    return Module(
        brand=brand, name=name, hp=hp, module_type="UTIL", io_ports=[], tags=[], source="test"
    )


@pytest.fixture
def rows(db_session: Session) -> dict:
    db_session.add_all(
        [
            Manufacturer(slug="maker-one", canonical_name="Maker One", status="active", provenance={}),
            Manufacturer(slug="lead-only", canonical_name="Lead Only", status="active", provenance={}),
            _catalog_row(
                KNOWN_SLUG, "Maker One", "Known Osc", hp=10, category="VCO",
                source="ManufacturerCrawl", access_basis="official_publication",
            ),
            # Never tagged: this decision covers `unknown`, not NULL.
            _catalog_row(
                "maker-one-untagged-filter", "Maker One", "Untagged Filter", hp=8, category="VCF",
                source="ManufacturerVerified",
            ),
            _catalog_row(
                LEAD_SLUG, "Lead Only", "Lead LFO", hp=4, category="LFO",
                source="SynthCatalogResearch", access_basis="unknown",
                evidence_status="CATALOG_OBSERVED",
            ),
            _catalog_row(
                LEAD_NO_HP_SLUG, "Maker One", "Lead Env", hp=None, category="ENV",
                source="SynthCatalogResearch", access_basis="unknown",
                evidence_status="CATALOG_OBSERVED",
            ),
            _catalog_row(
                RETIRED_LEAD_SLUG, "Maker One", "Retired Lead", hp=6, category="UTIL",
                source="SynthCatalogResearch", access_basis="unknown",
                evidence_status="CATALOG_OBSERVED",
                tombstoned_at=datetime(2026, 10, 28), tombstone_reason="wrong brand",
            ),
        ]
    )
    known = _module("Maker One", "Known Osc", 10)
    lead = _module("Lead Only", "Lead LFO", 4)
    no_catalog_row = _module("Maker Two", "Not In Catalog", 12)
    db_session.add_all([known, lead, no_catalog_row])
    db_session.commit()
    return {"known": known, "lead": lead, "no_catalog_row": no_catalog_row}


def _signed_in(db_session: Session, role: str) -> dict:
    return bearer_headers(make_user(db_session, f"reader-{role.lower()}", role))


# --- Anonymous --------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "/api/modules/catalog",
        "/api/modules/catalog?search=lead",
        "/api/modules/catalog?brand=Lead+Only",
        "/api/modules/catalog?category=LFO",
        "/api/modules/catalog?source=SynthCatalogResearch",
        "/api/modules/catalog?hp_known=false",
        "/api/modules/catalog/brands",
        "/api/modules/catalog/categories",
        "/api/registry/search?q=lead",
        "/api/registry/search?brand=lead-only",
        "/api/registry/manufacturers/maker-one",
        "/api/registry/manufacturers/maker-one/models",
        "/api/registry/manufacturers/lead-only",
        "/api/registry/manufacturers/lead-only/models",
        "/api/modules/",
        "/api/modules/?brand=Lead",
    ],
)
def test_no_anonymous_read_names_an_unknown_basis_row(client: TestClient, rows: dict, url: str) -> None:
    response = client.get(url)
    assert response.status_code == 200, response.text
    for name in LEAD_NAMES:
        assert name not in response.text


def test_anonymous_browse_keeps_known_and_untagged_rows(client: TestClient, rows: dict) -> None:
    body = client.get("/api/modules/catalog").json()
    assert body["total"] == 2
    assert {row["name"] for row in body["modules"]} == {"Known Osc", "Untagged Filter"}
    assert {row["access_basis"] for row in body["modules"]} == {"official_publication", None}


def test_anonymous_browse_counts_only_what_it_lists(client: TestClient, rows: dict) -> None:
    brands = client.get("/api/modules/catalog/brands").json()
    assert brands["brands"] == [{"name": "Maker One", "module_count": 2}]
    categories = client.get("/api/modules/catalog/categories").json()
    assert {c["name"] for c in categories["categories"]} == {"VCO", "VCF"}
    stats = client.get("/api/modules/catalog/stats").json()
    assert stats["total_modules"] == 2
    assert stats["total_brands"] == 1
    assert stats["total_categories"] == 2
    assert stats["hp_stats"]["known"] == 2
    assert stats["hp_stats"]["unknown"] == 0
    assert stats["by_source"] == {"ManufacturerCrawl": 1, "ManufacturerVerified": 1}
    assert stats["availability"]["available"] == 2


@pytest.mark.parametrize("slug", [LEAD_SLUG, LEAD_NO_HP_SLUG, RETIRED_LEAD_SLUG])
def test_an_anonymous_slug_read_answers_as_if_the_row_were_not_there(
    client: TestClient, rows: dict, slug: str
) -> None:
    hidden = client.get(f"/api/modules/catalog/{slug}")
    missing = client.get("/api/modules/catalog/no-such-slug")
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json()["detail"].replace(slug, "x") == missing.json()["detail"].replace("no-such-slug", "x")


def test_an_anonymous_slug_read_still_answers_for_a_known_row(client: TestClient, rows: dict) -> None:
    response = client.get(f"/api/modules/catalog/{KNOWN_SLUG}")
    assert response.status_code == 200
    assert response.json()["name"] == "Known Osc"


def test_an_anonymous_caller_cannot_materialize_an_unknown_basis_row(
    client: TestClient, db_session: Session, rows: dict
) -> None:
    db_session.delete(rows["lead"])
    db_session.commit()
    response = client.post(f"/api/modules/catalog/{LEAD_SLUG}/materialize")
    assert response.status_code == 404
    assert db_session.query(Module).filter_by(name="Lead LFO").count() == 0


def test_an_anonymous_caller_cannot_read_an_unknown_row_through_an_existing_module(
    client: TestClient, rows: dict
) -> None:
    response = client.post(f"/api/modules/catalog/{LEAD_SLUG}/materialize")
    assert response.status_code == 404
    assert "Lead LFO" not in response.text


def test_an_anonymous_caller_can_still_materialize_a_known_row(client: TestClient, rows: dict) -> None:
    response = client.post(f"/api/modules/catalog/{KNOWN_SLUG}/materialize")
    assert response.status_code == 200
    assert response.json()["module"]["name"] == "Known Osc"


def test_anonymous_registry_counts_only_what_it_lists(client: TestClient, rows: dict) -> None:
    listed = {m["slug"]: m["model_count"] for m in client.get("/api/registry/manufacturers").json()["items"]}
    assert listed == {"maker-one": 2, "lead-only": 0}
    assert client.get("/api/registry/manufacturers/maker-one").json()["model_count"] == 2
    assert client.get("/api/registry/manufacturers/lead-only").json()["model_count"] == 0
    coverage = client.get("/api/registry/coverage").json()
    assert coverage["total_models"] == 2
    assert coverage["hp_coverage_pct"] == 100


def test_registry_services_hide_unknown_rows_unless_asked(db_session: Session, rows: dict) -> None:
    assert services.search_models(q="lead", db=db_session) == []
    assert services.get_coverage_report(db=db_session)["total_models"] == 2
    found = services.search_models(q="lead", db=db_session, include_unknown_basis=True)
    assert {row["name"] for row in found} == set(LEAD_NAMES)
    assert services.get_coverage_report(db=db_session, include_unknown_basis=True)["total_models"] == 4


def test_the_anonymous_module_list_leaves_out_rows_sharing_an_unknown_catalog_row(
    client: TestClient, rows: dict
) -> None:
    body = client.get("/api/modules/").json()
    assert body["total"] == 2
    assert {m["name"] for m in body["modules"]} == {"Known Osc", "Not In Catalog"}


def test_anonymous_single_module_reads_hide_rows_sharing_an_unknown_catalog_row(
    client: TestClient, rows: dict
) -> None:
    lead_id = rows["lead"].id
    assert client.get(f"/api/modules/{lead_id}").status_code == 404
    assert client.get(f"/api/modules/{lead_id}/power-configs").status_code == 404
    for key in ("known", "no_catalog_row"):
        assert client.get(f"/api/modules/{rows[key].id}").status_code == 200
        assert client.get(f"/api/modules/{rows[key].id}/power-configs").status_code == 200


def _case_record() -> dict:
    return {
        "manufacturer": "Full Co",
        "model": "Dual 84",
        "format_family": "eurorack",
        "production_status": "available",
        "powered": True,
        "revision": {
            "revision_key": "research-2026",
            "row_count": 1,
            "capacity_value": 84,
            "capacity_unit": "hp",
            "depth_min_mm": 50,
            "confidence": "medium",
        },
        "rows": [
            {
                "row_index": 0,
                "format_family": "eurorack",
                "capacity_value": 84,
                "capacity_unit": "hp",
                "depth_min_mm": 50,
            }
        ],
        "power_systems": [],
        "features": [],
        "sources": [],
        "prices": [],
    }


def test_the_case_compatibility_check_does_not_resolve_a_hidden_module_for_anonymous_callers(
    client: TestClient, db_session: Session, rows: dict
) -> None:
    assert import_records(db_session, [_case_record()])["inserted"] == 1
    body = {"modules": [{"module_id": rows["lead"].id, "row_index": 0, "start_hp": 0}]}
    url = "/api/cases/catalog/full-co-dual-84/compatibility"

    anonymous = client.post(url, json=body)
    assert anonymous.status_code == 200, anonymous.text
    assert "Lead LFO" not in anonymous.text
    assert "MODULE_NOT_FOUND" in anonymous.text

    signed_in = client.post(url, json=body, headers=_signed_in(db_session, "User"))
    assert signed_in.status_code == 200, signed_in.text
    assert "MODULE_NOT_FOUND" not in signed_in.text


# --- Signed in --------------------------------------------------------------------


@pytest.mark.parametrize("role", ["User", "Admin"])
def test_a_signed_in_caller_reads_every_live_row(
    client: TestClient, db_session: Session, rows: dict, role: str
) -> None:
    headers = _signed_in(db_session, role)
    body = client.get("/api/modules/catalog", headers=headers).json()
    assert body["total"] == 4
    names = {row["name"] for row in body["modules"]}
    assert names == {"Known Osc", "Untagged Filter", *LEAD_NAMES}
    # The UI's "Unverified lead" chip reads this.
    lead = next(row for row in body["modules"] if row["slug"] == LEAD_SLUG)
    assert lead["evidence_status"] == "CATALOG_OBSERVED"

    assert client.get("/api/modules/catalog/stats", headers=headers).json()["total_modules"] == 4
    brands = client.get("/api/modules/catalog/brands", headers=headers).json()["brands"]
    assert {b["name"] for b in brands} == {"Maker One", "Lead Only"}
    categories = client.get("/api/modules/catalog/categories", headers=headers).json()["categories"]
    assert {c["name"] for c in categories} == {"VCO", "VCF", "LFO", "ENV"}


@pytest.mark.parametrize("role", ["User", "Admin"])
def test_a_signed_in_caller_can_read_and_materialize_an_unknown_basis_row(
    client: TestClient, db_session: Session, rows: dict, role: str
) -> None:
    headers = _signed_in(db_session, role)
    assert client.get(f"/api/modules/catalog/{LEAD_SLUG}", headers=headers).status_code == 200
    # A slug lookup still answers for a retired row (FR-036).
    assert client.get(f"/api/modules/catalog/{RETIRED_LEAD_SLUG}", headers=headers).status_code == 200
    placed = client.post(f"/api/modules/catalog/{LEAD_SLUG}/materialize", headers=headers)
    assert placed.status_code == 200
    assert placed.json()["module_id"] == rows["lead"].id


@pytest.mark.parametrize("role", ["User", "Admin"])
def test_a_signed_in_caller_reads_the_full_registry_and_module_list(
    client: TestClient, db_session: Session, rows: dict, role: str
) -> None:
    headers = _signed_in(db_session, role)
    search = client.get("/api/registry/search", params={"q": "lead"}, headers=headers).json()["results"]
    assert {row["name"] for row in search} == set(LEAD_NAMES)
    maker = client.get("/api/registry/manufacturers/lead-only", headers=headers).json()
    assert maker["model_count"] == 1
    assert client.get("/api/registry/coverage", headers=headers).json()["total_models"] == 4
    items = client.get("/api/registry/manufacturers", headers=headers).json()["items"]
    assert {m["slug"]: m["model_count"] for m in items} == {"maker-one": 3, "lead-only": 1}

    # The rack builder's module picker reads this list.
    modules = client.get("/api/modules/", headers=headers).json()
    assert modules["total"] == 3
    assert "Lead LFO" in {m["name"] for m in modules["modules"]}
    assert client.get(f"/api/modules/{rows['lead'].id}", headers=headers).status_code == 200


# --- A token that no longer counts is not the same as no token ---------------------


FILTERED_READS = [
    "/api/modules/catalog",
    "/api/modules/catalog/brands",
    "/api/modules/catalog/categories",
    "/api/modules/catalog/stats",
    f"/api/modules/catalog/{KNOWN_SLUG}",
    "/api/modules/",
    "/api/registry/search?q=lead",
    "/api/registry/coverage",
    "/api/registry/manufacturers",
    "/api/registry/manufacturers/maker-one",
    "/api/registry/manufacturers/maker-one/models",
]


def _expired_token(user: User) -> str:
    return create_access_token(
        {"user_id": user.id, "username": user.username}, expires_delta=timedelta(seconds=-1)
    )


@pytest.mark.parametrize("url", FILTERED_READS)
def test_an_expired_token_gets_a_401_so_the_client_renews_it(
    client: TestClient, db_session: Session, rows: dict, url: str
) -> None:
    """The web client renews on a 401. A silent anonymous answer would never trigger that,
    so a signed-in person would lose the leads 15 minutes after their last renewal."""
    token = _expired_token(make_user(db_session, "stale"))
    response = client.get(url, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_an_expired_token_gets_a_401_on_materialize_and_compatibility(
    client: TestClient, db_session: Session, rows: dict
) -> None:
    headers = {"Authorization": f"Bearer {_expired_token(make_user(db_session, 'stale'))}"}
    assert client.post(f"/api/modules/catalog/{LEAD_SLUG}/materialize", headers=headers).status_code == 401
    assert client.get(f"/api/modules/{rows['lead'].id}", headers=headers).status_code == 401
    assert (
        client.get(f"/api/modules/{rows['lead'].id}/power-configs", headers=headers).status_code == 401
    )
    assert (
        client.post(
            "/api/cases/catalog/no-such-case/compatibility", json={"modules": []}, headers=headers
        ).status_code
        == 401
    )


def test_a_revoked_token_gets_a_401(client: TestClient, db_session: Session, rows: dict) -> None:
    user = make_user(db_session, "revoked")
    headers = bearer_headers(user)
    user.token_version = int(user.token_version or 0) + 1
    db_session.commit()
    assert client.get("/api/modules/catalog", headers=headers).status_code == 401


def test_a_request_without_a_bearer_token_is_anonymous(client: TestClient, rows: dict) -> None:
    assert client.get("/api/modules/catalog").json()["total"] == 2
    basic = client.get("/api/modules/catalog", headers={"Authorization": "Basic abc"})
    assert basic.status_code == 200
    assert basic.json()["total"] == 2


# --- A row someone already placed --------------------------------------------------


def _placement(module: Module, start_hp: int = 0) -> dict:
    return {"module_id": module.id, "row_index": 0, "start_hp": start_hp}


@pytest.fixture
def placed_rack(client: TestClient, db_session: Session, rows: dict, sample_case: Case) -> dict:
    owner = make_user(db_session, "rackowner2")
    headers = bearer_headers(owner)
    created = client.post(
        "/api/racks",
        headers=headers,
        json={
            "case_id": sample_case.id,
            "name": "Rig with a lead",
            "is_public": True,
            "modules": [_placement(rows["lead"])],
        },
    )
    assert created.status_code == 201, created.text
    return {"id": created.json()["id"], "headers": headers}


def _placed_names(rack: dict) -> list[str]:
    return [placed["module"]["name"] for placed in rack["modules"]]


def test_a_signed_in_person_can_place_a_module_with_an_unknown_catalog_row(placed_rack: dict) -> None:
    assert placed_rack["id"]


def test_a_placed_module_renders_on_its_owners_rack_after_the_catalog_hides_it(
    client: TestClient, placed_rack: dict
) -> None:
    assert client.get("/api/modules/catalog", params={"search": "Lead LFO"}).json()["total"] == 0
    rack = client.get(f"/api/racks/{placed_rack['id']}", headers=placed_rack["headers"]).json()
    assert _placed_names(rack) == ["Lead LFO"]
    module = rack["modules"][0]["module"]
    assert (module["brand"], module["hp"]) == ("Lead Only", 4)


def test_a_placed_module_renders_on_a_public_rack_for_an_anonymous_reader(
    client: TestClient, placed_rack: dict
) -> None:
    rack = client.get(f"/api/racks/{placed_rack['id']}").json()
    assert _placed_names(rack) == ["Lead LFO"]
    listed = client.get("/api/racks", params={"is_public": True}).json()["racks"]
    assert _placed_names(next(r for r in listed if r["id"] == placed_rack["id"])) == ["Lead LFO"]


def test_an_existing_rack_with_a_placed_lead_can_still_be_saved_and_checked(
    client: TestClient, db_session: Session, rows: dict, placed_rack: dict
) -> None:
    saved = client.patch(
        f"/api/racks/{placed_rack['id']}",
        headers=placed_rack["headers"],
        json={"modules": [_placement(rows["lead"]), _placement(rows["known"], start_hp=4)]},
    )
    assert saved.status_code == 200, saved.text
    assert _placed_names(saved.json()) == ["Lead LFO", "Known Osc"]
    # These test modules declare no power draw; nothing else is warned about.
    codes = {warning["details"]["code"] for warning in saved.json()["validation_warnings"]}
    assert codes == {"POWER_RAIL_INCOMPLETE"}
    compatibility = client.get(f"/api/racks/{placed_rack['id']}/compatibility")
    assert compatibility.status_code == 200
