"""One brand holds one spelling, and a row retires when a split gave it a second name."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "synth-catalog"
for path in (CATALOG, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import population as P  # noqa: E402

OLD, NEW = "Mutable instruments", "Mutable Instruments"


def load(*parts: str) -> dict:
    return json.loads(CATALOG.joinpath(*parts).read_text(encoding="utf-8"))


def catalog_row(**extra) -> dict:
    return {"brand": OLD, "name": "Beads", "source": "ManufacturerCrawl", **extra}


def test_a_loaded_file_reads_every_brand_under_its_one_spelling(tmp_path: Path) -> None:
    source = tmp_path / "overlay.json"
    source.write_text(json.dumps({
        "brand": OLD,
        "rows": [{"brand": OLD, "name": OLD}, {"brand": "Doepfer"}, {"nested": [{"brand": OLD}]}],
        "brands": [OLD],
    }))
    assert P._load(source) == {
        "brand": NEW,
        "rows": [{"brand": NEW, "name": OLD}, {"brand": "Doepfer"}, {"nested": [{"brand": NEW}]}],
        "brands": [OLD],
    }


def test_rows_move_to_the_one_spelling_with_the_old_value_archived() -> None:
    plan = P.Plan()
    catalog = {"mutable-instruments-beads": catalog_row(), "doepfer-a-110-1": catalog_row(brand="Doepfer")}
    modules = {(OLD, "Beads"): {"status": "active"}, ("Doepfer", "A-110-1"): {"status": "active"}}
    P._schedule_brand_renames(plan, catalog, modules)
    assert catalog["mutable-instruments-beads"]["brand"] == NEW
    assert catalog["doepfer-a-110-1"]["brand"] == "Doepfer"
    assert set(modules) == {(NEW, "Beads"), ("Doepfer", "A-110-1")}
    assert plan.updates == {"catalog_brand_renamed": 1, "module_brand_renamed": 1, "archive_keys_renamed": 1}
    assert plan.inserts == {"catalog_value_archive": 2}
    archives = [op for op in plan.ops if "batch" in op.params]
    assert {op.params["batch"] for op in archives} == {P.BRAND_RENAME_BATCH}
    assert {op.params["row_key"] for op in archives} == {"mutable-instruments-beads", f"{NEW}::Beads"}


def test_a_module_that_already_holds_the_spelling_is_a_conflict() -> None:
    plan = P.Plan()
    modules = {(OLD, "Beads"): {"status": "active"}, (NEW, "Beads"): {"status": "active"}}
    P._schedule_brand_renames(plan, {}, modules)
    assert plan.conflicts[0]["reason"] == "brand_rename_collision"
    assert not plan.updates and (OLD, "Beads") in modules


def test_a_retired_row_moves_too() -> None:
    plan = P.Plan()
    catalog = {"mutable-instruments-beads": catalog_row(tombstoned=True)}
    modules = {(OLD, "Beads"): {"status": "tombstoned"}}
    P._schedule_brand_renames(plan, catalog, modules)
    assert catalog["mutable-instruments-beads"]["brand"] == NEW and (NEW, "Beads") in modules


def test_a_second_pass_plans_nothing() -> None:
    plan = P.Plan()
    catalog, modules = {"mutable-instruments-beads": catalog_row()}, {(OLD, "Beads"): {"status": "active"}}
    P._schedule_brand_renames(plan, catalog, modules)
    again = P.Plan()
    P._schedule_brand_renames(again, catalog, modules)
    assert not again.ops


def test_an_archived_key_reads_under_the_one_spelling() -> None:
    assert P._renamed_row_key(f"{OLD}::Beads") == f"{NEW}::Beads"
    assert P._renamed_row_key(f"{NEW}::Beads") == f"{NEW}::Beads"
    assert P._renamed_row_key("mutable-instruments-beads") == "mutable-instruments-beads"


def test_the_retirements_name_the_rows_the_splits_left() -> None:
    rows = {row["slug"]: row for row in load("overlays", "catalog-retirements-v6.json")["rows"]}
    assert {slug: row["kept_as"] for slug, row in rows.items()} == {
        "joranalogue-filter-8": "joranalogue-audio-design-filter-8",
        "joranalogue-generate-3": "joranalogue-audio-design-generate-3",
        "mutable-instruments-ripples": "mutable-instruments-ripples-original",
        "mutable-instruments-tides-2014-version": "mutable-instruments-tides-original",
        "endorphin-es-milky-way-1u-silver": "endorphin-es-milky-way-1u",
    }
    for row in rows.values():
        assert row["evidence_url"].startswith("https://") and row["kept_as"] in row["reason"]


def test_generate_3_keeps_its_category_under_the_brand_that_stays() -> None:
    (entry,) = load("overlays", "module-catalog-category-v10.json")["entries"]
    assert (entry["brand"], entry["name"], entry["category"]) == ("Joranalogue Audio Design", "Generate 3", "VCO")
    assert entry["does"] in entry["maker_quote"]
