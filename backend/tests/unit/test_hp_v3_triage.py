"""Spec 003 T039: the v1 HP triage (owner decision 9, 2026-10-30).

The v3 overlay re-sources the v1 values whose enrichment result cites the maker's
own page and whose page, fetched 2026-10-30, states that width for that exact product
(each entry quotes it). Where the page states another width, v3 carries the page's
value and maker-corrections-v3 fixes stored copies of v1's. The loader keeps ``module_catalog.hp_source = 'legacy_unsourced'`` on
the rows whose stored HP is still an uncited v1 value.
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402
from modules.catalog import ModuleCatalog  # noqa: E402

CATALOG = ROOT / "data" / "synth-catalog"
OVERLAYS = CATALOG / "overlays"
HAND_CHECKED = {
    "make-noise-dpo": 28,
    "make-noise-morphagene": 20,
    "bastl-instruments-knit-rider": 16,
    "intellijel-mems-mic-1u": 10,
}


def _load(name: str) -> dict:
    return json.loads((OVERLAYS / name).read_text(encoding="utf-8"))


def _official_citations() -> dict[str, dict]:
    cited = {}
    for path in sorted(
        glob.glob(str(CATALOG / "hermes-research" / "hp-enrichment-batch*-results.filtered.json"))
    ):
        for result in json.loads(Path(path).read_text(encoding="utf-8"))["results"]:
            if "source_class=official" in result["notes"]:
                cited[result["slug"]] = result
    return cited


def test_v3_cites_a_maker_page_for_every_entry_in_the_v2_schema() -> None:
    v2, v3 = _load("module-catalog-hp-v2.json"), _load("module-catalog-hp-v3.json")
    assert v3["dataset_version"] == "module-catalog-hp-overlay-v3"
    assert v3["count"] == len(v3["entries"]) == 106
    assert set(v3) == set(v2)
    slugs = [e["slug"] for e in v3["entries"]]
    assert len(slugs) == len(set(slugs))
    for entry in v3["entries"]:
        assert set(entry) == set(v2["entries"][0]), entry["slug"]
        assert P._hp_entry_sourced(entry), entry["slug"]
        assert "?" not in entry["source_url"] and "#" not in entry["source_url"]
        assert P.HP_BAND[0] <= entry["hp"] <= P.HP_BAND[1]
        assert entry["provenance"] == "OBSERVED"
        assert entry["slug"] == P.create_slug(entry["brand"], entry["name"])
        # Every entry quotes its page, and the quote states the entry's width.
        prefix = 'maker-page-checked-2026-10-30: "'
        assert entry["verification"].startswith(prefix) and entry["verification"].endswith('"')
        quote = entry["verification"][len(prefix) : -1]
        assert re.search(rf"(?<!\d){entry['hp']}\s?(HP|hp|TE)\b", quote), entry["slug"]
    assert "module-catalog-hp-v3.json" not in P.UNSOURCED_HP_OVERLAYS


def test_v3_carries_v1_values_only_where_the_enrichment_cites_the_maker() -> None:
    v1 = {e["slug"]: e for e in _load("module-catalog-hp-v1.json")["entries"]}
    cited = _official_citations()
    for entry in _load("module-catalog-hp-v3.json")["entries"]:
        old = v1[entry["slug"]]
        assert (old["brand"], old["name"]) == (entry["brand"], entry["name"])
        if entry["slug"] in cited:
            assert entry["source_url"] == cited[entry["slug"]]["source_url"]
        else:
            # Uncited in v1's lineage; the maker page was read by hand.
            assert entry["slug"] in {"make-noise-dpo", "make-noise-morphagene"}
        if entry["slug"] in HAND_CHECKED:
            assert entry["hp"] == HAND_CHECKED[entry["slug"]] != old["hp"]
            continue
        assert entry["hp"] == old["hp"] == cited[entry["slug"]]["hp"]
    v3 = {e["slug"] for e in _load("module-catalog-hp-v3.json")["entries"]}
    # Left out: the #153 corrections (v2's), ADDAC200PI (another product's page), and the
    # citations the page check could not confirm (blocked host, timeout, another product
    # or version, an inconsistent page). They stay legacy_unsourced.
    left_out = {slug for slug in cited if slug in v1} - v3
    assert "addac-system-addac200pi" in left_out
    corrected_153 = {"acid-rain-technology-junction", "doepfer-a-101-3", "doepfer-a-137-2"}
    # 52 the page check could not confirm, plus ADDAC200PI.
    assert len(left_out - corrected_153) == 53
    assert not v3 & UNCONFIRMED
    assert all(
        slug.startswith(("addac-system-", "befaco-", "instruo-"))
        or slug in UNCONFIRMED
        or slug in corrected_153
        for slug in left_out
    )


def test_a_fresh_load_takes_the_hand_checked_maker_values() -> None:
    overlays = [
        (p.name, json.loads(p.read_text()))
        for p in sorted(OVERLAYS.glob("module-catalog-hp-v*.json"))
    ]
    catalog = {
        e["slug"]: {"brand": e["brand"], "name": e["name"], "hp": None}
        for _, o in overlays
        for e in o["entries"]
    }
    plan = P.Plan()
    P._schedule_hp_overlays(plan, catalog, overlays)
    writes = {op.params["slug"]: op.params["hp"] for op in plan.ops}
    assert {slug: writes[slug] for slug in HAND_CHECKED} == HAND_CHECKED
    assert len(writes) == len(plan.ops) and plan.conflicts_total == 0


# The cited page names another product or version, or contradicts itself.
UNCONFIRMED = {
    "doepfer-a-101-4",
    "doepfer-a-106-1",
    "doepfer-a-138m",
    "intellijel-att",
    "mutable-instruments-tides-2014-version",
    "make-noise-rene",
    "cwejman-d-lfo",
}

IDENT = {"brand": "Acme", "name": "VCO"}


def _overlays(v1_hp=10, sourced_hp=None):
    overlays = [
        (
            "module-catalog-hp-v1.json",
            {
                "entries": [
                    {"slug": "acme-vco", **IDENT, "hp": v1_hp, "source_class": "maker_or_retail"},
                    {
                        "slug": "acme-lfo",
                        "brand": "Acme",
                        "name": "LFO",
                        "hp": 4,
                        "source_class": "maker_or_retail",
                    },
                ]
            },
        )
    ]
    if sourced_hp is not None:
        overlays.append(
            (
                "module-catalog-hp-v3.json",
                {
                    "entries": [
                        {
                            "slug": "acme-vco",
                            **IDENT,
                            "hp": sourced_hp,
                            "source_class": "maker",
                            "source_url": "https://acme.example/vco",
                        },
                    ]
                },
            )
        )
    return overlays


def _markers(catalog, overlays, **kwargs):
    plan = P.Plan()
    P._schedule_hp_source_markers(plan, catalog, overlays, **kwargs)
    return plan


def _row(hp, hp_source=None, **ident):
    return {**(ident or IDENT), "hp": hp, "hp_source": hp_source}


def test_a_stored_v1_value_is_marked_once() -> None:
    catalog = {"acme-vco": _row(10), "acme-lfo": _row(4, brand="Acme", name="LFO")}
    plan = _markers(catalog, _overlays())
    assert plan.updates == {"hp_source_legacy_marked": 2}
    assert [op.params["slug"] for op in plan.ops] == ["acme-lfo", "acme-vco"]
    assert "hp = :hp AND hp_source IS NULL" in plan.ops[0].sql
    assert catalog["acme-vco"]["hp_source"] == P.HP_SOURCE_LEGACY
    assert _markers(catalog, _overlays()).ops == []


def test_maker_backed_or_different_values_are_not_marked() -> None:
    lfo = {"acme-lfo": _row(4, P.HP_SOURCE_LEGACY, brand="Acme", name="LFO")}
    # A maker-cited overlay entry for the slug, whatever its value.
    assert _markers({"acme-vco": _row(10), **lfo}, _overlays(sourced_hp=10)).ops == []
    assert _markers({"acme-vco": _row(10), **lfo}, _overlays(sourced_hp=12)).ops == []
    # A maker-checked catalog row carries the HP.
    assert (
        _markers({"acme-vco": _row(10), **lfo}, _overlays(), maker_hp_slugs={"acme-vco"}).ops == []
    )
    # The stored HP is not v1's (a maker value, or a correction), or there is none.
    assert _markers({"acme-vco": _row(12), **lfo}, _overlays()).ops == []
    assert _markers({"acme-vco": _row(None), **lfo}, _overlays()).ops == []
    # An identity mismatch is never marked.
    assert _markers({"acme-vco": _row(10, brand="Acme", name="VCO2"), **lfo}, _overlays()).ops == []


def test_a_marker_is_cleared_once_the_value_is_sourced_or_corrected() -> None:
    lfo = {"acme-lfo": _row(4, P.HP_SOURCE_LEGACY, brand="Acme", name="LFO")}
    for catalog, overlays in (
        ({"acme-vco": _row(10, P.HP_SOURCE_LEGACY), **lfo}, _overlays(sourced_hp=10)),
        ({"acme-vco": _row(12, P.HP_SOURCE_LEGACY), **lfo}, _overlays()),
    ):
        plan = _markers(catalog, overlays)
        assert plan.updates == {"hp_source_legacy_cleared": 1}
        (op,) = plan.ops
        assert op.params["slug"] == "acme-vco" and "SET hp_source = NULL" in op.sql
        assert catalog["acme-vco"]["hp_source"] is None
        P.assert_safe_sql(op.rendered())


def test_another_hp_source_value_is_left_alone() -> None:
    catalog = {
        "acme-vco": _row(10, "maker"),
        "acme-lfo": _row(4, P.HP_SOURCE_LEGACY, brand="Acme", name="LFO"),
    }
    assert _markers(catalog, _overlays()).ops == []


def test_the_catalog_api_exposes_hp_source() -> None:
    row = ModuleCatalog(
        slug="acme-vco", brand="Acme", name="VCO", hp=10, hp_source=P.HP_SOURCE_LEGACY
    )
    assert row.to_dict()["hp_source"] == "legacy_unsourced"
    assert (
        ModuleCatalog(slug="acme-lfo", brand="Acme", name="LFO", hp=4).to_dict()["hp_source"]
        is None
    )
