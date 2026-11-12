"""Reviewed corrections of 2026-11-08: Doepfer A-138m's width and six Analogue Systems types (FR-038)."""

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

WIDTH_PATH = CATALOG / "provenance" / "maker-corrections-v8.json"
TYPES_PATH = CATALOG / "provenance" / "category-corrections-v8.json"
WIDTH = json.loads(WIDTH_PATH.read_text(encoding="utf-8"))
TYPES = json.loads(TYPES_PATH.read_text(encoding="utf-8"))
RECEIPT = json.loads((CATALOG / "receipts" / "free-reads-2026-11-08.json").read_text(encoding="utf-8"))

MAKER_PAGES = "https://www.analoguesystems.co.uk/index.php/as-modules/"
CORRECTED = {
    "RS-20": ("LFO", "FX"),
    "RS-70": ("ENV", "UTIL"),
    "RS-85": ("VCO", "LFO"),
    "RS-380": ("SAMP", "LFO"),
    "RS-380N": ("SAMP", "LFO"),
    "RS-610N Dual Ring Modulator": ("LFO", "FX"),
}
# Read and left as they are: the page doesn't settle one category (see the evidence record).
LEFT_FOR_THE_OWNER = {"RS-35", "RS-35N", "RS-250", "RS-260", "RS-420"}
LEFT_TWO_FUNCTIONS = {"RS-295", "RS-510e", "RS-510N Synthishaper", "RS-600"}


def _state(name: str, stored: str) -> tuple[dict, dict]:
    slug = next(row["slug"] for row in TYPES["rows"] if row["name"] == name and row["table"] == "module_catalog")
    catalog = {slug: {"brand": "Analogue Systems", "name": name, "category": stored}}
    modules = {("Analogue Systems", name): {"brand": "Analogue Systems", "name": name, "module_type": stored, "_duplicate": False}}
    return catalog, modules


def test_each_manifest_runs_in_the_list_its_field_needs() -> None:
    assert WIDTH_PATH in P.PROVENANCE_MANIFESTS
    assert TYPES_PATH in P.CATEGORY_CORRECTION_MANIFESTS
    assert TYPES_PATH not in P.PROVENANCE_MANIFESTS


def test_a138m_corrects_the_modules_row_from_doepfers_stated_width() -> None:
    assert WIDTH["flag_reverify"] is False
    assert [(row["table"], row["brand"], row["name"]) for row in WIDTH["rows"]] == [("modules", "Doepfer", "A-138m")]
    item = WIDTH["rows"][0]["fields"][0]
    assert (item["field"], item["action"], item["only_if_value"], item["value"]) == ("hp", "correct", 8, 20)
    assert item["evidence_url"] == "https://doepfer.de/A138m.htm"
    assert "20 TE/HP" in item["source_tag"]


@pytest.mark.parametrize(("stored", "written"), [(8, 20), (12, 12)])
def test_a138m_is_only_corrected_over_the_value_that_was_reviewed(stored: int, written: int) -> None:
    modules = {("Doepfer", "A-138m"): {"brand": "Doepfer", "name": "A-138m", "hp": stored, "_duplicate": False}}
    plan = P.Plan()
    P._schedule_provenance(plan, {}, modules, WIDTH, set())
    assert modules[("Doepfer", "A-138m")]["hp"] == written
    assert plan.provenance["maker-corrections-v8"]["corrected_values"] == int(stored == 8)
    assert plan.provenance["maker-corrections-v8"]["value_not_matched"] == int(stored != 8)
    P.assert_safe_sql(P.render_plan(plan))


def test_the_other_a138_modules_stay_separate_products() -> None:
    assert {row["name"] for row in WIDTH["rows"]} == {"A-138m"}
    retired = [
        row["name"]
        for path in sorted((CATALOG / "overlays").glob("catalog-retirements-v*.json"))
        for row in json.loads(path.read_text(encoding="utf-8")).get("rows") or []
        if row.get("brand") == "Doepfer"
    ]
    assert not [name for name in retired if name.startswith("A-138")]


def test_each_type_is_corrected_in_both_tables_from_the_makers_page() -> None:
    assert TYPES["flag_reverify"] is False
    seen: dict[str, set[str]] = {}
    for row in TYPES["rows"]:
        old, new = CORRECTED[row["name"]]
        assert row["brand"] == "Analogue Systems"
        assert len(row["fields"]) == 1
        item = row["fields"][0]
        assert item["field"] == {"module_catalog": "category", "modules": "module_type"}[row["table"]]
        assert (item["action"], item["only_if_value"], item["value"]) == ("correct", old, new)
        assert new in P.MODULE_CATEGORIES
        assert item["evidence_url"].startswith(MAKER_PAGES)
        assert item["evidence_url"] in item["source_tag"]
        seen.setdefault(row["name"], set()).add(row["table"])
    assert seen == {name: {"module_catalog", "modules"} for name in CORRECTED}
    assert "modulargrid" not in json.dumps(TYPES).lower()


@pytest.mark.parametrize("name", sorted(CORRECTED))
def test_a_correction_writes_only_over_the_reviewed_value(name: str) -> None:
    old, new = CORRECTED[name]
    catalog, modules = _state(name, old)
    plan = P.Plan()
    P._schedule_provenance(plan, catalog, modules, {**TYPES, "rows": [r for r in TYPES["rows"] if r["name"] == name]}, set())
    assert next(iter(catalog.values()))["category"] == new
    assert modules[("Analogue Systems", name)]["module_type"] == new
    assert not plan.conflicts

    catalog, modules = _state(name, "VCA")
    plan = P.Plan()
    P._schedule_provenance(plan, catalog, modules, {**TYPES, "rows": [r for r in TYPES["rows"] if r["name"] == name]}, set())
    assert next(iter(catalog.values()))["category"] == "VCA"
    assert plan.provenance["category-corrections-v8"]["value_not_matched"] == 2


def test_the_new_category_follows_from_the_makers_words_by_the_catalogs_rule() -> None:
    assert O.tag_categories(["ring modulator"]) == {"FX"}
    assert O.tag_categories(["inverter"]) == O.tag_categories(["preamp"]) == {"UTIL"}
    assert O.tag_categories(["s&h"]) == {"LFO"}
    assert B.category(["vc-lfo"], "") == "LFO"


def test_rows_the_page_does_not_settle_are_left_alone() -> None:
    touched = {row["name"] for row in TYPES["rows"]}
    assert not touched & (LEFT_FOR_THE_OWNER | LEFT_TWO_FUNCTIONS)


def test_the_reads_paid_for_nothing_and_kept_no_page_text() -> None:
    assert RECEIPT["paid_attempts"] == 0
    assert all(set(row) == {"url", "ok", "status", "method", "sha256", "timestamp"} for row in RECEIPT["reads"])
    assert not any("modulargrid" in row["url"] for row in RECEIPT["reads"])
    read = {row["url"] for row in RECEIPT["reads"] if row["ok"]}
    assert "https://doepfer.de/A138m.htm" in read
    assert {item["evidence_url"] for row in TYPES["rows"] for item in row["fields"]} <= read
