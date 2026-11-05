"""The owner's catalog taxonomy decisions of 2026-11-04 (5, 6, 7, 14 and 17).

VIDEO and SYSTEM in the vocabulary, the whole-tag and noise rules, the reviewed Mutable table,
the category corrections and the Jolin retirement.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import build_category_overlay as c  # noqa: E402
import population as P  # noqa: E402
from core.database import get_db  # noqa: E402
from main import app  # noqa: E402
from modules.catalog import ModuleCatalog  # noqa: E402

CATALOG = ROOT / "data" / "synth-catalog"
OVERLAYS = CATALOG / "overlays"
RULES = json.loads((OVERLAYS / "module-catalog-category-v4.json").read_text())
REVIEWED_PATH = OVERLAYS / "module-catalog-category-v5.json"
REVIEWED = json.loads(REVIEWED_PATH.read_text())
CORRECTIONS_PATH = CATALOG / "provenance" / "category-corrections-v1.json"
CORRECTIONS = json.loads(CORRECTIONS_PATH.read_text())
RETIREMENTS = json.loads((OVERLAYS / "catalog-retirements-v3.json").read_text())

CATEGORIES = {"VCO", "VCF", "VCA", "ENV", "LFO", "MIX", "FX", "SEQ", "UTIL", "SAMP", "MIDI", "VIDEO", "SYSTEM"}
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
    "michigan-synth-works-microstreams": "VCA",
    "michigan-synth-works-microtides-8hp-tides-version-2": "LFO",
    "michigan-synth-works-nanorings-nrings-8hp-rings": "VCO",
    "michigan-synth-works-plancks-ii": "VCA",
    "michigan-synth-works-quarks-22hp-elements": "VCO",
    "michigan-synth-works-twiigs": "UTIL",
    "michigan-synth-works-twist-6hp-warps": "FX",
    "plum-audio-apex": "ENV",
    "tall-dog-plaits-se": "VCO",
    "tall-dog-rings-se": "VCO",
    "tlm-audio-modax-mutable-instruments-elements-clone": "VCO",
    "tlm-audio-physc-mutable-instruments-rings-clone": "VCO",
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
    P._schedule_category(plan, catalog, {"slug": "acme-x", "brand": "Acme", "name": "X", "category": "NOISE"})
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
    assert REVIEWED["reviewed_by"] and REVIEWED["count"] == len(REVIEWED["entries"]) == len(entries) == 14
    derived = {slug: e["category"] for slug, e in entries.items() if not slug.startswith("mutable-instruments-")}
    assert derived == MUTABLE_DERIVED
    own = {slug: e["category"] for slug, e in entries.items() if slug.startswith("mutable-instruments-")}
    assert own == {"mutable-instruments-ripples-original": "VCF", "mutable-instruments-tides-original": "LFO"}


def test_each_reviewed_entry_says_what_the_module_does_and_cites_it() -> None:
    for entry in REVIEWED["entries"]:
        assert entry["basis"] == "review" and entry["does"] and entry["evidence"], entry["slug"]
        assert entry["source_url"].startswith("https://") and entry["content_sha256"], entry["slug"]
        assert all((CATALOG / cite).is_file() for cite in entry["cites"]), entry["slug"]
        if entry["does_source"] == "maker_wording":
            # The quote must really be in the committed file it cites, not reworded from memory.
            assert any(entry["maker_quote"] in (CATALOG / cite).read_text() for cite in entry["cites"]), entry["slug"]
        else:
            assert entry["does_source"] == "reviewer_knowledge" and "maker_quote" not in entry, entry["slug"]
    assert "modulargrid" not in json.dumps(REVIEWED["entries"]).lower()


def test_a_reviewed_table_is_never_regenerated() -> None:
    before = REVIEWED_PATH.read_bytes()
    with pytest.raises(SystemExit, match="hand-reviewed"):
        c.main(["--version", "5"])
    assert REVIEWED_PATH.read_bytes() == before


# --- the load --------------------------------------------------------------------------------


def test_a_load_from_the_committed_inputs_has_no_conflict_and_fills_every_row(fresh) -> None:
    plan, catalog, _ = fresh
    assert plan.conflicts_total == 0
    assert "category" not in plan.unmatched
    for entry in RULES["entries"] + REVIEWED["entries"]:
        row = catalog[entry["slug"]]
        assert (row["brand"], row["name"], row["category"]) == (entry["brand"], entry["name"], entry["category"])
        assert not row.get("tombstoned")
    assert not {e["slug"] for e in RULES["entries"]} & {e["slug"] for e in REVIEWED["entries"]}


def test_firmware_platforms_stay_empty(fresh) -> None:
    _, catalog, _ = fresh
    for slug in FIRMWARE_PLATFORMS:
        assert catalog[slug]["category"] is None, slug


def test_these_overlays_leave_the_open_rows_for_a_maker_page() -> None:
    filled = {e["slug"] for e in RULES["entries"] + REVIEWED["entries"]}
    assert not filled & (FIRMWARE_PLATFORMS | NEEDS_MAKER_PAGE | {"nekyia-circuits-ouija"})


def test_video_and_system_hold_the_rows_the_owner_named(fresh) -> None:
    _, catalog, _ = fresh
    assert VIDEO_ROWS | set(VIDEO_CORRECTIONS) <= {s for s, r in catalog.items() if r.get("category") == "VIDEO"}
    assert POWER_ROWS | {"alyseum-eole"} <= {s for s, r in catalog.items() if r.get("category") == "SYSTEM"}


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


def test_each_correction_covers_both_tables_and_cites_its_page() -> None:
    assert len(CORRECTIONS["rows"]) == 10
    by_identity: dict[tuple[str, str], dict[str, dict]] = {}
    for row in CORRECTIONS["rows"]:
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
        ({"value": "NOISE"}, "correction_bad_category"),
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
