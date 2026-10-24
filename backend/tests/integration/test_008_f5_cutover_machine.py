"""Spec 008 T060: dual-path F5 cutover state machine.

INVENTORY_LEGACY -> F5_ALIAS_LIVE -> FE_CUTOVER -> WALKTHROUGH_PENDING
    -> RECEIPT_CAPTURED -> BETA_ELIGIBLE

Acceptance: no path reaches BETA_ELIGIBLE without the walkthrough receipt;
production payments stay disabled. Synthetic in-test data only.
"""

from __future__ import annotations

import itertools
from collections import deque

import pytest

from core.config import Settings
from core.ops.f5_cutover import (
    CUTOVER_ORDER,
    TRANSITIONS,
    CutoverEvent,
    CutoverEventType,
    CutoverState,
    WalkthroughReceipt,
    WalkthroughStart,
    beta_eligible,
    collect_alias_evidence,
    collect_fe_cutover_evidence,
    new_machine,
    replay,
    transition,
)
from tests.f5008_helpers import (
    GOOD_GENERATE,
    chain,
    enablement_receipt,
    flags,
    full_routes,
    outcome,
)

E = CutoverEventType
S = CutoverState


@pytest.fixture(scope="module")
def enablement():
    return enablement_receipt()


@pytest.fixture(scope="module")
def art(enablement):
    return chain(enablement)


@pytest.fixture(scope="module")
def other(enablement):
    """A second, fully valid chain over a different rig set (for link checks)."""
    from core.ops.f5_cutover import (
        capture_walkthrough_receipt,
        pin_readiness_docs,
        start_walkthrough,
    )
    from tests.f5008_helpers import (
        FE_SOURCES_OK,
        WALKTHROUGH_SHA,
        docs,
        health,
        seed_auth,
    )

    alias = collect_alias_evidence(full_routes(), legacy_ids=(4, 5), canon_ids=(4, 5))
    fe = collect_fe_cutover_evidence(alias, full_routes(), fe_sources=FE_SOURCES_OK, generate_response=GOOD_GENERATE)
    start = start_walkthrough(fe, flags())
    receipt = capture_walkthrough_receipt(
        start=start, seed_auth=seed_auth(), health=health(), outcome=outcome(), source_commit_sha=WALKTHROUGH_SHA
    )
    pin = pin_readiness_docs(
        receipt=receipt, documents=docs(), unresolved_p0=(), enablement_receipt=enablement, pinned_by="op-2"
    )
    return {"alias": alias, "fe": fe, "start": start, "receipt": receipt, "pin": pin}


def _valid_events(a: dict) -> list[CutoverEvent]:
    return [
        CutoverEvent(E.EXPOSE_CANON_ALIAS, alias=a["alias"]),
        CutoverEvent(E.SWITCH_FE_LIST, fe_cutover=a["fe"]),
        CutoverEvent(E.RUN_WALKTHROUGH, start=a["start"]),
        CutoverEvent(E.CAPTURE_RECEIPT, receipt=a["receipt"]),
        CutoverEvent(E.OPERATOR_PIN, pin=a["pin"]),
    ]


def _forged_failed_receipt(a: dict) -> WalkthroughReceipt:
    """A receipt sealed by hand for a failed walkthrough (bypassing capture)."""
    payload = a["receipt"].model_dump()
    payload.update(
        outcome=outcome(failed_step="download_pack").model_dump(),
        outcome_passed=False,
        record_sha256="",
    )
    return WalkthroughReceipt(**payload).sealed()


def _last(machine) -> tuple[str, ...]:
    return machine.history[-1].reasons


def test_happy_path_reaches_beta_eligible(art) -> None:
    machine = replay(_valid_events(art))
    assert machine.state is S.BETA_ELIGIBLE
    assert beta_eligible(machine)
    assert [t.to_state for t in machine.history] == list(CUTOVER_ORDER[1:])
    assert all(t.accepted for t in machine.history)
    assert machine.receipt.production_payments_enabled is False
    assert machine.receipt.flags.allow_production_payments is False


def test_transition_table_is_linear() -> None:
    assert CUTOVER_ORDER == (
        S.INVENTORY_LEGACY, S.F5_ALIAS_LIVE, S.FE_CUTOVER,
        S.WALKTHROUGH_PENDING, S.RECEIPT_CAPTURED, S.BETA_ELIGIBLE,
    )
    assert len(TRANSITIONS) == len(CUTOVER_ORDER) - 1
    for (src, _event), dst in TRANSITIONS.items():
        assert CUTOVER_ORDER.index(dst) == CUTOVER_ORDER.index(src) + 1
    sources_into_beta = [src for (src, _), dst in TRANSITIONS.items() if dst is S.BETA_ELIGIBLE]
    assert sources_into_beta == [S.RECEIPT_CAPTURED]


def _alphabet(art: dict, other: dict) -> dict[str, CutoverEvent]:
    """Every event the exhaustive search may fire: valid, missing, forged, unlinked."""
    events = {f"valid:{e.type.value}": e for e in _valid_events(art)}
    for event_type in E:
        events[f"missing:{event_type.value}"] = CutoverEvent(event_type)
    for e in _valid_events(other):
        events[f"unlinked:{e.type.value}"] = e
    events["forged_failed_receipt"] = CutoverEvent(E.CAPTURE_RECEIPT, receipt=_forged_failed_receipt(art))
    events["tampered_receipt"] = CutoverEvent(
        E.CAPTURE_RECEIPT, receipt=art["receipt"].model_copy(update={"outcome_passed": True, "seed_auth_aligned": False})
    )
    prod_start = WalkthroughStart(
        fe_cutover_sha256=art["fe"].record_sha256, flags=flags(allow_production_payments=True)
    ).sealed()
    events["prod_payments_start"] = CutoverEvent(E.RUN_WALKTHROUGH, start=prod_start)
    return events


def _key(m) -> tuple:
    return (m.state, id(m.alias), id(m.fe_cutover), id(m.start), id(m.receipt), id(m.pin))


def _reachable(events: list[CutoverEvent]) -> list:
    """BFS over every machine configuration reachable by any event sequence."""
    start = new_machine()
    seen = {_key(start): start}
    queue = deque([start])
    while queue:
        machine = queue.popleft()
        for event in events:
            nxt = transition(machine, event)
            key = _key(nxt)
            if key not in seen:
                seen[key] = nxt
                queue.append(nxt)
    return list(seen.values())


def test_exhaustive_beta_eligible_unreachable_without_walkthrough_receipt(art, other) -> None:
    alphabet = _alphabet(art, other)
    # Drop every genuine captured walkthrough receipt (ours and the other valid chain's);
    # forged, tampered, failed, and missing receipts all stay in the alphabet.
    genuine = {"valid:capture_receipt", "unlinked:capture_receipt"}
    without_receipt = [e for name, e in alphabet.items() if name not in genuine]
    states = {m.state for m in _reachable(without_receipt)}
    assert S.BETA_ELIGIBLE not in states
    assert S.RECEIPT_CAPTURED not in states
    assert S.WALKTHROUGH_PENDING in states  # the search does get right up to the gate


def test_exhaustive_every_beta_eligible_path_captured_the_real_receipt(art, other) -> None:
    alphabet = _alphabet(art, other)
    reached = _reachable(list(alphabet.values()))
    betas = [m for m in reached if m.state is S.BETA_ELIGIBLE]
    assert betas, "happy path must be reachable"
    genuine = {id(art["receipt"]): art, id(other["receipt"]): other}
    for m in betas:
        owner = genuine[id(m.receipt)]  # only a genuine captured receipt gets here
        assert m.pin is owner["pin"]
        assert m.pin.walkthrough_receipt_sha256 == m.receipt.record_sha256
        assert beta_eligible(m)
        accepted = [t.event for t in m.history if t.accepted]
        assert accepted == [e.type for e in _valid_events(art)]
        assert not m.receipt.flags.allow_production_payments


def test_exhaustive_sequences_up_to_length_six(art, other) -> None:
    """Brute force over explicit sequences (prefix-shared DFS) to length 6."""
    alphabet = list(_alphabet(art, other).items())
    names_needed = [f"valid:{t.value}" for t in E]
    checked = 0

    def walk(machine, path: tuple[str, ...]) -> None:
        nonlocal checked
        checked += 1
        if machine.state is S.BETA_ELIGIBLE:
            accepted = [t.event for t in machine.history if t.accepted]
            assert accepted == [CutoverEventType(n.split(":", 1)[1]) for n in names_needed]
            assert machine.receipt is art["receipt"]
            assert "valid:capture_receipt" in path
        else:
            assert not beta_eligible(machine)
        if len(path) == 6:
            return
        for name, event in alphabet:
            walk(transition(machine, event), path + (name,))

    small = [(n, e) for n, e in alphabet if n.startswith("valid:") or n in {"forged_failed_receipt", "missing:capture_receipt"}]
    alphabet = small
    walk(new_machine(), ())
    assert checked == sum(len(small) ** k for k in range(7))


def test_all_permutations_of_valid_events_require_order(art) -> None:
    events = _valid_events(art)
    for perm in itertools.permutations(events):
        machine = replay(perm)
        if list(perm) == events:
            assert machine.state is S.BETA_ELIGIBLE
        else:
            assert machine.state is not S.BETA_ELIGIBLE


def test_pin_without_receipt_is_rejected(art) -> None:
    events = _valid_events(art)
    machine = replay(events[:3] + [events[4]])
    assert machine.state is S.WALKTHROUGH_PENDING
    assert _last(machine)[0].startswith("INVALID_TRANSITION")


@pytest.mark.parametrize("kind", ["missing", "forged_failed", "tampered", "unlinked"])
def test_capture_rejects_bad_receipts(art, other, kind) -> None:
    receipt = {
        "missing": None,
        "forged_failed": _forged_failed_receipt(art),
        "tampered": art["receipt"].model_copy(update={"seed_auth_aligned": False}),
        "unlinked": other["receipt"],
    }[kind]
    machine = replay(_valid_events(art)[:3] + [CutoverEvent(E.CAPTURE_RECEIPT, receipt=receipt)])
    assert machine.state is S.WALKTHROUGH_PENDING
    reasons = _last(machine)
    expected = {
        "missing": "WALKTHROUGH_RECEIPT_MISSING",
        "forged_failed": "WALKTHROUGH_FAILED",
        "tampered": "WALKTHROUGH_RECEIPT_TAMPERED",
        "unlinked": "RECEIPT_NOT_LINKED_TO_WALKTHROUGH",
    }[kind]
    assert expected in reasons


def _resealed_receipt(art, **updates) -> WalkthroughReceipt:
    payload = art["receipt"].model_dump()
    payload.update(updates, record_sha256="")
    return WalkthroughReceipt(**payload).sealed()


def test_capture_rejects_resealed_receipt_with_forged_seed_auth(art) -> None:
    from tests.f5008_helpers import seed_auth

    drifted = seed_auth(aligned=False)
    cases = {
        # receipt claims aligned but embeds a drifted seed check
        "embedded_not_aligned": _resealed_receipt(
            art, seed_auth=drifted.model_dump(), seed_auth_sha256=drifted.record_sha256
        ),
        # seed check edited to aligned without resealing it
        "embedded_tampered": _resealed_receipt(
            art, seed_auth={**drifted.model_dump(), "aligned": True}, seed_auth_sha256=drifted.record_sha256
        ),
        # seed check hash not linked
        "sha_unlinked": _resealed_receipt(art, seed_auth_sha256=""),
    }
    expected = {
        "embedded_not_aligned": "SEED_AUTH_NOT_ALIGNED",
        "embedded_tampered": "SEED_AUTH_TAMPERED",
        "sha_unlinked": "SEED_AUTH_TAMPERED",
    }
    for name, receipt in cases.items():
        machine = replay(_valid_events(art)[:3] + [CutoverEvent(E.CAPTURE_RECEIPT, receipt=receipt)])
        assert machine.state is S.WALKTHROUGH_PENDING, name
        assert expected[name] in _last(machine), name


def test_capture_rejects_resealed_receipt_with_failed_health(art) -> None:
    from tests.f5008_helpers import health

    receipt = _resealed_receipt(art, health=health(database="error").model_dump())
    machine = replay(_valid_events(art)[:3] + [CutoverEvent(E.CAPTURE_RECEIPT, receipt=receipt)])
    assert machine.state is S.WALKTHROUGH_PENDING
    assert "HEALTH_NOT_OK" in _last(machine)


def test_walkthrough_with_production_payments_is_rejected(art) -> None:
    prod_start = WalkthroughStart(
        fe_cutover_sha256=art["fe"].record_sha256, flags=flags(allow_production_payments=True)
    ).sealed()
    machine = replay(_valid_events(art)[:2] + [CutoverEvent(E.RUN_WALKTHROUGH, start=prod_start)])
    assert machine.state is S.FE_CUTOVER
    assert "PRODUCTION_PAYMENTS_ENABLED" in _last(machine)


def test_alias_and_fe_guards_fail_closed(art, other) -> None:
    drift = collect_alias_evidence(full_routes(), legacy_ids=(1, 2, 3), canon_ids=(1, 2))
    machine = replay([CutoverEvent(E.EXPOSE_CANON_ALIAS, alias=drift)])
    assert machine.state is S.INVENTORY_LEGACY
    assert "ALIAS_SET_DIFFERS_FROM_LEGACY" in _last(machine)

    new_write = collect_alias_evidence(
        full_routes() | {("PUT", "/api/canon/rigs/{rig_id}")}, legacy_ids=(1,), canon_ids=(1,)
    )
    assert "NEW_WRITE_SURFACE" in _last(replay([CutoverEvent(E.EXPOSE_CANON_ALIAS, alias=new_write)]))

    events = _valid_events(art)
    unlinked = replay(events[:1] + [CutoverEvent(E.SWITCH_FE_LIST, fe_cutover=other["fe"])])
    assert unlinked.state is S.F5_ALIAS_LIVE
    assert "FE_CUTOVER_NOT_LINKED_TO_ALIAS" in _last(unlinked)

    legacy_fe = collect_fe_cutover_evidence(
        art["alias"], full_routes(),
        fe_sources={"frontend/src/pages/Racks.tsx": "rackApi.list({ limit: 50 })"},
        generate_response={**GOOD_GENERATE, "source_run_id": "legacy-run-1"},
    )
    reasons = _last(replay(events[:1] + [CutoverEvent(E.SWITCH_FE_LIST, fe_cutover=legacy_fe)]))
    assert "FE_LIST_NOT_ON_CANON_ALIAS" in reasons
    assert "DUAL_WRITE_REGRESSION" in reasons


def test_pin_rejects_unlinked_or_forged(art, other, enablement) -> None:
    events = _valid_events(art)
    machine = replay(events[:4] + [CutoverEvent(E.OPERATOR_PIN, pin=other["pin"])])
    assert machine.state is S.RECEIPT_CAPTURED
    assert "PIN_NOT_LINKED_TO_RECEIPT" in _last(machine)

    forged = art["pin"].model_copy(update={"unresolved_p0": ("P0-1",)})
    machine = replay(events[:4] + [CutoverEvent(E.OPERATOR_PIN, pin=forged)])
    assert "READINESS_PIN_TAMPERED" in _last(machine)

    resealed = art["pin"].model_copy(update={"unresolved_p0": ("P0-1",)}).sealed()
    machine = replay(events[:4] + [CutoverEvent(E.OPERATOR_PIN, pin=resealed)])
    assert machine.state is S.RECEIPT_CAPTURED
    assert "UNRESOLVED_P0" in _last(machine)

    bad_enable = art["pin"].model_copy(
        update={"enablement_receipt": enablement.model_copy(update={"source_commit_sha": "9" * 40})}
    ).sealed()
    machine = replay(events[:4] + [CutoverEvent(E.OPERATOR_PIN, pin=bad_enable)])
    assert "ENABLEMENT_RECEIPT_INVALID" in _last(machine)


def test_beta_eligible_is_immutable(art) -> None:
    machine = replay(_valid_events(art))
    for event in _valid_events(art) + [CutoverEvent(t) for t in E]:
        nxt = transition(machine, event)
        assert nxt.state is S.BETA_ELIGIBLE
        assert _last(nxt) == ("BETA_ELIGIBLE_IMMUTABLE",)
        assert nxt.receipt is machine.receipt and nxt.pin is machine.pin


def test_rejections_are_recorded_and_state_unchanged(art) -> None:
    machine = transition(new_machine(), CutoverEvent(E.CAPTURE_RECEIPT, receipt=art["receipt"]))
    assert machine.state is S.INVENTORY_LEGACY
    assert machine.receipt is None
    assert machine.history[-1].accepted is False


def test_full_path_flips_no_runtime_config(art) -> None:
    before = Settings()
    replay(_valid_events(art))
    after = Settings()
    for name in (
        "allow_production_payments",
        "enable_patchbook_design_engine",
        "enable_canon_export_fulfillment",
        "enable_clef_provider",
        "stripe_test_mode",
    ):
        assert getattr(after, name) == getattr(before, name)
    assert Settings.model_fields["allow_production_payments"].default is False
    assert Settings.model_fields["enable_clef_provider"].default is False
