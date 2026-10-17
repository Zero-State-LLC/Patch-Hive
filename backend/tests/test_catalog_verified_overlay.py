from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402


def _offline_plan(monkeypatch):
    monkeypatch.setattr(P, "_catalog_state", lambda conn: {})
    monkeypatch.setattr(P, "_module_state", lambda conn: {})
    monkeypatch.setattr(P, "_manufacturer_state", lambda conn: set())
    return P.build_plan(None)


def test_verified_overlay_wins_and_older_unverified_entries_are_skipped(monkeypatch):
    plan = _offline_plan(monkeypatch)
    ops = [op for op in plan.ops if op.params.get("brand") == "Noise Engineering" and op.params.get("name") == "Desmodus Versio"]
    module_ops = [op for op in ops if "INSERT INTO modules" in op.sql]
    assert len(module_ops) == 1
    params = module_ops[0].params
    # Manufacturer lists two revisions, so power stays empty even though older overlays had 70/70.
    assert params["power_12v_ma"] is None
    assert params["power_neg12v_ma"] is None
    assert params["depth_mm"] == 38.0
    assert params["verification_status"] == "verified"
    assert not [op for op in ops if op.sql.lstrip().startswith("UPDATE modules")]


def test_catalog_additions_have_no_modulargrid_data():
    rows = json.loads((ROOT / "data/synth-catalog/overlays/catalog-additions-v1.json").read_text())["rows"]
    assert rows
    for row in rows:
        assert "modulargrid" not in (row.get("manufacturer_url") or "")
        assert row["hp"] is not None


def test_entry_verification_rejects_unknown_status():
    assert P._entry_verification({"verification_status": "bogus"}) == (None, None)
    assert P._entry_verification({"verification_status": "verified", "source_url": "https://x.example"}) == (
        "verified",
        "https://x.example",
    )


def test_verified_entry_that_disagrees_with_stored_values_flags_instead_of_verifying():
    plan = P.Plan()
    existing = {
        "brand": "Noise Engineering",
        "name": "Basimilus Iteritas Alter",
        "power_12v_ma": 70,
        "power_neg12v_ma": 10,
        "power_5v_ma": None,
        "depth_mm": None,
        "verification_status": "unverified",
        "verification_source_url": None,
    }
    P._schedule_fill(
        plan,
        existing,
        {
            "power_12v_ma": 150,
            "power_neg12v_ma": 5,
            "power_5v_ma": 0,
            "depth_mm": 38.0,
            "verification_status": "verified",
            "verification_source_url": "https://example.com/manual",
        },
        kind="power_depth_overlay",
    )
    assert existing["power_12v_ma"] == 70
    assert existing["power_neg12v_ma"] == 10
    assert existing["verification_status"] == "flagged"
    assert existing["depth_mm"] == 38.0
