"""A maker-cited HP overlay wins over the unsourced legacy v1 overlay on a fill (D3).

v1 sorts first, and HP is fill-null, so before this fix a v1 value landed on every
slug both overlays carry. The maker value must land instead, v1 must still fill
where no maker entry exists, and a stored HP must never be overwritten.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402

OVERLAYS = ROOT / "data" / "synth-catalog" / "overlays"


def _real_overlays() -> list[tuple[str, dict]]:
    paths = sorted(OVERLAYS.glob("module-catalog-hp-v*.json"))
    return [(path.name, json.loads(path.read_text(encoding="utf-8"))) for path in paths]


def _empty_catalog(overlays: list[tuple[str, dict]]) -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    for _, overlay in overlays:
        for entry in overlay["entries"]:
            catalog[entry["slug"]] = {"brand": entry["brand"], "name": entry["name"], "hp": None}
    return catalog


def _hp_writes(plan: P.Plan) -> dict[str, int]:
    return {op.params["slug"]: op.params["hp"] for op in plan.ops}


def test_on_a_fresh_load_the_maker_value_wins_over_v1() -> None:
    overlays = _real_overlays()
    assert [name for name, _ in overlays][:2] == [
        "module-catalog-hp-v1.json",
        "module-catalog-hp-v2.json",
    ]
    catalog = _empty_catalog(overlays)
    plan = P.Plan()
    P._schedule_hp_overlays(plan, catalog, overlays)

    writes = _hp_writes(plan)
    # The disagreeing slugs take the maker-page value (hand-checked 2026-10-29).
    assert writes["acid-rain-technology-junction"] == 4
    assert writes["alm-busy-circuits-akemie-s-castle"] == 38
    assert writes["doepfer-a-101-3"] == 30
    assert writes["doepfer-a-137-2"] == 14
    assert writes["doepfer-a-101-9"] == 8
    # One write per slug: v1 never adds a second fill for a superseded slug.
    assert len(plan.ops) == len(writes) == plan.updates["hp_overlay"]
    assert plan.conflicts_total == 0


def test_v1_still_fills_where_no_maker_entry_exists() -> None:
    overlays = _real_overlays()
    sourced = {
        e["slug"]
        for name, o in overlays
        if name != "module-catalog-hp-v1.json"
        for e in o["entries"]
    }
    v1 = dict(overlays)["module-catalog-hp-v1.json"]["entries"]
    v1_only = [e for e in v1 if e["slug"] not in sourced]
    assert v1_only
    catalog = _empty_catalog(overlays)
    plan = P.Plan()
    P._schedule_hp_overlays(plan, catalog, overlays)
    writes = _hp_writes(plan)
    for entry in v1_only:
        assert writes[entry["slug"]] == entry["hp"]


def _synthetic(v1_hp: int, v2_hp: int, stored: int | None):
    ident = {"slug": "acme-vco", "brand": "Acme", "name": "VCO"}
    overlays = [
        (
            "module-catalog-hp-v1.json",
            {
                "entries": [
                    {**ident, "hp": v1_hp, "source_class": "unknown_non_modulargrid"},
                    {"slug": "acme-lfo", "brand": "Acme", "name": "LFO", "hp": 4},
                ]
            },
        ),
        (
            "module-catalog-hp-v2.json",
            {
                "entries": [
                    {
                        **ident,
                        "hp": v2_hp,
                        "source_class": "maker",
                        "source_url": "https://acme.example/vco",
                    }
                ]
            },
        ),
    ]
    catalog = {
        "acme-vco": {"brand": "Acme", "name": "VCO", "hp": stored},
        "acme-lfo": {"brand": "Acme", "name": "LFO", "hp": None},
    }
    plan = P.Plan()
    P._schedule_hp_overlays(plan, catalog, overlays)
    return plan, catalog


def test_maker_wins_and_v1_fills_the_rest() -> None:
    plan, catalog = _synthetic(10, 14, stored=None)
    assert catalog["acme-vco"]["hp"] == 14
    assert catalog["acme-lfo"]["hp"] == 4
    assert _hp_writes(plan) == {"acme-vco": 14, "acme-lfo": 4}


def test_a_stored_hp_is_never_overwritten() -> None:
    plan, catalog = _synthetic(10, 14, stored=10)
    assert catalog["acme-vco"]["hp"] == 10
    assert "acme-vco" not in _hp_writes(plan)
    assert plan.conflicts_total == 0


def test_an_unsourced_entry_in_a_later_overlay_does_not_supersede_v1() -> None:
    ident = {"slug": "acme-vco", "brand": "Acme", "name": "VCO"}
    overlays = [
        ("module-catalog-hp-v1.json", {"entries": [{**ident, "hp": 10}]}),
        (
            "module-catalog-hp-v2.json",
            {"entries": [{**ident, "hp": 14, "source_class": "maker_or_retail"}]},
        ),
    ]
    catalog = {"acme-vco": {"brand": "Acme", "name": "VCO", "hp": None}}
    plan = P.Plan()
    P._schedule_hp_overlays(plan, catalog, overlays)
    assert catalog["acme-vco"]["hp"] == 10
    assert [c["reason"] for c in plan.conflicts] == ["hp_overlay_unsourced"]
