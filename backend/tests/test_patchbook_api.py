"""API tests for PatchBook export endpoint."""

from __future__ import annotations

import pytest

pytest.importorskip("httpx", reason="httpx is required for FastAPI TestClient")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from export.patchbook.models import PATCHBOOK_TEMPLATE_VERSION
from main import app
from patches.models import Patch
from racks.models import Rack


@pytest.fixture(autouse=True)
def legacy_patchbook_on(monkeypatch):
    from core import settings

    monkeypatch.setattr(settings, "enable_legacy_patchbook_export", True)


@pytest.fixture
def client(db_session: Session, owner_headers: dict):
    from core import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, headers=owner_headers)
    app.dependency_overrides.clear()


def _create_patch(db_session: Session, rack: Rack) -> Patch:
    patch = Patch(
        rack_id=rack.id,
        run_id=None,
        name="API Patch",
        category="Voice",
        description="API test patch",
        connections=[
            {
                "from_module_id": rack.modules[0].module_id,
                "from_port": "Audio Out",
                "to_module_id": rack.modules[1].module_id,
                "to_port": "Audio In",
                "cable_type": "audio",
            }
        ],
        generation_seed=7,
        generation_version="1.0.0",
        engine_config={"parameters": {str(rack.modules[0].module_id): {"Tune": "1 o'clock"}}},
    )
    db_session.add(patch)
    db_session.commit()
    db_session.refresh(patch)
    return patch


def test_export_patchbook_api_headers(
    client: TestClient, db_session: Session, sample_rack_basic: Rack
):
    patch = _create_patch(db_session, sample_rack_basic)
    payload = {"rack_id": sample_rack_basic.id, "patch_ids": [patch.id]}

    response = client.post("/api/export/patchbook", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["X-PatchBook-Template-Version"] == PATCHBOOK_TEMPLATE_VERSION

    expected_hash = response.headers["X-PatchBook-Content-Hash"]
    assert expected_hash

    response_repeat = client.post("/api/export/patchbook", json=payload)
    assert response_repeat.headers["X-PatchBook-Content-Hash"] == expected_hash


def test_the_legacy_patch_book_is_off_unless_enabled(
    client: TestClient, db_session: Session, sample_rack_basic: Rack, monkeypatch
):
    from core import settings

    monkeypatch.setattr(settings, "enable_legacy_patchbook_export", False)
    patch = _create_patch(db_session, sample_rack_basic)
    resp = client.post("/api/export/patchbook", json={"rack_id": sample_rack_basic.id, "patch_ids": [patch.id]})
    assert resp.status_code == 410
    assert resp.json()["detail"].startswith("LEGACY_PATCHBOOK_EXPORT_DISABLED")


def test_a_patch_from_another_rig_is_refused(
    client: TestClient, db_session: Session, sample_rack_basic: Rack, sample_rack_full: Rack
):
    """Spec 002 FR-013/FR-014: a book compiles against one rig, never silently dropping modules."""
    ours = _create_patch(db_session, sample_rack_basic)
    theirs = _create_patch(db_session, sample_rack_full)
    resp = client.post(
        "/api/export/patchbook",
        json={"rack_id": sample_rack_basic.id, "patch_ids": [ours.id, theirs.id]},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == {"code": "PATCH_BOOK_REFERENCE_UNRESOLVED", "patch_ids": [theirs.id]}


def test_an_unreadable_patch_is_not_named(
    client: TestClient, db_session: Session, sample_rack_basic: Rack, sample_case
):
    """An inaccessible patch stays a 404; its id never appears in the foreign-patch error."""
    from tests.conftest import make_user

    stranger = make_user(db_session, "stranger-book")
    private = Rack(user_id=stranger.id, name="Private", case_id=sample_case.id, is_public=False)
    db_session.add(private)
    db_session.commit()
    hidden = Patch(rack_id=private.id, name="Hidden", category="Voice", connections=[],
                   generation_seed=1, generation_version="1.0.0")
    db_session.add(hidden)
    db_session.commit()
    ours = _create_patch(db_session, sample_rack_basic)
    resp = client.post(
        "/api/export/patchbook",
        json={"rack_id": sample_rack_basic.id, "patch_ids": [ours.id, hidden.id]},
    )
    assert resp.status_code == 404
    assert str(hidden.id) not in resp.text
