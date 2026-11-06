"""Spec 001 T010: the module evidence lifecycle, read through the mapping in plan.md.

No code has the spec's five named states (T001 record, D7). The rules run through the spec 005
resolution machine and the confirm decisions, and existing tests hold most of them. This file
names the test that holds each spec row, and fails if a row or its test goes missing. Rejects
aren't recorded yet (D8), so the rejected row only covers what a reject does to canon today.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
SPEC = TESTS.parents[1] / "specs" / "001-rig-intelligence" / "spec.md"
MACHINE = "unit/test_resolution_machine.py"
VISUAL = "unit/test_visual_system_intelligence.py"
DECISION = "unit/test_decision_intelligence.py"
CONFIRM = "api/test_evidence_confirmations.py"

HELD_BY = {
    ("EVIDENCE_RECEIVED", "candidate_ranked", "PROPOSED"): (CONFIRM, "test_list_and_confirm_candidates"),
    ("EVIDENCE_RECEIVED", "evidence_invalid", "UNRESOLVED"): (
        MACHINE, "test_provider_success_with_invalid_packet_fails_closed",
    ),
    ("PROPOSED", "conflict_or_low_confidence", "UNRESOLVED"): (
        DECISION, "test_none_of_above_remains_unresolved_even_with_high_confidence",
    ),
    ("UNRESOLVED", "new_evidence", "EVIDENCE_RECEIVED"): (
        CONFIRM, "test_new_evidence_is_appended_and_leaves_earlier_evidence_unchanged",
    ),
    ("PROPOSED", "confirmed", "CONFIRMED"): (CONFIRM, "test_list_and_confirm_candidates"),
    ("PROPOSED", "rejected", "REJECTED"): (VISUAL, "test_unconfirmed_candidates_do_not_enter_inventory"),
}
ILLEGAL_HELD_BY = [
    (VISUAL, "test_classification_candidate_cannot_self_confirm"),
    (VISUAL, "test_provider_detect_modules_cannot_promote_confirmed"),
    (MACHINE, "test_user_confirm_without_confirmation_path_is_rejected"),
    (CONFIRM, "test_a_confirm_needs_a_candidate_the_rack_holds"),
    (DECISION, "test_provider_failure_escalates_never_confirms"),
    (VISUAL, "test_inventory_requires_confirmation_and_is_immutable_hash_stable"),
]


def _lifecycle() -> str:
    return SPEC.read_text(encoding="utf-8").split("### Module evidence disposition lifecycle", 1)[1]


def test_every_spec_row_names_what_holds_it() -> None:
    table = _lifecycle().split("#### Transitions", 1)[1].split("#### Illegal transitions", 1)[0]
    rows = set()
    for line in table.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 5 and cells[0] not in {"from", "---"}:
            rows.add((cells[0], cells[1], cells[3]))
    assert rows == set(HELD_BY)


def test_the_spec_still_lists_the_illegal_moves_these_cover() -> None:
    illegal = _lifecycle().split("#### Illegal transitions", 1)[1].split("```mermaid", 1)[0]
    assert len([line for line in illegal.splitlines() if line.startswith("- ")]) == 4


@pytest.mark.parametrize("location", [*HELD_BY.values(), *ILLEGAL_HELD_BY], ids=lambda loc: loc[1])
def test_each_named_test_exists(location: tuple[str, str]) -> None:
    path, name = location
    assert f"def {name}(" in (TESTS / path).read_text(encoding="utf-8")
