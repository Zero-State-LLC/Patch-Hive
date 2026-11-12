"""One rounding rule for published draws: half a milliamp rounds up."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402


def test_half_milliamps_round_up_not_down() -> None:
    assert P._as_stored("power_12v_ma", 3.5) == 4
    assert P._as_stored("power_12v_ma", 2.5) == 3
