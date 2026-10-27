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
