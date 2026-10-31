"""Spec 003 T039 remainder: the v5 HP overlay (2026-10-30, evening).

v5 re-sources the rows still marked ``legacy_unsourced`` after #172 whose maker states
the width on its own page or in its own manual (each entry quotes it). Blocked hosts
(ADDAC System, Befaco, Instruo, Dreadbox) were not worked around. Intellijel's Dixie II
manual states 6 HP, not v1's 8; maker-corrections-v6 fixes stored copies of v1's value.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402

CATALOG = ROOT / "data" / "synth-catalog"
OVERLAYS = CATALOG / "overlays"
PREFIX = 'maker-page-checked-2026-10-30: "'
BLOCKED = ("addac-system-", "befaco-", "instruo-", "dreadbox-")


def _load(name: str) -> dict:
    return json.loads((OVERLAYS / name).read_text(encoding="utf-8"))


def test_v5_quotes_a_maker_source_for_every_entry_in_the_v4_schema() -> None:
    v4, v5 = _load("module-catalog-hp-v4.json"), _load("module-catalog-hp-v5.json")
    assert v5["dataset_version"] == "module-catalog-hp-overlay-v5"
    assert v5["count"] == len(v5["entries"]) == 4
    assert set(v5) == set(v4)
    for entry in v5["entries"]:
        assert set(entry) == set(v4["entries"][0]), entry["slug"]
        assert P._hp_entry_sourced(entry), entry["slug"]
        assert entry["slug"] == P.create_slug(entry["brand"], entry["name"])
        assert not entry["slug"].startswith(BLOCKED)
        assert "?" not in entry["source_url"] and "#" not in entry["source_url"]
        assert entry["verification"].startswith(PREFIX) and entry["verification"].endswith('"')
        quote = entry["verification"][len(PREFIX) : -1]
        assert re.search(rf"(?<!\d){entry['hp']}\s?(HP|hp|TE)\b", quote), entry["slug"]
    assert "module-catalog-hp-v5.json" not in P.UNSOURCED_HP_OVERLAYS


def test_v5_re_sources_only_v1_values_no_earlier_overlay_cites() -> None:
    v1 = {e["slug"]: e for e in _load("module-catalog-hp-v1.json")["entries"]}
    earlier = {
        e["slug"]
        for name in ("module-catalog-hp-v2.json", "module-catalog-hp-v3.json", "module-catalog-hp-v4.json")
        for e in _load(name)["entries"]
    }
    for entry in _load("module-catalog-hp-v5.json")["entries"]:
        old = v1[entry["slug"]]
        assert (old["brand"], old["name"]) == (entry["brand"], entry["name"])
        assert entry["slug"] not in earlier
        expected = 6 if entry["slug"] == "intellijel-dixie-ii" else old["hp"]
        assert entry["hp"] == expected


def test_maker_corrections_v6_fixes_dixie_ii_in_both_tables() -> None:
    path = CATALOG / "provenance" / "maker-corrections-v6.json"
    manifest = json.loads(path.read_text())
    assert P.PROVENANCE_MANIFESTS[-1] == path and manifest["flag_reverify"] is False
    assert {(row["table"], row["name"]) for row in manifest["rows"]} == {
        ("module_catalog", "Dixie II"), ("modules", "Dixie II"),
    }
    v5 = {e["slug"]: e for e in _load("module-catalog-hp-v5.json")["entries"]}
    for row in manifest["rows"]:
        (item,) = row["fields"]
        assert (item["field"], item["action"], item["only_if_value"], item["value"]) == ("hp", "correct", 8, 6)
        assert item["evidence_url"] == v5["intellijel-dixie-ii"]["source_url"]
        assert P._correction_problem(row["table"], item) is None


def test_v5_slugs_lose_their_marker_once() -> None:
    overlays = [(p.name, json.loads(p.read_text())) for p in sorted(OVERLAYS.glob("module-catalog-hp-v*.json"))]
    v1 = {e["slug"]: e for e in _load("module-catalog-hp-v1.json")["entries"]}
    v5 = {e["slug"]: e for e in _load("module-catalog-hp-v5.json")["entries"]}
    # A database loaded before v5, after maker-corrections-v6 has run: each row holds v5's value.
    catalog = {
        slug: {"brand": v1[slug]["brand"], "name": v1[slug]["name"], "hp": v5[slug]["hp"], "hp_source": P.HP_SOURCE_LEGACY}
        for slug in v5
    }
    plan = P.Plan()
    P._schedule_hp_source_markers(plan, catalog, overlays)
    assert plan.updates == {"hp_source_legacy_cleared": len(v5)}
    again = P.Plan()
    P._schedule_hp_source_markers(again, catalog, overlays)
    assert again.ops == []


def test_v6_fills_the_golden_cockpit_from_the_same_maker_page() -> None:
    v5 = {e["slug"]: e for e in _load("module-catalog-hp-v5.json")["entries"]}
    v6 = _load("module-catalog-hp-v6.json")
    assert v6["count"] == len(v6["entries"]) == 1 and set(v6) == set(_load("module-catalog-hp-v5.json"))
    (entry,) = v6["entries"]
    black = v5["endorphin-es-cockpit-black"]
    assert set(entry) == set(black)
    assert (entry["slug"], entry["hp"]) == ("endorphin-es-cockpit-golden", 6)
    assert entry["slug"] == P.create_slug(entry["brand"], entry["name"])
    # One maker page offers both colours and states the width once.
    assert entry["source_url"] == black["source_url"] and entry["verification"] == black["verification"]
    assert "GOLDEN" in entry["verification"] and P._hp_entry_sourced(entry)
    # The golden row is not a v1 value: modulargrid-provenance-v1 nulled it and nothing refilled it.
    v1 = {e["slug"] for e in _load("module-catalog-hp-v1.json")["entries"]}
    assert entry["slug"] not in v1
    overlays = [(p.name, json.loads(p.read_text())) for p in sorted(OVERLAYS.glob("module-catalog-hp-v*.json"))]
    catalog = {entry["slug"]: {"brand": entry["brand"], "name": entry["name"], "hp": None}}
    plan = P.Plan()
    P._schedule_hp_overlays(plan, catalog, overlays)
    assert [(op.params["slug"], op.params["hp"]) for op in plan.ops] == [("endorphin-es-cockpit-golden", 6)]
