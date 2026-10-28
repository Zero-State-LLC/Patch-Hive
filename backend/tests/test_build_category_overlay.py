"""Category overlay (fill missing module_catalog categories from maker crawl tags)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import build_category_overlay as c  # noqa: E402
import population as P  # noqa: E402

OVERLAY = ROOT / "data" / "synth-catalog" / "overlays" / "module-catalog-category-v1.json"
CATEGORIES = {"VCO", "VCF", "VCA", "ENV", "LFO", "MIX", "FX", "SEQ", "UTIL", "SAMP", "MIDI"}


@pytest.mark.parametrize(
    "tags,expected",
    [
        (["low pass gate", "vactrol", "Buchla"], ("VCA", "crawl_tag")),
        (["chaos", "divider"], ("LFO", "crawl_tag")),
        (["mute", "quad"], ("UTIL", "crawl_tag")),
        (["drive", "EQ"], ("FX", "crawl_tag")),
        (["controller"], ("SEQ", "crawl_tag")),
        # Two whole tags that point to different categories: left empty.
        (["expander", "random"], None),
        # A word inside a longer tag is not a match.
        (["noise reduction"], None),
        (["cv", "stereo"], None),
    ],
)
def test_classify_uses_whole_tags_and_leaves_ambiguity_empty(tags, expected) -> None:
    assert c.classify(tags, "Widget", "") == expected


def test_existing_rules_win_over_tag_rules() -> None:
    assert c.classify(["filter", "random"], "Widget", "") == ("VCF", "crawl_tags_or_name")


def test_url_path_is_used_when_tags_and_name_say_nothing() -> None:
    assert c.classify([], "Widget", "https://maker.example/modules/filters/widget") == ("VCF", "source_url_path")


def test_committed_overlay_uses_existing_categories_and_names_unique_rows() -> None:
    data = json.loads(OVERLAY.read_text())
    entries = data["entries"]
    assert data["count"] == len(entries) > 0
    assert {e["category"] for e in entries} <= CATEGORIES
    assert len({e["slug"] for e in entries}) == len(entries)
    assert all(e["source_url"] and e["brand"] and e["name"] for e in entries)
    assert "modulargrid" not in json.dumps(entries).lower()


def _plan_with(catalog: dict, entry: dict) -> P.Plan:
    plan = P.Plan()
    P._schedule_category(plan, catalog, entry)
    return plan


def test_loader_fills_only_a_missing_category() -> None:
    catalog = {"acme-gate": {"brand": "Acme", "name": "Gate", "hp": 4, "category": None}}
    plan = _plan_with(catalog, {"slug": "acme-gate", "brand": "Acme", "name": "Gate", "category": "VCA"})
    assert catalog["acme-gate"]["category"] == "VCA"
    assert plan.updates == {"category_overlay": 1}
    assert "category IS NULL" in plan.ops[0].sql

    again = _plan_with(catalog, {"slug": "acme-gate", "brand": "Acme", "name": "Gate", "category": "FX"})
    assert catalog["acme-gate"]["category"] == "VCA"
    assert again.ops == []


def test_loader_flags_identity_mismatch_and_counts_unmatched() -> None:
    catalog = {"acme-gate": {"brand": "Acme", "name": "Gate", "hp": 4, "category": None}}
    mismatch = _plan_with(catalog, {"slug": "acme-gate", "brand": "Acme", "name": "Other", "category": "VCA"})
    assert mismatch.conflicts and mismatch.conflicts[0]["reason"] == "category_overlay_identity_mismatch"
    assert catalog["acme-gate"]["category"] is None

    missing = _plan_with(catalog, {"slug": "nope", "brand": "Acme", "name": "Nope", "category": "VCA"})
    assert missing.unmatched == {"category": 1}
    assert missing.ops == []
