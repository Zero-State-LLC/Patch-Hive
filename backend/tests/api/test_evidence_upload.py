"""Multi-image evidence upload and retention."""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from canon.models import ImageAssetRecord
from evidence.retention import expire_image_assets
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


def test_multi_image_upload_and_list(
    db_session: Session, sample_rack_basic: Rack, tmp_path
) -> None:
    from core import settings

    settings.export_dir = str(tmp_path)
    client = _client(db_session)
    files = [
        ("files", ("a.jpg", _jpeg_bytes(), "image/jpeg")),
        ("files", ("b.jpg", _jpeg_bytes(130, 100), "image/jpeg")),
    ]
    data = {
        "retention_days": "14",
        "consent_provider_processing": "false",
        "run_vision_mock": "true",
    }
    resp = client.post(
        f"/api/racks/{sample_rack_basic.id}/evidence/images",
        files=files,
        data=data,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["uploaded"]) == 2
    assert body["rejected"] == []
    assert all(item["retention_days"] == 14 for item in body["uploaded"])
    assert all(
        item.get("evidence_status") in {"INFERRED", "NOT_COMPUTABLE"} for item in body["uploaded"]
    )

    listed = client.get(f"/api/racks/{sample_rack_basic.id}/evidence/images")
    assert listed.status_code == 200
    assert listed.json()["total"] == 2

    asset_id = body["uploaded"][0]["id"]
    deleted = client.delete(f"/api/racks/{sample_rack_basic.id}/evidence/images/{asset_id}")
    assert deleted.status_code == 200
    listed2 = client.get(f"/api/racks/{sample_rack_basic.id}/evidence/images")
    assert listed2.json()["total"] == 1
    app.dependency_overrides.clear()


def test_reject_hostile_and_tiny(db_session: Session, sample_rack_basic: Rack, tmp_path) -> None:
    from core import settings

    settings.export_dir = str(tmp_path)
    client = _client(db_session)
    files = [
        ("files", ("evil.svg", b"<svg><script/></svg>", "image/svg+xml")),
        ("files", ("tiny.jpg", _jpeg_bytes(16, 16), "image/jpeg")),
    ]
    resp = client.post(
        f"/api/racks/{sample_rack_basic.id}/evidence/images",
        files=files,
        data={"retention_days": "30"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["uploaded"] == []
    assert len(body["rejected"]) == 2
    app.dependency_overrides.clear()


def test_retention_expiry(db_session: Session, sample_rack_basic: Rack, tmp_path) -> None:
    from core import settings

    settings.export_dir = str(tmp_path)
    client = _client(db_session)
    resp = client.post(
        f"/api/racks/{sample_rack_basic.id}/evidence/images",
        files=[("files", ("a.jpg", _jpeg_bytes(), "image/jpeg"))],
        data={"retention_days": "1"},
    )
    assert resp.status_code == 201
    asset_id = resp.json()["uploaded"][0]["id"]
    record = db_session.get(ImageAssetRecord, asset_id)
    assert record is not None
    record.retention_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    result = expire_image_assets(db_session)
    db_session.commit()
    assert result["soft_deleted"] == 1
    refreshed = db_session.get(ImageAssetRecord, asset_id)
    assert refreshed is not None
    assert refreshed.deleted_at is not None
    app.dependency_overrides.clear()
