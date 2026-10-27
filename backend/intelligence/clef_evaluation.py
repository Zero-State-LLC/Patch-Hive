"""Labeled corpus and pinned-receipt extensions for Clef evaluation (Spec 006)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from intelligence.contracts import DecisionPacket
from intelligence.evaluation import (
    EvaluationCase,
    EvaluationMetrics,
    evaluate,
    evaluation_receipt,
)
from intelligence.policy import DecisionPolicy

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class Modality(str, Enum):
    text = "text"
    vision = "vision"


class LabeledCorpusCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    cohort: str = Field(min_length=1)
    modality: Modality
    expected_choice: str = Field(min_length=1)
    licensed_source: str = Field(min_length=1)
    packet: DecisionPacket
    image_sha256: str | None = None
    notes: str | None = None

    @field_validator("licensed_source")
    @classmethod
    def _no_blank_source(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("licensed_source must not be blank")
        return value

    @model_validator(mode="after")
    def _validate_modality_modalities(self) -> "LabeledCorpusCase":
        if self.modality is Modality.vision:
            if self.image_sha256 is None:
                raise ValueError("vision cases require image_sha256")
            if not _HEX64.match(self.image_sha256):
                raise ValueError(
                    "image_sha256 must be 64 lowercase hex characters"
                )
        else:
            if self.image_sha256 is not None:
                raise ValueError("text cases must not carry image_sha256")
        return self

    def to_evaluation_case(self) -> EvaluationCase:
        return EvaluationCase(
            case_id=self.case_id,
            cohort=self.cohort,
            expected_choice=self.expected_choice,
            licensed_source=self.licensed_source,
            packet=self.packet,
        )


def load_labeled_corpus(path: Path) -> tuple[LabeledCorpusCase, ...]:
    cases: list[LabeledCorpusCase] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except Exception as exc:
            raise ValueError(f"invalid JSON at line {line_number}") from exc
        try:
            case = LabeledCorpusCase.model_validate(payload)
        except Exception as exc:
            raise ValueError(
                f"invalid labeled corpus case at line {line_number}"
            ) from exc
        if case.case_id in seen:
            raise ValueError(
                f"duplicate case_id {case.case_id!r} at line {line_number}"
            )
        seen.add(case.case_id)
        cases.append(case)
    if not cases:
        raise ValueError("labeled corpus is empty")
    modalities = {case.modality for case in cases}
    if Modality.text not in modalities or Modality.vision not in modalities:
        raise ValueError("corpus must contain both text and vision cases")
    return tuple(cases)


def labeled_corpus_sha256(cases: Iterable[LabeledCorpusCase]) -> str:
    rows = sorted(
        (case.model_dump(mode="json") for case in cases),
        key=lambda row: row["case_id"],
    )
    payload = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class OperatorThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    thresholds_version: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    top1_min: float = Field(ge=0, le=1)
    topk_min: float = Field(ge=0, le=1)
    brier_max: float = Field(ge=0, le=1)
    abstention_max: float = Field(ge=0, le=1)
    false_canonicalization_max: int = 0

    @model_validator(mode="after")
    def _zero_false_canonicalization(self) -> "OperatorThresholds":
        if self.false_canonicalization_max != 0:
            raise ValueError("false_canonicalization_max must be zero")
        return self


@dataclass(frozen=True)
class ThresholdCheck:
    metric: str
    observed: float
    limit: float
    comparator: str
    passed: bool


def check_thresholds(
    metrics: EvaluationMetrics, thresholds: OperatorThresholds
) -> tuple[ThresholdCheck, ...]:
    checks: list[ThresholdCheck] = []

    def _record(
        metric: str, observed: float, limit: float, comparator: str
    ) -> None:
        passed = observed >= limit if comparator == "min" else observed <= limit
        checks.append(
            ThresholdCheck(
                metric=metric,
                observed=observed,
                limit=limit,
                comparator=comparator,
                passed=passed,
            )
        )

    _record("top1_accuracy", metrics.top1_accuracy, thresholds.top1_min, "min")
    _record("topk_accuracy", metrics.topk_accuracy, thresholds.topk_min, "min")
    _record("brier_score", metrics.brier_score, thresholds.brier_max, "max")
    _record(
        "abstention_rate", metrics.abstention_rate, thresholds.abstention_max, "max"
    )
    _record(
        "false_canonicalization_count",
        float(metrics.false_canonicalization_count),
        float(thresholds.false_canonicalization_max),
        "max",
    )
    return tuple(checks)


def evaluate_labeled_corpus(
    cases: Iterable[LabeledCorpusCase], policy: DecisionPolicy
) -> dict[str, EvaluationMetrics]:
    rows = tuple(cases)
    if not rows:
        raise ValueError("labeled corpus is empty")

    def _subset(modality: Modality | None) -> tuple[EvaluationCase, ...]:
        selected = rows if modality is None else tuple(
            case for case in rows if case.modality is modality
        )
        return tuple(case.to_evaluation_case() for case in selected)

    return {
        "overall": evaluate(_subset(None), policy),
        "text": evaluate(_subset(Modality.text), policy),
        "vision": evaluate(_subset(Modality.vision), policy),
    }


def receipt_sha256(receipt: dict[str, object]) -> str:
    payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def verify_pinned_receipt(receipt: dict[str, object]) -> bool:
    stored = receipt.get("receipt_sha256")
    if not isinstance(stored, str):
        return False
    try:
        computed = receipt_sha256(receipt)
    except (ValueError, TypeError):
        return False
    return computed == stored


def build_pinned_receipt(
    *,
    cases: Iterable[LabeledCorpusCase],
    policy: DecisionPolicy,
    baseline_id: str,
    provider_id: str,
    thresholds: OperatorThresholds | None,
) -> dict[str, object]:
    rows = tuple(cases)
    if not rows:
        raise ValueError("labeled corpus is empty")

    metrics_by_modality = evaluate_labeled_corpus(rows, policy)
    overall = metrics_by_modality["overall"]
    eval_cases = tuple(case.to_evaluation_case() for case in rows)

    receipt = evaluation_receipt(
        cases=eval_cases,
        metrics=overall,
        policy=policy,
        baseline_id=baseline_id,
        provider_id=provider_id,
    )
    receipt["schema_version"] = "patchhive.clef-eval-receipt.v1"
    receipt["labeled_corpus_sha256"] = labeled_corpus_sha256(rows)
    receipt["modality_counts"] = {
        "text": sum(1 for case in rows if case.modality is Modality.text),
        "vision": sum(1 for case in rows if case.modality is Modality.vision),
    }
    receipt["modality_metrics"] = {
        "text": metrics_by_modality["text"].__dict__,
        "vision": metrics_by_modality["vision"].__dict__,
    }

    if thresholds is None:
        receipt["thresholds"] = None
        receipt["threshold_checks"] = []
        receipt["gate_passed"] = False
        receipt["status"] = "MEASURED_NOT_APPROVED"
    else:
        checks = check_thresholds(overall, thresholds)
        receipt["thresholds"] = thresholds.model_dump(mode="json")
        receipt["threshold_checks"] = [
            {
                "metric": check.metric,
                "observed": check.observed,
                "limit": check.limit,
                "comparator": check.comparator,
                "passed": check.passed,
            }
            for check in checks
        ]
        gate_passed = all(check.passed for check in checks)
        receipt["gate_passed"] = gate_passed
        receipt["status"] = (
            "THRESHOLDS_MET_PENDING_OPERATOR"
            if gate_passed
            else "THRESHOLDS_FAILED"
        )

    receipt["receipt_sha256"] = receipt_sha256(receipt)
    return receipt
