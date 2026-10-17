from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from intelligence.contracts import ChoiceOption, ChoiceRequest, DecisionPacket, DecisionPurpose
from intelligence.policy import DecisionDisposition, DecisionPolicy, PolicyThresholds
from intelligence.telemetry import project_telemetry


def _policy() -> DecisionPolicy:
    return DecisionPolicy(
        PolicyThresholds(
            policy_version="adversarial-v1",
            auto_propose_at=0.9,
            user_review_at=0.65,
            probability_margin=0.1,
        )
    )


def test_unknown_packet_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        DecisionPacket(
            decision_id="d",
            request_id="r",
            provider="fixture",
            provider_version="1",
            evidence_hash="h",
            answer_type="probability",
            probability_yes=0.9,
            created_at=datetime.now(timezone.utc),
            canonical_module_id="forbidden",
        )


def test_probability_distribution_must_sum_to_one() -> None:
    with pytest.raises(ValidationError, match="sum to 1"):
        DecisionPacket(
            decision_id="d",
            request_id="r",
            provider="fixture",
            provider_version="1",
            evidence_hash="h",
            answer_type="choice",
            selected_choice="a",
            probabilities={"a": 0.8, "b": 0.8},
            confidence=0.8,
            created_at=datetime.now(timezone.utc),
        )


def test_policy_threshold_order_is_validated() -> None:
    with pytest.raises(ValidationError, match="user_review_at"):
        PolicyThresholds(
            policy_version="bad",
            auto_propose_at=0.6,
            user_review_at=0.8,
        )


def test_ambiguous_noul_stays_unresolved() -> None:
    packet = DecisionPacket(
        decision_id="d",
        request_id="r",
        provider="fixture",
        provider_version="1",
        evidence_hash="h",
        answer_type="probability",
        probability_yes=0.55,
        created_at=datetime.now(timezone.utc),
    )
    assert _policy().evaluate(packet).disposition is DecisionDisposition.UNRESOLVED


def test_telemetry_does_not_expose_evidence_or_selected_choice() -> None:
    request = ChoiceRequest(
        request_id="r",
        purpose=DecisionPurpose.module_identity,
        evidence_hash="sensitive-hash",
        evidence_refs=("private-image-id",),
        context={"ocr": "manufacturer text"},
        idempotency_key="idem",
        question="Which module?",
        choices=(ChoiceOption(choice_id="a"), ChoiceOption(choice_id="none_of_above")),
    )
    packet = DecisionPacket(
        decision_id="d",
        request_id=request.request_id,
        provider="fixture",
        provider_version="1",
        evidence_hash=request.evidence_hash,
        answer_type="choice",
        selected_choice="a",
        probabilities={"a": 0.95, "none_of_above": 0.05},
        confidence=0.95,
        candidate_set_hash=request.candidate_set_hash(),
        created_at=datetime.now(timezone.utc),
    )
    telemetry = project_telemetry(packet, _policy().evaluate(packet))
    serialized = repr(telemetry)
    assert "sensitive-hash" not in serialized
    assert "private-image-id" not in serialized
    assert "manufacturer text" not in serialized
    assert "selected_choice" not in serialized
