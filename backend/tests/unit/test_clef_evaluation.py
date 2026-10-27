"""Unit tests for Clef evaluation receipts and resolution telemetry (T080)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from intelligence.clef_evaluation import (
    LabeledCorpusCase,
    Modality,
    OperatorThresholds,
    build_pinned_receipt,
    labeled_corpus_sha256,
    load_labeled_corpus,
    verify_pinned_receipt,
)
from intelligence.clef_telemetry import (
    OutcomeCategory,
    emit,
    telemetry_for_policy_result,
    telemetry_for_provider_failure,
    to_log_record,
)
from intelligence.contracts import DecisionPacket
from intelligence.policy import DecisionDisposition, DecisionPolicy, PolicyThresholds

POLICY = DecisionPolicy(
    PolicyThresholds(
        policy_version="test-v1",
        auto_propose_at=0.9,
        user_review_at=0.65,
        probability_margin=0.1,
    )
)

FORBIDDEN_LOG_KEYS = {"context", "evidence", "selected_choice", "images"}
IMAGE_SHA = "a" * 64


def _choice_packet(
    request_id: str,
    selected: str,
    probabilities: dict[str, float],
    confidence: float,
) -> DecisionPacket:
    return DecisionPacket(
        decision_id=f"decision-{request_id}",
        request_id=request_id,
        provider="clef",
        provider_version="@cf/cloudflare/clef",
        evidence_hash=f"evidence-{request_id}",
        answer_type="choice",
        selected_choice=selected,
        probabilities=probabilities,
        confidence=confidence,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _text_case(case_id: str = "text-1") -> LabeledCorpusCase:
    return LabeledCorpusCase(
        case_id=case_id,
        cohort="beta",
        modality=Modality.text,
        expected_choice="mod-a",
        licensed_source="internal-test-license",
        packet=_choice_packet(
            request_id=f"req-{case_id}",
            selected="mod-a",
            probabilities={"mod-a": 0.95, "none_of_above": 0.05},
            confidence=0.95,
        ),
    )


def _vision_case(case_id: str = "vision-1") -> LabeledCorpusCase:
    return LabeledCorpusCase(
        case_id=case_id,
        cohort="beta",
        modality=Modality.vision,
        expected_choice="mod-a",
        licensed_source="internal-test-license",
        packet=_choice_packet(
            request_id=f"req-{case_id}",
            selected="mod-a",
            probabilities={"mod-a": 0.95, "none_of_above": 0.05},
            confidence=0.95,
        ),
        image_sha256=IMAGE_SHA,
    )


def _wrong_vision_case() -> LabeledCorpusCase:
    return LabeledCorpusCase(
        case_id="vision-wrong",
        cohort="beta",
        modality=Modality.vision,
        expected_choice="mod-a",
        licensed_source="internal-test-license",
        packet=_choice_packet(
            request_id="req-vision-wrong",
            selected="mod-b",
            probabilities={"mod-a": 0.05, "mod-b": 0.95},
            confidence=0.95,
        ),
        image_sha256=IMAGE_SHA,
    )


def _write_jsonl(path: Path, cases: tuple[LabeledCorpusCase, ...]) -> Path:
    lines = [json.dumps(case.model_dump(mode="json"), sort_keys=True) for case in cases]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _met_thresholds() -> OperatorThresholds:
    return OperatorThresholds(
        thresholds_version="v1",
        approved_by="operator",
        top1_min=0.9,
        topk_min=0.9,
        brier_max=0.1,
        abstention_max=0.1,
        false_canonicalization_max=0,
    )


def _build(cases: tuple[LabeledCorpusCase, ...], thresholds: OperatorThresholds | None):
    return build_pinned_receipt(
        cases=cases,
        policy=POLICY,
        baseline_id="baseline-1",
        provider_id="clef",
        thresholds=thresholds,
    )


# corpus loading ------------------------------------------------------------


def test_load_labeled_corpus_reads_text_and_vision(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "corpus.jsonl", (_text_case(), _vision_case()))
    loaded = load_labeled_corpus(path)

    assert {case.case_id for case in loaded} == {"text-1", "vision-1"}
    vision = next(case for case in loaded if case.modality is Modality.vision)
    assert vision.image_sha256 == IMAGE_SHA


def test_load_labeled_corpus_requires_both_modalities(tmp_path: Path) -> None:
    text_only = (_text_case("text-1"), _text_case("text-2"))
    path = _write_jsonl(tmp_path / "text_only.jsonl", text_only)

    with pytest.raises(ValueError, match="both text and vision"):
        load_labeled_corpus(path)


def test_load_labeled_corpus_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "duplicate.jsonl", (_text_case("dup"), _text_case("dup")))

    with pytest.raises(ValueError, match="duplicate case_id"):
        load_labeled_corpus(path)


def test_vision_case_requires_image_sha256() -> None:
    payload = _vision_case().model_dump(mode="json")
    payload["image_sha256"] = None

    with pytest.raises(ValueError, match="vision cases require image_sha256"):
        LabeledCorpusCase.model_validate(payload)


def test_text_case_rejects_image_sha256() -> None:
    payload = _text_case().model_dump(mode="json")
    payload["image_sha256"] = IMAGE_SHA

    with pytest.raises(ValueError, match="text cases must not carry image_sha256"):
        LabeledCorpusCase.model_validate(payload)


def test_labeled_corpus_sha256_is_order_independent() -> None:
    first = _text_case("text-1")
    second = _vision_case("vision-1")

    assert labeled_corpus_sha256((first, second)) == labeled_corpus_sha256((second, first))


# thresholds ----------------------------------------------------------------


def test_operator_thresholds_requires_zero_false_canonicalization() -> None:
    with pytest.raises(ValueError, match="false_canonicalization_max must be zero"):
        OperatorThresholds(
            thresholds_version="v1",
            approved_by="operator",
            top1_min=0.9,
            topk_min=0.9,
            brier_max=0.1,
            abstention_max=0.1,
            false_canonicalization_max=1,
        )


# receipts ------------------------------------------------------------------


def test_receipt_without_thresholds_is_measured_not_approved() -> None:
    receipt = _build((_text_case(), _vision_case()), None)

    assert receipt["status"] == "MEASURED_NOT_APPROVED"
    assert receipt["gate_passed"] is False
    assert receipt.get("operator_approval") is None
    assert verify_pinned_receipt(receipt) is True


def test_receipt_reports_modality_counts() -> None:
    receipt = _build((_text_case(), _vision_case()), None)

    assert receipt["modality_counts"] == {"text": 1, "vision": 1}


def test_tampered_receipt_fails_verification() -> None:
    receipt = _build((_text_case(), _vision_case()), _met_thresholds())
    assert verify_pinned_receipt(receipt) is True

    receipt["modality_metrics"]["text"]["top1_accuracy"] = 0.0

    assert verify_pinned_receipt(receipt) is False


def test_thresholds_met_is_pending_operator_never_approved() -> None:
    receipt = _build((_text_case(), _vision_case()), _met_thresholds())

    assert receipt["gate_passed"] is True
    assert receipt["status"] == "THRESHOLDS_MET_PENDING_OPERATOR"
    assert receipt.get("operator_approval") is None
    assert verify_pinned_receipt(receipt) is True


def test_thresholds_failing_is_reported_as_failed() -> None:
    receipt = _build((_text_case(), _wrong_vision_case()), _met_thresholds())

    assert receipt["gate_passed"] is False
    assert receipt["status"] == "THRESHOLDS_FAILED"


# telemetry -----------------------------------------------------------------


def test_provider_timeout_classified_as_provider_failure() -> None:
    telemetry = telemetry_for_provider_failure(
        provider="clef",
        provider_version="@cf/cloudflare/clef",
        error_code="CLEF_TIMEOUT",
        adapter_state="TIMEOUT",
        resolution_state="REJECT",
    )

    assert telemetry.category is OutcomeCategory.PROVIDER_FAILURE
    assert telemetry.error_code == "CLEF_TIMEOUT"
    assert telemetry.has_confidence is False


def test_provider_disabled_classified_as_disabled() -> None:
    telemetry = telemetry_for_provider_failure(
        provider="clef",
        provider_version="@cf/cloudflare/clef",
        error_code="CLEF_DISABLED",
        adapter_state="IDLE",
        resolution_state="PENDING",
    )

    assert telemetry.category is OutcomeCategory.DISABLED


def test_unresolved_low_confidence_is_not_a_provider_failure() -> None:
    result = SimpleNamespace(
        disposition=DecisionDisposition.UNRESOLVED,
        reason_codes=("CONFIDENCE_LOW",),
    )
    packet = _choice_packet(
        request_id="req-low",
        selected="mod-a",
        probabilities={"mod-a": 0.55, "none_of_above": 0.45},
        confidence=0.55,
    )

    telemetry = telemetry_for_policy_result(
        packet=packet,
        result=result,
        resolution_state="UNRESOLVED",
    )

    assert telemetry.category is OutcomeCategory.LOW_CONFIDENCE
    assert telemetry.category is not OutcomeCategory.PROVIDER_FAILURE


def test_none_of_above_abstention_is_classified_as_abstained() -> None:
    result = SimpleNamespace(
        disposition=DecisionDisposition.UNRESOLVED,
        reason_codes=("ABSTAINED_UNKNOWN",),
    )
    packet = _choice_packet(
        request_id="req-abstain",
        selected="none_of_above",
        probabilities={"mod-a": 0.2, "none_of_above": 0.8},
        confidence=0.8,
    )

    telemetry = telemetry_for_policy_result(
        packet=packet,
        result=result,
        resolution_state="UNRESOLVED",
    )

    assert telemetry.category is OutcomeCategory.ABSTAINED


def test_emit_logs_json_without_sensitive_keys(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    telemetry = telemetry_for_provider_failure(
        provider="clef",
        provider_version="@cf/cloudflare/clef",
        error_code="CLEF_TIMEOUT",
        adapter_state="TIMEOUT",
        resolution_state="REJECT",
    )

    record = emit(telemetry)

    assert record == to_log_record(telemetry)
    logged = json.loads(caplog.records[-1].message)
    assert logged["category"] == "PROVIDER_FAILURE"
    assert FORBIDDEN_LOG_KEYS.isdisjoint(logged)
