"""Rig revision listing and mutable patch overlays."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.models import Case
from community.models import User
from core import create_access_token, get_db
from main import app
from racks.models import Rack
from runs.models import Run


def _client(db_session: Session) -> TestClient:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"user_id": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def test_list_rig_revisions_groups_runs(db_session: Session) -> None:
    user = User(username="rev-user", email="rev@example.com", password_hash="h")
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
    rack = Rack(user_id=user.id, case_id=case.id, name="Rig")
    db_session.add(rack)
    db_session.flush()
    db_session.add(Run(rack_id=rack.id, status="completed", created_at=datetime.utcnow()))
    db_session.add(Run(rack_id=rack.id, status="completed", created_at=datetime.utcnow()))
    db_session.commit()

    client = _client(db_session)
    resp = client.get(f"/api/canon/rigs/{rack.id}/revisions", headers=_auth_headers(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1
    assert body["revisions"][0]["rig_revision_id"].startswith("rig-rev-")
    assert body["revisions"][0]["run_count"] >= 1
    app.dependency_overrides.clear()


def test_overlay_upsert_and_get(db_session: Session) -> None:
    user = User(username="ov-user", email="ov@example.com", password_hash="h")
    db_session.add(user)
    db_session.commit()

    client = _client(db_session)
    headers = _auth_headers(user)
    patch_ref = "legacy-patch-42"

    empty = client.get(f"/api/canon/overlays/{patch_ref}", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["favorite"] is False

    put = client.put(
        f"/api/canon/overlays/{patch_ref}",
        headers=headers,
        json={"notes": "try with slower LFO", "favorite": True, "tried": False},
    )
    assert put.status_code == 200, put.text
    assert put.json()["notes"] == "try with slower LFO"
    assert put.json()["favorite"] is True
    assert put.json()["id"].startswith("overlay-")

    got = client.get(f"/api/canon/overlays/{patch_ref}", headers=headers)
    assert got.json()["favorite"] is True
    assert got.json()["notes"] == "try with slower LFO"

    # Patch only tried flag
    put2 = client.put(
        f"/api/canon/overlays/{patch_ref}",
        headers=headers,
        json={"tried": True},
    )
    assert put2.json()["tried"] is True
    assert put2.json()["favorite"] is True
    assert put2.json()["notes"] == "try with slower LFO"

    unauth = client.put(f"/api/canon/overlays/{patch_ref}", json={"favorite": False})
    assert unauth.status_code == 401
    app.dependency_overrides.clear()
