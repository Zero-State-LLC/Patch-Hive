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
from modules.models import Module
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


@pytest.fixture
def client(db_session: Session, sample_user):
    """Bind the app to the in-memory session, signed in as the sample rack's owner."""
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
    revision = db_session.get(SystemInventoryRevisionRecord, result["inventory_revision_id"])
    assert revision
    # The body said "tester"; who confirmed is the signed-in owner (spec 005 FR-006).
    assert revision.created_by == f"user:{sample_rack_basic.user_id}"

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


def test_a_confirm_needs_a_candidate_the_rack_holds(
    db_session: Session, sample_rack_basic: Rack, tmp_path
) -> None:
    """Spec 001: evidence can't jump to confirmed. A decision must name a listed candidate."""
    from core import settings

    settings.export_dir = str(tmp_path)
    client = _client(db_session)
    response = client.post(
        f"/api/racks/{sample_rack_basic.id}/evidence/confirmations",
        json={
            "decisions": [
                {"candidate_id": "not-a-candidate", "status": "confirm", "module_revision_id": "catalog-module-test-vco"},
            ]
        },
    )
    assert response.status_code == 400
    assert "UNKNOWN_CANDIDATE:not-a-candidate" in response.text
    assert db_session.query(SystemInventoryRevisionRecord).count() == 0
    app.dependency_overrides.clear()


def test_new_evidence_is_appended_and_leaves_earlier_evidence_unchanged(
    db_session: Session, sample_rack_basic: Rack, tmp_path
) -> None:
    from canon.models import ClassificationEvidenceRecord
    from core import settings

    settings.export_dir = str(tmp_path)
    client = _client(db_session)

    def upload(colour: tuple[int, int, int]) -> None:
        buffer = io.BytesIO()
        Image.new("RGB", (128, 96), colour).save(buffer, format="JPEG")
        response = client.post(
            f"/api/racks/{sample_rack_basic.id}/evidence/images",
            files=[("files", ("rig.jpg", buffer.getvalue(), "image/jpeg"))],
            data={"run_vision_mock": "true", "retention_days": "30"},
        )
        assert response.status_code == 201, response.text

    upload((11, 22, 33))
    first = {row.id: row.evidence_packet for row in db_session.query(ClassificationEvidenceRecord)}
    assert first
    upload((200, 100, 50))
    after = {row.id: row.evidence_packet for row in db_session.query(ClassificationEvidenceRecord)}
    assert len(after) > len(first)
    assert {key: after[key] for key in first} == first
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


# Owner decision 35 (#283): the API's readiness answer and generation's answer are one
# answer. A confirmed photo has no row or HP, so it stays listed until the rack route places it.


def _upload_photo(client: TestClient, rack_id: int) -> None:
    upload = client.post(
        f"/api/racks/{rack_id}/evidence/images",
        files=[("files", ("rig.jpg", _jpeg_bytes(), "image/jpeg"))],
        data={"run_vision_mock": "true", "retention_days": "30"},
    )
    assert upload.status_code == 201, upload.text


def _confirm_top_candidate(client: TestClient, rack_id: int) -> tuple[dict, dict]:
    """Upload a photo, confirm the top candidate, reject the rest. Returns (candidate, body)."""
    _upload_photo(client, rack_id)
    candidates = client.get(f"/api/racks/{rack_id}/evidence/candidates").json()["candidates"]
    top = candidates[0]
    confirm = client.post(
        f"/api/racks/{rack_id}/evidence/confirmations",
        json={
            "decisions": [
                {
                    "candidate_id": top["candidate_id"],
                    "status": "confirm",
                    "module_revision_id": f"catalog-{top['candidate_id']}",
                },
                *[{"candidate_id": c["candidate_id"], "status": "reject"} for c in candidates[1:]],
            ],
        },
    )
    assert confirm.status_code == 201, confirm.text
    return top, confirm.json()


def _generate(client: TestClient, rack_id: int) -> dict:
    response = client.post(f"/api/patches/generate/{rack_id}", json={})
    assert response.status_code == 200, response.text
    return response.json()


def _inventory(client: TestClient, rack_id: int) -> dict:
    response = client.get(f"/api/racks/{rack_id}/evidence/inventory")
    assert response.status_code == 200, response.text
    return response.json()


def _mock_oscillator(db_session: Session) -> Module:
    """The catalog row for the module the mock vision provider ranks first."""
    module = Module(
        brand="MockAudio",
        name="Oscillator A",
        hp=10,
        module_type="VCO",
        power_12v_ma=50,
        power_neg12v_ma=10,
        power_5v_ma=0,
        io_ports=[{"name": "CV In", "type": "cv_in"}, {"name": "Out", "type": "audio_out"}],
        source="test",
    )
    db_session.add(module)
    db_session.commit()
    db_session.refresh(module)
    return module


def test_photo_only_rig_is_not_ready_and_generation_agrees(
    client, db_session, sample_rack_empty, tmp_path
) -> None:
    from core import settings

    settings.export_dir = str(tmp_path)
    module = _mock_oscillator(db_session)
    rack_id = sample_rack_empty.id

    _top, confirmed = _confirm_top_candidate(client, rack_id)
    assert confirmed["confirmed_count"] == 1
    assert confirmed["ready_for_generation"] is False
    assert [
        (entry["manufacturer"], entry["model"], entry["module_id"])
        for entry in confirmed["modules_to_place"]
    ] == [("MockAudio", "Oscillator A", module.id)]

    listed = _inventory(client, rack_id)
    assert listed["latest"]["ready_for_generation"] is False
    assert all(not revision["ready_for_generation"] for revision in listed["revisions"])
    assert [entry["module_id"] for entry in listed["modules_to_place"]] == [module.id]

    # Generation gives the same answer, with no run.
    refused = _generate(client, rack_id)
    assert refused["generation_status"] == "NOT_COMPUTABLE"
    assert refused["run_id"] is None

    # A refused generation seals an empty placement revision; the module is still to place.
    after_refusal = _inventory(client, rack_id)
    assert after_refusal["latest"]["ready_for_generation"] is False
    assert [entry["module_id"] for entry in after_refusal["modules_to_place"]] == [module.id]


def test_placing_a_confirmed_module_through_the_rack_route_makes_the_rig_ready(
    client, db_session, sample_rack_empty, sample_case, tmp_path
) -> None:
    from core import settings

    settings.export_dir = str(tmp_path)
    module = _mock_oscillator(db_session)
    rack_id = sample_rack_empty.id
    _confirm_top_candidate(client, rack_id)

    # The rack route checks fit: a placement past the row's HP changes nothing.
    too_far = client.patch(
        f"/api/racks/{rack_id}",
        json={
            "modules": [{"module_id": module.id, "row_index": 0, "start_hp": sample_case.total_hp}]
        },
    )
    assert too_far.status_code == 400, too_far.text
    still_waiting = _inventory(client, rack_id)
    assert still_waiting["latest"]["ready_for_generation"] is False
    assert [entry["module_id"] for entry in still_waiting["modules_to_place"]] == [module.id]

    placed = client.patch(
        f"/api/racks/{rack_id}",
        json={"modules": [{"module_id": module.id, "row_index": 0, "start_hp": 0}]},
    )
    assert placed.status_code == 200, placed.text

    listed = _inventory(client, rack_id)
    assert listed["latest"]["ready_for_generation"] is True
    assert listed["modules_to_place"] == []

    accepted = _generate(client, rack_id)
    assert accepted["generation_status"] != "NOT_COMPUTABLE"
    assert accepted["run_id"] is not None


def test_rig_with_placed_modules_stays_ready_and_lists_the_unplaced_one(
    client, db_session, sample_rack_basic, tmp_path
) -> None:
    """Generation accepts this rig on its placed modules, so the API says ready; the
    confirmed module it won't use yet is listed."""
    from core import settings

    settings.export_dir = str(tmp_path)
    rack_id = sample_rack_basic.id

    _top, confirmed = _confirm_top_candidate(client, rack_id)
    assert confirmed["ready_for_generation"] is True
    assert [entry["model"] for entry in confirmed["modules_to_place"]] == ["Oscillator A"]
    # No catalog row for the mock module, and nothing invents one.
    assert confirmed["modules_to_place"][0]["module_id"] is None

    accepted = _generate(client, rack_id)
    assert accepted["generation_status"] != "NOT_COMPUTABLE"
    assert accepted["run_id"] is not None

    # A generation that ran seals a placement revision; the list survives it.
    listed = _inventory(client, rack_id)
    assert listed["latest"]["ready_for_generation"] is True
    assert [entry["model"] for entry in listed["modules_to_place"]] == ["Oscillator A"]


def test_vision_alone_lists_nothing_to_place(
    client, db_session, sample_rack_empty, tmp_path
) -> None:
    """Image and evidence aren't inventory: until the owner confirms, nothing is to place."""
    from core import settings

    settings.export_dir = str(tmp_path)
    rack_id = sample_rack_empty.id
    _upload_photo(client, rack_id)
    assert client.get(f"/api/racks/{rack_id}/evidence/candidates").json()["total"] >= 1

    listed = _inventory(client, rack_id)
    assert listed["latest"] is None
    assert listed["modules_to_place"] == []


def test_a_later_confirmation_replaces_what_is_still_to_place(
    client, db_session, sample_rack_empty, tmp_path
) -> None:
    """The newest confirmation is the owner's current answer, even when it confirms nothing."""
    from core import settings

    settings.export_dir = str(tmp_path)
    rack_id = sample_rack_empty.id
    top, confirmed = _confirm_top_candidate(client, rack_id)
    assert len(confirmed["modules_to_place"]) == 1

    rejected = client.post(
        f"/api/racks/{rack_id}/evidence/confirmations",
        json={"decisions": [{"candidate_id": top["candidate_id"], "status": "reject"}]},
    )
    assert rejected.status_code == 201, rejected.text
    assert rejected.json()["modules_to_place"] == []
    assert _inventory(client, rack_id)["modules_to_place"] == []
