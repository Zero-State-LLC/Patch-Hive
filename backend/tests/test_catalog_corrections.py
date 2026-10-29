"""Spec 003 FR-038: reviewed corrections archive the old value, then write the new one."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402

MANIFEST = ROOT / "data" / "synth-catalog" / "provenance" / "maker-corrections-v1.json"
PAGE = "https://maker.example/eurorack"


def _manifest(**field) -> dict:
    item = {"field": "hp", "action": "correct", "only_if_value": 14, "value": 4,
            "evidence_url": PAGE, "source_tag": "test", "maker_check": "maker_page_reviewed"}
    item.update(field)
    return {"batch": "test-corrections", "flag_reverify": False,
            "rows": [{"table": "modules", "brand": "Acme", "name": "Chicane", "fields": [item]}]}


def _modules(hp=14):
    return {("Acme", "Chicane"): {"brand": "Acme", "name": "Chicane", "hp": hp,
                                  "verification_source_url": "https://maker.example/1u", "_duplicate": False}}


def _plan(manifest: dict, modules: dict, archived=frozenset()) -> P.Plan:
    plan = P.Plan()
    P._schedule_provenance(plan, {}, modules, manifest, set(archived))
    return plan


def test_a_matching_correction_archives_then_writes_and_never_flags() -> None:
    modules = _modules()
    plan = _plan(_manifest(), modules)
    kinds = [op.kind for op in plan.ops]
    assert kinds == ["archive_values", "correct_values", "archive_markers"]
    correct = plan.ops[1]
    assert "a.action = 'correct'" in correct.sql and "needs_reverify" not in correct.sql
    assert correct.params["c0"] == 4
    assert modules[("Acme", "Chicane")]["hp"] == 4
    assert plan.provenance["test-corrections"]["corrected_values"] == 1
    P.assert_safe_sql(P.render_plan(plan))


def test_a_value_changed_since_review_is_left_alone() -> None:
    modules = _modules(hp=6)
    plan = _plan(_manifest(), modules)
    assert [op.kind for op in plan.ops] == ["archive_markers"]
    assert modules[("Acme", "Chicane")]["hp"] == 6
    assert plan.provenance["test-corrections"]["value_not_matched"] == 1


def test_a_processed_row_is_never_corrected_twice() -> None:
    plan = _plan(_manifest(), _modules(), archived={("modules", "Acme::Chicane", P.ROW_MARKER)})
    assert plan.ops == []


@pytest.mark.parametrize(
    "field,reason",
    [
        ({"value": None}, "correction_needs_old_and_new_value"),
        ({"only_if_value": None}, "correction_needs_old_and_new_value"),
        ({"evidence_url": ""}, "correction_needs_maker_page"),
        ({"evidence_url": "http://maker.example"}, "correction_needs_maker_page"),
        ({"value": 52}, "correction_hp_outside_band"),
        ({"value": "4"}, "correction_hp_outside_band"),
        ({"field": "verification_source_url", "only_if_value": "x", "value": "ftp://x"}, "correction_bad_url"),
    ],
)
def test_an_unusable_correction_is_a_conflict_and_writes_nothing(field, reason) -> None:
    modules = _modules()
    plan = _plan(_manifest(**field), modules)
    assert [c["reason"] for c in plan.conflicts] == [reason]
    assert modules[("Acme", "Chicane")]["hp"] == 14
    assert not [op for op in plan.ops if op.kind in ("archive_values", "correct_values")]


def test_the_chicane_manifest_cites_the_eurorack_page() -> None:
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["batch"] == "maker-corrections-v1" and manifest["flag_reverify"] is False
    (row,) = manifest["rows"]
    fields = {f["field"]: f for f in row["fields"]}
    assert (row["brand"], row["name"]) == ("Sovage Engineering", "CHICANE")
    assert (fields["hp"]["only_if_value"], fields["hp"]["value"]) == (14, 4)
    assert fields["verification_source_url"]["value"] == "https://www.sovageengineering.com/product-page/chicane"
    assert all(f["evidence_url"] == "https://www.sovageengineering.com/product-page/chicane" for f in row["fields"])
    assert MANIFEST in P.PROVENANCE_MANIFESTS


def _flagged(**extra):
    modules = _modules()
    modules[("Acme", "Chicane")].update({"needs_reverify": True, "status": "active", **extra})
    return modules


def test_a_correction_schedules_the_flag_check_after_the_write() -> None:
    plan = _plan(_manifest(), _flagged())
    kinds = [op.kind for op in plan.ops]
    assert kinds == ["archive_values", "correct_values", "archive_markers", "clear_reverify"]
    clear = plan.ops[-1].sql
    # Cleared only while no flag or relabel lacks a later correction, and no nulled field is empty.
    assert "a.action IN ('flag', 'relabel')" in clear and "c.archived_at >= a.archived_at" in clear
    assert "depth_mm IS NULL" in clear and "status <> 'tombstoned'" in clear
    assert plan.provenance["test-corrections"]["reverify_clear_scheduled"] == 1
    P.assert_safe_sql(P.render_plan(plan))


def test_a_correction_applied_earlier_still_gets_the_flag_check() -> None:
    plan = _plan(_manifest(), _flagged(), archived={("modules", "Acme::Chicane", P.ROW_MARKER)})
    assert [op.kind for op in plan.ops] == ["clear_reverify"]


def test_an_unflagged_row_needs_no_check() -> None:
    plan = _plan(_manifest(), _modules())
    assert "clear_reverify" not in [op.kind for op in plan.ops]


def test_a_tombstoned_row_is_refused_and_untouched() -> None:
    modules = _flagged(status="tombstoned")
    plan = _plan(_manifest(), modules)
    assert plan.ops == []
    assert modules[("Acme", "Chicane")]["hp"] == 14
    assert plan.provenance["test-corrections"]["refused_row_tombstoned"] == 1


def test_a_tombstoned_catalog_row_is_refused() -> None:
    manifest = {"batch": "test-catalog", "rows": [{
        "table": "module_catalog", "slug": "acme-chicane", "brand": "Acme", "name": "Chicane",
        "fields": [{"field": "hp", "action": "null", "only_if_value": 14}]}]}
    catalog = {"acme-chicane": {"brand": "Acme", "name": "Chicane", "hp": 14, "tombstoned": True}}
    plan = P.Plan()
    P._schedule_provenance(plan, catalog, {}, manifest, set())
    assert plan.ops == [] and catalog["acme-chicane"]["hp"] == 14
    assert plan.provenance["test-catalog"]["refused_row_tombstoned"] == 1


def test_every_row_statement_skips_retired_rows() -> None:
    assert "status <> 'tombstoned'" in P._row_where("modules")
    assert "tombstoned_at IS NULL" in P._row_where("module_catalog")
    plan = _plan(_manifest(), _modules())
    archive = plan.ops[0].sql
    assert "t.status <> 'tombstoned'" in archive
