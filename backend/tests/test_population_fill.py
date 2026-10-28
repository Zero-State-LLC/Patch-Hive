"""Fill rules for module power values: what counts as a disagreement (no database needed)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402


def _existing(**values):
    row = {"brand": "B", "name": "N", "verification_status": "verified", "verification_source_url": "https://b.example/n"}
    return {**row, **dict.fromkeys(P.POWER_FIELDS), **values}


def _incoming(status="verified", **values):
    return {"verification_status": status, "verification_source_url": "https://b.example/n", **values}


def test_a_published_decimal_agrees_with_its_stored_integer():
    plan = P.Plan()
    # The maker says 3.5 mA; the INTEGER column holds 4. Same value, no conflict.
    P._schedule_fill(plan, _existing(power_12v_ma=75, power_neg12v_ma=4), _incoming(power_12v_ma=75, power_neg12v_ma=3.5), kind="k")
    assert plan.conflicts == []


def test_a_real_disagreement_is_still_a_conflict():
    plan = P.Plan()
    P._schedule_fill(plan, _existing(power_12v_ma=40, power_neg12v_ma=15), _incoming(power_12v_ma=70, power_neg12v_ma=30), kind="k")
    assert [c["reason"] for c in plan.conflicts] == ["verification_conflict"]


def test_depth_keeps_its_decimals():
    plan = P.Plan()
    P._schedule_fill(plan, _existing(depth_mm=24.0), _incoming(depth_mm=24.5), kind="k")
    assert [c["reason"] for c in plan.conflicts] == ["verification_conflict"]


def test_an_unverified_source_never_conflicts_with_a_verified_module():
    plan = P.Plan()
    P._schedule_fill(plan, _existing(power_12v_ma=60, power_neg12v_ma=50), _incoming("unverified", power_12v_ma=60), kind="k")
    assert plan.conflicts == []


def test_stored_rounding_is_half_away_from_zero():
    assert P._as_stored("power_neg12v_ma", 2.5) == 3
    assert P._as_stored("power_neg12v_ma", 1.18) == 1
    assert P._as_stored("depth_mm", 24.5) == 24.5


def test_review_renames_only_the_named_page():
    review = {"renames": [{"brand": "W", "name": "L", "url_prefix": "https://w.example/l-4hp", "to": "L 4HP"}]}
    assert P._reviewed({"brand": "W", "name": "L", "source_url": "https://w.example/l-4hp-x/"}, review)["name"] == "L 4HP"
    assert P._reviewed({"brand": "W", "name": "L", "source_url": "https://w.example/l-10hp/"}, review)["name"] == "L"
    assert P._reviewed({"brand": "W", "name": "L", "manufacturer_url": "https://w.example/l-4hp"}, review)["name"] == "L 4HP"


def test_review_drops_a_page_that_is_not_a_module():
    review = {"renames": [{"brand": "T", "name": "S", "url_prefix": "https://t.example/arm", "to": "ARM", "not_module": True}]}
    assert P._reviewed({"brand": "T", "name": "S", "source_url": "https://t.example/arm-84hp"}, review) is None


def test_every_review_rename_matches_exactly_one_overlay_entry():
    import json

    review = json.loads(P.MAKER_REVIEW.read_text(encoding="utf-8"))
    entries = [
        e
        for path in sorted((P.CATALOG / "overlays").glob("module-power-depth-v*.json"))
        for e in json.loads(path.read_text(encoding="utf-8")).get("entries") or []
    ]
    for rename in review["renames"]:
        hits = [
            e for e in entries
            if e["brand"] == rename["brand"] and e["name"] == rename["name"]
            and (e.get("source_url") or "").startswith(rename["url_prefix"])
        ]
        assert len(hits) == 1, rename["to"]


def _catalog_after_review():
    import json

    review = json.loads(P.MAKER_REVIEW.read_text(encoding="utf-8"))
    rows = []
    for name in ("seed-phase2-v1.json", "seed-phase3-v1.json"):
        rows += json.loads((P.CATALOG / name).read_text(encoding="utf-8")).get("catalog_modules") or []
    for path in sorted((P.CATALOG / "overlays").glob("catalog-additions-v*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")).get("rows") or []:
            if (reviewed := P._reviewed(row, review)) is not None:
                rows.append(reviewed)
    rows += review.get("catalog_rows") or []
    catalog: dict = {}
    for row in rows:  # insert-if-absent: the first row for a name wins, as in the loader
        catalog.setdefault((row["brand"], row["name"]), row)
    return review, catalog


def test_every_reviewed_product_has_a_catalog_target_on_a_fresh_database():
    review, catalog = _catalog_after_review()
    for rename in review["renames"]:
        if rename.get("not_module"):
            assert (rename["brand"], rename["to"]) not in catalog, rename["to"]
        else:
            assert (rename["brand"], rename["to"]) in catalog, rename["to"]
    # The current product keeps its own row when its legacy page is renamed away.
    assert catalog[("Atonal Circuits", "SEE")]["manufacturer_url"].startswith("https://www.atonal.be/store/")
    assert catalog[("ALM Busy Circuits", "MCO")]["manufacturer_url"].endswith("/alm046")


def test_the_1u_chicane_tile_never_becomes_a_eurorack_row():
    _, catalog = _catalog_after_review()
    assert ("Sovage Engineering", "CHICANE 1U") not in catalog
    assert catalog[("Sovage Engineering", "CHICANE")]["hp"] == 4


def test_catalog_category_fills_only_an_empty_category():
    catalog = {"b-n": {"brand": "B", "name": "N", "hp": 8, "category": None, "_planned": False}}
    plan = P.Plan()
    P._schedule_catalog(plan, catalog, {"brand": "B", "name": "N", "slug": "b-n", "hp": 8, "category": "SEQ"}, None)
    assert catalog["b-n"]["category"] == "SEQ" and plan.updates.get("module_catalog_category") == 1
    plan = P.Plan()
    P._schedule_catalog(plan, catalog, {"brand": "B", "name": "N", "slug": "b-n", "hp": 8, "category": "VCO"}, None)
    assert catalog["b-n"]["category"] == "SEQ" and not plan.updates.get("module_catalog_category")
