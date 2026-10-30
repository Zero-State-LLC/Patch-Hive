"""Spec 003 T039 remainder: the v4 HP overlay (2026-10-30).

v4 re-sources values still marked ``legacy_unsourced`` after #164 where a plain GET of
the maker's own page names that exact product and states its width (each entry quotes
it). ADDAC System and Befaco were not fetched (bot challenge, CAPTCHA). Where the page
states another width (Doepfer A-106-1 and A-138m), v4 carries the page value and
maker-corrections-v4 fixes stored copies of v1's.
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
CORRECTED = {"doepfer-a-106-1": 14, "doepfer-a-138m": 20}
PREFIX = 'maker-page-checked-2026-10-30: "'


def _load(name: str) -> dict:
    return json.loads((OVERLAYS / name).read_text(encoding="utf-8"))


def _all_overlays() -> list[tuple[str, dict]]:
    return [
        (p.name, json.loads(p.read_text()))
        for p in sorted(OVERLAYS.glob("module-catalog-hp-v*.json"))
    ]


def test_v4_quotes_a_maker_page_for_every_entry_in_the_v3_schema() -> None:
    v3, v4 = _load("module-catalog-hp-v3.json"), _load("module-catalog-hp-v4.json")
    assert v4["dataset_version"] == "module-catalog-hp-overlay-v4"
    assert v4["count"] == len(v4["entries"]) == 26
    assert set(v4) == set(v3)
    slugs = [e["slug"] for e in v4["entries"]]
    assert len(slugs) == len(set(slugs))
    for entry in v4["entries"]:
        assert set(entry) == set(v3["entries"][0]), entry["slug"]
        assert P._hp_entry_sourced(entry), entry["slug"]
        assert "?" not in entry["source_url"] and "#" not in entry["source_url"]
        assert P.HP_BAND[0] <= entry["hp"] <= P.HP_BAND[1]
        assert entry["provenance"] == "OBSERVED"
        assert entry["slug"] == P.create_slug(entry["brand"], entry["name"])
        # Every entry quotes its page, and the quote states the entry's width.
        assert entry["verification"].startswith(PREFIX) and entry["verification"].endswith('"')
        quote = entry["verification"][len(PREFIX) : -1]
        assert re.search(rf"(?<!\d){entry['hp']}\s?(HP|hp|TE)\b", quote), entry["slug"]
    assert "module-catalog-hp-v4.json" not in P.UNSOURCED_HP_OVERLAYS


def test_v4_re_sources_only_v1_values_that_v2_and_v3_leave_uncited() -> None:
    v1 = {e["slug"]: e for e in _load("module-catalog-hp-v1.json")["entries"]}
    earlier = {
        e["slug"]
        for name in ("module-catalog-hp-v2.json", "module-catalog-hp-v3.json")
        for e in _load(name)["entries"]
    }
    for entry in _load("module-catalog-hp-v4.json")["entries"]:
        old = v1[entry["slug"]]
        assert (old["brand"], old["name"]) == (entry["brand"], entry["name"])
        assert entry["slug"] not in earlier
        # Blocked hosts were never fetched (no route around a block).
        assert not entry["slug"].startswith(("addac-system-", "befaco-"))
        if entry["slug"] in CORRECTED:
            assert entry["hp"] == CORRECTED[entry["slug"]] != old["hp"]
        else:
            assert entry["hp"] == old["hp"]
    v4 = {e["slug"] for e in _load("module-catalog-hp-v4.json")["entries"]}
    # Still marked: the page names another product, version or nothing (A-101-4, legacy
    # Intellijel pages), contradicts itself (D-LFO), states no HP (Strega), or states a
    # width outside the FR-007 band that no manifest may write (A-155 is 50 HP).
    assert not v4 & {
        "doepfer-a-101-4",
        "doepfer-a-155",
        "cwejman-d-lfo",
        "intellijel-att",
        "make-noise-strega",
        "endorphin-es-cockpit-black",
    }


def test_a_fresh_load_takes_the_v4_page_values_once() -> None:
    overlays = _all_overlays()
    catalog = {
        e["slug"]: {"brand": e["brand"], "name": e["name"], "hp": None}
        for _, o in overlays
        for e in o["entries"]
    }
    plan = P.Plan()
    P._schedule_hp_overlays(plan, catalog, overlays)
    writes = {op.params["slug"]: op.params["hp"] for op in plan.ops}
    assert {slug: writes[slug] for slug in CORRECTED} == CORRECTED
    assert len(writes) == len(plan.ops) and plan.conflicts_total == 0


def test_no_v4_slug_is_marked_and_a_stale_marker_is_cleared() -> None:
    overlays = _all_overlays()
    v1 = {e["slug"]: e for e in _load("module-catalog-hp-v1.json")["entries"]}
    v4 = {e["slug"]: e for e in _load("module-catalog-hp-v4.json")["entries"]}
    # A database loaded before v4: every v4 slug holds v1's value and the marker.
    catalog = {
        slug: {
            "brand": v1[slug]["brand"],
            "name": v1[slug]["name"],
            "hp": v1[slug]["hp"],
            "hp_source": P.HP_SOURCE_LEGACY,
        }
        for slug in v4
    }
    plan = P.Plan()
    P._schedule_hp_source_markers(plan, catalog, overlays)
    assert plan.updates == {"hp_source_legacy_cleared": len(v4)}
    assert all(row["hp_source"] is None for row in catalog.values())
    again = P.Plan()
    P._schedule_hp_source_markers(again, catalog, overlays)
    assert again.ops == []
