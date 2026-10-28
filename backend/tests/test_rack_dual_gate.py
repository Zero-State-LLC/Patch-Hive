"""Dual-gate: legacy validation + catalog conflicts on rack write."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.materialize import materialize_legacy_case
from core.database import get_db
from integrations.case_catalog_populator import import_records
from main import app
from modules.models import Module
from racks.models import Rack


def _shallow_case() -> dict:
    return {
        "manufacturer": "Gate Co",
        "model": "Shallow 40",
        "format_family": "eurorack",
        "production_status": "available",
        "powered": True,
        "revision": {
            "revision_key": "research-2026",
            "row_count": 1,
            "capacity_value": 40,
            "capacity_unit": "hp",
            "depth_min_mm": 30,
            "depth_max_mm": 30,
            "confidence": "medium",
        },
        "rows": [
            {
                "row_index": 0,
                "format_family": "eurorack",
                "capacity_value": 40,
                "capacity_unit": "hp",
                "depth_min_mm": 30,
            }
        ],
        "power_systems": [
            {
                "name": "primary",
                "connector_count": 4,
                "current_pos12_ma": 500,
                "current_neg12_ma": 500,
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
    from tests.conftest import bearer_headers, make_user

    # Racks are owner-scoped: these tests create racks as a signed-in user.
    yield TestClient(app, headers=bearer_headers(make_user(db_session)))
    app.dependency_overrides.clear()


@pytest.fixture
def shallow_setup(db_session: Session) -> dict:
    assert import_records(db_session, [_shallow_case()])["inserted"] == 1
    legacy, _ = materialize_legacy_case(db_session, "gate-co-shallow-40")
    deep = Module(
        brand="Deep",
        name="Too Deep",
        hp=10,
        module_type="FX",
        power_12v_ma=50,
        power_neg12v_ma=20,
        power_5v_ma=0,
        depth_mm=50.0,
        io_ports=[],
        tags=[],
        source="test",
    )
    ok = Module(
        brand="OK",
        name="Fits",
        hp=8,
        module_type="UTIL",
        power_12v_ma=20,
        power_neg12v_ma=20,
        power_5v_ma=0,
        depth_mm=25.0,
        io_ports=[],
        tags=[],
        source="test",
    )
    db_session.add_all([deep, ok])
    db_session.commit()
    db_session.refresh(deep)
    db_session.refresh(ok)
    return {"case_id": legacy.id, "deep_id": deep.id, "ok_id": ok.id}


def test_create_rack_catalog_depth_conflict_hard_fails(
    client: TestClient, shallow_setup: dict
) -> None:
    resp = client.post(
        "/api/racks/",
        json={
            "case_id": shallow_setup["case_id"],
            "name": "Deep fail",
            "modules": [
                {
                    "module_id": shallow_setup["deep_id"],
                    "row_index": 0,
                    "start_hp": 0,
                }
            ],
        },
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["message"] == "Rack validation failed"
    codes = [e.get("details", {}).get("code") for e in detail["errors"]]
    assert any(c and ("DEPTH" in str(c) or "PHYSICAL" in str(c) or "CONFLICT" in str(c)) for c in codes)


def test_create_rack_catalog_ok_passes(client: TestClient, shallow_setup: dict) -> None:
    resp = client.post(
        "/api/racks/",
        json={
            "case_id": shallow_setup["case_id"],
            "name": "Fits",
            "modules": [
                {
                    "module_id": shallow_setup["ok_id"],
                    "row_index": 0,
                    "start_hp": 0,
                }
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["case"]["catalog_slug"] == "gate-co-shallow-40"
    assert body["modules"]


def test_update_rack_catalog_conflict(client: TestClient, shallow_setup: dict, db_session: Session) -> None:
    create = client.post(
        "/api/racks/",
        json={
            "case_id": shallow_setup["case_id"],
            "name": "Start ok",
            "modules": [
                {
                    "module_id": shallow_setup["ok_id"],
                    "row_index": 0,
                    "start_hp": 0,
                }
            ],
        },
    )
    assert create.status_code == 201
    rack_id = create.json()["id"]

    bad = client.patch(
        f"/api/racks/{rack_id}",
        json={
            "modules": [
                {
                    "module_id": shallow_setup["deep_id"],
                    "row_index": 0,
                    "start_hp": 0,
                }
            ]
        },
    )
    assert bad.status_code == 400
