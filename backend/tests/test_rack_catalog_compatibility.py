"""Rack ↔ catalog compatibility bridge tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.materialize import materialize_legacy_case
from core.database import get_db
from integrations.case_catalog_populator import import_records
from main import app
from modules.models import Module
from racks.models import Rack, RackModule


def _case() -> dict:
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
        "power_systems": [
            {
                "name": "primary",
                "connector_count": 8,
                "current_pos12_ma": 2000,
                "current_neg12_ma": 1000,
                "current_pos5_ma": 500,
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

    # Read-only checks over racks owned by other users: sign in as a read-all admin role.
    yield TestClient(app, headers=bearer_headers(make_user(db_session, "auditor", "ReadOnly")))
    app.dependency_overrides.clear()


@pytest.fixture
def wired_rack(db_session: Session) -> Rack:
    assert import_records(db_session, [_case()])["inserted"] == 1
    legacy, _ = materialize_legacy_case(db_session, "full-co-dual-84")
    module = Module(
        brand="Test",
        name="Util 8",
        hp=8,
        module_type="UTIL",
        power_12v_ma=40,
        power_neg12v_ma=20,
        power_5v_ma=0,
        io_ports=[],
        tags=[],
        source="test",
    )
    db_session.add(module)
    db_session.flush()
    rack = Rack(user_id=1, case_id=legacy.id, name="Test rig", tags=[], is_public=False)
    db_session.add(rack)
    db_session.flush()
    db_session.add(
        RackModule(rack_id=rack.id, module_id=module.id, row_index=0, start_hp=0)
    )
    db_session.commit()
    db_session.refresh(rack)
    return rack


def test_rack_compatibility_endpoint(client: TestClient, wired_rack: Rack) -> None:
    resp = client.get(f"/api/racks/{wired_rack.id}/compatibility")
    assert resp.status_code == 200
    body = resp.json()
    assert body["bridge_status"] == "ok"
    assert body["catalog_slug"] == "full-co-dual-84"
    assert body["module_count"] == 1
    assert body["compatibility"]["overall_status"] in {"verified", "incomplete"}
    assert body["compatibility"]["format_check"]["status"] == "verified"


def test_materialize_batch(client: TestClient, db_session: Session) -> None:
    assert import_records(db_session, [_case()])["inserted"] == 1
    resp = client.post("/api/cases/catalog/materialize-batch", params={"format_family": "eurorack"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scanned"] >= 1
    assert body["created"] + body["updated"] >= 1
    assert body["failed"] == 0


def test_rack_response_includes_catalog_slug(client: TestClient, wired_rack: Rack) -> None:
    resp = client.get(f"/api/racks/{wired_rack.id}")
    assert resp.status_code == 200
    case = resp.json()["case"]
    assert case["catalog_slug"] == "full-co-dual-84"
