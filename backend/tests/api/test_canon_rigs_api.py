"""F2: thin GET /api/canon/rigs read adapter over racks table."""

from __future__ import annotations

import pytest

pytest.importorskip("httpx", reason="httpx is required for FastAPI TestClient")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.models import Case
from community.models import User
from core import get_db
from main import app
from modules.models import Module
from racks.models import Rack, RackModule


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from tests.conftest import bearer_headers, make_user

    # These tests read rigs owned by several users: sign in as a read-all admin role.
    yield TestClient(app, headers=bearer_headers(make_user(db_session, "auditor", "ReadOnly")))
    app.dependency_overrides.clear()


def _seed_rig(
    db_session: Session,
    *,
    name: str = "Canon Rig",
    is_public: bool = False,
    with_module: bool = True,
) -> Rack:
    user = User(username=f"u-{name}", email=f"{name}@example.com", password_hash="h")
    case = Case(
        brand="PH",
        name="Case",
        total_hp=84,
        rows=1,
        hp_per_row=[84],
        source="test",
    )
    db_session.add_all((user, case))
    db_session.flush()
    rack = Rack(
        user_id=user.id,
        case_id=case.id,
        name=name,
        is_public=is_public,
    )
    db_session.add(rack)
    db_session.flush()
    if with_module:
        mod = Module(
            brand="Test",
            name="VCO",
            hp=12,
            module_type="VCO",
            power_12v_ma=50,
            power_neg12v_ma=10,
            power_5v_ma=0,
            depth_mm=40,
            io_ports=[{"name": "Out", "type": "audio_out"}],
            source="test",
        )
        db_session.add(mod)
        db_session.flush()
        db_session.add(
            RackModule(rack_id=rack.id, module_id=mod.id, row_index=0, start_hp=0)
        )
    db_session.commit()
    db_session.refresh(rack)
    return rack


def test_list_canon_rigs_returns_rig_id_eq_rack_id(
    client: TestClient, db_session: Session
) -> None:
    rack = _seed_rig(db_session, name="list-a")
    _seed_rig(db_session, name="list-b", is_public=True)

    resp = client.get("/api/canon/rigs")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 2
    assert len(body["rigs"]) >= 2
    match = next(r for r in body["rigs"] if r["rig_id"] == rack.id)
    assert match["rack_id"] == match["rig_id"] == rack.id
    assert match["name"] == "list-a"
    assert match["module_count"] == 1
    assert "legacy-" not in str(match["rig_id"])


def test_list_canon_rigs_filter_public(client: TestClient, db_session: Session) -> None:
    _seed_rig(db_session, name="priv", is_public=False)
    pub = _seed_rig(db_session, name="pub", is_public=True)

    resp = client.get("/api/canon/rigs", params={"is_public": True})
    assert resp.status_code == 200
    body = resp.json()
    ids = {r["rig_id"] for r in body["rigs"]}
    assert pub.id in ids
    assert all(r["is_public"] is True for r in body["rigs"])


def test_get_canon_rig_detail(client: TestClient, db_session: Session) -> None:
    rack = _seed_rig(db_session, name="detail-rig")

    resp = client.get(f"/api/canon/rigs/{rack.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rig_id"] == body["rack_id"] == rack.id
    assert body["name"] == "detail-rig"
    assert body["module_count"] == 1
    assert len(body["modules"]) == 1
    assert body["case"] is not None
    assert body["case"]["total_hp"] == 84


def test_get_canon_rig_not_found(client: TestClient) -> None:
    resp = client.get("/api/canon/rigs/999999")
    assert resp.status_code == 404


def test_canon_rig_revisions_still_mounted(client: TestClient, db_session: Session) -> None:
    """Ensure F2 list/get did not shadow /rigs/{id}/revisions."""
    rack = _seed_rig(db_session, name="rev-rig", with_module=False)
    resp = client.get(f"/api/canon/rigs/{rack.id}/revisions")
    assert resp.status_code == 200, resp.text
    assert "revisions" in resp.json()
