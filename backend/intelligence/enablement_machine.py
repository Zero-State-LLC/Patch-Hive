"""Evaluation & enablement state machine (Spec 007).

States (linear):
    CORPUS_DRAFT -> CORPUS_FROZEN -> BASELINE_RUN -> THRESHOLDS_PROPOSED
    -> OPERATOR_APPROVED -> STAGING_ENABLED -> RECEIPT_PINNED

Each event carries the artifact produced by the matching Spec 007 step. Guards
re-verify the artifact's integrity and its SHA link to the previously accepted
artifact, so a transition can never be satisfied by a stale, tampered, or
unrelated record. Missing artifacts fail closed. The machine is pure: no I/O, no
provider calls, no settings mutation, and no canon writes.

No path reaches STAGING_ENABLED without OPERATOR_APPROVED, and every artifact
must report a false-canonicalization count of zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping

from intelligence.evaluation_corpus import CorpusFreeze, verify_corpus_freeze
from intelligence.evaluation_enablement import (
    STAGING_ENVIRONMENT,
    BaselineRun,
    EnablementError,
    EvaluationEnablementReceipt,
    OperatorApproval,
    StagingEnablement,
    ThresholdProposal,
    check_frozen_thresholds,
    is_pinned_sha,
    metrics_collected,
    pin_receipt,
    verify_enablement_receipt,
)


class EnablementState(str, Enum):
    CORPUS_DRAFT = "CORPUS_DRAFT"
    CORPUS_FROZEN = "CORPUS_FROZEN"
    BASELINE_RUN = "BASELINE_RUN"
    THRESHOLDS_PROPOSED = "THRESHOLDS_PROPOSED"
    OPERATOR_APPROVED = "OPERATOR_APPROVED"
    STAGING_ENABLED = "STAGING_ENABLED"
    RECEIPT_PINNED = "RECEIPT_PINNED"


ENABLEMENT_ORDER: tuple[EnablementState, ...] = tuple(EnablementState)


class EnablementEventType(str, Enum):
    PROMOTE_CASES = "promote_cases"
    RUN_BASELINE = "run_baseline"
    PROPOSE_THRESHOLDS = "propose_thresholds"
    OPERATOR_APPROVE = "operator_approve"
    ENABLE_STAGING = "enable_staging"
    PIN_RECEIPT = "pin_receipt"


TRANSITIONS: Mapping[tuple[EnablementState, EnablementEventType], EnablementState] = (
    MappingProxyType(
        {
            (EnablementState.CORPUS_DRAFT, EnablementEventType.PROMOTE_CASES): EnablementState.CORPUS_FROZEN,
            (EnablementState.CORPUS_FROZEN, EnablementEventType.RUN_BASELINE): EnablementState.BASELINE_RUN,
            (EnablementState.BASELINE_RUN, EnablementEventType.PROPOSE_THRESHOLDS): EnablementState.THRESHOLDS_PROPOSED,
            (EnablementState.THRESHOLDS_PROPOSED, EnablementEventType.OPERATOR_APPROVE): EnablementState.OPERATOR_APPROVED,
            (EnablementState.OPERATOR_APPROVED, EnablementEventType.ENABLE_STAGING): EnablementState.STAGING_ENABLED,
            (EnablementState.STAGING_ENABLED, EnablementEventType.PIN_RECEIPT): EnablementState.RECEIPT_PINNED,
        }
    )
)


@dataclass(frozen=True)
class EnablementEvent:
    """One event plus the artifact that satisfies its guard (others ignored)."""

    type: EnablementEventType
    corpus: CorpusFreeze | None = None
    run: BaselineRun | None = None
    proposal: ThresholdProposal | None = None
    approval: OperatorApproval | None = None
    staging: StagingEnablement | None = None
    receipt: EvaluationEnablementReceipt | None = None


@dataclass(frozen=True)
class EnablementTransition:
    from_state: EnablementState
    event: EnablementEventType
    to_state: EnablementState
    accepted: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EnablementMachine:
    state: EnablementState = EnablementState.CORPUS_DRAFT
    corpus: CorpusFreeze | None = None
    run: BaselineRun | None = None
    proposal: ThresholdProposal | None = None
    approval: OperatorApproval | None = None
    staging: StagingEnablement | None = None
    receipt: EvaluationEnablementReceipt | None = None
    history: tuple[EnablementTransition, ...] = field(default_factory=tuple)


def new_machine() -> EnablementMachine:
    return EnablementMachine()


def staging_enabled(machine: EnablementMachine) -> bool:
    """True only once STAGING_ENABLED (or later) was reached via approval."""
    return (
        machine.state in {EnablementState.STAGING_ENABLED, EnablementState.RECEIPT_PINNED}
        and machine.approval is not None
        and machine.staging is not None
        and machine.approval.intact()
        and machine.staging.intact()
        and machine.staging.approval_sha256 == machine.approval.record_sha256
    )


def _guard_promote(m: EnablementMachine, ev: EnablementEvent) -> tuple[str, ...]:
    if ev.corpus is None:
        return ("CORPUS_MISSING",)
    if not verify_corpus_freeze(ev.corpus):
        return ("CORPUS_NOT_ADMITTED_OR_TAMPERED",)
    return ()


def _guard_run(m: EnablementMachine, ev: EnablementEvent) -> tuple[str, ...]:
    run = ev.run
    if m.corpus is None or not verify_corpus_freeze(m.corpus):
        return ("CORPUS_MISSING",)
    if run is None:
        return ("BASELINE_RUN_MISSING",)
    failed: list[str] = []
    if not run.intact():
        failed.append("BASELINE_RUN_TAMPERED")
    if not is_pinned_sha(run.harness_sha):
        failed.append("HARNESS_SHA_NOT_PINNED")
    if run.corpus_record_sha256 != m.corpus.record_sha256 or run.corpus_sha256 != m.corpus.corpus_sha256:
        failed.append("RUN_NOT_ON_FROZEN_CORPUS")
    if run.baseline.false_canonicalization_count or run.assisted.false_canonicalization_count:
        failed.append("FALSE_CANONICALIZATION_NONZERO")
    return tuple(failed)


def _guard_propose(m: EnablementMachine, ev: EnablementEvent) -> tuple[str, ...]:
    proposal = ev.proposal
    if m.run is None:
        return ("BASELINE_RUN_MISSING",)
    if proposal is None:
        return ("PROPOSAL_MISSING",)
    failed: list[str] = []
    if not proposal.intact():
        failed.append("PROPOSAL_TAMPERED")
    if proposal.run_sha256 != m.run.record_sha256:
        failed.append("PROPOSAL_NOT_LINKED_TO_RUN")
    if proposal.thresholds.false_canonicalization_max != 0:
        failed.append("FALSE_CANONICALIZATION_THRESHOLD_NONZERO")
    if not (metrics_collected(m.run.baseline) and metrics_collected(m.run.assisted)):
        failed.append("CALIBRATION_OR_ABSTENTION_NOT_COLLECTED")
    return tuple(failed)


def _guard_approve(m: EnablementMachine, ev: EnablementEvent) -> tuple[str, ...]:
    approval = ev.approval
    if m.proposal is None:
        return ("PROPOSAL_MISSING",)
    if approval is None:
        return ("OPERATOR_APPROVAL_MISSING",)
    failed: list[str] = []
    if not approval.intact():
        failed.append("APPROVAL_TAMPERED")
    if approval.explicit_sign_off is not True or approval.decision != "APPROVED":
        failed.append("EXPLICIT_SIGN_OFF_REQUIRED")
    if not approval.approved_at:
        failed.append("APPROVAL_TIMESTAMP_MISSING")
    if approval.proposal_sha256 != m.proposal.record_sha256:
        failed.append("APPROVAL_NOT_LINKED_TO_PROPOSAL")
    if approval.thresholds != m.proposal.thresholds:
        failed.append("APPROVED_THRESHOLDS_DIFFER_FROM_PROPOSAL")
    if (
        approval.run_sha256 != m.proposal.run_sha256
        or approval.corpus_sha256 != m.proposal.corpus_sha256
        or approval.policy_version != m.proposal.policy_version
        or approval.thresholds_version != m.proposal.proposal_version
    ):
        failed.append("APPROVAL_NOT_LINKED_TO_PROPOSAL")
    if approval.assisted_provider_id != m.proposal.assisted_provider_id:
        failed.append("PROVIDER_NOT_EVALUATED")
    return tuple(failed)


def _guard_enable(m: EnablementMachine, ev: EnablementEvent) -> tuple[str, ...]:
    staging = ev.staging
    if m.approval is None or m.state is not EnablementState.OPERATOR_APPROVED:
        return ("THRESHOLDS_NOT_APPROVED",)
    if staging is None:
        return ("STAGING_ENABLEMENT_MISSING",)
    failed: list[str] = []
    if not staging.intact():
        failed.append("STAGING_ENABLEMENT_TAMPERED")
    if staging.approval_sha256 != m.approval.record_sha256:
        failed.append("STAGING_NOT_LINKED_TO_APPROVAL")
    if staging.environment != STAGING_ENVIRONMENT:
        failed.append("NON_STAGING_ENVIRONMENT")
    if staging.production_traffic or not staging.production_flag_default_off:
        failed.append("PRODUCTION_FLAG_OR_TRAFFIC")
    if staging.live_payments or staging.d1_permitted:
        failed.append("PAYMENTS_OR_D1_PERMITTED")
    if m.run is None:
        return ("BASELINE_RUN_MISSING",)
    if staging.providers != (m.approval.assisted_provider_id,) or staging.providers != (
        m.run.assisted_provider_id,
    ):
        failed.append("PROVIDER_NOT_EVALUATED")
    if staging.run_sha256 != m.run.record_sha256 or staging.corpus_sha256 != m.run.corpus_sha256:
        failed.append("STAGING_NOT_LINKED_TO_RUN")
    if not all(check.passed for check in check_frozen_thresholds(m.run.assisted, m.approval.thresholds)):
        failed.append("THRESHOLDS_NOT_MET")
    return tuple(failed)


def _guard_pin(m: EnablementMachine, ev: EnablementEvent) -> tuple[str, ...]:
    receipt = ev.receipt
    if m.staging is None:
        return ("STAGING_ENABLEMENT_MISSING",)
    if receipt is None:
        return ("RECEIPT_MISSING",)
    if m.corpus is None or m.run is None or m.proposal is None or m.approval is None:
        return ("CHAIN_RECORD_MISSING",)
    failed: list[str] = []
    if not verify_enablement_receipt(receipt):
        failed.append("RECEIPT_SHA_MISMATCH")
    if not is_pinned_sha(receipt.source_commit_sha):
        failed.append("SOURCE_SHA_NOT_PINNED")
    expected = (
        (receipt.corpus_sha256, m.corpus.corpus_sha256),
        (receipt.corpus_record_sha256, m.corpus.record_sha256),
        (receipt.harness_sha, m.run.harness_sha),
        (receipt.run_sha256, m.run.record_sha256),
        (receipt.proposal_sha256, m.proposal.record_sha256),
        (receipt.approval_sha256, m.approval.record_sha256),
        (receipt.staging_enablement_sha256, m.staging.record_sha256),
    )
    if any(actual != wanted for actual, wanted in expected):
        failed.append("RECEIPT_NOT_LINKED_TO_CHAIN")
    # Content must equal the receipt rebuilt from the machine's own artifacts.
    try:
        rebuilt = pin_receipt(
            corpus=m.corpus,
            run=m.run,
            proposal=m.proposal,
            approval=m.approval,
            staging=m.staging,
            source_commit_sha=receipt.source_commit_sha,
        )
    except EnablementError as exc:
        failed.append(f"RECEIPT_CHAIN_INVALID:{exc.code}")
    else:
        if rebuilt.as_payload() != receipt.as_payload():
            failed.append("RECEIPT_CONTENT_MISMATCH")
    return tuple(failed)


_GUARDS = MappingProxyType(
    {
        EnablementEventType.PROMOTE_CASES: _guard_promote,
        EnablementEventType.RUN_BASELINE: _guard_run,
        EnablementEventType.PROPOSE_THRESHOLDS: _guard_propose,
        EnablementEventType.OPERATOR_APPROVE: _guard_approve,
        EnablementEventType.ENABLE_STAGING: _guard_enable,
        EnablementEventType.PIN_RECEIPT: _guard_pin,
    }
)

_ARTIFACT_FIELD = MappingProxyType(
    {
        EnablementEventType.PROMOTE_CASES: "corpus",
        EnablementEventType.RUN_BASELINE: "run",
        EnablementEventType.PROPOSE_THRESHOLDS: "proposal",
        EnablementEventType.OPERATOR_APPROVE: "approval",
        EnablementEventType.ENABLE_STAGING: "staging",
        EnablementEventType.PIN_RECEIPT: "receipt",
    }
)


def _record(
    m: EnablementMachine, ev: EnablementEvent, to_state: EnablementState, accepted: bool, reasons: tuple[str, ...]
) -> tuple[EnablementTransition, ...]:
    return m.history + (EnablementTransition(m.state, ev.type, to_state, accepted, reasons),)


def transition(machine: EnablementMachine, event: EnablementEvent) -> EnablementMachine:
    """Apply one event. Rejections are recorded and leave state unchanged."""
    target = TRANSITIONS.get((machine.state, event.type))
    if target is None:
        reason = "RECEIPT_PINNED_IMMUTABLE" if machine.state is EnablementState.RECEIPT_PINNED else "INVALID_TRANSITION"
        return replace(machine, history=_record(machine, event, machine.state, False, (reason,)))
    failed = _GUARDS[event.type](machine, event)
    if failed:
        return replace(machine, history=_record(machine, event, machine.state, False, failed))
    artifact = getattr(event, _ARTIFACT_FIELD[event.type])
    return replace(
        machine,
        state=target,
        history=_record(machine, event, target, True, ()),
        **{_ARTIFACT_FIELD[event.type]: artifact},
    )


def replay(events: Iterable[EnablementEvent]) -> EnablementMachine:
    machine = new_machine()
    for event in events:
        machine = transition(machine, event)
    return machine
