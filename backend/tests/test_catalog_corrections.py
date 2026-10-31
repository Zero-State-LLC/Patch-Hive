"""Spec 003 FR-038: reviewed corrections archive the old value, then write the new one."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
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
        ({"value": 85}, "correction_hp_outside_band"),
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


FLAGGED_AT = datetime(2026, 10, 17, tzinfo=timezone.utc)


def _with_history(manifest: dict, modules: dict, history: dict, archived=frozenset()) -> P.Plan:
    plan = P.Plan()
    P._schedule_provenance(plan, {}, modules, manifest, set(archived), history)
    return plan


def _clears(plan: P.Plan) -> int:
    return sum(op.kind == "clear_reverify" for op in plan.ops)


def test_a_row_with_a_nulled_field_still_empty_is_not_planned_for_a_clear() -> None:
    # The Doepfer A-101-3 case: hp flagged and power nulled; the hp correction alone can't clear it,
    # so the plan must not promise a clear the database refuses on every run.
    modules = _flagged()
    modules[("Acme", "Chicane")]["power_12v_ma"] = None
    history = {("modules", "Acme::Chicane"): [("hp", "flag", FLAGGED_AT), ("power_12v_ma", "null", FLAGGED_AT)]}
    plan = _with_history(_manifest(), modules, history)
    assert [op.kind for op in plan.ops] == ["archive_values", "correct_values", "archive_markers"]
    assert plan.provenance["test-corrections"]["reverify_clear_scheduled"] == 0
    # A rerun after the correction plans nothing at all.
    history[("modules", "Acme::Chicane")].append(("hp", "correct", datetime(2026, 10, 30, tzinfo=timezone.utc)))
    rerun = _with_history(_manifest(), modules, history, archived={("modules", "Acme::Chicane", P.ROW_MARKER)})
    assert rerun.ops == []


def test_a_nulled_field_filled_again_lets_the_clear_through() -> None:
    modules = _flagged()
    modules[("Acme", "Chicane")]["power_12v_ma"] = 80
    history = {("modules", "Acme::Chicane"): [("hp", "flag", FLAGGED_AT), ("power_12v_ma", "null", FLAGGED_AT)]}
    assert _clears(_with_history(_manifest(), modules, history)) == 1


def test_another_flagged_field_without_a_correction_blocks_the_clear() -> None:
    history = {("modules", "Acme::Chicane"): [("hp", "flag", FLAGGED_AT), ("depth_mm", "flag", FLAGGED_AT)]}
    assert _clears(_with_history(_manifest(), _flagged(), history)) == 0


def test_a_correction_older_than_the_flag_does_not_count() -> None:
    corrected = datetime(2026, 10, 1, tzinfo=timezone.utc)
    history = {("modules", "Acme::Chicane"): [("hp", "correct", corrected), ("hp", "flag", FLAGGED_AT)]}
    plan = _with_history(_manifest(), _flagged(), history, archived={("modules", "Acme::Chicane", P.ROW_MARKER)})
    assert _clears(plan) == 0


def test_a_correction_applied_earlier_with_nothing_open_is_still_cleared() -> None:
    corrected = datetime(2026, 10, 29, tzinfo=timezone.utc)
    history = {("modules", "Acme::Chicane"): [("hp", "flag", FLAGGED_AT), ("hp", "correct", corrected)]}
    plan = _with_history(_manifest(), _flagged(), history, archived={("modules", "Acme::Chicane", P.ROW_MARKER)})
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


def test_the_v2_manifest_corrects_the_v1_overlay_hp_in_every_table() -> None:
    path = ROOT / "data" / "synth-catalog" / "provenance" / "maker-corrections-v2.json"
    manifest = json.loads(path.read_text())
    assert manifest["batch"] == "maker-corrections-v2" and manifest["flag_reverify"] is False
    assert path in P.PROVENANCE_MANIFESTS
    corrections = {}
    for row in manifest["rows"]:
        (item,) = row["fields"]
        assert item["field"] == "hp" and item["action"] == "correct"
        assert P._correction_problem(row["table"], item) is None
        assert "?" not in item["evidence_url"] and item["evidence_url"] in item["source_tag"]
        assert item["maker_check"] == "maker_page_reviewed"
        if row["table"] == "module_catalog":
            assert row["slug"] == P.create_slug(row["brand"], row["name"])
        corrections[(row["table"], row["brand"], row["name"])] = (item["only_if_value"], item["value"])
    assert corrections == {
        ("module_catalog", "Acid Rain Technology", "Junction"): (6, 4),
        ("module_catalog", "Doepfer", "A-101-3"): (10, 30),
        ("module_catalog", "Doepfer", "A-137-2"): (10, 14),
        ("modules", "Acid Rain Technology", "Junction"): (6, 4),
        ("modules", "Doepfer", "A-101-3"): (10, 30),
    }
    # Each old value is the unsourced v1 overlay's; each new value is the maker-cited v2 one.
    overlays = ROOT / "data" / "synth-catalog" / "overlays"
    v1 = {e["slug"]: e["hp"] for e in json.loads((overlays / "module-catalog-hp-v1.json").read_text())["entries"]}
    v2 = {e["slug"]: e["hp"] for e in json.loads((overlays / "module-catalog-hp-v2.json").read_text())["entries"]}
    for (_, brand, name), (old, new) in corrections.items():
        slug = P.create_slug(brand, name)
        assert (v1[slug], v2[slug]) == (old, new)


def test_the_v3_manifest_corrects_the_hand_checked_v1_hp_in_every_table() -> None:
    """Spec 003 T039: rows holding a v1 value their maker page contradicts take the page value."""
    path = ROOT / "data" / "synth-catalog" / "provenance" / "maker-corrections-v3.json"
    manifest = json.loads(path.read_text())
    assert manifest["batch"] == "maker-corrections-v3" and manifest["flag_reverify"] is False
    # v4 (the T039 remainder) is read right after v3, then v5 (the A-155 width).
    assert P.PROVENANCE_MANIFESTS[-3] == path
    corrections = {}
    for row in manifest["rows"]:
        (item,) = row["fields"]
        assert item["field"] == "hp" and item["action"] == "correct"
        assert P._correction_problem(row["table"], item) is None
        assert "?" not in item["evidence_url"] and item["evidence_url"] in item["source_tag"]
        assert len(item["source_tag"]) <= 200
        assert item["maker_check"] == "maker_page_reviewed"
        if row["table"] == "module_catalog":
            assert row["slug"] == P.create_slug(row["brand"], row["name"])
        corrections[(row["table"], row["brand"], row["name"])] = (item["only_if_value"], item["value"])
    assert corrections == {
        ("module_catalog", "Make Noise", "DPO"): (30, 28),
        ("module_catalog", "Make Noise", "Morphagene"): (18, 20),
        ("modules", "Make Noise", "DPO"): (30, 28),
        ("modules", "Make Noise", "Morphagene"): (18, 20),
        ("module_catalog", "Bastl Instruments", "Knit Rider"): (2, 16),
        ("module_catalog", "Intellijel", "MEMS Mic 1U"): (2, 10),
        ("modules", "Bastl Instruments", "Knit Rider"): (2, 16),
        ("modules", "Intellijel", "MEMS Mic 1U"): (2, 10),
    }
    # Each old value is the unsourced v1 overlay's; each new value is the maker-cited v3 one,
    # so a fresh load and a corrected database agree.
    overlays = ROOT / "data" / "synth-catalog" / "overlays"
    v1 = {e["slug"]: e["hp"] for e in json.loads((overlays / "module-catalog-hp-v1.json").read_text())["entries"]}
    v3 = {e["slug"]: e for e in json.loads((overlays / "module-catalog-hp-v3.json").read_text())["entries"]}
    for (_, brand, name), (old, new) in corrections.items():
        slug = P.create_slug(brand, name)
        assert (v1[slug], v3[slug]["hp"]) == (old, new)
    for row in manifest["rows"]:
        slug = P.create_slug(row["brand"], row["name"])
        assert v3[slug]["source_url"] == row["fields"][0]["evidence_url"]


def test_the_v4_manifest_corrects_the_page_checked_v1_hp() -> None:
    """Spec 003 T039 remainder: Doepfer's own pages state A-106-1 14 HP and A-138m 20 HP.

    Neither module has a ``modules`` row, so only ``module_catalog`` is corrected.
    """
    path = ROOT / "data" / "synth-catalog" / "provenance" / "maker-corrections-v4.json"
    manifest = json.loads(path.read_text())
    assert manifest["batch"] == "maker-corrections-v4" and manifest["flag_reverify"] is False
    assert P.PROVENANCE_MANIFESTS[-2] == path
    corrections = {}
    for row in manifest["rows"]:
        (item,) = row["fields"]
        assert item["field"] == "hp" and item["action"] == "correct"
        assert P._correction_problem(row["table"], item) is None
        assert "?" not in item["evidence_url"] and item["evidence_url"] in item["source_tag"]
        assert len(item["source_tag"]) <= 200
        assert item["maker_check"] == "maker_page_reviewed"
        assert row["slug"] == P.create_slug(row["brand"], row["name"])
        corrections[(row["table"], row["brand"], row["name"])] = (item["only_if_value"], item["value"])
    assert corrections == {
        ("module_catalog", "Doepfer", "A-106-1"): (8, 14),
        ("module_catalog", "Doepfer", "A-138m"): (8, 20),
    }
    overlays = ROOT / "data" / "synth-catalog" / "overlays"
    v1 = {e["slug"]: e["hp"] for e in json.loads((overlays / "module-catalog-hp-v1.json").read_text())["entries"]}
    v4 = {e["slug"]: e for e in json.loads((overlays / "module-catalog-hp-v4.json").read_text())["entries"]}
    for row in manifest["rows"]:
        (item,) = row["fields"]
        slug = row["slug"]
        assert (v1[slug], v4[slug]["hp"]) == (item["only_if_value"], item["value"])
        assert v4[slug]["source_url"] == item["evidence_url"]
    # Doepfer A-155's page states 50 HP: a reviewed correction may go to 84 HP (FR-038), past
    # the FR-007 extraction band; maker-corrections-v5 makes it.
    assert P._correction_problem("module_catalog", {"field": "hp", "only_if_value": 4, "value": 50,
                                                    "evidence_url": "https://doepfer.de/a155.htm"}) is None
    assert P._correction_problem("module_catalog", {"field": "hp", "only_if_value": 4, "value": 85,
                                                    "evidence_url": "https://doepfer.de/a155.htm"}) == "correction_hp_outside_band"
    assert P.HP_BAND == (1, 42) and P.CORRECTION_HP_BAND == (1, 84)


def test_maker_corrections_v5_sets_the_a155_to_its_stated_width() -> None:
    manifest = json.loads((ROOT / "data" / "synth-catalog" / "provenance" / "maker-corrections-v5.json").read_text())
    assert manifest["batch"] == "maker-corrections-v5" and manifest["flag_reverify"] is False
    assert P.PROVENANCE_MANIFESTS[-1] == ROOT / "data" / "synth-catalog" / "provenance" / "maker-corrections-v5.json"
    assert {(row["table"], row["brand"], row["name"]) for row in manifest["rows"]} == {
        ("module_catalog", "Doepfer", "A-155"), ("modules", "Doepfer", "A-155"),
    }
    for row in manifest["rows"]:
        (item,) = row["fields"]
        assert (item["field"], item["action"], item["only_if_value"], item["value"]) == ("hp", "correct", 4, 50)
        assert item["evidence_url"] == "https://doepfer.de/a155.htm"
        assert "50 TE / 50 HP" in item["source_tag"]
        assert P._correction_problem(row["table"], item) is None
