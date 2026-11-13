"""Categories for Modules that already have jack lists, read from makers' documents (slice N5)."""

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

OVERLAY_PATH = CATALOG / "overlays" / "module-catalog-category-v11.json"
OVERLAY = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
ENTRIES = OVERLAY["entries"]
JACKS = {
    (entry["brand"], entry["name"]): entry
    for entry in json.loads((CATALOG / "overlays" / "module-jacks-v1.json").read_text(encoding="utf-8"))["entries"]
}
EVIDENCE = (ROOT / "docs" / "evidence" / "CATALOG_JACK_LIST_CATEGORIES_2026-11-10.md").read_text(encoding="utf-8")

FILLED = {
    ("2hp", "Tape Stop"): "FX",
    ("Alyseum", "PUSH"): "SEQ",
    ("Ge0sync Synth", "GS1-O"): "VCO",
    ("Make Noise", "Bruxa"): "FX",
    ("Mutable Instruments", "Warps"): "FX",
    ("Pittsburgh Modular", "Collapse"): "FX",
    ("Pittsburgh Modular", "Crush"): "FX",
    ("Pittsburgh Modular", "VC Bend"): "UTIL",
    ("Qu-Bit Electronix", "Prism"): "FX",
}
# Read and left empty: the document names two functions, or no category (see the evidence record).
LEFT_FOR_THE_OWNER = {
    ("Analogue Systems", "RS-260"),
    ("Infrasonic Audio", "DISENTANGLER"),
    ("Intellijel", "Scales"),
    ("Make Noise", "MMG"),
    ("Pittsburgh Modular", "Toolbox"),
    ("Rossum Electro-Music", "PANHARMONIUM Mutating Spectral Resynthesizer"),
    ("Tall Dog", "µRings SE"),
    ("Tall Dog", "µo_C SE"),
    ("Tenderfoot Electronics", "Morse"),
    ("Verbos Electronics", "Amp & Tone (2020 Version)"),
}
DRUMS = {("2hp", "Hat"), ("Mosaic", "Bass Drum"), ("ST Modular", "DRUM"), ("Manikk", "DRM7")}
CATEGORY_MANIFESTS = sorted((CATALOG / "provenance").glob("category-corrections-v*.json"))


def follows_from_the_function(function: str, category: str, rule: str) -> bool:
    if rule == "decision_17":
        return O.OWNER_TAG_CATEGORY.get(function) == category
    return {category} == O.tag_categories([function]) or B.category([function], "") == category


def test_the_overlay_fills_exactly_the_reviewed_rows() -> None:
    assert {(entry["brand"], entry["name"]): entry["category"] for entry in ENTRIES} == FILLED
    assert OVERLAY["count"] == len(ENTRIES)
    assert len({entry["slug"] for entry in ENTRIES}) == len(ENTRIES)


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e["slug"])
def test_each_row_rests_on_the_makers_document_its_jack_list_came_from(entry) -> None:
    jacks = JACKS[(entry["brand"], entry["name"])]
    assert (entry["source_url"], entry["source_kind"]) == (jacks["source_url"], jacks["source_kind"])
    assert len(entry["content_sha256"]) == 64
    assert entry["basis"] == "jack_list_review"


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e["slug"])
def test_each_category_follows_by_the_catalogs_rule(entry) -> None:
    assert entry["category"] in P.MODULE_CATEGORIES
    assert follows_from_the_function(entry["function"], entry["category"], entry["rule"])


def test_no_quote_from_a_makers_document_is_committed() -> None:
    assert not [entry["slug"] for entry in ENTRIES if "maker_quote" in entry]
    assert "modulargrid" not in json.dumps(ENTRIES).lower()


def test_no_earlier_overlay_fills_these_rows() -> None:
    earlier = {
        entry["slug"]
        for path in (CATALOG / "overlays").glob("module-catalog-category-v*.json")
        if path != OVERLAY_PATH
        for entry in json.loads(path.read_text(encoding="utf-8"))["entries"]
    }
    assert not {entry["slug"] for entry in ENTRIES} & earlier


def test_rows_the_document_does_not_settle_stay_empty_and_are_listed() -> None:
    assert not LEFT_FOR_THE_OWNER & set(FILLED)
    assert LEFT_FOR_THE_OWNER <= set(JACKS)
    for brand, name in LEFT_FOR_THE_OWNER | DRUMS:
        assert f"{brand} {name}" in EVIDENCE, name


def test_the_catalogs_rules_send_a_drum_to_vco_and_there_is_no_drum_category() -> None:
    assert B.category(["drum"], "") == "VCO"
    assert B.category([], "Hat") is None and B.category([], "Hi-Hat") == "VCO"
    assert O.tag_categories(["percussion"]) == O.tag_categories(["kick"]) == {"VCO"}
    assert "DRUM" not in P.MODULE_CATEGORIES


def test_the_four_drums_are_not_changed_here() -> None:
    assert DRUMS <= set(JACKS)
    assert not DRUMS & set(FILLED)
    named = {
        (row["brand"], row["name"])
        for path in CATEGORY_MANIFESTS
        if path.name != "category-corrections-v8.json"
        for row in json.loads(path.read_text(encoding="utf-8")).get("rows") or []
    }
    assert not DRUMS & named
    assert not list((CATALOG / "provenance").glob("category-corrections-v9.json"))


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e["slug"])
def test_a_fill_writes_once_and_never_over_a_stored_category(entry) -> None:
    catalog = {entry["slug"]: {"brand": entry["brand"], "name": entry["name"], "category": None}}
    plan = P.Plan()
    P._schedule_category(plan, catalog, entry)
    assert catalog[entry["slug"]]["category"] == entry["category"]
    assert plan.updates["category_overlay"] == 1 and not plan.conflicts
    P.assert_safe_sql(P.render_plan(plan))

    plan = P.Plan()
    P._schedule_category(plan, catalog, entry)
    assert not plan.ops

    catalog = {entry["slug"]: {"brand": entry["brand"], "name": entry["name"], "category": "ENV"}}
    plan = P.Plan()
    P._schedule_category(plan, catalog, entry)
    assert catalog[entry["slug"]]["category"] == "ENV" and not plan.ops


def test_a_row_stored_under_another_name_is_a_conflict_and_writes_nothing() -> None:
    entry = ENTRIES[0]
    catalog = {entry["slug"]: {"brand": entry["brand"], "name": "Another name", "category": None}}
    plan = P.Plan()
    P._schedule_category(plan, catalog, entry)
    assert [conflict["reason"] for conflict in plan.conflicts] == ["category_overlay_identity_mismatch"]
    assert catalog[entry["slug"]]["category"] is None and not plan.ops


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e["slug"])
def test_a_fill_reaches_the_row_patch_rules_read(entry) -> None:
    key = (entry["brand"], entry["name"])
    catalog = {entry["slug"]: {"brand": entry["brand"], "name": entry["name"], "category": entry["category"]}}
    modules = {
        key: {
            "brand": entry["brand"],
            "name": entry["name"],
            "module_type": P.MODULE_TYPE_PLACEHOLDER,
            "source": P.LOADER_MODULE_SOURCES[0],
            "status": "active",
        }
    }
    plan = P.Plan()
    P._schedule_module_type_sync(plan, catalog, modules)
    assert plan.module_type_sync["synced"] == 1
    assert plan.updates["module_type_from_category"] == 1
