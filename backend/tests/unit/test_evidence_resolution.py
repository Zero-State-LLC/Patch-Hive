from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from canon.models import ClassificationEvidenceRecord, ImageAssetRecord, SystemInventoryRevisionRecord
from core.database import Base
from intelligence.contracts import DecisionPacket
from intelligence.evidence_resolution import (
    DecisionIntelligenceDisabled,
    EvidenceResolutionError,
    resolve_module_identity,
)
from intelligence.fixture_provider import FixtureDecisionProvider
from intelligence.models import DecisionReceiptRecord
from intelligence.policy import DecisionPolicy, PolicyThresholds


def _policy() -> DecisionPolicy:
    return DecisionPolicy(PolicyThresholds(
        policy_version="test-v1",
        auto_propose_at=0.9,
        user_review_at=0.65,
        probability_margin=0.1,
    ))


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(db, *, evidence_id: str = "ev-1", candidate_evidence_id: str = "ev-1"):
    now = datetime.now(timezone.utc)
    db.add(ImageAssetRecord(
        id="img-1", rack_id=1, user_id=1, content_sha256="a" * 64,
        media_type="image/jpeg", width=100, height=100, byte_length=10,
        storage_path="/tmp/none", retention_days=30,
        retention_expires_at=now + timedelta(days=30),
        consent_provider_processing=False, created_at=now,
    ))
    raw = {
        "candidate_id": "module-a", "entity_type": "module",
        "manufacturer": "Make", "model": "Alpha", "confidence": 0.8,
        "confidence_method": "fixture", "classification_status": "INFERRED",
        "evidence_id": candidate_evidence_id,
    }
    db.add(ClassificationEvidenceRecord(
        id=evidence_id, image_asset_id="img-1", inventory_revision_id=None,
        evidence_packet={"devices": [raw]}, provider="fixture-vision",
        pipeline_version="vision-v1", status="INFERRED", created_at=now,
    ))
    db.flush()


def test_flag_off_makes_no_provider_call_or_receipt() -> None:
    db = _db()
    _seed(db)
    class Never:
        def choose(self, request): raise AssertionError("provider called")
        def score(self, request): raise AssertionError
        def probability(self, request): raise AssertionError
    with pytest.raises(DecisionIntelligenceDisabled):
        resolve_module_identity(
            db, evidence_id="ev-1", provider=Never(), policy=_policy(),
            enabled=False, idempotency_key="idem",
        )
    assert db.query(DecisionReceiptRecord).count() == 0


def test_exact_evidence_binding_is_enforced() -> None:
    db = _db()
    _seed(db, candidate_evidence_id="ev-other")
    with pytest.raises(EvidenceResolutionError, match="binding"):
        resolve_module_identity(
            db, evidence_id="ev-1", provider=FixtureDecisionProvider({}),
            policy=_policy(), enabled=True, idempotency_key="idem",
        )
    assert db.query(DecisionReceiptRecord).count() == 0


def test_fixture_resolution_persists_advisory_only() -> None:
    db = _db()
    _seed(db)
    # Build the expected candidate-set hash through a recording pass.
    class Recorder:
        request = None
        def choose(self, request):
            self.request = request
            return DecisionPacket(
                decision_id="decision-1", request_id=request.request_id,
                provider="fixture", provider_version="1",
                evidence_hash=request.evidence_hash, answer_type="choice",
                selected_choice="module-a",
                probabilities={"module-a": 0.95, "none_of_above": 0.05},
                confidence=0.95, candidate_set_hash=request.candidate_set_hash(),
                created_at=datetime.now(timezone.utc),
            )
        def score(self, request): raise AssertionError
        def probability(self, request): raise AssertionError

    proposal = resolve_module_identity(
        db, evidence_id="ev-1", provider=Recorder(), policy=_policy(),
        enabled=True, idempotency_key="idem",
    )
    assert proposal.packet.selected_choice == "module-a"
    receipt = db.query(DecisionReceiptRecord).one()
    assert receipt.evidence_hash == "ev-1"
    assert receipt.disposition == "AUTO_PROPOSE"
    # This orchestration module has no inventory model dependency/write path.


def test_provider_failure_persists_escalation_without_canon_mutation() -> None:
    from intelligence.fixture_provider import failed_fixture

    db = _db()
    _seed(db)
    packet = failed_fixture(
        decision_id="failed-1", request_id="module-identity:ev-1",
        provider_status="failed", evidence_hash="ev-1", error_code="FIXTURE_FAILURE",
    )
    provider = FixtureDecisionProvider({"module-identity:ev-1": packet})
    before = db.query(SystemInventoryRevisionRecord).count()
    proposal = resolve_module_identity(
        db, evidence_id="ev-1", provider=provider, policy=_policy(),
        enabled=True, idempotency_key="idem",
    )
    assert proposal.policy.disposition.value == "ESCALATE"
    assert db.query(DecisionReceiptRecord).one().provider_status == "failed"
    assert db.query(SystemInventoryRevisionRecord).count() == before == 0


def test_repeated_resolution_is_idempotent_and_never_mints_inventory() -> None:
    db = _db()
    _seed(db)

    class StableProvider:
        def choose(self, request):
            return DecisionPacket(
                decision_id="stable-decision", request_id=request.request_id,
                provider="fixture", provider_version="1",
                evidence_hash=request.evidence_hash, answer_type="choice",
                selected_choice="module-a",
                probabilities={"module-a": 0.95, "none_of_above": 0.05},
                confidence=0.95, candidate_set_hash=request.candidate_set_hash(),
                created_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
            )
        def score(self, request): raise AssertionError
        def probability(self, request): raise AssertionError

    for _ in range(2):
        resolve_module_identity(
            db, evidence_id="ev-1", provider=StableProvider(), policy=_policy(),
            enabled=True, idempotency_key="same-idem",
        )
    assert db.query(DecisionReceiptRecord).count() == 1
    assert db.query(SystemInventoryRevisionRecord).count() == 0


def test_malformed_bounded_candidate_fails_closed() -> None:
    db = _db()
    now = datetime.now(timezone.utc)
    db.add(ImageAssetRecord(
        id="img-1", rack_id=1, user_id=1, content_sha256="a" * 64,
        media_type="image/jpeg", width=100, height=100, byte_length=10,
        storage_path="/tmp/none", retention_days=30,
        retention_expires_at=now + timedelta(days=30),
        consent_provider_processing=False, created_at=now,
    ))
    db.add(ClassificationEvidenceRecord(
        id="ev-1", image_asset_id="img-1", inventory_revision_id=None,
        evidence_packet={"devices": [{"candidate_id": "broken", "entity_type": "module", "manufacturer": "Make", "model": "Alpha", "confidence": 2.0, "confidence_method": "fixture", "classification_status": "INFERRED", "evidence_id": "ev-1"}]},
        provider="fixture-vision", pipeline_version="vision-v1",
        status="INFERRED", created_at=now,
    ))
    db.flush()
    with pytest.raises(EvidenceResolutionError, match="malformed candidate"):
        resolve_module_identity(
            db, evidence_id="ev-1", provider=FixtureDecisionProvider({}),
            policy=_policy(), enabled=True, idempotency_key="idem",
        )
    assert db.query(DecisionReceiptRecord).count() == 0
