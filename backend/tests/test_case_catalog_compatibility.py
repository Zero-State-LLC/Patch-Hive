"""Tests for catalog-backed rack compatibility calculations."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.database import get_db
from integrations.case_catalog_populator import import_records
from main import app
from modules.models import Module


def _case_record() -> dict:
    return {
        "manufacturer": "Fit Co",
        "model": "Skiff 84",
        "format_family": "eurorack",
        "production_status": "available",
        "powered": True,
        "revision": {
            "revision_key": "research-2026",
            "row_count": 1,
            "capacity_value": 84,
            "capacity_unit": "hp",
            "depth_min_mm": 40,
            "depth_max_mm": 45,
            "close_patched_lid": False,
            "removable_lid": True,
            "portable": True,
            "confidence": "medium",
        },
        "rows": [
            {
                "row_index": 0,
                "format_family": "eurorack",
                "capacity_value": 84,
                "capacity_unit": "hp",
                "depth_min_mm": 40,
                "depth_max_mm": 45,
            }
        ],
        "power_systems": [
            {
                "name": "primary",
                "supply_type": "external_brick",
                "connector_count": 2,
                "current_pos12_ma": 1000,
                "current_neg12_ma": 1000,
                "current_pos5_ma": 0,
            }
        ],
        "features": [],
        "sources": [],
        "prices": [],
    }


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def catalog_case(db_session: Session) -> None:
    receipt = import_records(db_session, [_case_record()])
    assert receipt["inserted"] == 1


@pytest.fixture
def modules(db_session: Session) -> dict[str, Module]:
    shallow = Module(
        brand="Test",
        name="Shallow 10",
        hp=10,
        module_type="UTIL",
        power_12v_ma=50,
        power_neg12v_ma=40,
        power_5v_ma=0,
        io_ports=[],
        tags=[],
        source="test",
    )
    deep = Module(
        brand="Test",
        name="Deep 20",
        hp=20,
        module_type="VCO",
        power_12v_ma=200,
        power_neg12v_ma=50,
        power_5v_ma=100,
        io_ports=[],
        tags=[],
        source="test",
    )
    db_session.add_all([shallow, deep])
    db_session.commit()
    db_session.refresh(shallow)
    db_session.refresh(deep)
    return {"shallow": shallow, "deep": deep}


def test_compatibility_verified_fit(client: TestClient, catalog_case: None, modules: dict) -> None:
    resp = client.post(
        "/api/cases/catalog/fit-co-skiff-84/compatibility",
        json={
            "modules": [
                {
                    "module_id": modules["shallow"].id,
                    "row_index": 0,
                    "start_hp": 0,
                    "depth_mm": 35,
                }
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_status"] in {"verified", "incomplete"}
    assert body["format_check"]["status"] == "verified"
    assert body["physical_fit"]["status"] == "verified"
    assert body["remaining_capacity"][0]["remaining_value"] == 74
    assert body["connector_availability"]["status"] == "verified"
    rails = {r["rail"]: r for r in body["power_headroom"]}
    assert rails["+12V"]["headroom_ma"] == 950
    assert rails["+5V"]["status"] == "verified"


def test_compatibility_depth_and_power_conflicts(
    client: TestClient, catalog_case: None, modules: dict
) -> None:
    resp = client.post(
        "/api/cases/catalog/fit-co-skiff-84/compatibility",
        json={
            "modules": [
                {
                    "module_id": modules["deep"].id,
                    "row_index": 0,
                    "start_hp": 0,
                    "depth_mm": 50,
                }
            ],
            "plan_close_lid": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["physical_fit"]["status"] == "conflict"
    assert body["pos5_compatibility"]["status"] == "conflict"
    assert body["lid_close"]["status"] == "conflict"
    assert body["overall_status"] == "conflict"


def test_compatibility_incomplete_without_module_depth(
    client: TestClient, catalog_case: None, modules: dict, db_session: Session
) -> None:
    # Ensure registry depth is null so depth fit stays incomplete without override.
    modules["shallow"].depth_mm = None
    db_session.add(modules["shallow"])
    db_session.commit()

    resp = client.post(
        "/api/cases/catalog/fit-co-skiff-84/compatibility",
        json={
            "modules": [
                {
                    "module_id": modules["shallow"].id,
                    "row_index": 0,
                    "start_hp": 0,
                }
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["physical_fit"]["status"] == "incomplete"
    assert any(w["code"] == "DEPTH_MODULE_UNKNOWN" for w in body["warnings"])


def test_compatibility_uses_registry_depth_mm(
    client: TestClient, catalog_case: None, modules: dict, db_session: Session
) -> None:
    modules["shallow"].depth_mm = 35.0
    db_session.add(modules["shallow"])
    db_session.commit()

    resp = client.post(
        "/api/cases/catalog/fit-co-skiff-84/compatibility",
        json={
            "modules": [
                {
                    "module_id": modules["shallow"].id,
                    "row_index": 0,
                    "start_hp": 0,
                }
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["physical_fit"]["status"] == "verified"
    assert not any(w["code"] == "DEPTH_MODULE_UNKNOWN" for w in body["warnings"])


def test_compatibility_connector_overflow(
    client: TestClient, catalog_case: None, modules: dict
) -> None:
    resp = client.post(
        "/api/cases/catalog/fit-co-skiff-84/compatibility",
        json={
            "modules": [
                {
                    "module_id": modules["shallow"].id,
                    "row_index": 0,
                    "start_hp": 0,
                    "depth_mm": 30,
                },
                {
                    "module_id": modules["shallow"].id,
                    "row_index": 0,
                    "start_hp": 10,
                    "depth_mm": 30,
                },
                {
                    "module_id": modules["shallow"].id,
                    "row_index": 0,
                    "start_hp": 20,
                    "depth_mm": 30,
                },
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["connector_availability"]["status"] == "conflict"
    assert body["connector_availability"]["code"] == "CONNECTORS_EXCEEDED"


def test_compatibility_not_found(client: TestClient) -> None:
    resp = client.post(
        "/api/cases/catalog/missing-case/compatibility",
        json={"modules": []},
    )
    assert resp.status_code == 404


def _module(db: Session, name: str, **power) -> Module:
    m = Module(brand="Test", name=name, hp=4, module_type="UTIL", io_ports=[], tags=[], source="test", **power)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _check(client: TestClient, *mods: Module) -> dict:
    resp = client.post(
        "/api/cases/catalog/fit-co-skiff-84/compatibility",
        json={"modules": [
            {"module_id": m.id, "row_index": 0, "start_hp": i * 4, "depth_mm": 30} for i, m in enumerate(mods)
        ]},
    )
    assert resp.status_code == 200
    return resp.json()


def test_a_missing_rail_is_unknown_not_zero(client: TestClient, catalog_case: None, db_session: Session) -> None:
    """A jumper-set module that states +-12V but not +5V is not assumed to need no +5V."""
    jumper = _module(db_session, "Jumper Module", power_12v_ma=60, power_neg12v_ma=20, power_5v_ma=None)
    body = _check(client, jumper)
    rails = {r["rail"]: r for r in body["power_headroom"]}
    assert rails["+12V"]["status"] == "verified" and rails["+12V"]["unknown_draw_count"] == 0
    assert rails["+5V"]["status"] == "incomplete"
    assert rails["+5V"]["unknown_modules"] == ["Jumper Module"]
    assert body["pos5_compatibility"]["code"] == "POS5_UNKNOWN"
    assert body["overall_status"] != "verified"
    warning = next(w for w in body["warnings"] if w["code"] == "MODULE_POWER_UNKNOWN")
    assert warning["details"]["unknown_draw_count"] == {"+12V": 0, "-12V": 0, "+5V": 1}


def test_unknown_draws_make_a_rail_a_lower_bound(client: TestClient, catalog_case: None, db_session: Session) -> None:
    known = _module(db_session, "Known", power_12v_ma=300, power_neg12v_ma=30, power_5v_ma=0)
    blank = _module(db_session, "Blank")
    rails = {r["rail"]: r for r in _check(client, known, blank)["power_headroom"]}
    plus = rails["+12V"]
    assert plus["status"] == "incomplete"
    assert (plus["module_draw_ma"], plus["headroom_ma"], plus["unknown_draw_count"]) == (300, 700, 1)
    assert plus["message"] == "+12V: at least 300mA of 1000mA plus 1 unknown; at most 700mA headroom"


def test_known_draws_over_capacity_conflict_even_with_unknowns(
    client: TestClient, catalog_case: None, db_session: Session
) -> None:
    hungry = _module(db_session, "Hungry", power_12v_ma=1200, power_neg12v_ma=10, power_5v_ma=0)
    blank = _module(db_session, "Blank")
    rails = {r["rail"]: r for r in _check(client, hungry, blank)["power_headroom"]}
    assert rails["+12V"]["status"] == "conflict"
    assert "plus 1 unknown" in rails["+12V"]["message"]
