"""One rounding rule for published draws: the overlay script matches the loader."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import apply_module_power_depth_overlay as overlay  # noqa: E402
import population as P  # noqa: E402


@pytest.mark.parametrize("published", [3.5, 2.5, 0.4, 0.5, 12, "7.5", -3.5])
def test_overlay_script_stores_draws_like_the_loader(published) -> None:
    assert overlay.stored_ma(published) == P._as_stored("power_12v_ma", published)


def test_half_milliamps_round_up_not_down() -> None:
    assert overlay.stored_ma(3.5) == 4
    assert overlay.stored_ma(2.5) == 3
