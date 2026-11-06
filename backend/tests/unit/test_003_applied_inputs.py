"""Spec 003 FR-018: a catalog input is versioned and never edited in place."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

from population import input_file_hashes  # noqa: E402

FROZEN = json.loads((ROOT / "data" / "synth-catalog" / "applied-inputs.json").read_text(encoding="utf-8"))["files"]


def test_no_recorded_input_has_changed():
    current = input_file_hashes()
    changed = sorted(path for path, digest in FROZEN.items() if current.get(path) != digest)
    assert changed == [], "write a new version of these instead of editing them"


def test_every_input_is_recorded():
    missing = sorted(input_file_hashes().keys() - FROZEN.keys())
    assert missing == [], "run scripts/freeze_catalog_inputs.py to record new versions"
