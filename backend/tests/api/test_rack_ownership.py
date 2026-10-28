"""
Users own their racks: owners read and change them, public racks are readable by
anyone, admin read roles read everything, and everyone else sees 404.
"""

import pytest

pytest.importorskip("httpx", reason="httpx is required for FastAPI TestClient")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.models import Case
from main import app
from modules.models import Module
from patches.models import Patch
from racks.models import Rack
from tests.conftest import bearer_headers, make_user


@pytest.fixture
def client(db_session: Session):
    from core import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def people(db_session: Session) -> dict:
    return {
        "owner": make_user(db_session, "owner"),
        "other": make_user(db_session, "other"),
        "support": make_user(db_session, "support", "Support"),
    }


def _rack(db_session: Session, user_id: int, case: Case, *, public: bool = False) -> Rack:
    rack = Rack(user_id=user_id, case_id=case.id, name="Rig", tags=[], is_public=public)
    db_session.add(rack)
    db_session.commit()
    return rack


def _patch(db_session: Session, rack: Rack, *, public: bool = False) -> Patch:
    patch = Patch(
        rack_id=rack.id, name="P", category="Voice", connections=[], generation_seed=1,
        generation_version="1.0.0", engine_config={}, is_public=public,
    )
    db_session.add(patch)
    db_session.commit()
    return patch


def test_creating_a_rack_needs_a_user_and_records_the_owner(
    client: TestClient, people: dict, sample_case: Case, sample_vco: Module
) -> None:
    body = {"case_id": sample_case.id, "modules": [{"module_id": sample_vco.id, "row_index": 0, "start_hp": 0}]}
    assert client.post("/api/racks", json=body).status_code == 401
    created = client.post("/api/racks", json=body, headers=bearer_headers(people["owner"]))
    assert created.status_code == 201
    assert created.json()["user_id"] == people["owner"].id


def test_a_private_rack_is_hidden_from_everyone_but_its_owner_and_admins(
    client: TestClient, db_session: Session, people: dict, sample_case: Case
) -> None:
    rack = _rack(db_session, people["owner"].id, sample_case)
    url = f"/api/racks/{rack.id}"
    assert client.get(url).status_code == 404
    assert client.get(url, headers=bearer_headers(people["other"])).status_code == 404
    assert client.get(url, headers=bearer_headers(people["owner"])).status_code == 200
    assert client.get(url, headers=bearer_headers(people["support"])).status_code == 200
    # A non-owner cannot even learn it exists through a write.
    assert client.patch(url, json={"name": "x"}, headers=bearer_headers(people["other"])).status_code == 404
    assert client.delete(url, headers=bearer_headers(people["other"])).status_code == 404


def test_a_public_rack_is_readable_but_only_its_owner_changes_it(
    client: TestClient, db_session: Session, people: dict, sample_case: Case
) -> None:
    rack = _rack(db_session, people["owner"].id, sample_case, public=True)
    url = f"/api/racks/{rack.id}"
    assert client.get(url).status_code == 200
    other = bearer_headers(people["other"])
    assert client.patch(url, json={"name": "x"}, headers=other).status_code == 403
    assert client.delete(url, headers=other).status_code == 403
    assert client.post(f"/api/patches/generate/{rack.id}", json={}, headers=other).status_code == 403
    # Admin read roles can read, not write.
    assert client.delete(url, headers=bearer_headers(people["support"])).status_code == 403
    owner = bearer_headers(people["owner"])
    assert client.patch(url, json={"name": "Mine"}, headers=owner).json()["name"] == "Mine"
    assert client.delete(url, headers=owner).status_code == 204


def test_lists_show_own_and_public_racks_only(
    client: TestClient, db_session: Session, people: dict, sample_case: Case
) -> None:
    mine = _rack(db_session, people["owner"].id, sample_case)
    theirs = _rack(db_session, people["other"].id, sample_case)
    shared = _rack(db_session, people["other"].id, sample_case, public=True)

    def ids(headers=None, path="/api/racks/", key="racks", field="id"):
        return {r[field] for r in client.get(path, headers=headers or {}).json()[key]}

    assert ids() == {shared.id}
    assert ids(bearer_headers(people["owner"])) == {mine.id, shared.id}
    assert ids(bearer_headers(people["support"])) == {mine.id, theirs.id, shared.id}
    canon = ids(bearer_headers(people["owner"]), "/api/canon/rigs", "rigs", "rig_id")
    assert canon == {mine.id, shared.id}


def test_patches_follow_their_rack(
    client: TestClient, db_session: Session, people: dict, sample_case: Case
) -> None:
    rack = _rack(db_session, people["owner"].id, sample_case)
    hidden = _patch(db_session, rack)
    shared = _patch(db_session, rack, public=True)
    other = bearer_headers(people["other"])
    assert client.get(f"/api/patches/{hidden.id}", headers=other).status_code == 404
    assert client.get(f"/api/patches/{shared.id}", headers=other).status_code == 200
    assert client.delete(f"/api/patches/{shared.id}", headers=other).status_code == 403
    listed = {p["id"] for p in client.get("/api/patches/", headers=other).json()["patches"]}
    assert listed == {shared.id}
    assert client.get(f"/api/export/racks/{rack.id}/layout.svg", headers=other).status_code == 404
    assert client.get("/api/runs/", params={"rack_id": rack.id}, headers=other).status_code == 404
    owner = bearer_headers(people["owner"])
    assert client.delete(f"/api/patches/{hidden.id}", headers=owner).status_code == 204
