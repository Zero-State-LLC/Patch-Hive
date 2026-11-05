"""The free reads of 2026-11-05: what the overlays rest on (owner decisions 13, 14, 17, 18, 50, 54)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "synth-catalog"
for path in (CATALOG, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_category_overlay as O  # noqa: E402
import build_maker_overlays as B  # noqa: E402
import population as P  # noqa: E402

FILLS = json.loads((CATALOG / "overlays" / "module-catalog-category-v6.json").read_text(encoding="utf-8"))["entries"]
CORRECTIONS = json.loads((CATALOG / "provenance" / "category-corrections-v4.json").read_text(encoding="utf-8"))["rows"]
MAKER = json.loads((CATALOG / "provenance" / "maker-corrections-v7.json").read_text(encoding="utf-8"))["rows"]
RETIRED = json.loads((CATALOG / "overlays" / "catalog-retirements-v4.json").read_text(encoding="utf-8"))["rows"]
HP = json.loads((CATALOG / "overlays" / "module-catalog-hp-v8.json").read_text(encoding="utf-8"))["entries"]
RECEIPT = json.loads((CATALOG / "receipts" / "free-reads-2026-11-05.json").read_text(encoding="utf-8"))


def follows_from_the_words(does: str, category: str, rule: str) -> bool:
    low = does.lower()
    if rule == "decision_14":
        return category == "SYSTEM"
    if rule == "decision_17":
        return category == "MIX" and low.rstrip("s") == "crossfader"
    if rule == "spelled_out_lfo":
        return category == "LFO" and low == "low frequency oscillator"
    if rule == "derived_from_frames":
        return category == "MIX"  # Frames' own page: "Keyframer/mixer"
    return {category} == (O.tag_categories([low]) or O.tag_categories([low.rstrip("s")])) or (
        B.category([does], does) == category
    )


@pytest.mark.parametrize("entry", FILLS, ids=lambda e: e["slug"])
def test_each_fill_follows_from_the_makers_words(entry) -> None:
    assert entry["category"] in P.MODULE_CATEGORIES
    assert entry["does"].lower() in entry["maker_quote"].lower()
    assert len(entry["maker_quote"]) <= 170
    assert follows_from_the_words(entry["does"], entry["category"], entry["rule"])
    assert str(entry["source_url"]).startswith("http")
    assert "modulargrid" not in json.dumps(entry).lower()


def test_the_reads_paid_for_nothing_and_kept_no_page_text() -> None:
    assert RECEIPT["paid_attempts"] == 0
    assert all("text" not in row and "description" not in row for row in RECEIPT["reads"])
    assert not any("modulargrid" in str(row["url"]) for row in RECEIPT["reads"])


def test_rows_that_name_two_functions_or_run_firmware_stay_empty() -> None:
    filled = {entry["slug"] for entry in FILLS}
    two_functions = {"make-noise-dxg", "make-noise-qxg", "noise-engineering-sinclastic-empulatrix", "plankton-electronics-nutone"}
    firmware = {  # decision 17
        "bela-pepper", "rebel-technology-genius", "rebel-technology-owl-modular",
        "north-coast-synthesis-msk-014-gracious-host", "p4l-modular-pikocoreuro-built", "wgd-modular-carciofo",
    }
    assert not filled & (two_functions | firmware)


def test_a_rings_or_streams_clone_waits_for_a_word_that_names_a_category() -> None:
    # Decisions 50 and 55: "Resonator" and "Dual dynamics gate" don't name one.
    filled = {entry["slug"] for entry in FILLS}
    assert not {slug for slug in filled if slug.startswith(("tall-dog-rings", "michigan-synth-works-nanorings", "michigan-synth-works-microstreams"))}
    assert "mutable-instruments-streams" not in filled


@pytest.mark.parametrize("table,field", [("module_catalog", "category"), ("modules", "module_type")])
def test_each_category_correction_covers_its_table_and_cites_its_page(table, field) -> None:
    rows = [row for row in CORRECTIONS if row["table"] == table]
    assert {row["name"] for row in rows} == {"Yarns", "Frames", "Edges", "Sensory Translator", "Animate"}
    for row in rows:
        assert [item["field"] for item in row["fields"]] == [field]
        assert all(item["evidence_url"].startswith("https://") and item["only_if_value"] for item in row["fields"])


def test_supply_outputs_are_cleared_only_where_the_stored_value_is_the_output() -> None:
    cleared = {row["name"]: row for row in MAKER if any(item["action"] == "null" for item in row["fields"])}
    assert set(cleared) == {"SOURCE MK3", "UPWR", "DC High-Quality Power Supply", "POW!", "STV"}
    for row in cleared.values():
        assert row["table"] == "modules"
        assert all(item["field"] in P.POWER_FIELDS and item["only_if_value"] for item in row["fields"])
    # A later fill must not bring them back, on a loaded database or a load from empty.
    for path in (CATALOG / "overlays").glob("module-power-depth-v*.json"):
        for entry in json.loads(path.read_text(encoding="utf-8"))["entries"]:
            if entry["name"] in cleared and entry["brand"] == cleared[entry["name"]]["brand"]:
                assert not any(entry.get(field) for field in ("power_12v_ma", "power_neg12v_ma", "power_5v_ma"))


def test_a_width_changes_only_with_a_quote_from_the_maker() -> None:
    widths = [item for row in MAKER for item in row["fields"] if item["field"] == "hp"]
    assert widths
    assert all(item["action"] == "correct" and item["evidence_url"].startswith("https://") for item in widths)
    assert all(P.CORRECTION_HP_BAND[0] <= item["value"] <= P.CORRECTION_HP_BAND[1] for item in widths)
    assert all(entry["source_class"] == "maker" and entry["source_url"].startswith("https://") for entry in HP)


def test_a_url_correction_cites_the_makers_own_page_and_clears_no_flag() -> None:
    rows = json.loads((CATALOG / "provenance" / "catalog-url-corrections-v1.json").read_text(encoding="utf-8"))["rows"]
    assert [row["slug"] for row in rows] == ["noise-engineering-basimilus-iteritas-alter"]
    item = rows[0]["fields"][0]
    assert "manualslib" in item["only_if_value"] and item["value"] == item["evidence_url"]
    assert P._correction_problem("module_catalog", item) is None
    assert P._correction_problem("module_catalog", {**item, "value": "http://noiseengineering.us/"}) == "correction_bad_url"

    plan = P.Plan()
    catalog = {"noise-engineering-basimilus-iteritas-alter": {
        "brand": "Noise Engineering", "name": "Basimilus Iteritas Alter", "needs_reverify": True,
        "manufacturer_url": item["only_if_value"], "tombstoned": False,
    }}
    P._schedule_provenance(plan, catalog, {}, {"batch": "t", "flag_reverify": False, "rows": rows}, set(), {})
    assert catalog["noise-engineering-basimilus-iteritas-alter"]["manufacturer_url"] == item["value"]
    assert plan.provenance["t"]["reverify_clear_scheduled"] == 0


def test_a_retirement_cites_the_page_and_keeps_placed_rows_to_blank_or_not_modules() -> None:
    assert len(RETIRED) == 11
    assert all(row["evidence_url"].startswith("https://") and "The page says" in row["reason"] for row in RETIRED)
    assert all(";" not in row["reason"] for row in RETIRED)  # the plan's SQL guard splits on it
