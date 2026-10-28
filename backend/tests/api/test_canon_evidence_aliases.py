"""F4: evidence dual-mount under /api/canon/rigs/{id}/evidence/* (≡ /api/racks/...)."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from main import app
from racks.models import Rack


def _client(db_session: Session) -> TestClient:
    from core import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from tests.conftest import sample_owner_headers

    return TestClient(app, headers=sample_owner_headers(db_session))


def _jpeg_bytes(width: int = 128, height: int = 96) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (20, 40, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def test_canon_rig_evidence_upload_list_parity(
    db_session: Session, sample_rack_basic: Rack, tmp_path
) -> None:
    from core import settings

    settings.export_dir = str(tmp_path)
    client = _client(db_session)
    rid = sample_rack_basic.id
    files = [
        ("files", ("a.jpg", _jpeg_bytes(), "image/jpeg")),
    ]
    data = {
        "retention_days": "14",
        "consent_provider_processing": "false",
        "run_vision_mock": "true",
    }

    canon_post = client.post(
        f"/api/canon/rigs/{rid}/evidence/images",
        files=files,
        data=data,
    )
    assert canon_post.status_code == 201, canon_post.text
    uploaded = canon_post.json()["uploaded"]
    assert len(uploaded) == 1
    asset_id = uploaded[0]["id"]

    canon_list = client.get(f"/api/canon/rigs/{rid}/evidence/images")
    rack_list = client.get(f"/api/racks/{rid}/evidence/images")
    assert canon_list.status_code == 200
    assert rack_list.status_code == 200
    assert canon_list.json()["total"] == rack_list.json()["total"] == 1
    assert canon_list.json()["assets"][0]["id"] == asset_id

    candidates = client.get(f"/api/canon/rigs/{rid}/evidence/candidates")
    assert candidates.status_code == 200

    reconcile = client.get(f"/api/canon/rigs/{rid}/evidence/reconcile")
    assert reconcile.status_code == 200
    assert "fused_entities" in reconcile.json()

    inventory = client.get(f"/api/canon/rigs/{rid}/evidence/inventory")
    assert inventory.status_code == 200

    deleted = client.delete(f"/api/canon/rigs/{rid}/evidence/images/{asset_id}")
    assert deleted.status_code == 200
    listed = client.get(f"/api/canon/rigs/{rid}/evidence/images")
    assert listed.json()["total"] == 0

    app.dependency_overrides.clear()


def test_canon_rig_evidence_404(db_session: Session) -> None:
    client = _client(db_session)
    resp = client.get("/api/canon/rigs/999999/evidence/images")
    assert resp.status_code == 404
    app.dependency_overrides.clear()
