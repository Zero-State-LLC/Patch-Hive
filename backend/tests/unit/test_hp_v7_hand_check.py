"""Spec 003 OQ-2: the maker-vs-v1 HP disagreements, checked by hand (2026-11-02).

Each maker page or manual states the width the databases already hold, so v1's value
was the wrong one. v7 quotes the maker for each; it fills only empty rows and a fresh
load takes its value, never v1's. ALM Akemie's Castle stays unconfirmed (no width on
the product page; the manual host answered with a bot check).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402

OVERLAYS = ROOT / "data" / "synth-catalog" / "overlays"
PREFIX = 'maker-page-checked-2026-11-02: "'
# Maker value per slug, as staging and production store it (checked 2026-11-02).
EXPECTED = {
    "befaco-hexmix-vca": 14,
    "intellijel-quadrax": 14,
    "intellijel-rubicon-2": 20,
    "erica-synths-fusion-vco": 24,
    "doepfer-a-110-1": 10,
    "joranalogue-generate-3": 12,
    "joranalogue-audio-design-generate-3": 12,
    "qu-bit-electronix-chord-v2": 14,
    "qu-bit-electronix-data-bender": 14,
}


def _load(name: str) -> dict:
    return json.loads((OVERLAYS / name).read_text(encoding="utf-8"))


def test_v7_quotes_a_maker_source_for_each_disagreement() -> None:
    v5, v7 = _load("module-catalog-hp-v5.json"), _load("module-catalog-hp-v7.json")
    assert v7["dataset_version"] == "module-catalog-hp-overlay-v7"
    assert set(v7) == set(v5)
    assert v7["count"] == len(v7["entries"])
    assert {e["slug"]: e["hp"] for e in v7["entries"]} == EXPECTED
    for entry in v7["entries"]:
        assert set(entry) == set(v5["entries"][0]), entry["slug"]
        assert P._hp_entry_sourced(entry), entry["slug"]
        assert entry["slug"] == P.create_slug(entry["brand"], entry["name"])
        assert entry["verification"].startswith(PREFIX) and entry["verification"].endswith('"')
        assert str(entry["hp"]) in entry["verification"]


def test_v1_held_a_different_value_for_every_checked_module() -> None:
    v1 = {e["slug"]: e["hp"] for e in _load("module-catalog-hp-v1.json")["entries"]}
    for slug, hp in EXPECTED.items():
        if slug in v1:
            assert v1[slug] != hp, slug


def test_a_fresh_load_takes_the_maker_value_not_v1() -> None:
    overlays = [(p.name, json.loads(p.read_text())) for p in sorted(OVERLAYS.glob("module-catalog-hp-v*.json"))]
    v7 = {e["slug"]: e for e in _load("module-catalog-hp-v7.json")["entries"]}
    catalog = {slug: {"brand": e["brand"], "name": e["name"], "hp": None} for slug, e in v7.items()}
    plan = P.Plan()
    P._schedule_hp_overlays(plan, catalog, overlays)
    assert {op.params["slug"]: op.params["hp"] for op in plan.ops} == EXPECTED


def test_v7_changes_nothing_a_database_already_holds() -> None:
    overlays = [(p.name, json.loads(p.read_text())) for p in sorted(OVERLAYS.glob("module-catalog-hp-v*.json"))]
    v7 = {e["slug"]: e for e in _load("module-catalog-hp-v7.json")["entries"]}
    catalog = {slug: {"brand": e["brand"], "name": e["name"], "hp": e["hp"], "hp_source": None} for slug, e in v7.items()}
    plan = P.Plan()
    P._schedule_hp_overlays(plan, catalog, overlays)
    P._schedule_hp_source_markers(plan, catalog, overlays)
    assert plan.ops == []
