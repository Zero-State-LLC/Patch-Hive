"""Pure guarded state machine for decision and evidence resolution.

Providers (including Clef) never mutate machine state directly: the adapter
only emits events, and this module owns every transition. Disposition values
originate from the Spec 005 DecisionPolicy and are applied here deterministically.
No canonical write is permitted before CONFIRMED. The machine itself performs
no canonical writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping

from intelligence.policy import DecisionDisposition


class ResolutionState(str, Enum):
    PENDING = "PENDING"
    CLASSIFYING = "CLASSIFYING"
    PACKET_EMITTED = "PACKET_EMITTED"
    POLICY_APPLIED = "POLICY_APPLIED"
    AUTO_PROPOSE = "AUTO_PROPOSE"
    USER_REVIEW = "USER_REVIEW"
    UNRESOLVED = "UNRESOLVED"
    ESCALATE = "ESCALATE"
    REJECT = "REJECT"
    CONFIRMED = "CONFIRMED"
    DEFERRED = "DEFERRED"
    ARCHIVED = "ARCHIVED"


class ResolutionEventType(str, Enum):
    SUBMIT_EVIDENCE = "submit_evidence"
    PROVIDER_SUCCESS = "provider_success"
    PROVIDER_FAIL = "provider_fail"
    PROVIDER_TIMEOUT = "timeout"
    APPLY_POLICY = "apply_policy"
    DISPOSITION = "disposition"
    USER_CONFIRM = "user_confirm"
    USER_DEFER = "user_defer"
    ARCHIVE = "archive"


@dataclass(frozen=True)
class ResolutionGuard:
    evidence_hash_valid: bool = False
    candidates_bounded: bool = False
    packet_schema_valid: bool = False
    policy_version_pinned: bool = False
    disposition: DecisionDisposition | None = None
    routing_target_exists: bool = False
    existing_confirmation_path: bool = False


@dataclass(frozen=True)
class ResolutionEvent:
    type: ResolutionEventType
    request_id: str
    guard: ResolutionGuard = field(default_factory=ResolutionGuard)

    def event_key(self) -> str:
        disposition = self.guard.disposition.value if self.guard.disposition else ""
        return f"{self.type.value}:{disposition}"


@dataclass(frozen=True)
class TransitionRecord:
    from_state: ResolutionState
    event: ResolutionEventType
    to_state: ResolutionState
    accepted: bool
    reason: str


@dataclass(frozen=True)
class ResolutionMachine:
    request_id: str
    state: ResolutionState
    history: tuple[TransitionRecord, ...]
    seen_event_keys: frozenset[str]


OUTCOME_STATES: frozenset[ResolutionState] = frozenset(
    {
        ResolutionState.AUTO_PROPOSE,
        ResolutionState.USER_REVIEW,
        ResolutionState.UNRESOLVED,
        ResolutionState.ESCALATE,
        ResolutionState.REJECT,
    }
)

TERMINAL_STATES: frozenset[ResolutionState] = frozenset(
    {
        ResolutionState.AUTO_PROPOSE,
        ResolutionState.USER_REVIEW,
        ResolutionState.UNRESOLVED,
        ResolutionState.ESCALATE,
        ResolutionState.REJECT,
        ResolutionState.CONFIRMED,
        ResolutionState.DEFERRED,
    }
)

FINAL_STATES: frozenset[ResolutionState] = TERMINAL_STATES | {ResolutionState.ARCHIVED}

_DISPOSITION_TO_STATE: Mapping[DecisionDisposition, ResolutionState] = MappingProxyType(
    {
        DecisionDisposition.AUTO_PROPOSE: ResolutionState.AUTO_PROPOSE,
        DecisionDisposition.USER_REVIEW: ResolutionState.USER_REVIEW,
        DecisionDisposition.UNRESOLVED: ResolutionState.UNRESOLVED,
        DecisionDisposition.ESCALATE: ResolutionState.ESCALATE,
        DecisionDisposition.REJECT: ResolutionState.REJECT,
    }
)

_STATE_EVENTS: Mapping[ResolutionState, frozenset[ResolutionEventType]] = MappingProxyType(
    {
        ResolutionState.PENDING: frozenset({ResolutionEventType.SUBMIT_EVIDENCE}),
        ResolutionState.CLASSIFYING: frozenset(
            {
                ResolutionEventType.PROVIDER_SUCCESS,
                ResolutionEventType.PROVIDER_FAIL,
                ResolutionEventType.PROVIDER_TIMEOUT,
            }
        ),
        ResolutionState.PACKET_EMITTED: frozenset({ResolutionEventType.APPLY_POLICY}),
        ResolutionState.POLICY_APPLIED: frozenset({ResolutionEventType.DISPOSITION}),
        ResolutionState.AUTO_PROPOSE: frozenset(
            {ResolutionEventType.USER_CONFIRM, ResolutionEventType.ARCHIVE}
        ),
        ResolutionState.USER_REVIEW: frozenset(
            {
                ResolutionEventType.USER_CONFIRM,
                ResolutionEventType.USER_DEFER,
                ResolutionEventType.ARCHIVE,
            }
        ),
        ResolutionState.UNRESOLVED: frozenset(
            {ResolutionEventType.USER_DEFER, ResolutionEventType.ARCHIVE}
        ),
        ResolutionState.ESCALATE: frozenset({ResolutionEventType.ARCHIVE}),
        ResolutionState.REJECT: frozenset({ResolutionEventType.ARCHIVE}),
        ResolutionState.CONFIRMED: frozenset({ResolutionEventType.ARCHIVE}),
        ResolutionState.DEFERRED: frozenset({ResolutionEventType.ARCHIVE}),
        ResolutionState.ARCHIVED: frozenset(),
    }
)

TRANSITIONS: Mapping[
    tuple[ResolutionState, ResolutionEventType], ResolutionState
] = MappingProxyType(
    {
        (ResolutionState.PENDING, ResolutionEventType.SUBMIT_EVIDENCE): ResolutionState.CLASSIFYING,
        (ResolutionState.CLASSIFYING, ResolutionEventType.PROVIDER_SUCCESS): ResolutionState.PACKET_EMITTED,
        # Nominal target only; with a routing target a provider failure escalates instead.
        (ResolutionState.CLASSIFYING, ResolutionEventType.PROVIDER_FAIL): ResolutionState.UNRESOLVED,
        (ResolutionState.CLASSIFYING, ResolutionEventType.PROVIDER_TIMEOUT): ResolutionState.UNRESOLVED,
        (ResolutionState.PACKET_EMITTED, ResolutionEventType.APPLY_POLICY): ResolutionState.POLICY_APPLIED,
        # Nominal target only; DISPOSITION resolves to a state determined by guard.disposition.
        (ResolutionState.POLICY_APPLIED, ResolutionEventType.DISPOSITION): ResolutionState.AUTO_PROPOSE,
        (ResolutionState.AUTO_PROPOSE, ResolutionEventType.USER_CONFIRM): ResolutionState.CONFIRMED,
        (ResolutionState.USER_REVIEW, ResolutionEventType.USER_CONFIRM): ResolutionState.CONFIRMED,
        (ResolutionState.USER_REVIEW, ResolutionEventType.USER_DEFER): ResolutionState.DEFERRED,
        (ResolutionState.UNRESOLVED, ResolutionEventType.USER_DEFER): ResolutionState.DEFERRED,
        (ResolutionState.AUTO_PROPOSE, ResolutionEventType.ARCHIVE): ResolutionState.ARCHIVED,
        (ResolutionState.USER_REVIEW, ResolutionEventType.ARCHIVE): ResolutionState.ARCHIVED,
        (ResolutionState.UNRESOLVED, ResolutionEventType.ARCHIVE): ResolutionState.ARCHIVED,
        (ResolutionState.ESCALATE, ResolutionEventType.ARCHIVE): ResolutionState.ARCHIVED,
        (ResolutionState.REJECT, ResolutionEventType.ARCHIVE): ResolutionState.ARCHIVED,
        (ResolutionState.CONFIRMED, ResolutionEventType.ARCHIVE): ResolutionState.ARCHIVED,
        (ResolutionState.DEFERRED, ResolutionEventType.ARCHIVE): ResolutionState.ARCHIVED,
    }
)


def new_machine(request_id: str) -> ResolutionMachine:
    if not request_id:
        raise ValueError("request_id must be non-empty")
    return ResolutionMachine(
        request_id=request_id,
        state=ResolutionState.PENDING,
        history=(),
        seen_event_keys=frozenset(),
    )


def is_final(machine: ResolutionMachine) -> bool:
    return machine.state in FINAL_STATES


def canon_write_permitted(machine: ResolutionMachine) -> bool:
    return machine.state is ResolutionState.CONFIRMED


def allowed_events(state: ResolutionState) -> frozenset[ResolutionEventType]:
    return _STATE_EVENTS[state]


def _append(
    machine: ResolutionMachine,
    event: ResolutionEvent,
    to_state: ResolutionState,
    accepted: bool,
    reason: str,
) -> ResolutionMachine:
    record = TransitionRecord(
        from_state=machine.state,
        event=event.type,
        to_state=to_state,
        accepted=accepted,
        reason=reason,
    )
    keys = machine.seen_event_keys
    if accepted:
        keys = keys | {event.event_key()}
    return ResolutionMachine(
        request_id=machine.request_id,
        state=to_state,
        history=machine.history + (record,),
        seen_event_keys=keys,
    )


def _reject(machine: ResolutionMachine, event: ResolutionEvent, reason: str) -> ResolutionMachine:
    return _append(machine, event, machine.state, False, reason)


def _accept(
    machine: ResolutionMachine,
    event: ResolutionEvent,
    to_state: ResolutionState,
    reason: str,
) -> ResolutionMachine:
    return _append(machine, event, to_state, True, reason)


def transition(machine: ResolutionMachine, event: ResolutionEvent) -> ResolutionMachine:
    if machine.state is ResolutionState.ARCHIVED:
        return _reject(machine, event, "ARCHIVED_IMMUTABLE")

    if event.request_id != machine.request_id:
        return _reject(machine, event, "REQUEST_ID_MISMATCH")

    if event.event_key() in machine.seen_event_keys:
        return machine

    state = machine.state

    if state is ResolutionState.PENDING and event.type is ResolutionEventType.SUBMIT_EVIDENCE:
        if not (event.guard.evidence_hash_valid and event.guard.candidates_bounded):
            return _reject(machine, event, "GUARD_EVIDENCE_INVALID")
        return _accept(machine, event, ResolutionState.CLASSIFYING, "SUBMIT_ACCEPTED")

    if state is ResolutionState.CLASSIFYING:
        if event.type is ResolutionEventType.PROVIDER_SUCCESS:
            if not event.guard.packet_schema_valid:
                # An unreadable packet is a provider failure, not a verdict on the evidence.
                target = (
                    ResolutionState.ESCALATE
                    if event.guard.routing_target_exists
                    else ResolutionState.UNRESOLVED
                )
                return _accept(machine, event, target, "PACKET_SCHEMA_INVALID")
            return _accept(machine, event, ResolutionState.PACKET_EMITTED, "PROVIDER_SUCCESS")
        if event.type in {ResolutionEventType.PROVIDER_FAIL, ResolutionEventType.PROVIDER_TIMEOUT}:
            # A provider that did not answer says nothing about the evidence (spec 005):
            # route it for review when there is somewhere to send it, else leave it open.
            target = (
                ResolutionState.ESCALATE
                if event.guard.routing_target_exists
                else ResolutionState.UNRESOLVED
            )
            return _accept(machine, event, target, event.type.name)

    if state is ResolutionState.PACKET_EMITTED and event.type is ResolutionEventType.APPLY_POLICY:
        if not event.guard.policy_version_pinned:
            return _reject(machine, event, "GUARD_POLICY_UNPINNED")
        return _accept(machine, event, ResolutionState.POLICY_APPLIED, "POLICY_APPLIED")

    if state is ResolutionState.POLICY_APPLIED and event.type is ResolutionEventType.DISPOSITION:
        disposition = event.guard.disposition
        if disposition is None:
            return _reject(machine, event, "GUARD_DISPOSITION_MISSING")
        target = _DISPOSITION_TO_STATE[disposition]
        if target is ResolutionState.ESCALATE and not event.guard.routing_target_exists:
            return _accept(machine, event, ResolutionState.UNRESOLVED, "ESCALATE_NO_ROUTING_TARGET")
        return _accept(machine, event, target, f"DISPOSITION_{disposition.value}")

    if event.type is ResolutionEventType.USER_CONFIRM and state in {
        ResolutionState.AUTO_PROPOSE,
        ResolutionState.USER_REVIEW,
    }:
        if not event.guard.existing_confirmation_path:
            return _reject(machine, event, "GUARD_CONFIRMATION_PATH_REQUIRED")
        return _accept(machine, event, ResolutionState.CONFIRMED, "USER_CONFIRMED")

    if event.type is ResolutionEventType.USER_DEFER and state in {
        ResolutionState.USER_REVIEW,
        ResolutionState.UNRESOLVED,
    }:
        return _accept(machine, event, ResolutionState.DEFERRED, "USER_DEFERRED")

    if event.type is ResolutionEventType.ARCHIVE and state in TERMINAL_STATES:
        return _accept(machine, event, ResolutionState.ARCHIVED, "ARCHIVED")

    return _reject(machine, event, "INVALID_TRANSITION")


def replay(request_id: str, events: Iterable[ResolutionEvent]) -> ResolutionMachine:
    machine = new_machine(request_id)
    for event in events:
        machine = transition(machine, event)
    return machine
