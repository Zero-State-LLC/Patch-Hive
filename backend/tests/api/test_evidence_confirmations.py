"""Ranked candidates + confirmation → inventory revision API."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from canon.models import ClassificationEvidenceRecord, ImageAssetRecord, SystemInventoryRevisionRecord
from intelligence.models import DecisionReceiptRecord
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
    return TestClient(app)


@pytest.fixture
def client(db_session: Session):
    """Bind the app to the in-memory session, matching the other API suites."""
    test_client = _client(db_session)
    yield test_client
    app.dependency_overrides.clear()


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (128, 96), (11, 22, 33)).save(buf, format="JPEG")
    return buf.getvalue()


def test_list_and_confirm_candidates(
    db_session: Session, sample_rack_basic: Rack, tmp_path
) -> None:
    from core import settings

    settings.export_dir = str(tmp_path)
    client = _client(db_session)

    upload = client.post(
        f"/api/racks/{sample_rack_basic.id}/evidence/images",
        files=[("files", ("rig.jpg", _jpeg_bytes(), "image/jpeg"))],
        data={"run_vision_mock": "true", "retention_days": "30"},
    )
    assert upload.status_code == 201, upload.text
    assert upload.json()["uploaded"]

    listed = client.get(f"/api/racks/{sample_rack_basic.id}/evidence/candidates")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] >= 1
    candidates = body["candidates"]
    # Ranked by confidence desc
    confidences = [c["confidence"] for c in candidates]
    assert confidences == sorted(confidences, reverse=True)

    top = candidates[0]
    confirm = client.post(
        f"/api/racks/{sample_rack_basic.id}/evidence/confirmations",
        json={
            "confirmed_by": "tester",
            "decisions": [
                {
                    "candidate_id": top["candidate_id"],
                    "status": "confirm",
                    "module_revision_id": "catalog-module-test-vco",
                },
                *[{"candidate_id": c["candidate_id"], "status": "reject"} for c in candidates[1:]],
            ],
        },
    )
    assert confirm.status_code == 201, confirm.text
    result = confirm.json()
    assert result["confirmed_count"] == 1
    assert result["ready_for_generation"] is True
    assert result["inventory_revision_id"].startswith("inv-rev-")
    assert db_session.get(SystemInventoryRevisionRecord, result["inventory_revision_id"])

    # Confirm without module revision fails closed
    bad = client.post(
        f"/api/racks/{sample_rack_basic.id}/evidence/confirmations",
        json={
            "decisions": [
                {"candidate_id": top["candidate_id"], "status": "confirm"},
            ]
        },
    )
    assert bad.status_code == 400
    assert "MODULE_REVISION_REQUIRED" in bad.text

    inv_list = client.get(f"/api/racks/{sample_rack_basic.id}/evidence/inventory")
    assert inv_list.status_code == 200, inv_list.text
    inv_body = inv_list.json()
    assert inv_body["total"] >= 1
    assert inv_body["latest"]["inventory_revision_id"] == result["inventory_revision_id"]
    assert inv_body["latest"]["ready_for_generation"] is True
    assert inv_body["latest"]["confirmed_count"] == 1

    app.dependency_overrides.clear()


def test_candidate_list_decision_advisory_is_optional_and_non_authoritative(
    client, db_session, sample_rack_basic
) -> None:
    """Candidate DTO may carry advisory metadata without changing confirmation authority."""
    listed = client.get(f"/api/racks/{sample_rack_basic.id}/evidence/candidates")
    assert listed.status_code == 200
    for candidate in listed.json()["candidates"]:
        assert "decision_advisory" in candidate
        advisory = candidate["decision_advisory"]
        if advisory is not None:
            assert set(advisory) == {"disposition", "provider", "confidence", "reason_codes"}
        # Canonical authority fields are never projected by Decision Intelligence.
        assert "canonical_module_id" not in candidate
        assert "confirmed" not in (advisory or {})


def test_decision_advisory_does_not_cross_evidence_boundary(
    client, db_session, sample_rack_basic
) -> None:
    """Same candidate ID on unrelated evidence must not inherit an advisory."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    asset = ImageAssetRecord(
        id="img-advisory-scope",
        rack_id=sample_rack_basic.id,
        user_id=sample_rack_basic.user_id,
        content_sha256="a" * 64,
        media_type="image/jpeg",
        width=128,
        height=96,
        byte_length=123,
        storage_path="/tmp/not-used.jpg",
        retention_days=30,
        retention_expires_at=now,
        consent_provider_processing=False,
        created_at=now,
    )
    db_session.add(asset)
    db_session.flush()
    candidate = {
        "candidate_id": "shared-module-id",
        "entity_type": "module",
        "manufacturer": "Example",
        "model": "Shared",
        "confidence": 0.8,
        "confidence_method": "fixture",
        "classification_status": "INFERRED",
        "evidence_id": "ev-current",
    }
    db_session.add(
        ClassificationEvidenceRecord(
            id="ev-current",
            image_asset_id=asset.id,
            inventory_revision_id=None,
            evidence_packet={"devices": [candidate]},
            provider="fixture",
            pipeline_version="vision-evidence.v1",
            status="INFERRED",
            created_at=now,
        )
    )
    db_session.add(
        DecisionReceiptRecord(
            id="receipt-unrelated",
            request_id="req-unrelated",
            schema_version="patchhive.decision.v1",
            provider="fixture",
            provider_version="1",
            purpose="module_identity",
            evidence_hash="ev-other-rack",
            candidate_set_hash="candidate-set",
            rubric_hash=None,
            answer_type="choice",
            selected_choice="shared-module-id",
            score=None,
            probability_yes=None,
            confidence=0.99,
            provider_status="succeeded",
            error_code=None,
            policy_version="test-v1",
            disposition="AUTO_PROPOSE",
            reason_codes=["CONFIDENCE_AUTO_PROPOSE"],
            packet_hash="b" * 64,
            raw_payload_hash=None,
            created_at=now,
        )
    )
    db_session.commit()

    listed = client.get(f"/api/racks/{sample_rack_basic.id}/evidence/candidates")
    assert listed.status_code == 200
    shared = next(c for c in listed.json()["candidates"] if c["candidate_id"] == "shared-module-id")
    assert shared["decision_advisory"] is None


def test_decision_advisory_projects_only_matching_evidence(
    client, db_session, sample_rack_basic
) -> None:
    """A receipt bound to the candidate's exact evidence may be shown as advisory."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    asset = ImageAssetRecord(
        id="img-advisory-match",
        rack_id=sample_rack_basic.id,
        user_id=sample_rack_basic.user_id,
        content_sha256="c" * 64,
        media_type="image/jpeg",
        width=128,
        height=96,
        byte_length=123,
        storage_path="/tmp/not-used-2.jpg",
        retention_days=30,
        retention_expires_at=now,
        consent_provider_processing=False,
        created_at=now,
    )
    db_session.add(asset)
    db_session.flush()
    candidate = {
        "candidate_id": "matched-module-id",
        "entity_type": "module",
        "manufacturer": "Example",
        "model": "Matched",
        "confidence": 0.8,
        "confidence_method": "fixture",
        "classification_status": "INFERRED",
        "evidence_id": "ev-match",
    }
    db_session.add(ClassificationEvidenceRecord(
        id="ev-match", image_asset_id=asset.id, inventory_revision_id=None,
        evidence_packet={"devices": [candidate]}, provider="fixture",
        pipeline_version="vision-evidence.v1", status="INFERRED", created_at=now,
    ))
    db_session.add(DecisionReceiptRecord(
        id="receipt-match", request_id="req-match", schema_version="patchhive.decision.v1",
        provider="fixture", provider_version="1", purpose="module_identity",
        evidence_hash="ev-match", candidate_set_hash="candidate-set", rubric_hash=None,
        answer_type="choice", selected_choice="matched-module-id", score=None,
        probability_yes=None, confidence=0.93, provider_status="succeeded", error_code=None,
        policy_version="test-v1", disposition="AUTO_PROPOSE",
        reason_codes=["CONFIDENCE_AUTO_PROPOSE"], packet_hash="d" * 64,
        raw_payload_hash=None, created_at=now,
    ))
    db_session.commit()

    listed = client.get(f"/api/racks/{sample_rack_basic.id}/evidence/candidates")
    assert listed.status_code == 200
    matched = next(c for c in listed.json()["candidates"] if c["candidate_id"] == "matched-module-id")
    assert matched["decision_advisory"]["confidence"] == 0.93
    assert matched["decision_advisory"]["disposition"] == "auto_propose"
