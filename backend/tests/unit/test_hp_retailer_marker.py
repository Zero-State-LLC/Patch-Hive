"""Spec 003 T039: retailer evidence for the rows still marked ``legacy_unsourced``.

One-off manual retailer lookups (D2, FR-006) never fill or change HP. Owner decision
2026-11-01: a quoted retailer page that states the stored HP moves the row's marker to
``retailer_observed``; a page that disagrees leaves ``legacy_unsourced``. A maker
source still clears either marker.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402

V1 = "module-catalog-hp-v1.json"


def _entry(name: str, hp: int, **extra) -> dict:
    return {"slug": P.create_slug("Acme", name), "brand": "Acme", "name": name, "hp": hp, **extra}


def _retailer(name: str, hp: int, **extra) -> dict:
    fields = {
        "source_class": "retailer",
        "evidence_status": "RETAILER_OBSERVED",
        "source_url": f"https://shop.example/{name.lower()}",
        "quote": f"Width: {hp} HP",
    }
    return _entry(name, hp, **{**fields, **extra})


def _catalog(marker: str | None = P.HP_SOURCE_LEGACY) -> dict:
    return {
        P.create_slug("Acme", name): {"brand": "Acme", "name": name, "hp": hp, "hp_source": marker}
        for name, hp in (("Agree", 8), ("Differ", 4), ("Unseen", 6))
    }


LEGACY = [(V1, {"entries": [_entry("Agree", 8), _entry("Differ", 4), _entry("Unseen", 6)]})]


def test_agreeing_retailer_page_moves_the_marker_and_the_rest_stay() -> None:
    catalog = _catalog()
    retailer = P._retailer_hp_index({"entries": [_retailer("Agree", 8), _retailer("Differ", 6)]})
    plan = P.Plan()
    P._schedule_hp_source_markers(plan, catalog, LEGACY, retailer_hp=retailer)
    assert plan.updates == {"hp_source_retailer_marked": 1}
    assert {s: r["hp_source"] for s, r in catalog.items()} == {
        "acme-agree": P.HP_SOURCE_RETAILER,
        "acme-differ": P.HP_SOURCE_LEGACY,
        "acme-unseen": P.HP_SOURCE_LEGACY,
    }
    assert all(r["hp"] == {"acme-agree": 8, "acme-differ": 4, "acme-unseen": 6}[s] for s, r in catalog.items())
    (op,) = plan.ops
    assert op.params["previous"] == P.HP_SOURCE_LEGACY and op.params["hp"] == 8
    again = P.Plan()
    P._schedule_hp_source_markers(again, catalog, LEGACY, retailer_hp=retailer)
    assert again.ops == []


def test_fresh_rows_are_marked_straight_to_the_right_value() -> None:
    catalog = _catalog(marker=None)
    plan = P.Plan()
    P._schedule_hp_source_markers(plan, catalog, LEGACY, retailer_hp={"acme-agree": 8})
    assert plan.updates == {"hp_source_retailer_marked": 1, "hp_source_legacy_marked": 2}
    assert catalog["acme-agree"]["hp_source"] == P.HP_SOURCE_RETAILER


def test_a_maker_source_still_clears_a_retailer_marker() -> None:
    catalog = _catalog()
    catalog["acme-agree"]["hp_source"] = P.HP_SOURCE_RETAILER
    maker = ("module-catalog-hp-v9.json", {"entries": [_entry(
        "Agree", 8, source_class="maker", source_url="https://acme.example/agree")]})
    plan = P.Plan()
    P._schedule_hp_source_markers(plan, catalog, [*LEGACY, maker], retailer_hp={"acme-agree": 8})
    assert plan.updates == {"hp_source_retailer_cleared": 1}
    assert catalog["acme-agree"]["hp_source"] is None


def test_a_retailer_marker_whose_page_is_withdrawn_returns_to_legacy() -> None:
    catalog = _catalog()
    catalog["acme-agree"]["hp_source"] = P.HP_SOURCE_RETAILER
    plan = P.Plan()
    P._schedule_hp_source_markers(plan, catalog, LEGACY, retailer_hp={})
    assert plan.updates == {"hp_source_legacy_marked": 1}
    assert catalog["acme-agree"]["hp_source"] == P.HP_SOURCE_LEGACY


def test_unquoted_or_non_https_retailer_entries_are_ignored() -> None:
    index = P._retailer_hp_index({"entries": [
        _retailer("Agree", 8, quote=""),
        _retailer("Differ", 4, source_url="http://shop.example/differ"),
        _retailer("Unseen", 6, evidence_status="CATALOG_OBSERVED"),
        {**_retailer("Agree", 8), "source_class": "maker"},
    ]})
    assert index == {}


def test_the_committed_retailer_overlay_is_evidence_for_marked_rows_only() -> None:
    import json

    overlays = P.CATALOG / "overlays"
    data = json.loads(P.HP_RETAILER_OVERLAY.read_text(encoding="utf-8"))
    v1 = {e["slug"]: e for e in json.loads((overlays / V1).read_text())["entries"]}
    assert data["count"] == len(data["entries"]) == 46
    assert len(data["not_found"]) == 11
    for entry in data["entries"]:
        assert entry["slug"] in v1 and v1[entry["slug"]]["hp"] == entry["stored_hp"], entry["slug"]
        assert entry["agrees"] == (entry["hp"] == entry["stored_hp"])
        assert entry["source_url"].startswith("https://") and "modulargrid" not in entry["source_url"]
        assert str(entry["hp"]) in entry["quote"]
        assert (entry["source_class"], entry["evidence_status"], entry["access_basis"]) == (
            "retailer", "RETAILER_OBSERVED", "manual_research")
    # Retailer entries are not HP overlays: the fill glob never sees them.
    assert P.HP_RETAILER_OVERLAY not in set(overlays.glob("module-catalog-hp-v*.json"))
    assert sum(e["agrees"] for e in data["entries"]) == 40
