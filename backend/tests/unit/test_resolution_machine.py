import dataclasses

import pytest

from intelligence.policy import DecisionDisposition
from intelligence.resolution_machine import (
    FINAL_STATES,
    OUTCOME_STATES,
    TRANSITIONS,
    ResolutionEvent,
    ResolutionEventType,
    ResolutionGuard,
    ResolutionState,
    canon_write_permitted,
    new_machine,
    transition,
)


def _machine(state: ResolutionState, request_id: str = "req") -> object:
    return dataclasses.replace(new_machine(request_id), state=state)


def _event(
    event_type: ResolutionEventType,
    guard: ResolutionGuard | None = None,
    request_id: str = "req",
) -> ResolutionEvent:
    return ResolutionEvent(
        type=event_type,
        request_id=request_id,
        guard=guard if guard is not None else ResolutionGuard(),
    )


def _satisfying_guard(event_type: ResolutionEventType) -> ResolutionGuard:
    if event_type is ResolutionEventType.SUBMIT_EVIDENCE:
        return ResolutionGuard(evidence_hash_valid=True, candidates_bounded=True)
    if event_type is ResolutionEventType.PROVIDER_SUCCESS:
        return ResolutionGuard(packet_schema_valid=True)
    if event_type is ResolutionEventType.APPLY_POLICY:
        return ResolutionGuard(policy_version_pinned=True)
    if event_type is ResolutionEventType.DISPOSITION:
        return ResolutionGuard(disposition=DecisionDisposition.AUTO_PROPOSE)
    if event_type is ResolutionEventType.USER_CONFIRM:
        return ResolutionGuard(existing_confirmation_path=True)
    return ResolutionGuard()


def _event_variants() -> tuple[ResolutionEvent, ...]:
    variants: list[ResolutionEvent] = []
    for event_type in ResolutionEventType:
        guards: list[ResolutionGuard]
        if event_type is ResolutionEventType.SUBMIT_EVIDENCE:
            guards = [
                ResolutionGuard(evidence_hash_valid=True, candidates_bounded=True),
                ResolutionGuard(evidence_hash_valid=False, candidates_bounded=True),
                ResolutionGuard(evidence_hash_valid=True, candidates_bounded=False),
            ]
        elif event_type is ResolutionEventType.PROVIDER_SUCCESS:
            guards = [
                ResolutionGuard(packet_schema_valid=True),
                ResolutionGuard(packet_schema_valid=False),
            ]
        elif event_type is ResolutionEventType.APPLY_POLICY:
            guards = [
                ResolutionGuard(policy_version_pinned=True),
                ResolutionGuard(policy_version_pinned=False),
            ]
        elif event_type is ResolutionEventType.DISPOSITION:
            guards = [
                ResolutionGuard(disposition=disposition, routing_target_exists=routing)
                for disposition in DecisionDisposition
                for routing in (True, False)
            ]
            guards.append(ResolutionGuard())
        elif event_type is ResolutionEventType.USER_CONFIRM:
            guards = [
                ResolutionGuard(existing_confirmation_path=True),
                ResolutionGuard(existing_confirmation_path=False),
            ]
        else:
            guards = [ResolutionGuard()]
        for guard in guards:
            variants.append(_event(event_type, guard))
    return tuple(variants)


def _reachable_states(max_depth: int = 8) -> set[ResolutionState]:
    variants = _event_variants()
    reachable = {ResolutionState.PENDING}
    frontier = {ResolutionState.PENDING}
    for _ in range(max_depth):
        next_frontier: set[ResolutionState] = set()
        for state in frontier:
            machine = _machine(state)
            for event in variants:
                after = transition(machine, event)
                if after.state not in reachable:
                    reachable.add(after.state)
                    next_frontier.add(after.state)
        frontier = next_frontier
    return reachable


def _can_reach_archive(start: ResolutionState, max_depth: int = 8) -> bool:
    variants = _event_variants()
    seen = {start}
    frontier = {start}
    for _ in range(max_depth):
        if ResolutionState.ARCHIVED in frontier:
            return True
        next_frontier: set[ResolutionState] = set()
        for state in frontier:
            machine = _machine(state)
            for event in variants:
                after = transition(machine, event)
                if after.state is state or after.state in seen:
                    continue
                seen.add(after.state)
                next_frontier.add(after.state)
        frontier = next_frontier
    return ResolutionState.ARCHIVED in seen


def test_every_transition_table_row_accepts_its_expected_target() -> None:
    for (from_state, event_type), expected in TRANSITIONS.items():
        machine = _machine(from_state)
        event = _event(event_type, _satisfying_guard(event_type))
        after = transition(machine, event)
        record = after.history[-1]
        assert record.accepted, (from_state, event_type, record.reason)
        assert after.state is expected, (from_state, event_type, after.state)


def test_bfs_reachable_paths_are_final_or_can_reach_archive() -> None:
    reachable = _reachable_states(max_depth=8)
    assert OUTCOME_STATES <= reachable
    for state in reachable:
        if state not in FINAL_STATES:
            assert _can_reach_archive(state), state
    for state in reachable:
        if state is not ResolutionState.ARCHIVED:
            assert _can_reach_archive(state), state


def test_canon_write_permitted_only_at_confirmed() -> None:
    for state in ResolutionState:
        assert canon_write_permitted(_machine(state)) is (state is ResolutionState.CONFIRMED)


def test_provider_fail_and_timeout_go_unresolved_or_escalate() -> None:
    """Spec 005: a provider that did not answer says nothing about the evidence, so it
    is never a rejection. It escalates when there is a review route, else stays open."""
    for event_type in (
        ResolutionEventType.PROVIDER_FAIL,
        ResolutionEventType.PROVIDER_TIMEOUT,
    ):
        after = transition(_machine(ResolutionState.CLASSIFYING), _event(event_type))
        assert after.state is ResolutionState.UNRESOLVED
        assert after.history[-1].accepted
        assert after.history[-1].reason == event_type.name

        routed = transition(
            _machine(ResolutionState.CLASSIFYING),
            _event(event_type, ResolutionGuard(routing_target_exists=True)),
        )
        assert routed.state is ResolutionState.ESCALATE
        assert canon_write_permitted(after) is canon_write_permitted(routed) is False


def test_provider_success_with_invalid_packet_fails_closed() -> None:
    event = _event(
        ResolutionEventType.PROVIDER_SUCCESS,
        ResolutionGuard(packet_schema_valid=False),
    )
    after = transition(_machine(ResolutionState.CLASSIFYING), event)
    assert after.state is ResolutionState.REJECT
    assert after.history[-1].reason == "PACKET_SCHEMA_INVALID"


def test_escalation_without_routing_target_goes_unresolved() -> None:
    event = _event(
        ResolutionEventType.DISPOSITION,
        ResolutionGuard(
            disposition=DecisionDisposition.ESCALATE,
            routing_target_exists=False,
        ),
    )
    after = transition(_machine(ResolutionState.POLICY_APPLIED), event)
    assert after.state is ResolutionState.UNRESOLVED
    assert after.history[-1].reason == "ESCALATE_NO_ROUTING_TARGET"

    event_with_target = _event(
        ResolutionEventType.DISPOSITION,
        ResolutionGuard(
            disposition=DecisionDisposition.ESCALATE,
            routing_target_exists=True,
        ),
    )
    after_with_target = transition(
        _machine(ResolutionState.POLICY_APPLIED),
        event_with_target,
    )
    assert after_with_target.state is ResolutionState.ESCALATE


def test_identical_event_replay_is_idempotent() -> None:
    event = _event(
        ResolutionEventType.SUBMIT_EVIDENCE,
        ResolutionGuard(evidence_hash_valid=True, candidates_bounded=True),
    )
    first = transition(new_machine("req"), event)
    second = transition(first, event)
    assert second is first


def test_request_id_mismatch_is_rejected() -> None:
    event = _event(
        ResolutionEventType.SUBMIT_EVIDENCE,
        ResolutionGuard(evidence_hash_valid=True, candidates_bounded=True),
        request_id="other",
    )
    after = transition(new_machine("req"), event)
    assert not after.history[-1].accepted
    assert after.history[-1].reason == "REQUEST_ID_MISMATCH"
    assert after.state is ResolutionState.PENDING


def test_archived_state_is_immutable_for_every_event_type() -> None:
    machine = _machine(ResolutionState.ARCHIVED)
    for event_type in ResolutionEventType:
        after = transition(machine, _event(event_type))
        assert not after.history[-1].accepted
        assert after.history[-1].reason == "ARCHIVED_IMMUTABLE"
        assert after.state is ResolutionState.ARCHIVED


def test_transition_is_pure_and_does_not_mutate_input_machine() -> None:
    machine = new_machine("req")
    before = dataclasses.replace(machine)
    event = _event(
        ResolutionEventType.SUBMIT_EVIDENCE,
        ResolutionGuard(evidence_hash_valid=True, candidates_bounded=True),
    )
    after = transition(machine, event)
    assert machine == before
    assert machine.history == ()
    assert after is not machine
    assert len(after.history) == 1


def test_user_confirm_without_confirmation_path_is_rejected() -> None:
    after = transition(
        _machine(ResolutionState.AUTO_PROPOSE),
        _event(ResolutionEventType.USER_CONFIRM),
    )
    assert not after.history[-1].accepted
    assert after.history[-1].reason == "GUARD_CONFIRMATION_PATH_REQUIRED"
    assert after.state is ResolutionState.AUTO_PROPOSE


def test_transition_mapping_is_read_only() -> None:
    with pytest.raises(TypeError):
        TRANSITIONS[
            (ResolutionState.PENDING, ResolutionEventType.SUBMIT_EVIDENCE)
        ] = ResolutionState.CLASSIFYING


def test_new_machine_requires_non_empty_request_id() -> None:
    with pytest.raises(ValueError):
        new_machine("")
