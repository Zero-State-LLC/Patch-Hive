"""Spec 005 T083/T085: idempotency before the provider call, and the routing target."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from canon.models import ClassificationEvidenceRecord, ImageAssetRecord
from core import get_db, settings
from core.database import Base
from intelligence.clef_resolution import resolve_module_identity_guarded
from intelligence.contracts import DecisionPacket, stable_sha256
from intelligence.models import DecisionReceiptKeyRecord, DecisionReceiptRecord
from intelligence.persistence import IdempotencyConflict
from intelligence.policy import DecisionPolicy, PolicyThresholds
from intelligence.resolution_machine import ResolutionState
from main import app
from tests.conftest import rack_owner_headers


def _policy() -> DecisionPolicy:
    return DecisionPolicy(PolicyThresholds(
        policy_version="test-v1", auto_propose_at=0.9, user_review_at=0.65,
        probability_margin=0.1,
    ))


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(db, *, image_sha: str = "a" * 64, model: str = "Alpha"):
    now = datetime.now(timezone.utc)
    db.add(ImageAssetRecord(
        id="img-1", rack_id=1, user_id=1, content_sha256=image_sha,
        media_type="image/jpeg", width=100, height=100, byte_length=10,
        storage_path="/tmp/none", retention_days=30,
        retention_expires_at=now + timedelta(days=30),
        consent_provider_processing=False, created_at=now,
    ))
    raw = {
        "candidate_id": "module-a", "entity_type": "module", "manufacturer": "Make",
        "model": model, "confidence": 0.8, "confidence_method": "fixture",
        "classification_status": "INFERRED", "evidence_id": "ev-1",
    }
    db.add(ClassificationEvidenceRecord(
        id="ev-1", image_asset_id="img-1", inventory_revision_id=None,
        evidence_packet={"devices": [raw]}, provider="fixture-vision",
        pipeline_version="vision-v1", status="INFERRED", created_at=now,
    ))
    db.flush()


class CountingProvider:
    def __init__(self, choice: str = "module-a", confidence: float = 0.95):
        self.calls = 0
        self._choice = choice
        self._confidence = confidence

    def choose(self, request):
        self.calls += 1
        return DecisionPacket(
            decision_id=f"decision-{self.calls}", request_id=request.request_id,
            provider="fixture", provider_version="1", evidence_hash=request.evidence_hash,
            answer_type="choice", selected_choice=self._choice,
            probabilities={"module-a": self._confidence, "none_of_above": 1 - self._confidence},
            confidence=self._confidence, candidate_set_hash=request.candidate_set_hash(),
            created_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
        )

    def score(self, request): raise AssertionError
    def probability(self, request): raise AssertionError


def _resolve(db, provider, key="idem", **kwargs):
    return resolve_module_identity_guarded(
        db, evidence_id="ev-1", provider=provider, policy=_policy(), enabled=True,
        idempotency_key=key, expected_policy_version="test-v1", **kwargs,
    )


def test_repeat_with_same_key_returns_stored_outcome_without_provider_call() -> None:
    db = _db()
    _seed(db)
    provider = CountingProvider()
    first = _resolve(db, provider)
    assert first.proposal is not None and provider.calls == 1

    # A different answer on the repeat must not matter: the provider is never asked.
    other = CountingProvider(choice="none_of_above", confidence=0.1)
    second = _resolve(db, other)
    assert other.calls == 0
    assert second.replayed_receipt is not None
    assert second.receipt_id == first.receipt_id
    assert second.replayed_receipt.selected_choice == "module-a"
    assert db.query(DecisionReceiptRecord).count() == 1


def _store_with_other_hash(db) -> None:
    # Retained evidence is append-only, so a different payload under the same
    # (request, key) is simulated by changing the stored key binding's hash (written
    # through the table, since the ORM rejects updates).
    table = DecisionReceiptKeyRecord.__table__
    db.execute(table.update().values(evidence_hash="0" * 64))
    db.flush()
    db.expire_all()


def test_same_key_with_changed_evidence_is_a_conflict() -> None:
    db = _db()
    _seed(db)
    _resolve(db, CountingProvider())
    _store_with_other_hash(db)

    provider = CountingProvider()
    with pytest.raises(IdempotencyConflict):
        _resolve(db, provider)
    assert provider.calls == 0
    assert db.query(DecisionReceiptRecord).count() == 1


def test_evidence_hash_covers_packet_and_image_sha() -> None:
    db = _db()
    _seed(db)
    _resolve(db, CountingProvider())
    receipt = db.query(DecisionReceiptRecord).one()
    packet = db.get(ClassificationEvidenceRecord, "ev-1").evidence_packet
    assert receipt.evidence_hash == stable_sha256(
        {"evidence_packet": packet, "image_sha256": "a" * 64}
    )
    assert receipt.evidence_hash != "ev-1"
    assert db.get(DecisionReceiptKeyRecord, (receipt.request_id, "idem")).receipt_id == receipt.id


def test_different_image_sha_changes_evidence_hash() -> None:
    first, second = _db(), _db()
    _seed(first, image_sha="a" * 64)
    _seed(second, image_sha="b" * 64)
    _resolve(first, CountingProvider())
    _resolve(second, CountingProvider())
    assert (
        first.query(DecisionReceiptRecord).one().evidence_hash
        != second.query(DecisionReceiptRecord).one().evidence_hash
    )


def test_key_table_rejects_duplicate_request_and_key() -> None:
    db = _db()
    _seed(db)
    _resolve(db, CountingProvider())
    receipt = db.query(DecisionReceiptRecord).one()
    db.add(DecisionReceiptKeyRecord(
        request_id=receipt.request_id, idempotency_key="idem",
        evidence_hash=receipt.evidence_hash, receipt_id=receipt.id,
    ))
    with pytest.raises(IntegrityError):
        db.flush()


def test_routing_target_makes_policy_escalate_reach_escalate_state() -> None:
    # A failed provider escalates only when a routing target exists (research R6).
    class Failing:
        def choose(self, request):
            raise RuntimeError("PROVIDER_DOWN")
        def score(self, request): raise AssertionError
        def probability(self, request): raise AssertionError

    for targets, expected in (
        (frozenset({"human_review"}), ResolutionState.ESCALATE),
        (frozenset(), ResolutionState.UNRESOLVED),
    ):
        db = _db()
        _seed(db)
        result = _resolve(db, Failing(), routing_targets=targets)
        assert result.machine.state is expected


def test_route_passes_configured_routing_target_and_replays(db_session, sample_rack_basic, monkeypatch):
    now = datetime.now(timezone.utc)
    db_session.add(ImageAssetRecord(
        id="img-idem", rack_id=sample_rack_basic.id, user_id=sample_rack_basic.user_id,
        content_sha256="c" * 64, media_type="image/jpeg", width=100, height=100,
        byte_length=10, storage_path="/tmp/idem.jpg", retention_days=30,
        retention_expires_at=now + timedelta(days=30), consent_provider_processing=False,
        created_at=now,
    ))
    candidate = {
        "candidate_id": "module-a", "entity_type": "module", "manufacturer": "Make",
        "model": "Alpha", "confidence": 0.8, "confidence_method": "fixture",
        "classification_status": "INFERRED", "evidence_id": "ev-idem",
    }
    db_session.add(ClassificationEvidenceRecord(
        id="ev-idem", image_asset_id="img-idem", inventory_revision_id=None,
        evidence_packet={"devices": [candidate]}, provider="fixture-vision",
        pipeline_version="vision-v1", status="INFERRED", created_at=now,
    ))
    db_session.commit()

    provider = CountingProvider()
    import evidence.routes as routes
    monkeypatch.setattr(routes, "_configured_decision_provider", lambda **_: provider)
    monkeypatch.setattr(settings, "enable_decision_intelligence", True)

    seen = {}
    import intelligence.clef_resolution as clef_resolution
    real = clef_resolution.resolve_module_identity_guarded

    def spy(*args, **kwargs):
        seen["routing_targets"] = kwargs["routing_targets"]
        return real(*args, **kwargs)

    monkeypatch.setattr(clef_resolution, "resolve_module_identity_guarded", spy)

    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app, headers=rack_owner_headers(db_session, sample_rack_basic.id))
        url = f"/api/racks/{sample_rack_basic.id}/evidence/decision-resolution"
        first = client.post(url, json={"evidence_id": "ev-idem", "idempotency_key": "k1"})
        assert first.status_code == 200, first.text
        assert seen["routing_targets"] == frozenset({settings.decision_routing_target})
        assert settings.decision_routing_target == "human_review"

        again = client.post(url, json={"evidence_id": "ev-idem", "idempotency_key": "k1"})
        assert again.status_code == 200, again.text
        assert again.json() == first.json()
        assert provider.calls == 1

        # Same key, different stored evidence hash: 409, provider untouched.
        _store_with_other_hash(db_session)
        db_session.commit()
        conflict = client.post(url, json={"evidence_id": "ev-idem", "idempotency_key": "k1"})
        assert conflict.status_code == 409
        assert conflict.json()["detail"] == "IDEMPOTENCY_KEY_CONFLICT"
        assert provider.calls == 1
    finally:
        app.dependency_overrides.clear()
        monkeypatch.setattr(settings, "enable_decision_intelligence", False)


def test_replay_ends_in_the_stored_disposition_state() -> None:
    db = _db()
    _seed(db)
    first = _resolve(db, CountingProvider())
    replay = _resolve(db, CountingProvider())
    assert replay.replayed_receipt is not None
    assert replay.machine.state is first.machine.state is ResolutionState.AUTO_PROPOSE


def test_deduplicated_decision_still_binds_the_new_key() -> None:
    # The provider returns the same decision id under a second key. The older receipt
    # is reused, but the new key must be bound so a retry does not call the provider.
    db = _db()
    _seed(db)
    first = CountingProvider()
    _resolve(db, first, key="k1")

    class SameDecision(CountingProvider):
        def choose(self, request):
            packet = super().choose(request)
            return packet.model_copy(update={"decision_id": "decision-1"})

    second = SameDecision()
    _resolve(db, second, key="k2")
    assert second.calls == 1
    assert db.query(DecisionReceiptRecord).count() == 1
    assert db.query(DecisionReceiptKeyRecord).count() == 2

    retry = SameDecision()
    replay = _resolve(db, retry, key="k2")
    assert retry.calls == 0
    assert replay.replayed_receipt is not None


def test_lost_race_replays_the_winner_instead_of_failing(monkeypatch) -> None:
    # Simulate an overlapping request that bound the key between our lookup and our
    # insert: the first lookup misses, then the winner commits its binding.
    import intelligence.clef_resolution as resolution_module

    db = _db()
    _seed(db)
    winner_provider = CountingProvider()
    real_find = resolution_module.find_idempotent_receipt
    state = {"first": True}

    def racing_find(*args, **kwargs):
        if state["first"]:
            state["first"] = False
            _resolve(db, winner_provider)  # the other request wins the key
            return None
        return real_find(*args, **kwargs)

    monkeypatch.setattr(resolution_module, "find_idempotent_receipt", racing_find)
    loser_provider = CountingProvider(choice="none_of_above", confidence=0.1)
    loser = _resolve(db, loser_provider)
    assert loser_provider.calls == 1  # it did not see the winner before calling
    assert loser.replayed_receipt is not None
    assert loser.replayed_receipt.selected_choice == "module-a"
    assert db.query(DecisionReceiptRecord).count() == 1
