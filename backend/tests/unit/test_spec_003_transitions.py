"""Spec 003 (catalog dataset pipeline): the admitted-row lifecycle, encoded from the spec tables.

Source: specs/003-catalog-dataset-pipeline/spec.md, "## Stateful behavior" ->
"### Row lifecycle (admitted rows)", amended by D4 / FR-038 (reviewed corrections may
overwrite) and FR-039. The loader is data/synth-catalog/population.py; it is driven here with
in-memory row state, so no database is needed.

The batch machine (TARGETED ... ADMITTED) has no executable state machine in the repository, so
only its RECEIPTED -> ADMITTED hash binding is covered (see ``test_plan_hash_*``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402

PAGE = "https://maker.example/eurorack"
BRAND, NAME = "Acme", "Chicane"
ROW_KEY = P.module_row_key(BRAND, NAME)
SLUG = P.create_slug(BRAND, NAME)

# Spec "Row lifecycle (admitted rows)" -> transitions table.
# (from, event, to, op kinds the loader plans for a module row)
ROW_TRANSITIONS = [
    ("LIVE", "flag", "FLAGGED", ["archive_values", "reverify_row", "archive_markers"]),
    ("FLAGGED", "correct", "LIVE", ["archive_values", "correct_values", "archive_markers", "clear_reverify"]),
    ("LIVE", "correct", "LIVE", ["archive_values", "correct_values", "archive_markers"]),
]
ROW_STATES = {"LIVE", "FLAGGED", "TOMBSTONED"}
# Spec "Illegal transitions": TOMBSTONED -> any flag or correction.
ACTIONS_ON_TOMBSTONED = ["flag", "null", "relabel", "keep", "correct"]


def _item(action: str, **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"field": "hp", "action": action, "source_tag": "test", "maker_check": "maker_page_reviewed"}
    if action == "correct":
        item.update(only_if_value=14, value=4, evidence_url=PAGE)
    item.update(extra)
    return item


def _manifest(item: dict[str, Any], table: str = "modules") -> dict[str, Any]:
    row = {"table": table, "brand": BRAND, "name": NAME, "fields": [item]}
    return {"batch": "t010-003", "flag_reverify": True, "rows": [row]}


def _module(state: str, hp: int = 14) -> dict[tuple[str, str], dict[str, Any]]:
    row: dict[str, Any] = {"brand": BRAND, "name": NAME, "hp": hp, "_duplicate": False,
                           "verification_source_url": "https://maker.example/1u", "status": "active"}
    if state == "FLAGGED":
        row["needs_reverify"] = True
    if state == "TOMBSTONED":
        row["status"] = "tombstoned"
    return {(BRAND, NAME): row}


def _schedule(item: dict[str, Any], modules: dict, table: str = "modules", catalog: dict | None = None) -> P.Plan:
    plan = P.Plan()
    P._schedule_provenance(plan, catalog or {}, modules, _manifest(item, table), set())
    return plan


def _kinds(plan: P.Plan) -> list[str]:
    return [op.kind for op in plan.ops]


@pytest.mark.parametrize(("source", "event", "target", "kinds"), ROW_TRANSITIONS)
def test_listed_row_transition_plans_exactly_the_listed_effect(source, event, target, kinds) -> None:
    modules = _module(source)
    plan = _schedule(_item(event), modules)
    assert _kinds(plan) == kinds
    stored = modules[(BRAND, NAME)]["hp"]
    if event == "correct":
        assert stored == 4  # the new value is written, after the old one is archived first
        assert _kinds(plan).index("archive_values") < _kinds(plan).index("correct_values")
        assert "needs_reverify" not in plan.ops[kinds.index("correct_values")].sql
    else:
        assert stored == 14  # flag archives the value and sets needs_reverify; nothing is rewritten
        assert "needs_reverify = TRUE" in plan.ops[kinds.index("reverify_row")].sql
    assert ("clear_reverify" in _kinds(plan)) == (source == "FLAGGED")
    P.assert_safe_sql(P.render_plan(plan))
    assert {source, target} <= ROW_STATES


def test_flag_by_null_action_archives_then_nulls_the_value() -> None:
    modules = _module("LIVE")
    plan = _schedule(_item("null", field="verification_source_url"), modules)
    assert _kinds(plan) == ["archive_values", "reverify_row", "archive_markers"]
    assert modules[(BRAND, NAME)]["verification_source_url"] is None
    assert "needs_reverify = TRUE" in plan.ops[1].sql


@pytest.mark.parametrize("source", ["LIVE", "FLAGGED"])
def test_retire_tombstones_the_row_and_never_deletes(source) -> None:
    modules = _module(source)
    catalog = {SLUG: {"brand": BRAND, "name": NAME, "hp": 14, "tombstoned": False}}
    entry = {"slug": SLUG, "brand": BRAND, "name": NAME, "reason": "filed under the wrong brand", "evidence_url": PAGE}
    plan = P.Plan()
    P._schedule_retirement(plan, catalog, modules, entry)
    assert _kinds(plan) == ["retire_catalog", "retire_module"]
    assert catalog[SLUG]["tombstoned"] is True
    assert modules[(BRAND, NAME)]["status"] == "tombstoned"
    assert "tombstoned_at = CAST(:tombstoned_at" in plan.ops[0].sql and "tombstone_reason" in plan.ops[0].sql
    assert "status = 'tombstoned'" in plan.ops[1].sql
    P.assert_safe_sql(P.render_plan(plan))


@pytest.mark.parametrize("missing", ["reason", "brand", "name"])
def test_retire_without_a_reason_or_identity_is_refused(missing) -> None:
    modules = _module("LIVE")
    entry = {"slug": SLUG, "brand": BRAND, "name": NAME, "reason": "wrong brand", "evidence_url": PAGE, missing: ""}
    plan = P.Plan()
    P._schedule_retirement(plan, {}, modules, entry)
    assert plan.ops == []
    assert [c["reason"] for c in plan.conflicts] == ["retirement_missing_identity_or_reason"]
    assert modules[(BRAND, NAME)]["status"] == "active"


def test_retire_of_a_tombstoned_row_changes_nothing() -> None:
    modules = _module("TOMBSTONED")
    catalog = {SLUG: {"brand": BRAND, "name": NAME, "hp": 14, "tombstoned": True}}
    plan = P.Plan()
    P._schedule_retirement(plan, catalog, modules,
                           {"slug": SLUG, "brand": BRAND, "name": NAME, "reason": "again", "evidence_url": PAGE})
    assert plan.ops == []


@pytest.mark.parametrize("evidence", ["", "http://maker.example/eurorack"])
def test_retire_without_evidence_is_refused(evidence) -> None:
    """Retire guard: a reason AND evidence (spec 003 OQ-9)."""
    modules = _module("LIVE")
    catalog = {SLUG: {"brand": BRAND, "name": NAME, "hp": 14, "tombstoned": False}}
    entry = {"slug": SLUG, "brand": BRAND, "name": NAME, "reason": "wrong brand", "evidence_url": evidence}
    plan = P.Plan()
    P._schedule_retirement(plan, catalog, modules, entry)
    assert plan.ops == []
    assert [c["reason"] for c in plan.conflicts] == ["retirement_needs_evidence"]
    assert catalog[SLUG]["tombstoned"] is False and modules[(BRAND, NAME)]["status"] == "active"


# --- Illegal transitions ----------------------------------------------------------------------


@pytest.mark.parametrize("action", ACTIONS_ON_TOMBSTONED)
def test_tombstoned_module_refuses_every_flag_and_correction(action) -> None:
    modules = _module("TOMBSTONED")
    plan = _schedule(_item(action), modules)
    assert plan.ops == []
    assert modules[(BRAND, NAME)]["hp"] == 14 and modules[(BRAND, NAME)]["status"] == "tombstoned"
    assert plan.provenance["t010-003"]["refused_row_tombstoned"] == 1  # counted in the receipt


@pytest.mark.parametrize("action", ACTIONS_ON_TOMBSTONED)
def test_tombstoned_catalog_row_refuses_every_flag_and_correction(action) -> None:
    catalog = {SLUG: {"brand": BRAND, "name": NAME, "hp": 14, "tombstoned": True}}
    plan = _schedule(_item(action), {}, table="module_catalog", catalog=catalog)
    assert plan.ops == []
    assert catalog[SLUG]["hp"] == 14
    assert plan.provenance["t010-003"]["refused_row_tombstoned"] == 1


def test_no_planned_statement_untombstones_or_deletes() -> None:
    plans = [_schedule(_item(a), _module(s)) for s in ("LIVE", "FLAGGED") for a in ("flag", "correct", "keep", "relabel")]
    retire = P.Plan()
    P._schedule_retirement(retire, {SLUG: {"brand": BRAND, "name": NAME, "tombstoned": False}}, _module("LIVE"),
                           {"slug": SLUG, "brand": BRAND, "name": NAME, "reason": "r", "evidence_url": PAGE})
    for plan in [*plans, retire]:
        for op in plan.ops:
            sql = " ".join(op.sql.upper().split())
            assert "DELETE" not in sql
            assert "TOMBSTONED_AT = NULL" not in sql and "STATUS = 'ACTIVE'" not in sql
        P.assert_safe_sql(P.render_plan(plan))


@pytest.mark.parametrize("state", ["LIVE", "FLAGGED"])
@pytest.mark.parametrize("action", ["flag", "keep", "relabel"])
def test_a_value_is_never_changed_without_a_correction_entry(state, action) -> None:
    modules = _module(state)
    plan = _schedule(_item(action), modules)
    assert "correct_values" not in _kinds(plan)
    assert modules[(BRAND, NAME)]["hp"] == 14


@pytest.mark.parametrize("state", ["LIVE", "FLAGGED"])
def test_a_correction_is_skipped_when_the_stored_value_changed_since_review(state) -> None:
    modules = _module(state, hp=6)
    plan = _schedule(_item("correct"), modules)
    assert not {"archive_values", "correct_values"} & set(_kinds(plan))
    assert modules[(BRAND, NAME)]["hp"] == 6
    assert plan.provenance["t010-003"]["value_not_matched"] == 1


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"only_if_value": None}, "correction_needs_old_and_new_value"),
        ({"value": None}, "correction_needs_old_and_new_value"),
        ({"evidence_url": ""}, "correction_needs_maker_page"),
        ({"evidence_url": "http://maker.example"}, "correction_needs_maker_page"),
        ({"value": 85}, "correction_hp_outside_band"),
        ({"value": 0}, "correction_hp_outside_band"),
    ],
)
def test_a_correction_must_name_old_value_new_value_and_a_maker_page(override, reason) -> None:
    modules = _module("LIVE")
    plan = _schedule(_item("correct", **override), modules)
    assert [c["reason"] for c in plan.conflicts] == [reason]
    assert not {"archive_values", "correct_values"} & set(_kinds(plan))
    assert modules[(BRAND, NAME)]["hp"] == 14


@pytest.mark.parametrize("value", [1, 84])
def test_corrected_hp_band_edges_are_accepted(value) -> None:
    modules = _module("LIVE")
    plan = _schedule(_item("correct", value=value), modules)
    assert plan.conflicts == [] and modules[(BRAND, NAME)]["hp"] == value


def test_an_already_processed_row_is_not_touched_twice() -> None:
    plan = P.Plan()
    P._schedule_provenance(plan, {}, _module("LIVE"), _manifest(_item("correct")), {("modules", ROW_KEY, P.ROW_MARKER)})
    assert plan.ops == []


# --- Batch machine fragment: RECEIPTED -> ADMITTED needs the receipt to bind the current plan ----


def test_plan_hash_binds_the_reviewed_plan_and_ignores_the_clock() -> None:
    first = _schedule(_item("correct"), _module("LIVE"))
    same = _schedule(_item("correct"), _module("LIVE"))
    changed = _schedule(_item("correct", value=5), _module("LIVE"))
    assert P.plan_hash(first) == P.plan_hash(same)
    assert P.plan_hash(first) != P.plan_hash(changed)
