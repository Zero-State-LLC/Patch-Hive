"""Endorphin.es Cockpit power and depth (2026-10-31): module-power-depth-v15.

The maker's COCKPIT MK1 page offers the module in BLACK and GOLDEN and states its draw
and depth once; modulargrid-provenance-v1 had nulled both rows. v15 fills them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402

OVERLAYS = ROOT / "data" / "synth-catalog" / "overlays"


def test_v15_fills_both_cockpits_from_the_maker_page_and_is_loaded() -> None:
    v14 = json.loads((OVERLAYS / "module-power-depth-v14.json").read_text())
    v15 = json.loads((OVERLAYS / "module-power-depth-v15.json").read_text())
    assert P.POWER_OVERLAY_LATEST == 15
    assert v15["count"] == len(v15["entries"]) == 2
    hp_source = {e["slug"]: e for e in json.loads((OVERLAYS / "module-catalog-hp-v5.json").read_text())["entries"]}
    page = hp_source["endorphin-es-cockpit-black"]["source_url"]
    for entry in v15["entries"]:
        assert set(v14["entries"][0]) <= set(entry)
        assert entry["brand"] == "Endorphin.es" and entry["name"] in {"Cockpit (black)", "Cockpit (golden)"}
        values = (entry["power_12v_ma"], entry["power_neg12v_ma"], entry["power_5v_ma"], entry["depth_mm"])
        assert values == (75, 4, 0, 38)
        assert entry["source_url"] == entry["verification_source_url"] == page
        assert entry["verification_status"] == "verified" and set(entry["sources"].values()) == {page}
        assert "75 mA +12V 4 mA -12V 0 mA 5V" in entry["quote"] and "38 mm deep" in entry["quote"]
        assert "GOLDEN" in entry["quote"]


def test_v15_fills_only_empty_fields() -> None:
    (black, _) = json.loads((OVERLAYS / "module-power-depth-v15.json").read_text())["entries"]
    empty = {"power_12v_ma": None, "power_neg12v_ma": None, "power_5v_ma": None, "depth_mm": None,
             "verification_status": None, "verification_source_url": None}
    modules = {("Endorphin.es", "Cockpit (black)"): dict(empty, brand="Endorphin.es", name="Cockpit (black)", depth_mm=40)}
    plan = P.Plan()
    P._schedule_power(plan, {}, modules, black)
    # One fill; every column is COALESCEd, so a value already stored is never overwritten.
    (op,) = plan.ops
    assert op.kind == "fill_module" and plan.conflicts_total == 0
    assert "COALESCE(depth_mm" in op.sql and "COALESCE(power_12v_ma" in op.sql
