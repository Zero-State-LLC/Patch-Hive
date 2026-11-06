"""The owner's catalog taxonomy decisions of 2026-11-04 (5, 6, 7, 14, 17, 49, 50, 51, 54 and 55).

VIDEO and SYSTEM in the vocabulary, the whole-tag and noise rules, the reviewed Mutable table,
the category corrections, the Jolin retirement, and a category reaching modules.module_type.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import build_category_overlay as c  # noqa: E402
import build_maker_overlays as B  # noqa: E402
import population as P  # noqa: E402
from core.database import get_db  # noqa: E402
from main import app  # noqa: E402
from modules.catalog import ModuleCatalog  # noqa: E402
from racks.validation import IN_RACK_SUPPLY_CODE, in_rack_supply_warning  # noqa: E402

CATALOG = ROOT / "data" / "synth-catalog"
OVERLAYS = CATALOG / "overlays"
RULES = json.loads((OVERLAYS / "module-catalog-category-v4.json").read_text())
REVIEWED_PATH = OVERLAYS / "module-catalog-category-v5.json"
REVIEWED = json.loads(REVIEWED_PATH.read_text())
CORRECTIONS_PATH = CATALOG / "provenance" / "category-corrections-v1.json"
CORRECTIONS = json.loads(CORRECTIONS_PATH.read_text())
FURTHER_VIDEO_PATH = CATALOG / "provenance" / "category-corrections-v2.json"
FURTHER_VIDEO = json.loads(FURTHER_VIDEO_PATH.read_text())
RACK_POWER_PATH = CATALOG / "provenance" / "category-corrections-v3.json"
RACK_POWER = json.loads(RACK_POWER_PATH.read_text())
RETIREMENTS = json.loads((OVERLAYS / "catalog-retirements-v3.json").read_text())

CATEGORIES = {"VCO", "VCF", "VCA", "ENV", "LFO", "MIX", "FX", "SEQ", "UTIL", "SAMP", "MIDI", "VIDEO", "SYSTEM", "NOISE"}
VIDEO_ROWS = {
    "afterlife-laboratories-video-keyer",
    "lzx-industries-doorway",
    "lzx-industries-esg3",
    "lzx-industries-liquid-tv",
    "lzx-industries-marble-index",
    "lzx-industries-navigator",
    "lzx-industries-p",
    "lzx-industries-pab",
    "lzx-industries-polar-fringe",
    "lzx-industries-prm",
    "lzx-industries-shapechanger",
    "lzx-industries-sumdist",
    "lzx-industries-swatch",
    "lzx-industries-tbc2",
    "nonlinearcircuits-ldrama",
    "syntonie-combines",
    "syntonie-courbes",
    "syntonie-entr-e",
    "syntonie-isoh-lie",
    "syntonie-rampes",
    "syntonie-sortie",
    "syntonie-vu003b",
    "syntonie-vu007",
    "syntonie-vu008",
}
POWER_ROWS = {
    "aircraft-designs-dc-high-quality-power-supply",
    "eowave-source-d-energie",
    "eowave-source-mk3",
    "feed-me-synthesis-parasitic-power",
    "feedback-reset",
    "m-rk-modules-usb-power-1u-black-panel",
    "soundmachines-silta",
    "st-modular-pow",
    "st-modular-usb",
    "vpme-de-upwr",
    "wgd-modular-stv",
}
RECTIFIERS = {
    "nonlinearcircuits-1u-difference-rectifier",
    "nonlinearcircuits-genie",
    "nonlinearcircuits-let-s-splosh",
    "nonlinearcircuits-splish",
    "rides-in-the-storm-cli",
}
CROSSFADERS = {"modulaire-maritime-r-k", "modulaire-maritime-vc-crossfader", "sonocurrent-m-c3a"}
NOISE_ROWS = {
    "wildsync-noise": ("VCO", "noise_rule_a1"),
    "steady-state-fate-quantum-rainbow-2": ("VCO", "noise_rule_a2"),
    "nonlinearcircuits-pseudo": ("LFO", "noise_rule_a3"),
    "nonlinearcircuits-1u-reverse-sigmoid": ("LFO", "noise_rule_a3"),
}
MUTABLE_DERIVED = {
    "michigan-synth-works-microtides-8hp-tides-version-2": "LFO",
    "tall-dog-plaits-se": "VCO",
}
# Decision 55: "Resonator" names no category, so these wait for a maker page.
RINGS_DERIVED = {
    "michigan-synth-works-nanorings-nrings-8hp-rings",
    "tall-dog-rings-se",
    "tlm-audio-physc-mutable-instruments-rings-clone",
}
# Decision 50: nothing committed says what these do, so they wait for a maker page.
MUTABLE_DERIVED_WITHOUT_A_SOURCE = {
    "michigan-synth-works-microstreams",
    "michigan-synth-works-plancks-ii",
    "michigan-synth-works-quarks-22hp-elements",
    "michigan-synth-works-twiigs",
    "michigan-synth-works-twist-6hp-warps",
    "plum-audio-apex",
    "tlm-audio-modax-mutable-instruments-elements-clone",
}
# Decision 49: the row's own maker page says video (Formes: RGB, a video signal).
FURTHER_VIDEO_ROWS = {
    "afterlife-laboratories-video-calculator",
    "dave-jones-design-jones-mvip",
    "foxing-hour-abc",
    "foxing-hour-felt",
    "foxing-hour-shutter",
    "foxing-hour-veil",
    "hive-mind-synthesis-dvm-1u-12hp-dirty-video-mixer",
    "hive-mind-synthesis-dvmdx",
    "hive-mind-synthesis-pvt",
    "hive-mind-synthesis-video-downer-1u-2hp-fixed-attenuator-for-video-synthesis",
    "hive-mind-synthesis-video-downer-3u-2hp-quad-fixed-attenuator-for-video-synthesis",
    "lzx-industries-mapper",
    "lzx-industries-passage",
    "lzx-industries-pendulum",
    "lzx-industries-prismatic-ray",
    "lzx-industries-topogram",
    "lzx-industries-war-of-the-ants",
    "syntonie-cbv001",
    "syntonie-d-tail",
    "syntonie-formes",
    "syntonie-ondes",
    "syntonie-stable",
    "syntonie-vu001b",
    "syntonie-vu001c",
}
# Decision 54: rack power, not video.
DC_DISTRO = {"lzx-industries-dc-distro-3a", "lzx-industries-dc-distro-5a"}
# Decisions 49 and 54: only the brand links these to video, and their own tags name another function.
WEAK_VIDEO_EVIDENCE = {
    "afterlife-laboratories-castle-circuits-2-100-101-111-combined-module",
    "lzx-industries-cyclops",
    "lzx-industries-sensory-translator",
    "syntonie-animate",
    "syntonie-cadrans",
    "syntonie-matrice",
    "syntonie-seuils",
    "syntonie-solaire",
    "syntonie-vu006",
}
FIRMWARE_PLATFORMS = {
    "apf-audio-eurorack-pmod",
    "apf-audio-eurorack-pmod-r3-1",
    "bela-pepper",
    "north-coast-synthesis-msk-014-gracious-host",
    "p4l-modular-pikocoreuro-built",
    "patching-panda-ephemere",
    "patching-panda-particles",
    "rebel-technology-genius",
    "rebel-technology-owl-modular",
    "wgd-modular-carciofo",
}
# The 9 "probably not modules" rows, less the fan. None of these is a fan or a USB power panel
# by committed data, so each waits for a maker page (USBee's tags say USB port, blank).
NEEDS_MAKER_PAGE = {
    "avalon-harmonics-alcove-printed-blank",
    "ethereal-electronics-starlight-16hp",
    "ethereal-electronics-starlight-8hp",
    "hive-mind-synthesis-usbee",
    "morph-modular-wormhole-portal",
    "nozo-d-nozori-expansion-panel",
    "plankton-electronics-nutone-pcb-only",
    "wgd-modular-ramen",
}
VIDEO_CORRECTIONS = {
    "hive-mind-synthesis-video-gate-1u-10hp": "UTIL",
    "melted-electronics-glitch-boy": "MIDI",
    "syntonie-animate-exp": "UTIL",
}
MUTABLE_CORRECTIONS = {"mutable-instruments-ripples": "VCF", "mutable-instruments-tides-2014-version": "LFO"}
# No committed maker wording settles these, so they wait for the free-reads PR.
MUTABLE_DEFERRED = {
    "mutable-instruments-yarns": "VCO",
    "mutable-instruments-rings": "VCO",
    "mutable-instruments-frames": "VCA",
    "mutable-instruments-edges": "SEQ",
}


@pytest.fixture(scope="module")
def fresh():
    """The plan and end state for a load from the committed inputs into an empty database."""
    catalog: dict = {}
    modules: dict = {}
    patch = pytest.MonkeyPatch()
    patch.setattr(P, "_catalog_state", lambda conn: catalog)
    patch.setattr(P, "_module_state", lambda conn: modules)
    patch.setattr(P, "_manufacturer_state", lambda conn: set())
    plan = P.build_plan(None)
    patch.undo()
    return plan, catalog, modules


def test_the_loader_vocabulary_holds_video_and_system() -> None:
    assert P.MODULE_CATEGORIES == CATEGORIES


def test_every_stored_and_planned_category_is_in_the_vocabulary(fresh) -> None:
    _, catalog, _ = fresh
    assert {row["category"] for row in catalog.values() if row.get("category")} <= CATEGORIES
    for path in OVERLAYS.glob("module-catalog-category-v*.json"):
        assert {e["category"] for e in json.loads(path.read_text())["entries"]} <= CATEGORIES


def test_an_overlay_outside_the_vocabulary_is_a_conflict_and_writes_nothing() -> None:
    catalog = {"acme-x": {"brand": "Acme", "name": "X", "hp": 4, "category": None}}
    plan = P.Plan()
    P._schedule_category(plan, catalog, {"slug": "acme-x", "brand": "Acme", "name": "X", "category": "DRONE"})
    assert [conflict["reason"] for conflict in plan.conflicts] == ["category_outside_vocabulary"]
    assert catalog["acme-x"]["category"] is None and plan.ops == []


# --- the rules -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tags,expected",
    [
        (["rectifier", "CV"], "UTIL"),  # decision 17 replaces "no rule" from the T031 pass
        (["neuron", "extrapolator", "rectifier"], "UTIL"),
        (["clipper", "rectifier", "matrix"], "UTIL"),  # the convention beats a two-category row
        (["crossfader", "VC", "1U"], "MIX"),
        (["crossfader", "array", "voltage-controlled"], "MIX"),
        (["ventilation", "temperature", "fan", "monitor"], "SYSTEM"),
    ],
)
def test_owner_conventions_settle_a_row(tags, expected) -> None:
    assert c.classify(tags, "Widget", "") == (expected, "owner_tag")


@pytest.mark.parametrize(
    "tags",
    [
        ["rectifier", "crossfader"],  # two conventions: left empty
        ["full-wave rectifier"],  # a word inside a longer tag is not a match
        ["fan out"],
    ],
)
def test_owner_conventions_match_one_whole_tag_only(tags) -> None:
    assert c.classify(tags, "Widget", "") is None


@pytest.mark.parametrize(
    "tags,name,expected",
    [
        (["noise", "random"], "NOISE", ("VCO", "noise_rule_a1")),
        (["noise", "random"], "Chaos Box", ("LFO", "noise_rule_a1")),
        (["noise", "random"], "Quantum Rainbow 2", ("VCO", "noise_rule_a2")),
        (["noise", "random", "pattern", "generator"], "PSEUDO", ("LFO", "noise_rule_a3")),
        (["chaos", "CV", "noise", "1u"], "1u Reverse Sigmoid", ("LFO", "noise_rule_a3")),
        (["glide", "noise", "sub", "ring mod"], "Ouija", None),  # A4: waits for the maker page
    ],
)
def test_noise_and_random_follow_option_a(tags, name, expected) -> None:
    assert c.classify(tags, name, "") == expected


def test_a_row_that_only_says_noise_keeps_the_existing_rule() -> None:
    assert c.classify(["noise", "CV"], "Widget", "") == ("VCO", "crawl_tag")


def test_the_rule_overlay_classifies_exactly_the_rows_the_owner_named() -> None:
    entries = {e["slug"]: e for e in RULES["entries"]}
    assert RULES["count"] == len(RULES["entries"]) == len(entries) == 48
    by_basis: dict[str, set[str]] = {}
    for slug, entry in entries.items():
        by_basis.setdefault(entry["basis"], set()).add(slug)
    assert by_basis["owner_video"] == VIDEO_ROWS and len(VIDEO_ROWS) == 24
    assert by_basis["owner_power"] == POWER_ROWS and len(POWER_ROWS) == 11
    assert by_basis["owner_tag"] == RECTIFIERS | CROSSFADERS | {"alyseum-eole"}
    assert Counter(entries[slug]["category"] for slug in by_basis["owner_tag"]) == {"UTIL": 5, "MIX": 3, "SYSTEM": 1}
    assert {slug: (entries[slug]["category"], entries[slug]["basis"]) for slug in NOISE_ROWS} == NOISE_ROWS
    assert {e["category"] for e in entries.values() if e["basis"] == "owner_video"} == {"VIDEO"}
    assert {e["category"] for e in entries.values() if e["basis"] == "owner_power"} == {"SYSTEM"}


def test_each_rule_entry_cites_the_crawled_maker_page() -> None:
    for entry in RULES["entries"]:
        assert entry["source_url"].startswith("https://"), entry["slug"]
        assert len(entry["content_sha256"]) == 64 and entry["tags"], entry["slug"]
    assert "modulargrid" not in json.dumps(RULES["entries"]).lower()


def test_every_row_the_t031_pass_held_now_has_its_category() -> None:
    held = json.loads((OVERLAYS / "module-catalog-category-v3.json").read_text())["held"]
    entries = {e["slug"]: e["category"] for e in RULES["entries"]}
    assert {h["slug"]: entries[h["slug"]] for h in held} == {
        h["slug"]: {"video": "VIDEO", "power": "SYSTEM"}[h["held_for"]] for h in held
    }


# --- the reviewed table ----------------------------------------------------------------------


def test_the_reviewed_table_names_each_mutable_derived_row() -> None:
    entries = {e["slug"]: e for e in REVIEWED["entries"]}
    assert REVIEWED["reviewed_by"] and REVIEWED["count"] == len(REVIEWED["entries"]) == len(entries) == 4
    derived = {slug: e["category"] for slug, e in entries.items() if not slug.startswith("mutable-instruments-")}
    assert derived == MUTABLE_DERIVED
    own = {slug: e["category"] for slug, e in entries.items() if slug.startswith("mutable-instruments-")}
    assert own == {"mutable-instruments-ripples-original": "VCF", "mutable-instruments-tides-original": "LFO"}


def test_each_reviewed_entry_says_what_the_module_does_and_cites_it() -> None:
    for entry in REVIEWED["entries"]:
        assert entry["basis"] == "review" and entry["does"] and entry["evidence"], entry["slug"]
        assert entry["source_url"].startswith("https://") and entry["content_sha256"], entry["slug"]
        assert all((CATALOG / cite).is_file() for cite in entry["cites"]), entry["slug"]
        # Decision 50: every row quotes the maker, and the quote must really be in the committed
        # file it cites. What the row says the module does is the maker's word, nothing added.
        assert entry["does_source"] == "maker_wording", entry["slug"]
        assert any(entry["maker_quote"] in (CATALOG / cite).read_text() for cite in entry["cites"]), entry["slug"]
        assert entry["does"] in entry["maker_quote"], entry["slug"]
    assert "modulargrid" not in json.dumps(REVIEWED["entries"]).lower()


def test_each_quote_gives_its_category_by_the_catalogs_own_rule() -> None:
    # Decision 55: a quote that names no category, such as "Resonator", isn't enough.
    for entry in REVIEWED["entries"]:
        assert B.category([entry["does"]], "") == entry["category"], entry["slug"]
    assert B.category(["Resonator"], "") is None


def test_the_own_mutable_rows_are_quoted_from_their_own_maker_page() -> None:
    cited = {e["source_url"]: e["verification"] for e in json.loads((OVERLAYS / "module-catalog-hp-v4.json").read_text())["entries"]}
    for entry in REVIEWED["entries"]:
        if entry["slug"].startswith("mutable-instruments-"):
            assert entry["maker_quote"] in cited[entry["source_url"]], entry["slug"]


def test_a_reviewed_table_is_never_regenerated() -> None:
    before = REVIEWED_PATH.read_bytes()
    with pytest.raises(SystemExit, match="hand-reviewed"):
        c.main(["--version", "5"])
    assert REVIEWED_PATH.read_bytes() == before


# --- the load --------------------------------------------------------------------------------


def test_a_load_from_the_committed_inputs_has_no_conflict_and_fills_every_row(fresh) -> None:
    plan, catalog, _ = fresh
    assert plan.conflicts_total == 0
    # Overlays v7 and v8 also fill leads that only a deployed database holds (spec 003 FR-034).
    filled_on_deployed_only = [
        entry["slug"]
        for version in ("v7", "v8")
        for entry in json.loads((OVERLAYS / f"module-catalog-category-{version}.json").read_text())["entries"]
        if entry["slug"] not in catalog
    ]
    assert plan.unmatched.get("category", 0) == len(filled_on_deployed_only)
    # Corrections run after the overlays, so decision 16 moves a row the rules first filled.
    moved_to_noise = {
        row["slug"]: field["value"]
        for row in json.loads((CATALOG / "provenance" / "category-corrections-v6.json").read_text())["rows"]
        if row["table"] == "module_catalog"
        for field in row["fields"]
        if field["field"] == "category"
    }
    # A row filled by these rules can later retire as a second name for another row.
    second_names = {
        row["slug"] for row in json.loads((OVERLAYS / "catalog-retirements-v5.json").read_text())["rows"]
    }
    for entry in RULES["entries"] + REVIEWED["entries"]:
        row = catalog[entry["slug"]]
        expected = moved_to_noise.get(entry["slug"], entry["category"])
        assert (row["brand"], row["name"], row["category"]) == (entry["brand"], entry["name"], expected)
        assert bool(row.get("tombstoned")) == (entry["slug"] in second_names)
    assert not {e["slug"] for e in RULES["entries"]} & {e["slug"] for e in REVIEWED["entries"]}


def test_firmware_platforms_stay_empty(fresh) -> None:
    _, catalog, _ = fresh
    for slug in FIRMWARE_PLATFORMS:
        assert catalog[slug]["category"] is None, slug


def test_these_overlays_leave_the_open_rows_for_a_maker_page() -> None:
    filled = {e["slug"] for e in RULES["entries"] + REVIEWED["entries"]}
    assert not filled & (
        FIRMWARE_PLATFORMS | NEEDS_MAKER_PAGE | MUTABLE_DERIVED_WITHOUT_A_SOURCE | RINGS_DERIVED
        | {"nekyia-circuits-ouija"}
    )


def test_video_and_system_hold_the_rows_the_owner_named(fresh) -> None:
    _, catalog, _ = fresh
    held = VIDEO_ROWS | set(VIDEO_CORRECTIONS) | FURTHER_VIDEO_ROWS
    assert held <= {s for s, r in catalog.items() if r.get("category") == "VIDEO"}
    assert POWER_ROWS | DC_DISTRO | {"alyseum-eole"} <= {s for s, r in catalog.items() if r.get("category") == "SYSTEM"}


# --- corrections -----------------------------------------------------------------------------


def test_the_manifest_names_the_three_video_rows_and_the_backed_mutable_rows() -> None:
    assert CORRECTIONS_PATH in P.CATEGORY_CORRECTION_MANIFESTS
    assert CORRECTIONS_PATH not in P.PROVENANCE_MANIFESTS
    assert CORRECTIONS["flag_reverify"] is False
    catalog_rows = {r["slug"]: r["fields"][0] for r in CORRECTIONS["rows"] if r["table"] == "module_catalog"}
    assert {slug: item["only_if_value"] for slug, item in catalog_rows.items() if item["value"] == "VIDEO"} == (
        VIDEO_CORRECTIONS
    )
    assert {slug: item["value"] for slug, item in catalog_rows.items() if item["value"] != "VIDEO"} == (
        MUTABLE_CORRECTIONS
    )
    assert not set(catalog_rows) & set(MUTABLE_DEFERRED)


@pytest.mark.parametrize("manifest,rows", [(CORRECTIONS, 10), (FURTHER_VIDEO, 48), (RACK_POWER, 4)])
def test_each_correction_covers_both_tables_and_cites_its_page(manifest, rows) -> None:
    assert len(manifest["rows"]) == rows
    by_identity: dict[tuple[str, str], dict[str, dict]] = {}
    for row in manifest["rows"]:
        (item,) = row["fields"]
        assert item["action"] == "correct" and item["value"] in CATEGORIES
        assert item["evidence_url"].startswith("https://") and len(item["source_tag"]) <= 200
        assert P._correction_problem(row["table"], item) is None
        by_identity.setdefault((row["brand"], row["name"]), {})[row["table"]] = item
    for items in by_identity.values():
        assert items["module_catalog"]["field"] == "category" and items["modules"]["field"] == "module_type"
        assert {k: v for k, v in items["module_catalog"].items() if k != "field"} == {
            k: v for k, v in items["modules"].items() if k != "field"
        }


def test_each_mutable_correction_quotes_the_maker_from_committed_data() -> None:
    quoted = [r["fields"][0] for r in CORRECTIONS["rows"] if r["brand"] == "Mutable Instruments"]
    assert len(quoted) == 4
    for item in quoted:
        assert item["maker_quote"] in (CATALOG / item["quote_source"]).read_text()
        # The maker's own docs, not the research seed's label.
        assert item["evidence_url"].startswith("https://pichenettes.github.io/mutable-instruments-documentation/")


def test_a_fresh_load_ends_with_the_corrected_value_in_both_tables(fresh) -> None:
    plan, catalog, modules = fresh
    for slug in VIDEO_CORRECTIONS:
        row = catalog[slug]
        assert row["category"] == "VIDEO"
        assert modules[(row["brand"], row["name"])]["module_type"] == "VIDEO"
    for slug, category in MUTABLE_CORRECTIONS.items():
        assert catalog[slug]["category"] == category
    stats = plan.provenance["category-corrections-v1"]
    # Every manifest row is corrected, or has no module row to correct.
    assert stats["corrected_values"] + stats["rows_missing"] == len(CORRECTIONS["rows"])
    assert stats["value_not_matched"] == 0 and stats["refused_row_tombstoned"] == 0


def test_decision_49_moves_the_rows_whose_own_page_says_video_and_no_others() -> None:
    assert FURTHER_VIDEO_PATH in P.CATEGORY_CORRECTION_MANIFESTS
    catalog_rows = {r["slug"]: r["fields"][0] for r in FURTHER_VIDEO["rows"] if r["table"] == "module_catalog"}
    assert set(catalog_rows) == FURTHER_VIDEO_ROWS and len(FURTHER_VIDEO_ROWS) == 24
    assert not set(catalog_rows) & (WEAK_VIDEO_EVIDENCE | DC_DISTRO)
    assert len(FURTHER_VIDEO_ROWS) + len(WEAK_VIDEO_EVIDENCE) + len(DC_DISTRO) == 35

    crawl = json.loads((CATALOG / "hermes-research" / "maker-crawl-v2.json").read_text())
    crawled = {m["source_url"]: m for brand in crawl["brands"] for m in brand.get("modules") or []}
    for slug, item in catalog_rows.items():
        page = crawled[item["evidence_url"]]
        assert item["maker_tags"] == page["tags"] and item["content_sha256"] == page["content_sha256"], slug
        says = {tag.strip().lower() for tag in page["tags"]}
        assert "video" in says or (slug == "syntonie-formes" and "rgb" in says), slug
    for row in FURTHER_VIDEO["rows"]:
        assert row["fields"][0]["value"] == "VIDEO"


def test_a_fresh_load_moves_the_further_video_rows_in_both_tables(fresh) -> None:
    plan, catalog, modules = fresh
    for slug in FURTHER_VIDEO_ROWS:
        row = catalog[slug]
        assert row["category"] == "VIDEO", slug
        assert modules[(row["brand"], row["name"])]["module_type"] == "VIDEO", slug
    stats = plan.provenance["category-corrections-v2"]
    assert stats["corrected_values"] == 48 and stats["value_not_matched"] == 0 and stats["rows_missing"] == 0


def test_decision_54_moves_the_dc_distros_to_system_and_no_other_weak_row(fresh) -> None:
    assert RACK_POWER_PATH in P.CATEGORY_CORRECTION_MANIFESTS
    moved = {r["slug"]: r["fields"][0] for r in RACK_POWER["rows"] if r["table"] == "module_catalog"}
    assert set(moved) == DC_DISTRO
    for item in moved.values():
        assert (item["only_if_value"], item["value"]) == ("UTIL", "SYSTEM") and "power" in item["maker_tags"]

    plan, catalog, modules = fresh
    for slug in DC_DISTRO:
        row = catalog[slug]
        assert row["category"] == "SYSTEM", slug
        assert modules[(row["brand"], row["name"])]["module_type"] == "SYSTEM", slug
    stats = plan.provenance["category-corrections-v3"]
    assert stats["corrected_values"] == 4 and stats["value_not_matched"] == 0 and stats["rows_missing"] == 0
    # Decision 54: these stay as they are until a maker page says otherwise. v4 is that page.
    maker_page = CATALOG / "provenance" / "category-corrections-v4.json"
    named = {
        r.get("slug") for path in P.CATEGORY_CORRECTION_MANIFESTS if path != maker_page
        for r in json.loads(path.read_text())["rows"]
    }
    assert not named & WEAK_VIDEO_EVIDENCE


def test_a_correction_runs_after_the_insert_and_fill_it_replaces(fresh) -> None:
    plan, _, _ = fresh
    def position(kind: str, **params) -> int:
        return next(
            i for i, op in enumerate(plan.ops)
            if op.kind == kind and all(op.params.get(k) == v for k, v in params.items())
        )

    slug = "melted-electronics-glitch-boy"
    identity = {"brand": "Melted Electronics", "name": "Glitch Boy"}
    corrected = position("correct_values", row_key=slug)
    assert position("update_category", slug=slug) < corrected
    assert position("insert_module", **identity) < position("correct_values", row_key=P.module_row_key(**identity))


def _correction(**field) -> dict:
    item = {"field": "category", "action": "correct", "only_if_value": "UTIL", "value": "VIDEO",
            "evidence_url": "https://maker.example/gate", "source_tag": "test", "maker_check": "test"}
    item.update(field)
    return {"batch": "test-category", "flag_reverify": False,
            "rows": [{"table": "module_catalog", "slug": "acme-gate", "brand": "Acme", "name": "Gate",
                      "fields": [item]}]}


def _catalog(category="UTIL", **extra) -> dict:
    return {"acme-gate": {"brand": "Acme", "name": "Gate", "hp": 4, "category": category, **extra}}


def _plan(manifest: dict, catalog: dict, modules: dict | None = None, archived=frozenset()) -> P.Plan:
    plan = P.Plan()
    P._schedule_provenance(plan, catalog, modules or {}, manifest, set(archived))
    return plan


def test_a_category_correction_archives_then_writes_the_new_value() -> None:
    catalog = _catalog()
    plan = _plan(_correction(), catalog)
    assert [op.kind for op in plan.ops] == ["archive_values", "correct_values", "archive_markers"]
    assert "category = CASE WHEN EXISTS" in plan.ops[1].sql and plan.ops[1].params["c0"] == "VIDEO"
    assert catalog["acme-gate"]["category"] == "VIDEO"
    P.assert_safe_sql(P.render_plan(plan))


def test_a_module_type_correction_reaches_the_row_the_engine_reads() -> None:
    modules = {("Acme", "Gate"): {"brand": "Acme", "name": "Gate", "module_type": "UTIL", "_duplicate": False}}
    manifest = _correction(field="module_type")
    manifest["rows"][0] = {"table": "modules", "brand": "Acme", "name": "Gate", "fields": manifest["rows"][0]["fields"]}
    plan = _plan(manifest, {}, modules)
    assert [op.kind for op in plan.ops] == ["archive_values", "correct_values", "archive_markers"]
    assert "module_type = CASE WHEN EXISTS" in plan.ops[1].sql
    assert modules[("Acme", "Gate")]["module_type"] == "VIDEO"


def test_a_category_changed_since_review_is_left_alone() -> None:
    catalog = _catalog(category="MIX")
    plan = _plan(_correction(), catalog)
    assert [op.kind for op in plan.ops] == ["archive_markers"]
    assert catalog["acme-gate"]["category"] == "MIX"
    assert plan.provenance["test-category"]["value_not_matched"] == 1


def test_a_processed_row_is_not_corrected_again() -> None:
    plan = _plan(_correction(), _catalog(), archived={("module_catalog", "acme-gate", P.ROW_MARKER)})
    assert plan.ops == []


@pytest.mark.parametrize(
    "field,reason",
    [
        ({"value": "DRONE"}, "correction_bad_category"),
        ({"value": "video"}, "correction_bad_category"),
        ({"evidence_url": "http://maker.example"}, "correction_needs_maker_page"),
        ({"only_if_value": None}, "correction_needs_old_and_new_value"),
        ({"action": "flag"}, "category_only_corrected"),
        ({"action": "keep"}, "category_only_corrected"),
        ({"action": "null"}, "not_nullable"),
    ],
)
def test_an_unusable_category_entry_is_a_conflict_and_writes_nothing(field, reason) -> None:
    catalog = _catalog()
    plan = _plan(_correction(**field), catalog)
    assert [conflict["reason"] for conflict in plan.conflicts] == [reason]
    assert catalog["acme-gate"]["category"] == "UTIL"
    assert not [op for op in plan.ops if op.kind in ("archive_values", "correct_values")]


def test_correcting_a_category_never_clears_an_hp_or_power_flag() -> None:
    plan = _plan(_correction(), _catalog(needs_reverify=True))
    assert "clear_reverify" not in [op.kind for op in plan.ops]
    assert plan.provenance["test-category"]["reverify_clear_scheduled"] == 0


# --- a category reaches modules.module_type (decision 51) -------------------------------------


def _sync(module_type="UNKNOWN", category="VCF", source="SynthCatalogResearch", catalog_extra=None, module_extra=None):
    catalog = {"acme-gate": {"brand": "Acme", "name": "Gate", "category": category, **(catalog_extra or {})}}
    modules = {("Acme", "Gate"): {"brand": "Acme", "name": "Gate", "module_type": module_type, "source": source,
                                  "_duplicate": False, **(module_extra or {})}}
    plan = P.Plan()
    P._schedule_module_type_sync(plan, catalog, modules)
    return plan, modules[("Acme", "Gate")]


def test_the_placeholder_takes_the_catalog_category_and_is_archived_first() -> None:
    plan, module = _sync()
    assert [op.kind for op in plan.ops] == ["archive_values", "update_module_type"]
    archive, update = plan.ops
    assert archive.params["batch"] == "module-type-sync-v1" and archive.params["e0"] == "UNKNOWN"
    assert update.params["category"] == "VCF" and module["module_type"] == "VCF"
    # The statement re-checks both guards when it runs, not only when it was planned.
    assert "module_type = :placeholder" in update.sql and "source IN (:source_a, :source_b)" in update.sql
    assert "status <> 'tombstoned'" in update.sql
    assert plan.updates == {"module_type_from_category": 1}
    assert plan.module_type_sync["synced"] == 1 and plan.module_type_sync["by_category"] == {"VCF": 1}
    P.assert_safe_sql(P.render_plan(plan))


@pytest.mark.parametrize(
    "kwargs,counter",
    [
        ({"module_type": "UTIL"}, "left_alone_other_value"),  # a person, an importer or a correction set it
        ({"source": "Admin"}, "left_alone_not_loader_row"),
        ({"source": "ModuleCatalog"}, "left_alone_not_loader_row"),
        ({"module_extra": {"_duplicate": True}}, "skipped_duplicate_module_row"),
        ({"category": "DRONE"}, "skipped_outside_vocabulary"),
    ],
)
def test_a_value_it_may_not_touch_stays_and_is_counted(kwargs, counter) -> None:
    before = kwargs.get("module_type", "UNKNOWN")
    plan, module = _sync(**kwargs)
    assert plan.ops == [] and module["module_type"] == before
    assert plan.module_type_sync[counter] == 1 and plan.module_type_sync["synced"] == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"category": None},
        {"catalog_extra": {"tombstoned": True}},
        {"module_extra": {"status": "tombstoned"}},
        {"module_type": "VCF"},  # already agrees: nothing to do and nothing to report
    ],
)
def test_nothing_is_planned_without_a_live_category_to_copy(kwargs) -> None:
    plan, _ = _sync(**kwargs)
    assert plan.ops == [] and plan.module_type_sync["synced"] == 0
    assert plan.module_type_sync["left_alone_other_value"] == 0


def test_two_catalog_rows_that_disagree_leave_the_placeholder() -> None:
    catalog = {
        "acme-gate": {"brand": "Acme", "name": "Gate", "category": "VCF"},
        "acme-gate-2": {"brand": "Acme", "name": "Gate", "category": "VCA"},
    }
    modules = {("Acme", "Gate"): {"module_type": "UNKNOWN", "source": "SynthCatalogResearch", "_duplicate": False}}
    plan = P.Plan()
    P._schedule_module_type_sync(plan, catalog, modules)
    assert plan.ops == [] and plan.module_type_sync["skipped_catalog_rows_disagree"] == 1


def test_a_corrected_category_reaches_a_module_row_still_holding_the_placeholder() -> None:
    # The correction can't match UNKNOWN, so it leaves the module row, and the sync then writes it.
    catalog = _catalog()
    modules = {("Acme", "Gate"): {"brand": "Acme", "name": "Gate", "module_type": "UNKNOWN",
                                  "source": "SynthCatalogResearch", "_duplicate": False}}
    manifest = _correction()
    manifest["rows"].append({"table": "modules", "brand": "Acme", "name": "Gate",
                             "fields": [_correction(field="module_type")["rows"][0]["fields"][0]]})
    plan = _plan(manifest, catalog, modules)
    assert plan.provenance["test-category"]["value_not_matched"] == 1
    P._schedule_module_type_sync(plan, catalog, modules)
    assert modules[("Acme", "Gate")]["module_type"] == "VIDEO"


def test_a_reviewed_correction_is_never_overwritten_by_the_sync() -> None:
    catalog = _catalog(category="VIDEO")
    modules = {("Acme", "Gate"): {"module_type": "VCF", "source": "SynthCatalogResearch", "_duplicate": False}}
    plan = P.Plan()
    P._schedule_module_type_sync(plan, catalog, modules)
    assert plan.ops == [] and modules[("Acme", "Gate")]["module_type"] == "VCF"


def _placed(module: dict) -> SimpleNamespace:
    return SimpleNamespace(id=1, brand="Acme", name="Gate", module_type=module["module_type"])


def test_the_sync_lets_the_in_rack_supply_warning_reach_a_loaded_database() -> None:
    # Decision 15's warning matches module_type, so a row left on the placeholder never warned.
    assert in_rack_supply_warning([_placed({"module_type": "UNKNOWN"})]) is None
    _, module = _sync(category="SYSTEM")
    assert in_rack_supply_warning([_placed(module)]).details["code"] == IN_RACK_SUPPLY_CODE


def test_every_system_row_warns_and_a_video_row_does_not(fresh) -> None:
    _, catalog, modules = fresh
    for slug in DC_DISTRO | POWER_ROWS | {"alyseum-eole"}:
        row = catalog[slug]
        assert in_rack_supply_warning([_placed(modules[(row["brand"], row["name"])])]) is not None, slug
    row = catalog["lzx-industries-doorway"]
    assert in_rack_supply_warning([_placed(modules[(row["brand"], row["name"])])]) is None


def test_a_load_from_empty_needs_no_sync(fresh) -> None:
    # The inserts already take the category, so only a loaded database has anything to catch up.
    plan, _, _ = fresh
    assert plan.module_type_sync["synced"] == 0
    assert "module_type_from_category" not in plan.updates


# --- the retirement --------------------------------------------------------------------------


def test_the_duplicate_getrekt_is_tombstoned_and_the_plain_row_kept(fresh) -> None:
    _, catalog, modules = fresh
    assert RETIREMENTS["count"] == len(RETIREMENTS["rows"]) == 1
    (entry,) = RETIREMENTS["rows"]
    assert entry["slug"] == "jolin-getrekt-touch-waveshaper" and entry["kept_as"] == "jolin-getrekt"
    assert entry["evidence_url"].startswith("https://") and entry["reason"]

    # Never deleted: both rows are still there, one of them tombstoned.
    retired = catalog["jolin-getrekt-touch-waveshaper"]
    assert retired["tombstoned"] is True and retired["category"] == "FX"
    assert modules[("Jolin", entry["name"])]["status"] == "tombstoned"
    kept = catalog["jolin-getrekt"]
    assert not kept.get("tombstoned") and kept["category"] == "FX"
    assert modules[("Jolin", "GETREKT")].get("status") != "tombstoned"


# --- the catalog API -------------------------------------------------------------------------


@pytest.fixture
def catalog_client(db_session: Session):
    db_session.add_all([
        ModuleCatalog(slug="lzx-doorway", brand="LZX", name="Doorway", hp=10, category="VIDEO"),
        ModuleCatalog(slug="eowave-source", brand="Eowave", name="Source", hp=4, category="SYSTEM"),
        ModuleCatalog(slug="acme-vco", brand="Acme", name="VCO", hp=8, category="VCO"),
    ])
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_the_category_filter_endpoint_lists_and_filters_the_new_categories(catalog_client: TestClient) -> None:
    categories = catalog_client.get("/api/modules/catalog/categories").json()["categories"]
    assert {c["name"] for c in categories} == {"VIDEO", "SYSTEM", "VCO"}
    for category, slug in (("VIDEO", "lzx-doorway"), ("SYSTEM", "eowave-source")):
        rows = catalog_client.get("/api/modules/catalog", params={"category": category}).json()["modules"]
        assert [row["slug"] for row in rows] == [slug]
