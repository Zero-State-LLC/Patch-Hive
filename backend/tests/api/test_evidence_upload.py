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


def _upload(client: TestClient, rack: Rack, **data: str) -> dict:
    resp = client.post(
        f"/api/racks/{rack.id}/evidence/images",
        files=[("files", ("a.jpg", _jpeg_bytes(), "image/jpeg"))],
        data={"consent_provider_processing": "false", **data},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["uploaded"][0]


def test_retention_defaults_to_30_days_and_is_capped_at_90(
    db_session: Session, sample_rack_basic: Rack, tmp_path
) -> None:
    from core import settings

    settings.export_dir = str(tmp_path)
    client = _client(db_session)
    url = f"/api/racks/{sample_rack_basic.id}/evidence/images"
    assert _upload(client, sample_rack_basic)["retention_days"] == 30
    assert _upload(client, sample_rack_basic, retention_days="90")["retention_days"] == 90
    for days in ("91", "365", "0"):
        refused = client.post(
            url,
            files=[("files", ("a.jpg", _jpeg_bytes(), "image/jpeg"))],
            data={"retention_days": days},
        )
        assert refused.status_code == 400, days
        assert refused.json()["detail"] == "RETENTION_DAYS_INVALID"
    app.dependency_overrides.clear()


def test_owner_delete_removes_the_stored_file(
    db_session: Session, sample_rack_basic: Rack, tmp_path
) -> None:
    from pathlib import Path

    from core import settings

    settings.export_dir = str(tmp_path)
    client = _client(db_session)
    asset = _upload(client, sample_rack_basic)
    record = db_session.get(ImageAssetRecord, asset["id"])
    stored = Path(str(record.storage_path))
    assert stored.exists()

    # Default delete (no flags) soft-deletes the row and removes the bytes.
    resp = client.delete(f"/api/racks/{sample_rack_basic.id}/evidence/images/{asset['id']}")
    assert resp.status_code == 200, resp.text
    db_session.refresh(record)
    assert record.deleted_at is not None
    assert not stored.exists()
    again = client.delete(f"/api/racks/{sample_rack_basic.id}/evidence/images/{asset['id']}")
    assert again.status_code == 200
    app.dependency_overrides.clear()


def test_delete_keeps_bytes_shared_with_a_live_asset(
    db_session: Session, sample_rack_basic: Rack, tmp_path
) -> None:
    from pathlib import Path

    from core import settings

    settings.export_dir = str(tmp_path)
    client = _client(db_session)
    first = _upload(client, sample_rack_basic)
    second = _upload(client, sample_rack_basic)  # same bytes, same content hash
    stored = Path(str(db_session.get(ImageAssetRecord, first["id"]).storage_path))
    client.delete(f"/api/racks/{sample_rack_basic.id}/evidence/images/{first['id']}")
    assert stored.exists()
    client.delete(f"/api/racks/{sample_rack_basic.id}/evidence/images/{second['id']}")
    assert not stored.exists()
    app.dependency_overrides.clear()


def test_only_the_owner_can_delete_an_evidence_image(
    db_session: Session, sample_rack_basic: Rack, tmp_path
) -> None:
    from core import settings
    from tests.conftest import bearer_headers, make_user

    settings.export_dir = str(tmp_path)
    client = _client(db_session)
    asset = _upload(client, sample_rack_basic)
    url = f"/api/racks/{sample_rack_basic.id}/evidence/images/{asset['id']}"

    stranger = make_user(db_session, "stranger")
    assert client.delete(url, headers=bearer_headers(stranger)).status_code == 404
    assert db_session.get(ImageAssetRecord, asset["id"]).deleted_at is None
    missing = client.delete(f"/api/racks/{sample_rack_basic.id}/evidence/images/img-nope")
    assert missing.status_code == 404
    app.dependency_overrides.clear()


def test_reads_survive_deleting_an_image_with_linked_evidence_and_decisions(
    db_session: Session, sample_rack_basic: Rack, tmp_path, monkeypatch
) -> None:
    from canon.models import ClassificationEvidenceRecord
    from core import settings
    from intelligence.models import DecisionReceiptRecord

    settings.export_dir = str(tmp_path)
    client = _client(db_session)
    asset = _upload(client, sample_rack_basic)
    base = f"/api/racks/{sample_rack_basic.id}/evidence"
    evidence = (
        db_session.query(ClassificationEvidenceRecord)
        .filter(ClassificationEvidenceRecord.image_asset_id == asset["id"])
        .first()
    )
    assert evidence is not None
    evidence_id = evidence.id
    now = datetime.now(timezone.utc)
    db_session.add(
        DecisionReceiptRecord(
            id="rcpt-del", request_id="req-del", schema_version="1", purpose="module_identity",
            provider="fixture", provider_version="1", provider_status="succeeded",
            answer_type="choice", selected_choice="module-a", evidence_hash=evidence_id,
            policy_version="p1", disposition="AUTO_PROPOSE", reason_codes=[],
            packet_hash="b" * 64, created_at=now,
        )
    )
    db_session.commit()

    assert client.delete(f"{base}/images/{asset['id']}").status_code == 200

    # Append-only history stays; reads answer instead of erroring.
    assert db_session.get(ClassificationEvidenceRecord, evidence_id) is not None
    assert db_session.get(DecisionReceiptRecord, "rcpt-del") is not None
    candidates = client.get(f"{base}/candidates")
    assert candidates.status_code == 200, candidates.text
    assert candidates.json()["total"] == 0
    assert client.get(f"{base}/images").json()["total"] == 0
    kept = client.get(f"{base}/images", params={"include_deleted": "true"}).json()
    assert [a["id"] for a in kept["assets"]] == [asset["id"]]
    assert kept["assets"][0]["deleted_at"] is not None
    assert client.get(f"{base}/inventory").status_code == 200
    assert client.get(f"{base}/reconcile").status_code == 200

    # A new decision on the deleted image is refused, not a server error.
    monkeypatch.setattr(settings, "enable_decision_intelligence", True)
    refused = client.post(
        f"{base}/decision-resolution", json={"evidence_id": evidence_id, "idempotency_key": "k"}
    )
    assert refused.status_code == 400
    assert refused.json()["detail"] == "EVIDENCE_NOT_BOUND_TO_RACK"
    app.dependency_overrides.clear()


def test_uploaded_photo_reaches_decision_resolution_by_its_candidate_evidence_id(
    db_session: Session, sample_rack_basic: Rack, sample_rack_empty: Rack, tmp_path, monkeypatch
) -> None:
    """The evidence id the candidates endpoint shows is the id the decision route accepts."""
    import evidence.routes as routes
    from canon.models import ClassificationEvidenceRecord
    from core import settings
    from intelligence.contracts import DecisionPacket
    from intelligence.models import DecisionReceiptRecord

    settings.export_dir = str(tmp_path)
    client = _client(db_session)
    asset = _upload(client, sample_rack_basic)
    base = f"/api/racks/{sample_rack_basic.id}/evidence"

    listed = client.get(f"{base}/candidates").json()["candidates"]
    assert listed, "upload produced no candidates"
    evidence_ids = {item["evidence_id"] for item in listed}
    assert len(evidence_ids) == 1
    evidence_id = evidence_ids.pop()
    stored = db_session.get(ClassificationEvidenceRecord, evidence_id)
    assert stored is not None and stored.image_asset_id == asset["id"]
    chosen = listed[0]["candidate_id"]

    class Provider:
        def choose(self, request):
            return DecisionPacket(
                decision_id="decision-upload", request_id=request.request_id,
                provider="fixture", provider_version="1", evidence_hash=request.evidence_hash,
                answer_type="choice", selected_choice=chosen,
                probabilities={chosen: 0.95, "none_of_above": 0.05},
                confidence=0.95, candidate_set_hash=request.candidate_set_hash(),
                created_at=datetime.now(timezone.utc),
            )

        def score(self, request):
            raise AssertionError

        def probability(self, request):
            raise AssertionError

    monkeypatch.setattr(routes, "_configured_decision_provider", lambda **_: Provider())
    monkeypatch.setattr(settings, "enable_decision_intelligence", True)
    body = {"evidence_id": evidence_id, "idempotency_key": "upload-1"}
    try:
        first = client.post(f"{base}/decision-resolution", json=body)
        assert first.status_code == 200, first.text
        assert first.json()["evidence_id"] == evidence_id
        assert first.json()["selected_choice"] == chosen
        assert first.json()["canonical_authority"] is False
        replay = client.post(f"{base}/decision-resolution", json=body)
        assert replay.status_code == 200, replay.text
        assert replay.json()["selected_choice"] == chosen
        assert db_session.query(DecisionReceiptRecord).count() == 1

        # The binding guard still refuses the same evidence on another rack.
        other = client.post(
            f"/api/racks/{sample_rack_empty.id}/evidence/decision-resolution",
            json={"evidence_id": evidence_id, "idempotency_key": "upload-2"},
        )
        assert other.status_code == 400
        assert other.json()["detail"] == "EVIDENCE_NOT_BOUND_TO_RACK"
    finally:
        app.dependency_overrides.clear()
