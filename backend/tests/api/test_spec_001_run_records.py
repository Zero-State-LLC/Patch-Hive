"""Spec 001 T090: what a run and an evidence decision leave behind (D2, D5, D6, D8)."""

from __future__ import annotations

import io

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

import patches.routes as routes
import patches.validation as validation
from canon.compiler import run_outcome_receipt
from canon.models import ArtifactManifestRecord, EvidenceDecisionRecord, StageReceiptRecord
from core import get_db, settings
from main import app
from patches.schemas import GeneratePatchesRequest
from racks.models import Rack
from runs.models import Run


def _generate(db: Session, rack: Rack):
    return routes.run_generation(db, rack, GeneratePatchesRequest())


def _receipts(db: Session, source_run_id: str) -> list[StageReceiptRecord]:
    return db.query(StageReceiptRecord).filter(StageReceiptRecord.run_id == source_run_id).all()


def _fail_engine_with(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    def boom(*args, **kwargs):
        raise error

    monkeypatch.setattr(routes, "generate_patches_with_ir", boom)


def test_a_not_computable_answer_names_the_failed_condition(db_session: Session, sample_rack_empty: Rack) -> None:
    result = _generate(db_session, sample_rack_empty)
    assert result.generation_status == "NOT_COMPUTABLE"
    assert result.inventory_gate_messages
    assert "USER_CONFIRMED" in result.inventory_gate_messages[0]


def test_a_failed_run_keeps_its_reason_and_a_receipt_but_never_the_message(
    db_session: Session, sample_rack_basic: Rack, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fail_engine_with(monkeypatch, RuntimeError("password=hunter2 in a stack frame"))
    with pytest.raises(RuntimeError):
        _generate(db_session, sample_rack_basic)
    run = db_session.query(Run).one()
    assert (run.status, run.failure_reason) == ("failed", "RuntimeError")
    receipts = db_session.query(StageReceiptRecord).all()
    assert [r.operation for r in receipts] == ["run_generation"]
    assert "hunter2" not in str(receipts[0].receipt)


def test_a_failed_run_keeps_an_http_errors_code(
    db_session: Session, sample_rack_basic: Rack, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fail_engine_with(monkeypatch, HTTPException(status_code=500, detail="EXPORT_BRIDGE_LEGACY_ID_FORBIDDEN"))
    with pytest.raises(HTTPException):
        _generate(db_session, sample_rack_basic)
    assert db_session.query(Run).one().failure_reason == "HTTP 500: EXPORT_BRIDGE_LEGACY_ID_FORBIDDEN"


def test_losing_a_failed_runs_receipt_does_not_hide_the_error(
    db_session: Session, sample_rack_basic: Rack, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fail_engine_with(monkeypatch, RuntimeError("engine exploded"))

    def no_receipt(*args, **kwargs):
        raise ValueError("receipt store down")

    monkeypatch.setattr("export.patchbook.design.dual_write.write_run_outcome_receipt", no_receipt)
    with pytest.raises(RuntimeError, match="engine exploded"):
        _generate(db_session, sample_rack_basic)
    assert db_session.query(Run).one().failure_reason == "RuntimeError"


def test_a_validation_failed_run_keeps_a_receipt_and_its_report(
    db_session: Session, sample_rack_basic: Rack, monkeypatch: pytest.MonkeyPatch
) -> None:
    def blocked(patch_graphs, modules_by_id, allowed_module_ids=None):
        report = validation.ValidationReport()
        report.add(validation.Finding("block", "PORT_DIRECTION_MISMATCH", "test", 0))
        return list(patch_graphs), report

    monkeypatch.setattr(validation, "resolve_and_validate", blocked)
    result = _generate(db_session, sample_rack_basic)
    assert result.generation_status == "VALIDATION_FAILED"
    assert [r.operation for r in _receipts(db_session, result.source_run_id)] == ["run_generation"]
    assert db_session.get(Run, result.run_id).validation_report["blocking"] is True
    assert db_session.query(ArtifactManifestRecord).count() == 0


def test_a_run_with_no_patches_keeps_a_receipt_and_a_sealed_empty_manifest(
    db_session: Session, sample_rack_basic: Rack, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = routes.generate_patches_with_ir

    def none_kept(*args, **kwargs):
        generation_ir, _, provenance = real(*args, **kwargs)
        return generation_ir, [], provenance

    monkeypatch.setattr(routes, "generate_patches_with_ir", none_kept)
    result = _generate(db_session, sample_rack_basic)
    assert result.generated_count == 0
    assert db_session.get(Run, result.run_id).status == "succeeded"
    assert [r.operation for r in _receipts(db_session, result.source_run_id)] == ["run_generation"]
    manifest = db_session.query(ArtifactManifestRecord).one()
    assert manifest.run_id == result.source_run_id and manifest.manifest["patches"] == []


def test_a_succeeded_run_stores_one_manifest_holding_each_patch(
    db_session: Session, sample_rack_basic: Rack
) -> None:
    result = _generate(db_session, sample_rack_basic)
    manifest = db_session.query(ArtifactManifestRecord).one()
    assert manifest.run_id == result.source_run_id
    assert manifest.manifest["rig_revision_id"] == result.rig_revision_id
    assert len(manifest.manifest["patches"]) == result.generated_count >= 1
    for item in manifest.manifest["patches"]:
        assert item["artifact_manifest"]["artifacts"]
    assert len(manifest.canonical_hash) == 64
    # Compile receipts only: a run that sealed patches needs no outcome receipt.
    assert "run_generation" not in {r.operation for r in _receipts(db_session, result.source_run_id)}


def test_an_outcome_receipt_is_stable_for_the_same_run_and_changes_with_the_outcome() -> None:
    from datetime import datetime, timezone

    common = {
        "run_id": "source-1", "rig_revision_id": "rig-1", "seed": 7,
        "created_at": datetime(2026, 11, 6, tzinfo=timezone.utc),
    }
    first = run_outcome_receipt(status="failed", detail={"reason": "RuntimeError"}, **common)
    again = run_outcome_receipt(status="failed", detail={"reason": "RuntimeError"}, **common)
    other = run_outcome_receipt(status="failed", detail={"reason": "ValueError"}, **common)
    assert first.canonical_dict() == again.canonical_dict()
    assert first.input_hash == other.input_hash and first.output_hash != other.output_hash


@pytest.fixture
def evidence_client(db_session: Session, owner_headers: dict, tmp_path):
    settings.export_dir = str(tmp_path)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, headers=owner_headers)
    app.dependency_overrides.clear()


def _candidates(client: TestClient, rack_id: int) -> list[dict]:
    buffer = io.BytesIO()
    Image.new("RGB", (128, 96), (11, 22, 33)).save(buffer, format="JPEG")
    uploaded = client.post(
        f"/api/racks/{rack_id}/evidence/images",
        files=[("files", ("rig.jpg", buffer.getvalue(), "image/jpeg"))],
        data={"run_vision_mock": "true", "retention_days": "30"},
    )
    assert uploaded.status_code == 201, uploaded.text
    return client.get(f"/api/racks/{rack_id}/evidence/candidates").json()["candidates"]


def _decide(client: TestClient, rack_id: int, **decision) -> dict:
    response = client.post(f"/api/racks/{rack_id}/evidence/confirmations", json={"decisions": [decision]})
    assert response.status_code == 201, response.text
    return response.json()


def test_a_reject_is_recorded_and_leaves_canon_unchanged(
    evidence_client: TestClient, db_session: Session, sample_rack_basic: Rack
) -> None:
    rack_id = sample_rack_basic.id
    candidate = _candidates(evidence_client, rack_id)[0]
    assert candidate["last_decision"] is None
    result = _decide(evidence_client, rack_id, candidate_id=candidate["candidate_id"], status="reject")
    assert result["confirmed_count"] == 0
    row = db_session.query(EvidenceDecisionRecord).one()
    assert (row.candidate_id, row.status, row.reverses_decision_id) == (candidate["candidate_id"], "reject", None)
    assert row.decided_by == f"user:{sample_rack_basic.user_id}"
    assert row.inventory_revision_id == result["inventory_revision_id"]
    listed = evidence_client.get(f"/api/racks/{rack_id}/evidence/candidates").json()["candidates"]
    assert {c["candidate_id"]: c["last_decision"] for c in listed}[candidate["candidate_id"]] == "reject"


def test_changing_a_decision_records_the_reversal_and_keeps_the_first(
    evidence_client: TestClient, db_session: Session, sample_rack_basic: Rack
) -> None:
    rack_id = sample_rack_basic.id
    candidate_id = _candidates(evidence_client, rack_id)[0]["candidate_id"]
    _decide(evidence_client, rack_id, candidate_id=candidate_id, status="reject")
    first = db_session.query(EvidenceDecisionRecord).one()
    _decide(
        evidence_client, rack_id, candidate_id=candidate_id, status="confirm",
        module_revision_id="catalog-module-test-vco",
    )
    rows = db_session.query(EvidenceDecisionRecord).order_by(EvidenceDecisionRecord.decided_at).all()
    assert [r.status for r in rows] == ["reject", "confirm"]
    assert rows[0].id == first.id and rows[1].reverses_decision_id == first.id
    assert rows[1].module_revision_id == "catalog-module-test-vco"


def test_repeating_a_decision_is_not_a_reversal(
    evidence_client: TestClient, db_session: Session, sample_rack_basic: Rack
) -> None:
    rack_id = sample_rack_basic.id
    candidate_id = _candidates(evidence_client, rack_id)[0]["candidate_id"]
    _decide(evidence_client, rack_id, candidate_id=candidate_id, status="reject")
    _decide(evidence_client, rack_id, candidate_id=candidate_id, status="reject")
    rows = db_session.query(EvidenceDecisionRecord).all()
    assert len(rows) == 2 and {r.reverses_decision_id for r in rows} == {None}


def test_a_decision_record_cannot_be_changed(
    evidence_client: TestClient, db_session: Session, sample_rack_basic: Rack
) -> None:
    rack_id = sample_rack_basic.id
    candidate_id = _candidates(evidence_client, rack_id)[0]["candidate_id"]
    _decide(evidence_client, rack_id, candidate_id=candidate_id, status="reject")
    row = db_session.query(EvidenceDecisionRecord).one()
    row.status = "confirm"
    with pytest.raises(Exception, match="(?i)immutable|append"):
        db_session.flush()
    db_session.rollback()
