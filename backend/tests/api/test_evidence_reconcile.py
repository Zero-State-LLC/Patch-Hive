"""API: multi-photo evidence reconcile."""

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


def _jpeg(n: int = 0) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (128 + n, 96), (10 + n, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def test_reconcile_after_multi_upload(
    db_session: Session, sample_rack_basic: Rack, tmp_path
) -> None:
    from core import settings

    settings.export_dir = str(tmp_path)
    client = _client(db_session)
    upload = client.post(
        f"/api/racks/{sample_rack_basic.id}/evidence/images",
        files=[
            ("files", ("a.jpg", _jpeg(0), "image/jpeg")),
            ("files", ("b.jpg", _jpeg(4), "image/jpeg")),
        ],
        data={"run_vision_mock": "true", "retention_days": "30"},
    )
    assert upload.status_code == 201, upload.text
    assert len(upload.json()["uploaded"]) == 2

    recon = client.get(f"/api/racks/{sample_rack_basic.id}/evidence/reconcile")
    assert recon.status_code == 200, recon.text
    body = recon.json()
    assert body["image_count"] >= 1
    assert "fused_entities" in body
    assert "conflict_count" in body
    assert "untrusted" in body["note"].lower() or "confirmation" in body["note"].lower()
    app.dependency_overrides.clear()
