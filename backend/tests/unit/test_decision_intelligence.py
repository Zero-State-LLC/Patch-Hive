from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from intelligence.contracts import (
    ChoiceOption,
    ChoiceRequest,
    DecisionPacket,
    DecisionPurpose,
    ProbabilityRequest,
)
from intelligence.fixture_provider import FixtureDecisionProvider, failed_fixture
from intelligence.policy import DecisionDisposition, DecisionPolicy, PolicyThresholds


def _choice_request() -> ChoiceRequest:
    return ChoiceRequest(
        request_id="req-1",
        purpose=DecisionPurpose.module_identity,
        evidence_hash="evidence-sha",
        evidence_refs=("image-1",),
        idempotency_key="idem-1",
        question="Which catalog module matches this evidence?",
        choices=(
            ChoiceOption(choice_id="mod-a", description="Manufacturer A / Module A"),
            ChoiceOption(choice_id="mod-b", description="Manufacturer B / Module B"),
            ChoiceOption(choice_id="none_of_above"),
        ),
    )


def _policy() -> DecisionPolicy:
    return DecisionPolicy(
        PolicyThresholds(
            policy_version="test-v1",
            auto_propose_at=0.9,
            user_review_at=0.65,
            probability_margin=0.1,
        )
    )


def test_module_identity_requires_none_of_above() -> None:
    with pytest.raises(ValidationError, match="none_of_above"):
        ChoiceRequest(
            request_id="req",
            purpose=DecisionPurpose.module_identity,
            evidence_hash="hash",
            idempotency_key="idem",
            question="identity?",
            choices=(ChoiceOption(choice_id="mod-a"),),
        )


def test_fixture_rejects_choice_outside_server_candidates() -> None:
    request = _choice_request()
    packet = DecisionPacket(
        decision_id="decision-1",
        request_id=request.request_id,
        provider="fixture",
        provider_version="1",
        evidence_hash=request.evidence_hash,
        answer_type="choice",
        selected_choice="not-allowed",
        probabilities={"not-allowed": 1.0},
        confidence=1.0,
        candidate_set_hash=request.candidate_set_hash(),
        created_at=datetime.now(timezone.utc),
    )
    provider = FixtureDecisionProvider({request.request_id: packet})
    with pytest.raises(ValueError, match="outside"):
        provider.choose(request)


def test_high_confidence_choice_is_only_auto_proposed() -> None:
    request = _choice_request()
    packet = DecisionPacket(
        decision_id="decision-1",
        request_id=request.request_id,
        provider="fixture",
        provider_version="1",
        evidence_hash=request.evidence_hash,
        answer_type="choice",
        selected_choice="mod-a",
        probabilities={"mod-a": 0.94, "mod-b": 0.04, "none_of_above": 0.02},
        confidence=0.94,
        candidate_set_hash=request.candidate_set_hash(),
        created_at=datetime.now(timezone.utc),
    )
    result = _policy().evaluate(FixtureDecisionProvider({request.request_id: packet}).choose(request))
    assert result.disposition is DecisionDisposition.AUTO_PROPOSE
    assert result.disposition.value != "CANONICALIZED"


def test_none_of_above_remains_unresolved_even_with_high_confidence() -> None:
    request = _choice_request()
    packet = DecisionPacket(
        decision_id="decision-2",
        request_id=request.request_id,
        provider="fixture",
        provider_version="1",
        evidence_hash=request.evidence_hash,
        answer_type="choice",
        selected_choice="none_of_above",
        probabilities={"mod-a": 0.01, "mod-b": 0.01, "none_of_above": 0.98},
        confidence=0.98,
        candidate_set_hash=request.candidate_set_hash(),
        created_at=datetime.now(timezone.utc),
    )
    result = _policy().evaluate(packet)
    assert result.disposition is DecisionDisposition.UNRESOLVED


def test_unknown_choice_is_an_abstention() -> None:
    packet = DecisionPacket(
        decision_id="decision-unknown", request_id="req", provider="fixture", provider_version="1",
        evidence_hash="hash", answer_type="choice", selected_choice="unknown",
        probabilities={"known": 0.01, "unknown": 0.99}, confidence=0.99,
        candidate_set_hash="candidate-hash", created_at=datetime.now(timezone.utc),
    )
    assert _policy().evaluate(packet).disposition is DecisionDisposition.UNRESOLVED


@pytest.mark.parametrize("status", ["failed", "timed_out"])
def test_provider_failure_escalates_never_confirms(status: str) -> None:
    packet = failed_fixture(
        decision_id="decision-fail",
        request_id="req",
        provider_status=status,
        evidence_hash="hash",
        error_code="UPSTREAM",
    )
    result = _policy().evaluate(packet)
    assert result.disposition is DecisionDisposition.ESCALATE


def test_probability_uses_two_sided_certainty() -> None:
    request = ProbabilityRequest(
        request_id="prob-1",
        purpose=DecisionPurpose.evidence_conflict,
        evidence_hash="hash",
        idempotency_key="idem",
        question="Do these claims materially conflict?",
        true_criteria="Claims cannot both be true.",
        false_criteria="Claims are compatible.",
    )
    packet = DecisionPacket(
        decision_id="decision-prob",
        request_id=request.request_id,
        provider="fixture",
        provider_version="1",
        evidence_hash=request.evidence_hash,
        answer_type="probability",
        probability_yes=0.03,
        created_at=datetime.now(timezone.utc),
    )
    result = _policy().evaluate(packet)
    assert result.disposition is DecisionDisposition.AUTO_PROPOSE
    assert result.binary_conclusion is False


def test_probability_preserves_positive_direction() -> None:
    packet = DecisionPacket(
        decision_id="decision-prob-yes", request_id="req", provider="fixture", provider_version="1",
        evidence_hash="hash", answer_type="probability", probability_yes=0.97,
        created_at=datetime.now(timezone.utc),
    )
    result = _policy().evaluate(packet)
    assert result.disposition is DecisionDisposition.AUTO_PROPOSE
    assert result.binary_conclusion is True


def test_probability_ambiguous_has_no_binary_conclusion() -> None:
    packet = DecisionPacket(
        decision_id="decision-prob-ambiguous", request_id="req", provider="fixture", provider_version="1",
        evidence_hash="hash", answer_type="probability", probability_yes=0.5,
        created_at=datetime.now(timezone.utc),
    )
    result = _policy().evaluate(packet)
    assert result.disposition is DecisionDisposition.UNRESOLVED
    assert result.binary_conclusion is None


def test_failed_packet_cannot_smuggle_answer() -> None:
    with pytest.raises(ValidationError, match="cannot carry an answer"):
        DecisionPacket(
            decision_id="decision-bad",
            request_id="req",
            provider="fixture",
            provider_version="1",
            evidence_hash="hash",
            answer_type="choice",
            selected_choice="mod-a",
            probabilities={"mod-a": 1.0},
            provider_status="failed",
            error_code="UPSTREAM",
            created_at=datetime.now(timezone.utc),
        )


def test_packet_hash_is_stable() -> None:
    request = _choice_request()
    kwargs = dict(
        decision_id="decision-1",
        request_id=request.request_id,
        provider="fixture",
        provider_version="1",
        evidence_hash=request.evidence_hash,
        answer_type="choice",
        selected_choice="mod-a",
        probabilities={"mod-a": 0.9, "mod-b": 0.05, "none_of_above": 0.05},
        confidence=0.9,
        candidate_set_hash=request.candidate_set_hash(),
        created_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
    )
    assert DecisionPacket(**kwargs).result_hash() == DecisionPacket(**kwargs).result_hash()
