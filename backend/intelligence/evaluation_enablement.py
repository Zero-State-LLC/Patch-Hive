"""Baseline evaluation, threshold proposal, operator approval, staging enablement,
and the pinned evaluation receipt (Spec 007, T020-T060).

Every artifact here is a frozen, SHA-linked record:

    CorpusFreeze -> BaselineRun -> ThresholdProposal -> OperatorApproval
                 -> StagingEnablement -> EvaluationEnablementReceipt

Each record carries the SHA of the record it depends on and its own content SHA.
Nothing here calls a provider, the network, or the database, and nothing writes
canon. Disposition always comes from the Spec 005 DecisionPolicy. Packets are
consumed only through the provider-neutral DecisionPacket contract, so no Clef
adapter type is referenced. Image bytes, evidence payloads, and secrets are never
copied into these records; only identifiers, hashes, and aggregate metrics are.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.ops.edge_readiness import config_gate_checks
from intelligence.clef_evaluation import (
    LabeledCorpusCase,
    Modality,
    OperatorThresholds,
    receipt_sha256,
    verify_pinned_receipt,
)
from intelligence.contracts import stable_sha256
from intelligence.evaluation import evaluate
from intelligence.evaluation_corpus import CorpusFreeze, verify_corpus_freeze
from intelligence.policy import DecisionPolicy
from intelligence.resolution_machine import (
    ResolutionEvent,
    ResolutionEventType,
    ResolutionGuard,
    canon_write_permitted,
    replay,
)

BASELINE_RUN_SCHEMA = "patchhive.eval-baseline-run.v1"
THRESHOLD_PROPOSAL_SCHEMA = "patchhive.eval-threshold-proposal.v1"
OPERATOR_APPROVAL_SCHEMA = "patchhive.eval-operator-approval.v1"
STAGING_ENABLEMENT_SCHEMA = "patchhive.eval-staging-enablement.v1"
ENABLEMENT_RECEIPT_SCHEMA = "patchhive.eval-enablement-receipt.v1"

PROPOSAL_RULE = "non_regression_vs_baseline.v1"
STAGING_ENVIRONMENT = "staging"
ENABLEABLE_PROVIDERS = frozenset({"clef", "jev"})
CALIBRATION_BINS = 10

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")

HARNESS_SOURCE_FILES: tuple[str, ...] = (
    "intelligence/evaluation.py",
    "intelligence/clef_evaluation.py",
    "intelligence/evaluation_corpus.py",
    "intelligence/evaluation_enablement.py",
    "intelligence/policy.py",
)


class EnablementError(ValueError):
    """Fail-closed error. ``code`` is stable and never contains secrets."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def is_pinned_sha(value: object) -> bool:
    """A pinned source SHA: 40 (git SHA-1) or 64 (SHA-256) lowercase hex characters."""
    return isinstance(value, str) and _GIT_SHA.match(value) is not None


def harness_source_sha256(backend_root: Path | None = None) -> str:
    """SHA-256 over the evaluation harness source files, in a fixed order."""
    root = backend_root or Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for relative in HARNESS_SOURCE_FILES:
        digest.update(relative.encode("ascii"))
        digest.update(b"\0")
        digest.update((root / relative).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


_R = TypeVar("_R", bound="_Record")


class _Record(BaseModel):
    """Frozen record whose ``record_sha256`` seals every other field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def content_sha256(self) -> str:
        return stable_sha256(self.model_dump(mode="json", exclude={"record_sha256"}))

    def sealed(self: _R) -> _R:
        return self.model_copy(update={"record_sha256": self.content_sha256()})

    def intact(self) -> bool:
        stored = getattr(self, "record_sha256", "")
        return bool(stored) and stored == self.content_sha256()


# ---------------------------------------------------------------------------
# T020 baseline vs provider-assisted evaluation
# ---------------------------------------------------------------------------


class ConditionMetrics(BaseModel):
    """Aggregate metrics for one evaluation condition. No per-case content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    condition: Literal["baseline", "assisted"]
    provider_id: str = Field(min_length=1)
    case_count: int = Field(ge=1)
    top1_accuracy: float = Field(ge=0, le=1)
    topk_accuracy: float = Field(ge=0, le=1)
    brier_score: float = Field(ge=0, le=1)
    calibration_error: float = Field(ge=0, le=1)
    abstention_rate: float = Field(ge=0, le=1)
    review_rate: float = Field(ge=0, le=1)
    escalation_rate: float = Field(ge=0, le=1)
    false_canonicalization_count: int = Field(ge=0)
    modality_counts: dict[str, int]


def expected_calibration_error(
    cases: Iterable[LabeledCorpusCase], bins: int = CALIBRATION_BINS
) -> float:
    """Expected calibration error over equal-width confidence bins.

    Confidence is the declared probability of the selected choice; a case is
    correct when the selected choice equals the expected choice.
    """
    rows = tuple(cases)
    if not rows:
        raise EnablementError("CORPUS_EMPTY")
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for case in rows:
        packet = case.packet
        if packet.answer_type != "choice" or packet.selected_choice is None:
            raise EnablementError("NON_CHOICE_PACKET", case.case_id)
        confidence = float(packet.probabilities.get(packet.selected_choice, 0.0))
        index = min(bins - 1, int(confidence * bins))
        buckets[index].append((confidence, packet.selected_choice == case.expected_choice))
    total = len(rows)
    error = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        mean_conf = sum(item[0] for item in bucket) / len(bucket)
        accuracy = sum(1 for item in bucket if item[1]) / len(bucket)
        error += (len(bucket) / total) * abs(mean_conf - accuracy)
    return min(1.0, max(0.0, error))


def structural_false_canonicalizations(
    cases: Iterable[LabeledCorpusCase], policy: DecisionPolicy
) -> int:
    """Count cases where the Spec 006 resolution machine would permit a canon write
    from the policy disposition alone (no user confirmation). Must be zero."""
    count = 0
    for case in cases:
        disposition = policy.evaluate(case.packet).disposition
        request_id = f"eval:{case.case_id}"
        machine = replay(
            request_id,
            (
                ResolutionEvent(
                    ResolutionEventType.SUBMIT_EVIDENCE,
                    request_id,
                    ResolutionGuard(evidence_hash_valid=True, candidates_bounded=True),
                ),
                ResolutionEvent(
                    ResolutionEventType.PROVIDER_SUCCESS,
                    request_id,
                    ResolutionGuard(packet_schema_valid=True),
                ),
                ResolutionEvent(
                    ResolutionEventType.APPLY_POLICY,
                    request_id,
                    ResolutionGuard(policy_version_pinned=True),
                ),
                ResolutionEvent(
                    ResolutionEventType.DISPOSITION,
                    request_id,
                    ResolutionGuard(disposition=disposition, routing_target_exists=True),
                ),
            ),
        )
        count += int(canon_write_permitted(machine))
    return count


def _condition_metrics(
    condition: Literal["baseline", "assisted"],
    provider_id: str,
    cases: tuple[LabeledCorpusCase, ...],
    policy: DecisionPolicy,
) -> ConditionMetrics:
    metrics = evaluate((case.to_evaluation_case() for case in cases), policy)
    structural = structural_false_canonicalizations(cases, policy)
    return ConditionMetrics(
        condition=condition,
        provider_id=provider_id,
        case_count=metrics.case_count,
        top1_accuracy=metrics.top1_accuracy,
        topk_accuracy=metrics.topk_accuracy,
        brier_score=metrics.brier_score,
        calibration_error=expected_calibration_error(cases),
        abstention_rate=metrics.abstention_rate,
        review_rate=metrics.review_rate,
        escalation_rate=metrics.escalation_rate,
        false_canonicalization_count=metrics.false_canonicalization_count + structural,
        modality_counts={
            "text": sum(1 for case in cases if case.modality is Modality.text),
            "vision": sum(1 for case in cases if case.modality is Modality.vision),
        },
    )


def _bind_to_corpus(
    corpus: CorpusFreeze, cases: tuple[LabeledCorpusCase, ...], label: str
) -> None:
    index = corpus.case_index()
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise EnablementError("DUPLICATE_CASE_ID", label)
    if set(ids) != set(index):
        raise EnablementError("CASES_NOT_FROZEN_CORPUS", label)
    for case in cases:
        frozen = index[case.case_id]
        if case.expected_choice != frozen.expected_choice:
            raise EnablementError("LABEL_DRIFT", f"{label}:{case.case_id}")
        if case.cohort != frozen.cohort:
            raise EnablementError("COHORT_DRIFT", f"{label}:{case.case_id}")
        if case.modality is Modality.vision and case.image_sha256 not in frozen.image_sha256_hex():
            raise EnablementError("IMAGE_NOT_IN_FROZEN_CORPUS", f"{label}:{case.case_id}")


class BaselineRun(_Record):
    schema_version: str = BASELINE_RUN_SCHEMA
    corpus_sha256: str
    corpus_record_sha256: str
    harness_sha: str
    policy_version: str = Field(min_length=1)
    baseline_provider_id: str = Field(min_length=1)
    assisted_provider_id: str = Field(min_length=1)
    baseline: ConditionMetrics
    assisted: ConditionMetrics
    record_sha256: str = ""


def run_baseline_comparison(
    *,
    corpus: CorpusFreeze | None,
    baseline_cases: Iterable[LabeledCorpusCase],
    assisted_cases: Iterable[LabeledCorpusCase],
    policy: DecisionPolicy,
    harness_sha: str,
    baseline_provider_id: str,
    assisted_provider_id: str,
) -> BaselineRun:
    """Evaluate baseline vs provider-assisted packets on the exact frozen corpus."""
    if corpus is None or not verify_corpus_freeze(corpus):
        raise EnablementError("CORPUS_MISSING_OR_UNFROZEN")
    if not is_pinned_sha(harness_sha):
        raise EnablementError("HARNESS_SHA_NOT_PINNED")
    if assisted_provider_id not in ENABLEABLE_PROVIDERS:
        raise EnablementError("ASSISTED_PROVIDER_UNKNOWN", assisted_provider_id)
    if baseline_provider_id == assisted_provider_id:
        raise EnablementError("BASELINE_EQUALS_ASSISTED")
    baseline = tuple(baseline_cases)
    assisted = tuple(assisted_cases)
    if not baseline or not assisted:
        raise EnablementError("CORPUS_EMPTY")
    _bind_to_corpus(corpus, baseline, "baseline")
    _bind_to_corpus(corpus, assisted, "assisted")
    if any(case.packet.provider != assisted_provider_id for case in assisted):
        raise EnablementError("ASSISTED_PROVIDER_MISMATCH")
    if any(case.packet.provider == assisted_provider_id for case in baseline):
        raise EnablementError("BASELINE_CONTAINS_ASSISTED_PACKETS")
    if any(case.packet.provider != baseline_provider_id for case in baseline):
        raise EnablementError("BASELINE_PROVIDER_MISMATCH")

    run = BaselineRun(
        corpus_sha256=corpus.corpus_sha256,
        corpus_record_sha256=corpus.record_sha256,
        harness_sha=harness_sha,
        policy_version=policy.thresholds.policy_version,
        baseline_provider_id=baseline_provider_id,
        assisted_provider_id=assisted_provider_id,
        baseline=_condition_metrics("baseline", baseline_provider_id, baseline, policy),
        assisted=_condition_metrics("assisted", assisted_provider_id, assisted, policy),
    )
    if run.baseline.false_canonicalization_count or run.assisted.false_canonicalization_count:
        raise EnablementError("FALSE_CANONICALIZATION_NONZERO")
    return run.sealed()


# ---------------------------------------------------------------------------
# T030 threshold proposal
# ---------------------------------------------------------------------------


class ProposedThresholds(BaseModel):
    """Ranking, calibration, abstention, and false-canonicalization thresholds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    top1_min: float = Field(ge=0, le=1)
    topk_min: float = Field(ge=0, le=1)
    brier_max: float = Field(ge=0, le=1)
    calibration_error_max: float = Field(ge=0, le=1)
    abstention_max: float = Field(ge=0, le=1)
    false_canonicalization_max: int = 0

    @model_validator(mode="after")
    def _zero_false_canonicalization(self) -> "ProposedThresholds":
        if self.false_canonicalization_max != 0:
            raise ValueError("false_canonicalization_max must be zero")
        return self


class ThresholdProposal(_Record):
    schema_version: str = THRESHOLD_PROPOSAL_SCHEMA
    proposal_version: str = Field(min_length=1)
    rule: str = PROPOSAL_RULE
    corpus_sha256: str
    run_sha256: str
    policy_version: str
    assisted_provider_id: str
    thresholds: ProposedThresholds
    status: Literal["PROPOSED_PENDING_OPERATOR"] = "PROPOSED_PENDING_OPERATOR"
    record_sha256: str = ""


def metrics_collected(metrics: ConditionMetrics) -> bool:
    values = (
        metrics.top1_accuracy,
        metrics.topk_accuracy,
        metrics.brier_score,
        metrics.calibration_error,
        metrics.abstention_rate,
    )
    return all(isinstance(value, float) and math.isfinite(value) for value in values)


def propose_thresholds(run: BaselineRun | None, *, proposal_version: str) -> ThresholdProposal:
    """Propose thresholds from baseline results (rule: non-regression vs baseline).

    The assisted provider must be at least as good as the measured baseline on
    ranking (top-1/top-k), calibration (Brier, ECE), and abstention, and must
    produce zero false canonicalizations. The proposal is versioned and is NOT
    approved: approval is a separate explicit operator action.
    """
    if run is None or not run.intact():
        raise EnablementError("BASELINE_RUN_MISSING_OR_TAMPERED")
    if not proposal_version or not proposal_version.strip():
        raise EnablementError("PROPOSAL_VERSION_MISSING")
    if not (metrics_collected(run.baseline) and metrics_collected(run.assisted)):
        raise EnablementError("METRICS_NOT_COLLECTED")
    base = run.baseline
    proposal = ThresholdProposal(
        proposal_version=proposal_version,
        corpus_sha256=run.corpus_sha256,
        run_sha256=run.record_sha256,
        policy_version=run.policy_version,
        assisted_provider_id=run.assisted_provider_id,
        thresholds=ProposedThresholds(
            top1_min=base.top1_accuracy,
            topk_min=base.topk_accuracy,
            brier_max=base.brier_score,
            calibration_error_max=base.calibration_error,
            abstention_max=base.abstention_rate,
            false_canonicalization_max=0,
        ),
    )
    return proposal.sealed()


# ---------------------------------------------------------------------------
# T040 operator approval (explicit, timestamped, SHA-linked) and frozen thresholds
# ---------------------------------------------------------------------------


class OperatorApproval(_Record):
    schema_version: str = OPERATOR_APPROVAL_SCHEMA
    decision: Literal["APPROVED"] = "APPROVED"
    explicit_sign_off: Literal[True]
    approved_by: str = Field(min_length=1)
    approved_at: str
    thresholds_version: str = Field(min_length=1)
    proposal_sha256: str
    run_sha256: str
    corpus_sha256: str
    policy_version: str
    assisted_provider_id: str
    thresholds: ProposedThresholds
    record_sha256: str = ""

    @field_validator("approved_at")
    @classmethod
    def _utc_timestamp(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("approved_at must be timezone-aware")
        return value

    def to_operator_thresholds(self) -> OperatorThresholds:
        """Frozen thresholds in the Spec 006 OperatorThresholds shape."""
        return OperatorThresholds(
            thresholds_version=self.thresholds_version,
            approved_by=self.approved_by,
            top1_min=self.thresholds.top1_min,
            topk_min=self.thresholds.topk_min,
            brier_max=self.thresholds.brier_max,
            abstention_max=self.thresholds.abstention_max,
            false_canonicalization_max=0,
        )


def approve_thresholds(
    proposal: ThresholdProposal | None,
    *,
    approved_by: str,
    approved_at: datetime,
    explicit_sign_off: bool,
) -> OperatorApproval:
    """Record an explicit operator sign-off on the exact proposal SHA."""
    if proposal is None or not proposal.intact():
        raise EnablementError("PROPOSAL_MISSING_OR_TAMPERED")
    if explicit_sign_off is not True:
        raise EnablementError("EXPLICIT_SIGN_OFF_REQUIRED")
    if not approved_by or not approved_by.strip():
        raise EnablementError("APPROVER_MISSING")
    if not isinstance(approved_at, datetime) or approved_at.tzinfo is None:
        raise EnablementError("APPROVAL_TIMESTAMP_INVALID")
    stamp = approved_at.astimezone(timezone.utc).isoformat(timespec="seconds")
    approval = OperatorApproval(
        explicit_sign_off=True,
        approved_by=approved_by,
        approved_at=stamp.replace("+00:00", "Z"),
        thresholds_version=proposal.proposal_version,
        proposal_sha256=proposal.record_sha256,
        run_sha256=proposal.run_sha256,
        corpus_sha256=proposal.corpus_sha256,
        policy_version=proposal.policy_version,
        assisted_provider_id=proposal.assisted_provider_id,
        thresholds=proposal.thresholds,
    )
    return approval.sealed()


class ThresholdCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str
    observed: float
    limit: float
    comparator: Literal["min", "max"]
    passed: bool


def check_frozen_thresholds(
    metrics: ConditionMetrics, thresholds: ProposedThresholds
) -> tuple[ThresholdCheckResult, ...]:
    def _check(metric: str, observed: float, limit: float, comparator: str) -> ThresholdCheckResult:
        passed = observed >= limit if comparator == "min" else observed <= limit
        return ThresholdCheckResult(
            metric=metric, observed=observed, limit=limit, comparator=comparator, passed=passed
        )

    return (
        _check("top1_accuracy", metrics.top1_accuracy, thresholds.top1_min, "min"),
        _check("topk_accuracy", metrics.topk_accuracy, thresholds.topk_min, "min"),
        _check("brier_score", metrics.brier_score, thresholds.brier_max, "max"),
        _check(
            "calibration_error",
            metrics.calibration_error,
            thresholds.calibration_error_max,
            "max",
        ),
        _check("abstention_rate", metrics.abstention_rate, thresholds.abstention_max, "max"),
        _check(
            "false_canonicalization_count",
            float(metrics.false_canonicalization_count),
            float(thresholds.false_canonicalization_max),
            "max",
        ),
    )


# ---------------------------------------------------------------------------
# T050 staging-only enablement
# ---------------------------------------------------------------------------


class StagingEnablement(_Record):
    schema_version: str = STAGING_ENABLEMENT_SCHEMA
    environment: Literal["staging"] = "staging"
    providers: tuple[str, ...]
    approval_sha256: str
    run_sha256: str
    corpus_sha256: str
    threshold_checks: tuple[ThresholdCheckResult, ...]
    config_checks: tuple[dict[str, Any], ...]
    production_flag_default_off: Literal[True] = True
    production_traffic: Literal[False] = False
    live_payments: Literal[False] = False
    d1_permitted: Literal[False] = False
    record_sha256: str = ""


_REQUIRED_CONFIG_CHECKS = ("PAYMENTS_LIVE_DISABLED", "CLEF_FLAG_DEFAULT_OFF", "NO_D1_BINDING")


def enable_staging(
    *,
    approval: OperatorApproval | None,
    run: BaselineRun | None,
    settings_obj: Any,
    target_environment: str,
    providers: Iterable[str] = ("clef",),
) -> StagingEnablement:
    """Authorize enabling evaluated provider(s) in staging only.

    This returns an authorization record; it does not mutate settings. The
    provider feature flag keeps its class default of false, so every other
    environment stays off unless an operator sets it there, which this record
    never authorizes. Production is always refused.
    """
    if approval is None or not approval.intact():
        raise EnablementError("THRESHOLDS_NOT_APPROVED")
    if run is None or not run.intact():
        raise EnablementError("BASELINE_RUN_MISSING_OR_TAMPERED")
    if approval.run_sha256 != run.record_sha256 or approval.corpus_sha256 != run.corpus_sha256:
        raise EnablementError("APPROVAL_NOT_LINKED_TO_RUN")
    if approval.assisted_provider_id != run.assisted_provider_id:
        raise EnablementError("PROVIDER_NOT_EVALUATED")
    if approval.policy_version != run.policy_version:
        raise EnablementError("POLICY_VERSION_DRIFT")
    if run.baseline.false_canonicalization_count or run.assisted.false_canonicalization_count:
        raise EnablementError("FALSE_CANONICALIZATION_NONZERO")
    if target_environment != STAGING_ENVIRONMENT:
        raise EnablementError("NON_STAGING_ENVIRONMENT", str(target_environment))
    settings_env = getattr(settings_obj, "environment", None)
    if settings_env != STAGING_ENVIRONMENT:
        raise EnablementError("NON_STAGING_ENVIRONMENT", str(settings_env))
    wanted = tuple(sorted(set(providers)))
    if not wanted:
        raise EnablementError("NO_PROVIDER_REQUESTED")
    if any(provider not in ENABLEABLE_PROVIDERS for provider in wanted):
        raise EnablementError("PROVIDER_UNKNOWN")
    if wanted != (approval.assisted_provider_id,):
        raise EnablementError("PROVIDER_NOT_EVALUATED")

    config = config_gate_checks(settings_obj, expected_frontend_origin=None)
    by_code = {check.code: check for check in config}
    failed = [code for code in _REQUIRED_CONFIG_CHECKS if not by_code.get(code) or not by_code[code].passed]
    if failed:
        raise EnablementError("CONFIG_GATES_FAILED", ",".join(failed))

    checks = check_frozen_thresholds(run.assisted, approval.thresholds)
    if not all(check.passed for check in checks):
        raise EnablementError(
            "THRESHOLDS_NOT_MET",
            ",".join(check.metric for check in checks if not check.passed),
        )

    record = StagingEnablement(
        providers=wanted,
        approval_sha256=approval.record_sha256,
        run_sha256=run.record_sha256,
        corpus_sha256=run.corpus_sha256,
        threshold_checks=checks,
        config_checks=tuple(
            {"code": by_code[code].code, "passed": by_code[code].passed, "detail": by_code[code].detail}
            for code in _REQUIRED_CONFIG_CHECKS
        ),
    )
    return record.sealed()


# ---------------------------------------------------------------------------
# T060 SHA-pinned evaluation receipt
# ---------------------------------------------------------------------------


class EvaluationEnablementReceipt(BaseModel):
    """Immutable receipt covering corpus, harness, thresholds, and staging enablement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = ENABLEMENT_RECEIPT_SCHEMA
    source_commit_sha: str
    harness_sha: str
    corpus_sha256: str
    corpus_record_sha256: str
    run_sha256: str
    proposal_sha256: str
    approval_sha256: str
    staging_enablement_sha256: str
    policy_version: str
    thresholds_version: str
    thresholds: ProposedThresholds
    approved_by: str
    approved_at: str
    environment: Literal["staging"] = "staging"
    providers: tuple[str, ...]
    baseline_metrics: ConditionMetrics
    assisted_metrics: ConditionMetrics
    false_canonicalization_count: Literal[0] = 0
    status: Literal["RECEIPT_PINNED"] = "RECEIPT_PINNED"
    receipt_sha256: str = ""

    def as_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def computed_sha256(self) -> str:
        return receipt_sha256(self.as_payload())


def pin_receipt(
    *,
    corpus: CorpusFreeze | None,
    run: BaselineRun | None,
    proposal: ThresholdProposal | None,
    approval: OperatorApproval | None,
    staging: StagingEnablement | None,
    source_commit_sha: str,
) -> EvaluationEnablementReceipt:
    """Build the pinned receipt after verifying the whole SHA chain."""
    if corpus is None or not verify_corpus_freeze(corpus):
        raise EnablementError("CORPUS_MISSING_OR_UNFROZEN")
    for name, record in (
        ("run", run),
        ("proposal", proposal),
        ("approval", approval),
        ("staging", staging),
    ):
        if record is None or not record.intact():
            raise EnablementError("CHAIN_RECORD_MISSING_OR_TAMPERED", name)
    if run is None or proposal is None or approval is None or staging is None:
        raise EnablementError("CHAIN_RECORD_MISSING_OR_TAMPERED")
    if not is_pinned_sha(source_commit_sha):
        raise EnablementError("SOURCE_SHA_NOT_PINNED")
    chain_ok = (
        run.corpus_record_sha256 == corpus.record_sha256
        and run.corpus_sha256 == corpus.corpus_sha256
        and proposal.run_sha256 == run.record_sha256
        and approval.proposal_sha256 == proposal.record_sha256
        and approval.run_sha256 == run.record_sha256
        and staging.approval_sha256 == approval.record_sha256
        and staging.run_sha256 == run.record_sha256
        and staging.corpus_sha256 == corpus.corpus_sha256
        and proposal.corpus_sha256 == corpus.corpus_sha256
        and approval.corpus_sha256 == corpus.corpus_sha256
    )
    if not chain_ok:
        raise EnablementError("SHA_CHAIN_BROKEN")
    content_ok = (
        proposal.assisted_provider_id == run.assisted_provider_id
        and approval.assisted_provider_id == run.assisted_provider_id
        and staging.providers == (run.assisted_provider_id,)
        and approval.thresholds == proposal.thresholds
        and approval.policy_version == run.policy_version
        and proposal.policy_version == run.policy_version
    )
    if not content_ok:
        raise EnablementError("CHAIN_CONTENT_INCONSISTENT")
    if run.baseline.false_canonicalization_count or run.assisted.false_canonicalization_count:
        raise EnablementError("FALSE_CANONICALIZATION_NONZERO")
    receipt = EvaluationEnablementReceipt(
        source_commit_sha=source_commit_sha,
        harness_sha=run.harness_sha,
        corpus_sha256=corpus.corpus_sha256,
        corpus_record_sha256=corpus.record_sha256,
        run_sha256=run.record_sha256,
        proposal_sha256=proposal.record_sha256,
        approval_sha256=approval.record_sha256,
        staging_enablement_sha256=staging.record_sha256,
        policy_version=run.policy_version,
        thresholds_version=approval.thresholds_version,
        thresholds=approval.thresholds,
        approved_by=approval.approved_by,
        approved_at=approval.approved_at,
        providers=staging.providers,
        baseline_metrics=run.baseline,
        assisted_metrics=run.assisted,
    )
    return receipt.model_copy(update={"receipt_sha256": receipt.computed_sha256()})


def verify_enablement_receipt(receipt: EvaluationEnablementReceipt | Mapping[str, Any] | None) -> bool:
    """True when the receipt's stored SHA matches its content."""
    if receipt is None:
        return False
    payload = receipt.as_payload() if isinstance(receipt, EvaluationEnablementReceipt) else dict(receipt)
    if payload.get("schema_version") != ENABLEMENT_RECEIPT_SCHEMA:
        return False
    if not _HEX64.match(str(payload.get("receipt_sha256", ""))):
        return False
    return verify_pinned_receipt(payload)
