"""Spec 003 FR-034: a lead becomes canonical only through its maker's page, recorded with the URL."""

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


def load(*parts: str) -> dict:
    return json.loads(CATALOG.joinpath(*parts).read_text(encoding="utf-8"))


PROMOTED = load("overlays", "lead-promotions-v1.json")["rows"]
FILLS = load("overlays", "module-catalog-category-v7.json")["entries"]
CORRECTIONS = load("provenance", "category-corrections-v5.json")["rows"]
WIDTHS = load("provenance", "hp-footer-corrections-v1.json")["rows"]


def lead(**extra) -> dict:
    return {"brand": "Acme", "name": "Lead", "source": "CatalogCandidate", "access_basis": "unknown", **extra}


def entry(**extra) -> dict:
    return {"slug": "acme-lead", "brand": "Acme", "name": "Lead", "source_url": "https://acme.example/lead", **extra}


def schedule(catalog: dict, *entries: dict) -> P.Plan:
    plan = P.Plan()
    P._schedule_lead_promotions(plan, catalog, {"rows": list(entries)})
    return plan


def test_a_lead_with_a_maker_page_is_confirmed_and_records_the_url() -> None:
    catalog = {"acme-lead": lead()}
    plan = schedule(catalog, entry())
    assert catalog["acme-lead"]["access_basis"] == "official_publication"
    assert catalog["acme-lead"]["manufacturer_url"] == "https://acme.example/lead"
    assert plan.lead_promotions["promoted"] == 1
    assert plan.updates == {"lead_promoted": 1}
    assert plan.inserts == {"catalog_value_archive": 1}


def test_a_stored_maker_url_is_kept() -> None:
    catalog = {"acme-lead": lead(manufacturer_url="https://acme.example/old")}
    schedule(catalog, entry())
    assert catalog["acme-lead"]["manufacturer_url"] == "https://acme.example/old"


@pytest.mark.parametrize(
    "extra,reason",
    [
        ({"source_url": "http://acme.example/lead"}, "lead_promotion_needs_maker_page"),
        ({"source_url": "https://www.modulargrid.net/e/acme-lead"}, "lead_promotion_needs_maker_page"),
        ({"source_url": None}, "lead_promotion_needs_maker_page"),
        ({"name": "Other"}, "lead_promotion_identity_mismatch"),
    ],
)
def test_a_bad_entry_is_a_conflict_and_changes_nothing(extra, reason) -> None:
    catalog = {"acme-lead": lead()}
    plan = schedule(catalog, entry(**extra))
    assert plan.conflicts_total == 1 and plan.conflicts[0]["reason"] == reason
    assert catalog["acme-lead"]["access_basis"] == "unknown" and not plan.ops


def test_only_a_lead_can_be_promoted() -> None:
    catalog = {"acme-lead": lead(source="ManufacturerCrawl")}
    plan = schedule(catalog, entry())
    assert plan.conflicts[0]["reason"] == "lead_promotion_not_a_lead"
    assert catalog["acme-lead"]["access_basis"] == "unknown"


@pytest.mark.parametrize(
    "row,counter",
    [
        (lead(access_basis="official_publication"), "already_confirmed"),
        (lead(tombstoned=True), "refused_row_tombstoned"),
    ],
)
def test_a_settled_or_retired_row_is_left_alone(row, counter) -> None:
    plan = schedule({"acme-lead": row}, entry())
    assert plan.lead_promotions[counter] == 1 and not plan.ops


def test_a_row_the_database_doesnt_hold_is_counted() -> None:
    assert schedule({}, entry()).lead_promotions["rows_missing"] == 1


@pytest.mark.parametrize("row", PROMOTED, ids=lambda r: r["slug"])
def test_each_promotion_cites_the_makers_page_and_a_short_quote(row) -> None:
    assert row["source_url"].startswith("https://")
    assert "modulargrid" not in json.dumps(row).lower() and "manualslib" not in json.dumps(row).lower()
    assert 0 < len(row["maker_quote"]) <= 170
    assert len(row["content_sha256"]) == 64


def test_a_promotion_names_each_row_once() -> None:
    assert len({row["slug"] for row in PROMOTED}) == len(PROMOTED)


def test_refused_or_unconfirmed_makers_are_not_promoted() -> None:
    assert not [row["slug"] for row in PROMOTED if row["brand"] in {"Befaco", "Dreadbox", "Instruo"}]
    held = {"intellijel-att", "doepfer-a-101-4", "doepfer-a-170-2", "expert-sleepers-disting-mk1"}
    assert not held & {row["slug"] for row in PROMOTED}


def follows(does: str, category: str, rule: str) -> bool:
    if rule == "decision_14":
        return category == "SYSTEM"
    low = does.lower()
    return {category} == (O.tag_categories([low]) or O.tag_categories([low.rstrip("s")])) or (
        B.category([does], does) == category or (low in ("modulation", "modulator") and category == "LFO")
    )


@pytest.mark.parametrize("entry_", FILLS, ids=lambda e: e["slug"])
def test_each_fill_follows_from_the_makers_words(entry_) -> None:
    assert entry_["does"].lower() in entry_["maker_quote"].lower()
    assert follows(entry_["does"], entry_["category"], entry_["rule"])


@pytest.mark.parametrize("table,field", [("module_catalog", "category"), ("modules", "module_type")])
def test_each_category_correction_covers_its_table_and_cites_its_page(table, field) -> None:
    rows = [row for row in CORRECTIONS if row["table"] == table]
    assert len(rows) == 37
    for row in rows:
        item = row["fields"][0]
        assert item["field"] == field and item["evidence_url"].startswith("https://")
        assert item["only_if_value"] != item["value"] and item["value"] in P.MODULE_CATEGORIES


def test_a_page_footer_width_is_replaced_by_the_width_the_page_states() -> None:
    catalog_rows = [row for row in WIDTHS if row["table"] == "module_catalog"]
    assert len(catalog_rows) == 15 and len(WIDTHS) == 30
    for row in WIDTHS:
        item = row["fields"][0]
        assert (item["field"], item["only_if_value"]) == ("hp", 104)
        assert 2 <= item["value"] <= 24 and item["evidence_url"].startswith("https://afterlateraudio.com/")


def test_a_101_4_is_no_longer_confirmed_by_the_a_110_4_page() -> None:
    entries = load("overlays", "module-catalog-hp-v8.json")["entries"]
    assert "doepfer-a-101-4" not in {entry_["slug"] for entry_ in entries}
