"""A public row that repeats another row's page retires, and the module stays under one name."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "synth-catalog"
for path in (CATALOG, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import population as P  # noqa: E402


def load(*parts: str) -> dict:
    return json.loads(CATALOG.joinpath(*parts).read_text(encoding="utf-8"))


ROWS = load("overlays", "catalog-retirements-v5.json")["rows"]
SLUGS = {row["slug"] for row in ROWS}


def test_the_list_names_each_row_once() -> None:
    assert len(ROWS) == 38 and len(SLUGS) == 38


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["slug"])
def test_each_row_cites_its_page_and_the_row_that_stays(row) -> None:
    assert row["evidence_url"].startswith("https://")
    assert row["kept_as"] != row["slug"] and row["kept_as"] not in SLUGS
    assert row["kept_as"] in row["reason"] and len(row["reason"]) <= 200
    assert "modulargrid" not in json.dumps(row).lower()


def test_no_row_was_already_retired() -> None:
    earlier = {
        row["slug"]
        for version in (1, 2, 3, 4)
        for row in load("overlays", f"catalog-retirements-v{version}.json")["rows"]
    }
    assert not SLUGS & earlier


@pytest.mark.parametrize(
    "slug",
    [
        "plum-audio-ex2",  # the page states both 12 HP and 2 HP, so neither row can be called wrong
        "plum-audio-ex2-cv-expander",
        "stochastic-instruments-strange-r",  # the page sells a bundle of two sizes
        "endorphin-es-milky-way-1u-silver",  # retired by v6, with the brand splits
        "joranalogue-filter-8",
        "joranalogue-generate-3",
        "mutable-instruments-ripples",
        "mutable-instruments-tides-2014-version",
        "analogue-systems-rs-650",  # robots.txt didn't answer
        "expert-sleepers-es-3-mk2",  # a revision the page names
        "atonal-circuits-see-v1",
        "bastl-instruments-knit-rider",  # a real pair with its expander
        "doepfer-a-180-1",
    ],
)
def test_a_row_the_review_left_alone_stays(slug) -> None:
    assert slug not in SLUGS


def test_a_kept_row_takes_what_only_the_retired_row_held() -> None:
    fills = {entry["slug"]: entry for entry in load("overlays", "module-catalog-category-v9.json")["entries"]}
    assert (fills["endorphin-es-autopilot"]["category"], fills["endorphin-es-grand-terminal"]["category"]) == (
        "UTIL", "VCF",
    )
    for entry in fills.values():
        assert entry["does"] in entry["maker_quote"] and len(entry["content_sha256"]) == 64
    (depth,) = load("overlays", "module-power-depth-v16.json")["entries"]
    assert (depth["name"], depth["depth_mm"]) == ("ES-40 SPDIF Interface", 51)
    assert "51mm" in depth["quote"]


def test_a_retirement_lists_the_module_only_the_first_time() -> None:
    plan = P.Plan()
    catalog = {"acme-lead": {"brand": "Acme", "name": "Lead"}}
    modules = {("Acme", "Lead"): {"status": "active"}}
    entry = {"slug": "acme-lead", "brand": "Acme", "name": "Lead", "reason": "duplicate", "evidence_url": "https://a.example"}
    P._schedule_retirement(plan, catalog, modules, entry)
    P._schedule_retirement(plan, catalog, modules, entry)
    assert plan.retiring_modules == [("Acme", "Lead")]


def test_the_rig_count_reports_racks_and_placements_only() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE modules (id INTEGER PRIMARY KEY, brand TEXT, name TEXT)"))
        conn.execute(text("CREATE TABLE rack_modules (id INTEGER PRIMARY KEY, rack_id INTEGER, module_id INTEGER)"))
        conn.execute(text("INSERT INTO modules VALUES (1, 'Acme', 'Lead'), (2, 'Acme', 'Other'), (3, 'Acme', 'Kept')"))
        conn.execute(text("INSERT INTO rack_modules VALUES (1, 10, 1), (2, 10, 1), (3, 11, 2), (4, 12, 3)"))
        got = P._rigs_holding(conn, [("Acme", "Lead"), ("Acme", "Other")])
        assert got == {"modules_retiring": 2, "rigs": 2, "placements": 3}
        assert P._rigs_holding(conn, []) == {"modules_retiring": 0, "rigs": 0, "placements": 0}
