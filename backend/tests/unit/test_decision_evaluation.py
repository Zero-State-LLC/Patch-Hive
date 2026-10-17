from datetime import datetime, timezone

from intelligence.contracts import DecisionPacket
from intelligence.evaluation import EvaluationCase, corpus_sha256, evaluate, evaluation_receipt
from intelligence.policy import DecisionPolicy, PolicyThresholds


def _packet(choice: str, probabilities: dict[str, float], confidence: float):
    return DecisionPacket(
        decision_id=f"d-{choice}",
        request_id=f"r-{choice}",
        provider="fixture",
        provider_version="eval-v1",
        evidence_hash="h",
        answer_type="choice",
        selected_choice=choice,
        probabilities=probabilities,
        confidence=confidence,
        candidate_set_hash="set",
        created_at=datetime.now(timezone.utc),
    )


def test_evaluation_reports_accuracy_calibration_and_abstention() -> None:
    policy = DecisionPolicy(
        PolicyThresholds(
            policy_version="eval-v1",
            auto_propose_at=0.9,
            user_review_at=0.65,
            probability_margin=0.1,
        )
    )
    cases = (
        EvaluationCase(
            case_id="a",
            cohort="clear-panel",
            expected_choice="mod-a",
            licensed_source="synthetic-fixture",
            packet=_packet("mod-a", {"mod-a": 0.95, "none_of_above": 0.05}, 0.95),
        ),
        EvaluationCase(
            case_id="b",
            cohort="unknown",
            expected_choice="none_of_above",
            licensed_source="synthetic-fixture",
            packet=_packet("none_of_above", {"mod-b": 0.1, "none_of_above": 0.9}, 0.9),
        ),
    )
    metrics = evaluate(cases, policy)
    assert metrics.case_count == 2
    assert metrics.top1_accuracy == 1.0
    assert metrics.abstention_rate == 0.5
    assert metrics.false_canonicalization_count == 0
    assert metrics.topk_accuracy == 1.0
    assert metrics.cohort_metrics["clear-panel"]["case_count"] == 1
    assert metrics.cohort_metrics["unknown"]["abstention_rate"] == 1.0
    assert 0 <= metrics.brier_score <= 1


def test_corpus_digest_is_stable_across_case_order() -> None:
    a = EvaluationCase(
        case_id="a", cohort="clear", expected_choice="mod-a",
        licensed_source="synthetic-fixture",
        packet=_packet("mod-a", {"mod-a": 1.0}, 1.0),
    )
    b = EvaluationCase(
        case_id="b", cohort="unknown", expected_choice="none_of_above",
        licensed_source="synthetic-fixture",
        packet=_packet("none_of_above", {"none_of_above": 1.0}, 1.0),
    )
    assert corpus_sha256((a, b)) == corpus_sha256((b, a))


def test_receipt_is_measured_but_not_operator_approved() -> None:
    policy = DecisionPolicy(
        PolicyThresholds(
            policy_version="eval-v1",
            auto_propose_at=0.9,
            user_review_at=0.65,
            probability_margin=0.1,
        )
    )
    cases = (
        EvaluationCase(
            case_id="a", cohort="clear", expected_choice="mod-a",
            licensed_source="synthetic-fixture",
            packet=_packet("mod-a", {"mod-a": 1.0}, 1.0),
        ),
    )
    metrics = evaluate(cases, policy)
    receipt = evaluation_receipt(
        cases=cases,
        metrics=metrics,
        policy=policy,
        baseline_id="vision-only",
        provider_id="fixture",
    )
    assert receipt["corpus_sha256"] == corpus_sha256(cases)
    assert receipt["status"] == "MEASURED_NOT_APPROVED"
    assert receipt["operator_approval"] is None


def test_topk_can_recover_a_top1_miss() -> None:
    policy = DecisionPolicy(PolicyThresholds(
        policy_version="eval-v1", auto_propose_at=0.9,
        user_review_at=0.65, probability_margin=0.1,
    ))
    case = EvaluationCase(
        case_id="topk", cohort="hard_negative", expected_choice="mod-b",
        licensed_source="synthetic-fixture",
        packet=_packet(
            "mod-a",
            {"mod-a": 0.45, "mod-b": 0.35, "none_of_above": 0.20},
            0.45,
        ),
    )
    metrics = evaluate((case,), policy)
    assert metrics.top1_accuracy == 0.0
    assert metrics.topk_accuracy == 1.0
    assert metrics.cohort_metrics["hard_negative"]["case_count"] == 1
