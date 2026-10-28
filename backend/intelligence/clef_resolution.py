"""Guarded provider-neutral evidence-resolution flow.

A DecisionProvider (Clef or any other adapter) never leaves the CLASSIFYING
stage as anything but an event: the T010 ResolutionMachine owns every
transition. Disposition is owned exclusively by the Spec 005 DecisionPolicy.
No raw image bytes or secrets enter DecisionPacket or receipts. No canon write
is permitted before CONFIRMED, and this flow never reaches CONFIRMED on its
own - only the existing Spec 005 confirmation path may drive that transition.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from sqlalchemy.orm import Session

from intelligence.clef_telemetry import (
    ResolutionTelemetry,
    emit,
    telemetry_for_policy_result,
    telemetry_for_provider_failure,
)
from intelligence.contracts import DecisionPacket
from intelligence.evidence_resolution import (
    DecisionIntelligenceDisabled,
    EvidenceResolutionError,
    load_identity_inputs,
)
from intelligence.module_service import DecisionProposal, ModuleDecisionService
from intelligence.persistence import persist_decision_proposal
from intelligence.policy import DecisionPolicy
from intelligence.provider import DecisionProvider
from intelligence.resolution_machine import (
    ResolutionEvent,
    ResolutionEventType,
    ResolutionGuard,
    ResolutionMachine,
    ResolutionState,
    new_machine,
    transition,
)

__all__ = [
    "GuardedResolution",
    "PolicyVersionNotPinned",
    "MAX_BOUNDED_CANDIDATES",
    "resolve_module_identity_guarded",
    "confirm_via_existing_path",
    "archive",
]

# + none_of_above = 255, the Clef / System One choice-count ceiling.
MAX_BOUNDED_CANDIDATES = 254

_STABLE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


class PolicyVersionNotPinned(EvidenceResolutionError):
    """Raised when the active policy version is not the operator-pinned version."""


@dataclass(frozen=True)
class GuardedResolution:
    machine: ResolutionMachine
    proposal: DecisionProposal | None
    receipt_id: str | None
    error_code: str | None
    telemetry: ResolutionTelemetry

    @property
    def state(self) -> ResolutionState:
        return self.machine.state

    @property
    def canonical_authority(self) -> bool:
        return False


def _provider_name(provider: DecisionProvider) -> str:
    name = getattr(provider, "provider_name", None)
    if isinstance(name, str) and name:
        return name
    type_name = type(provider).__name__
    if type_name.startswith("Clef"):
        return "clef"
    return type_name


def _provider_version(provider: DecisionProvider) -> str:
    version = getattr(provider, "provider_version", "unknown")
    return version if isinstance(version, str) else "unknown"


def _stable_code(exc: BaseException) -> str:
    text = str(exc)
    return text if _STABLE_CODE.match(text) else "PROVIDER_ERROR"


def _adapter_state_value(exc: BaseException) -> str | None:
    state = getattr(exc, "state", None)
    if isinstance(state, Enum):
        return str(state.value)
    return None


def _elapsed_ms(clock: Callable[[], float], started: float) -> int:
    return max(0, int(round((clock() - started) * 1000)))


def _transition(
    machine: ResolutionMachine,
    *,
    request_id: str,
    event_type: ResolutionEventType,
    guard: ResolutionGuard | None = None,
) -> ResolutionMachine:
    return transition(
        machine,
        ResolutionEvent(
            type=event_type,
            request_id=request_id,
            guard=guard if guard is not None else ResolutionGuard(),
        ),
    )


def _provider_failure_result(
    machine: ResolutionMachine,
    *,
    code: str,
    provider: DecisionProvider,
    adapter_state: str | None,
    latency_ms: int | None,
    logger: logging.Logger | None,
) -> GuardedResolution:
    telemetry = telemetry_for_provider_failure(
        provider=_provider_name(provider),
        provider_version=_provider_version(provider),
        error_code=code,
        adapter_state=adapter_state,
        resolution_state=machine.state.value,
        latency_ms=latency_ms,
    )
    emit(telemetry, logger)
    return GuardedResolution(
        machine=machine,
        proposal=None,
        receipt_id=None,
        error_code=code,
        telemetry=telemetry,
    )


def _packet_schema_valid(packet: DecisionPacket, request: Any) -> bool:
    try:
        DecisionPacket.model_validate(packet.model_dump())
    except Exception:
        return False
    allowed = {choice.choice_id for choice in request.choices}
    if packet.request_id != request.request_id:
        return False
    if packet.evidence_hash != request.evidence_hash:
        return False
    if packet.answer_type != "choice":
        return False
    if packet.candidate_set_hash != request.candidate_set_hash():
        return False
    if packet.selected_choice not in allowed:
        return False
    if any(key not in allowed for key in packet.probabilities):
        return False
    return True


def resolve_module_identity_guarded(
    db: Session,
    *,
    evidence_id: str,
    provider: DecisionProvider,
    policy: DecisionPolicy,
    enabled: bool,
    idempotency_key: str,
    expected_policy_version: str,
    routing_targets: frozenset[str] = frozenset(),
    clock: Callable[[], float] = time.monotonic,
    logger: logging.Logger | None = None,
) -> GuardedResolution:
    if not enabled:
        raise DecisionIntelligenceDisabled("Decision Intelligence is disabled")

    if policy.thresholds.policy_version != expected_policy_version:
        raise PolicyVersionNotPinned("POLICY_VERSION_NOT_PINNED")

    inputs = load_identity_inputs(db, evidence_id=evidence_id)
    request_id = inputs.request_id
    machine = new_machine(request_id)

    machine = _transition(
        machine,
        request_id=request_id,
        event_type=ResolutionEventType.SUBMIT_EVIDENCE,
        guard=ResolutionGuard(
            evidence_hash_valid=bool(evidence_id),
            candidates_bounded=1 <= len(inputs.candidates) <= MAX_BOUNDED_CANDIDATES,
        ),
    )
    if machine.state is not ResolutionState.CLASSIFYING:
        raise EvidenceResolutionError("evidence guard rejected")

    request = ModuleDecisionService.build_identity_request(
        request_id=request_id,
        evidence_hash=evidence_id,
        evidence_refs=inputs.evidence_refs,
        normalized_evidence=inputs.normalized_evidence,
        candidates=inputs.candidates,
        idempotency_key=idempotency_key,
    )

    # A failed provider escalates when there is a review route, else stays unresolved.
    failure_guard = ResolutionGuard(routing_target_exists=bool(routing_targets))
    started = clock()
    try:
        packet = provider.choose(request)
    except Exception as exc:
        latency_ms = _elapsed_ms(clock, started)
        code = _stable_code(exc)
        event_type = (
            ResolutionEventType.PROVIDER_TIMEOUT
            if "TIMEOUT" in code
            else ResolutionEventType.PROVIDER_FAIL
        )
        machine = _transition(
            machine, request_id=request_id, event_type=event_type, guard=failure_guard
        )
        return _provider_failure_result(
            machine,
            code=code,
            provider=provider,
            adapter_state=_adapter_state_value(exc),
            latency_ms=latency_ms,
            logger=logger,
        )

    latency_ms = _elapsed_ms(clock, started)

    if not isinstance(packet, DecisionPacket):
        machine = _transition(
            machine,
            request_id=request_id,
            event_type=ResolutionEventType.PROVIDER_FAIL,
            guard=failure_guard,
        )
        return _provider_failure_result(
            machine,
            code="PROVIDER_MALFORMED",
            provider=provider,
            adapter_state=None,
            latency_ms=latency_ms,
            logger=logger,
        )

    if packet.provider_status != "succeeded":
        timed_out = packet.provider_status == "timed_out"
        fallback = "PROVIDER_TIMED_OUT" if timed_out else "PROVIDER_FAILED"
        raw_code = packet.error_code or ""
        code = raw_code if _STABLE_CODE.match(raw_code) else fallback
        event_type = (
            ResolutionEventType.PROVIDER_TIMEOUT
            if timed_out
            else ResolutionEventType.PROVIDER_FAIL
        )
        machine = _transition(
            machine, request_id=request_id, event_type=event_type, guard=failure_guard
        )
        return _provider_failure_result(
            machine,
            code=code,
            provider=provider,
            adapter_state=None,
            latency_ms=latency_ms,
            logger=logger,
        )

    machine = _transition(
        machine,
        request_id=request_id,
        event_type=ResolutionEventType.PROVIDER_SUCCESS,
        guard=ResolutionGuard(packet_schema_valid=_packet_schema_valid(packet, request)),
    )
    if machine.state is not ResolutionState.PACKET_EMITTED:
        return _provider_failure_result(
            machine,
            code="PACKET_SCHEMA_INVALID",
            provider=provider,
            adapter_state=None,
            latency_ms=latency_ms,
            logger=logger,
        )

    policy_pinned = policy.thresholds.policy_version == expected_policy_version
    machine = _transition(
        machine,
        request_id=request_id,
        event_type=ResolutionEventType.APPLY_POLICY,
        guard=ResolutionGuard(policy_version_pinned=policy_pinned),
    )
    if machine.state is not ResolutionState.POLICY_APPLIED:
        raise EvidenceResolutionError("policy application guard rejected")

    result = policy.evaluate(packet, request)
    proposal = DecisionProposal(request=request, packet=packet, policy=result)

    machine = _transition(
        machine,
        request_id=request_id,
        event_type=ResolutionEventType.DISPOSITION,
        guard=ResolutionGuard(
            disposition=result.disposition,
            routing_target_exists=bool(routing_targets),
        ),
    )

    record = persist_decision_proposal(db, proposal)
    receipt_id = record.id

    telemetry = telemetry_for_policy_result(
        packet=packet,
        result=result,
        resolution_state=machine.state.value,
        latency_ms=latency_ms,
    )
    emit(telemetry, logger)
    return GuardedResolution(
        machine=machine,
        proposal=proposal,
        receipt_id=receipt_id,
        error_code=None,
        telemetry=telemetry,
    )


def confirm_via_existing_path(
    resolution: GuardedResolution, *, confirmation_path_used: bool
) -> ResolutionMachine:
    """Pure transition helper for the Spec 005 confirmation path.

    Returns a new machine; this function writes no canon and persists nothing.
    The existing Spec 005 confirmation UI/API remains the only canon writer.
    """
    event = ResolutionEvent(
        type=ResolutionEventType.USER_CONFIRM,
        request_id=resolution.machine.request_id,
        guard=ResolutionGuard(existing_confirmation_path=confirmation_path_used),
    )
    return transition(resolution.machine, event)


def archive(resolution: GuardedResolution) -> ResolutionMachine:
    """Pure archive transition from a terminal state. Performs no canonical write."""
    event = ResolutionEvent(
        type=ResolutionEventType.ARCHIVE,
        request_id=resolution.machine.request_id,
    )
    return transition(resolution.machine, event)
