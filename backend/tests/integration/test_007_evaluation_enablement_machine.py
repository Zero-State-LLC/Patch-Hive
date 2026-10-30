"""Spec 007 T070: evaluation & enablement state machine and gate checks.

Acceptance: no path reaches STAGING_ENABLED without OPERATOR_APPROVED; fail-closed
on missing corpus or unapproved thresholds. Synthetic in-test data only.
"""

from __future__ import annotations

import itertools

import pytest

from core.config import Settings
from core.ops.edge_readiness import (
    ReadinessEvent,
    ReadinessEvidence,
    ReadinessState,
    readiness_transition,
)
from intelligence.enablement_machine import (
    ENABLEMENT_ORDER,
    TRANSITIONS,
    EnablementEvent,
    EnablementEventType,
    EnablementState,
    new_machine,
    replay,
    staging_enabled,
    transition,
)
from intelligence.evaluation_corpus import freeze_corpus
from intelligence.evaluation_enablement import (
    StagingEnablement,
    approve_thresholds,
    enable_staging,
    pin_receipt,
    propose_thresholds,
    run_baseline_comparison,
)
from tests.eval007_helpers import (
    APPROVED_AT,
    HARNESS_SHA,
    POLICY,
    SOURCE_SHA,
    admitted_manifest,
    assisted_cases,
    baseline_cases,
    staging_settings,
)

E = EnablementEventType


def _artifacts(*, degrade: bool = False) -> dict:
    manifest = admitted_manifest()
    corpus = freeze_corpus(manifest)
    run = run_baseline_comparison(
        corpus=corpus,
        baseline_cases=baseline_cases(manifest),
        assisted_cases=assisted_cases(manifest, degrade=degrade),
        policy=POLICY,
        harness_sha=HARNESS_SHA,
        baseline_provider_id="fixture",
        assisted_provider_id="clef",
    )
    proposal = propose_thresholds(run, proposal_version="thresholds-v1")
    approval = approve_thresholds(
        proposal, approved_by="operator-1", approved_at=APPROVED_AT, explicit_sign_off=True
    )
    out = {"corpus": corpus, "run": run, "proposal": proposal, "approval": approval}
    if not degrade:
        staging = enable_staging(
            approval=approval, run=run, settings_obj=staging_settings(), target_environment="staging"
        )
        out["staging"] = staging
        out["receipt"] = pin_receipt(
            corpus=corpus, run=run, proposal=proposal, approval=approval, staging=staging,
            source_commit_sha=SOURCE_SHA,
        )
    return out


@pytest.fixture(scope="module")
def art() -> dict:
    return _artifacts()


def _events(a: dict) -> list[EnablementEvent]:
    return [
        EnablementEvent(E.PROMOTE_CASES, corpus=a["corpus"]),
        EnablementEvent(E.RUN_BASELINE, run=a["run"]),
        EnablementEvent(E.PROPOSE_THRESHOLDS, proposal=a["proposal"]),
        EnablementEvent(E.OPERATOR_APPROVE, approval=a["approval"]),
        EnablementEvent(E.ENABLE_STAGING, staging=a["staging"]),
        EnablementEvent(E.PIN_RECEIPT, receipt=a["receipt"]),
    ]


def _last_reasons(machine) -> tuple[str, ...]:
    return machine.history[-1].reasons


def test_happy_path_reaches_receipt_pinned(art) -> None:
    machine = new_machine()
    assert machine.state is EnablementState.CORPUS_DRAFT
    visited = [machine.state]
    for event in _events(art):
        machine = transition(machine, event)
        assert machine.history[-1].accepted, machine.history[-1]
        visited.append(machine.state)
    assert tuple(visited) == ENABLEMENT_ORDER
    assert machine.state is EnablementState.RECEIPT_PINNED
    assert staging_enabled(machine)
    assert machine.receipt is not None and machine.receipt.approval_sha256 == art["approval"].record_sha256


def test_transition_table_is_linear_and_only_approval_precedes_staging() -> None:
    sources = [src for (src, _), dst in TRANSITIONS.items() if dst is EnablementState.STAGING_ENABLED]
    assert sources == [EnablementState.OPERATOR_APPROVED]
    for index, state in enumerate(ENABLEMENT_ORDER[:-1]):
        outgoing = [dst for (src, _), dst in TRANSITIONS.items() if src is state]
        assert outgoing == [ENABLEMENT_ORDER[index + 1]]
    assert not [1 for (src, _) in TRANSITIONS if src is EnablementState.RECEIPT_PINNED]


def test_exhaustive_event_sequences_never_skip_approval(art) -> None:
    """Explore every event sequence up to length 7 over valid, missing, and forged
    artifacts (deduplicated by state + accepted-event prefix)."""
    valid = _events(art)
    missing = [EnablementEvent(event.type) for event in valid]
    forged_staging = StagingEnablement(
        providers=("clef",),
        approval_sha256="0" * 64,
        run_sha256=art["run"].record_sha256,
        corpus_sha256=art["corpus"].corpus_sha256,
        threshold_checks=(),
        config_checks=(),
    ).sealed()
    forged = [EnablementEvent(E.ENABLE_STAGING, staging=forged_staging)]
    alphabet = valid + missing + forged

    frontier = {(EnablementState.CORPUS_DRAFT, ()): new_machine()}
    seen: set[tuple] = set()
    reached_states: set[EnablementState] = set()
    for _ in range(7):
        next_frontier = {}
        for machine in frontier.values():
            for event in alphabet:
                after = transition(machine, event)
                accepted = tuple(r.event for r in after.history if r.accepted)
                key = (after.state, accepted)
                if key in seen:
                    continue
                seen.add(key)
                reached_states.add(after.state)
                for record in after.history:
                    if record.accepted and record.to_state is EnablementState.STAGING_ENABLED:
                        assert record.from_state is EnablementState.OPERATOR_APPROVED
                if after.state in {EnablementState.STAGING_ENABLED, EnablementState.RECEIPT_PINNED}:
                    assert E.OPERATOR_APPROVE in accepted
                    assert accepted.index(E.OPERATOR_APPROVE) < accepted.index(E.ENABLE_STAGING)
                    assert after.staging is art["staging"]
                next_frontier[key] = after
        frontier = next_frontier
    assert reached_states == set(EnablementState)


def test_all_permutations_of_valid_events_require_order(art) -> None:
    valid = _events(art)
    for perm in itertools.permutations(valid):
        machine = replay(perm)
        if machine.state is EnablementState.RECEIPT_PINNED:
            assert [e.type for e in perm] == [e.type for e in valid]
        if staging_enabled(machine):
            accepted = [r.event for r in machine.history if r.accepted]
            assert accepted.index(E.OPERATOR_APPROVE) < accepted.index(E.ENABLE_STAGING)


def test_skipping_approval_is_rejected(art) -> None:
    events = _events(art)
    machine = replay(events[:3])
    assert machine.state is EnablementState.THRESHOLDS_PROPOSED
    machine = transition(machine, events[4])
    assert machine.state is EnablementState.THRESHOLDS_PROPOSED
    assert _last_reasons(machine) == ("INVALID_TRANSITION",)
    assert not staging_enabled(machine)


def test_missing_corpus_fails_closed() -> None:
    machine = transition(new_machine(), EnablementEvent(E.PROMOTE_CASES))
    assert machine.state is EnablementState.CORPUS_DRAFT
    assert _last_reasons(machine) == ("CORPUS_MISSING",)
    machine = transition(new_machine(), EnablementEvent(E.RUN_BASELINE))
    assert machine.state is EnablementState.CORPUS_DRAFT
    assert _last_reasons(machine) == ("INVALID_TRANSITION",)


def test_tampered_corpus_is_rejected(art) -> None:
    tampered = art["corpus"].model_copy(update={"case_count": 1})
    machine = transition(new_machine(), EnablementEvent(E.PROMOTE_CASES, corpus=tampered))
    assert machine.state is EnablementState.CORPUS_DRAFT
    assert _last_reasons(machine) == ("CORPUS_NOT_ADMITTED_OR_TAMPERED",)


def test_run_on_other_corpus_is_rejected(art) -> None:
    manifest = admitted_manifest()
    manifest["pilot_version"] = "different-version"
    other = freeze_corpus(manifest)
    machine = replay([EnablementEvent(E.PROMOTE_CASES, corpus=other), EnablementEvent(E.RUN_BASELINE, run=art["run"])])
    assert machine.state is EnablementState.CORPUS_FROZEN
    assert "RUN_NOT_ON_FROZEN_CORPUS" in _last_reasons(machine)


def test_nonzero_false_canonicalization_blocks_run(art) -> None:
    bad_assisted = art["run"].assisted.model_copy(update={"false_canonicalization_count": 1})
    bad_run = art["run"].model_copy(update={"assisted": bad_assisted}).sealed()
    machine = replay([EnablementEvent(E.PROMOTE_CASES, corpus=art["corpus"]), EnablementEvent(E.RUN_BASELINE, run=bad_run)])
    assert machine.state is EnablementState.CORPUS_FROZEN
    assert "FALSE_CANONICALIZATION_NONZERO" in _last_reasons(machine)


def test_unpinned_harness_blocks_run(art) -> None:
    bad_run = art["run"].model_copy(update={"harness_sha": "main"}).sealed()
    machine = replay([EnablementEvent(E.PROMOTE_CASES, corpus=art["corpus"]), EnablementEvent(E.RUN_BASELINE, run=bad_run)])
    assert "HARNESS_SHA_NOT_PINNED" in _last_reasons(machine)


def test_unapproved_thresholds_fail_closed(art) -> None:
    events = _events(art)
    base = replay(events[:3])
    machine = transition(base, EnablementEvent(E.OPERATOR_APPROVE))
    assert machine.state is EnablementState.THRESHOLDS_PROPOSED
    assert _last_reasons(machine) == ("OPERATOR_APPROVAL_MISSING",)

    other_proposal = propose_thresholds(art["run"], proposal_version="thresholds-other")
    foreign = approve_thresholds(other_proposal, approved_by="op", approved_at=APPROVED_AT, explicit_sign_off=True)
    machine = transition(base, EnablementEvent(E.OPERATOR_APPROVE, approval=foreign))
    assert machine.state is EnablementState.THRESHOLDS_PROPOSED
    assert "APPROVAL_NOT_LINKED_TO_PROPOSAL" in _last_reasons(machine)

    widened = art["approval"].model_copy(
        update={"thresholds": art["approval"].thresholds.model_copy(update={"top1_min": 0.0})}
    ).sealed()
    machine = transition(base, EnablementEvent(E.OPERATOR_APPROVE, approval=widened))
    assert "APPROVED_THRESHOLDS_DIFFER_FROM_PROPOSAL" in _last_reasons(machine)

    tampered = art["approval"].model_copy(update={"approved_by": "someone-else"})
    machine = transition(base, EnablementEvent(E.OPERATOR_APPROVE, approval=tampered))
    assert "APPROVAL_TAMPERED" in _last_reasons(machine)


def test_enable_staging_rejects_missing_or_unlinked_or_failing(art) -> None:
    approved = replay(_events(art)[:4])
    assert approved.state is EnablementState.OPERATOR_APPROVED
    machine = transition(approved, EnablementEvent(E.ENABLE_STAGING))
    assert _last_reasons(machine) == ("STAGING_ENABLEMENT_MISSING",)

    unlinked = art["staging"].model_copy(update={"approval_sha256": "0" * 64}).sealed()
    machine = transition(approved, EnablementEvent(E.ENABLE_STAGING, staging=unlinked))
    assert machine.state is EnablementState.OPERATOR_APPROVED
    assert "STAGING_NOT_LINKED_TO_APPROVAL" in _last_reasons(machine)

    # Degraded provider approved on its own run: the guard re-checks thresholds.
    bad = _artifacts(degrade=True)
    approved_bad = replay(
        [
            EnablementEvent(E.PROMOTE_CASES, corpus=bad["corpus"]),
            EnablementEvent(E.RUN_BASELINE, run=bad["run"]),
            EnablementEvent(E.PROPOSE_THRESHOLDS, proposal=bad["proposal"]),
            EnablementEvent(E.OPERATOR_APPROVE, approval=bad["approval"]),
        ]
    )
    assert approved_bad.state is EnablementState.OPERATOR_APPROVED
    forged = StagingEnablement(
        providers=("clef",),
        approval_sha256=bad["approval"].record_sha256,
        run_sha256=bad["run"].record_sha256,
        corpus_sha256=bad["corpus"].corpus_sha256,
        threshold_checks=(),
        config_checks=(),
    ).sealed()
    machine = transition(approved_bad, EnablementEvent(E.ENABLE_STAGING, staging=forged))
    assert machine.state is EnablementState.OPERATOR_APPROVED
    assert "THRESHOLDS_NOT_MET" in _last_reasons(machine)


def test_pin_receipt_requires_linked_valid_receipt(art) -> None:
    staged = replay(_events(art)[:5])
    machine = transition(staged, EnablementEvent(E.PIN_RECEIPT))
    assert _last_reasons(machine) == ("RECEIPT_MISSING",)
    tampered = art["receipt"].model_copy(update={"source_commit_sha": "9" * 40})
    machine = transition(staged, EnablementEvent(E.PIN_RECEIPT, receipt=tampered))
    assert machine.state is EnablementState.STAGING_ENABLED
    assert "RECEIPT_SHA_MISMATCH" in _last_reasons(machine)


def test_receipt_pinned_is_immutable(art) -> None:
    machine = replay(_events(art))
    assert machine.state is EnablementState.RECEIPT_PINNED
    for event in _events(art):
        after = transition(machine, event)
        assert after.state is EnablementState.RECEIPT_PINNED
        assert after.receipt is machine.receipt
        assert _last_reasons(after) == ("RECEIPT_PINNED_IMMUTABLE",)


def test_flag_stays_default_off_and_no_payments_after_full_path(art) -> None:
    replay(_events(art))
    assert Settings.model_fields["enable_clef_provider"].default is False
    assert Settings.model_fields["allow_production_payments"].default is False
    fresh = Settings()
    assert fresh.enable_clef_provider is False
    assert fresh.allow_production_payments is False


def test_signed_pinned_receipt_satisfies_edge_readiness_gate(art, monkeypatch, tmp_path) -> None:
    from intelligence.receipt_signing import sign_receipt_sha256
    from tests.eval007_helpers import install_allowlist, throwaway_approver

    key, entry = throwaway_approver("operator-1")
    install_allowlist(monkeypatch, tmp_path, entry)
    receipt = art["receipt"]
    signature = sign_receipt_sha256(key, key_id="operator-1", receipt_sha256=receipt.receipt_sha256)
    evidence = ReadinessEvidence(
        payments_live_disabled=True,
        d1_absent=True,
        clef_flag_default_off=True,
        staging_host_plan_passed=True,
        evaluation_receipt_sha256=receipt.receipt_sha256,
        evaluation_receipt=receipt,
        evaluation_receipt_signature=signature,
    )
    result = readiness_transition(ReadinessState.CLEF_FLAGGED, ReadinessEvent.GATES_PASS, evidence)
    assert result.accepted, result.failed_checks
    assert result.to_state is ReadinessState.GATES_PASSED

    unsigned = ReadinessEvidence(
        payments_live_disabled=True,
        d1_absent=True,
        clef_flag_default_off=True,
        staging_host_plan_passed=True,
        evaluation_receipt_sha256=receipt.receipt_sha256,
        evaluation_receipt=receipt,
    )
    result = readiness_transition(ReadinessState.CLEF_FLAGGED, ReadinessEvent.GATES_PASS, unsigned)
    assert result.accepted is False
    assert "EVALUATION_RECEIPT_UNVERIFIED:RECEIPT_SIGNATURE_MISSING" in result.failed_checks


def _drive(a: dict, upto: int):
    machine = new_machine()
    for event in _events(a)[:upto]:
        machine = transition(machine, event)
        assert machine.history[-1].accepted, machine.history[-1]
    return machine


def test_resealed_approval_with_other_provider_is_rejected(art) -> None:
    forged = art["approval"].model_copy(update={"assisted_provider_id": "fixture"}).sealed()
    assert forged.intact()
    machine = _drive(art, 3)
    machine = transition(machine, EnablementEvent(E.OPERATOR_APPROVE, approval=forged))
    assert machine.state is EnablementState.THRESHOLDS_PROPOSED
    assert "PROVIDER_NOT_EVALUATED" in _last_reasons(machine)


def test_resealed_receipt_with_altered_content_is_rejected(art) -> None:
    receipt = art["receipt"].model_copy(update={"approved_by": "someone-else"})
    forged = receipt.model_copy(update={"receipt_sha256": receipt.computed_sha256()})
    machine = _drive(art, 5)
    machine = transition(machine, EnablementEvent(E.PIN_RECEIPT, receipt=forged))
    assert machine.state is EnablementState.STAGING_ENABLED
    assert "RECEIPT_CONTENT_MISMATCH" in _last_reasons(machine)


def test_pin_receipt_rejects_inconsistent_chain_content(art) -> None:
    from intelligence.evaluation_enablement import EnablementError

    staging = art["staging"].model_copy(update={"providers": ("fixture",)}).sealed()
    with pytest.raises(EnablementError) as exc:
        pin_receipt(
            corpus=art["corpus"], run=art["run"], proposal=art["proposal"],
            approval=art["approval"], staging=staging, source_commit_sha=SOURCE_SHA,
        )
    assert exc.value.code == "CHAIN_CONTENT_INCONSISTENT"
