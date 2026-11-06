"""Spec 003 FR-018: a catalog input is versioned and never edited in place."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))
sys.path.insert(0, str(ROOT / "scripts"))

from freeze_catalog_inputs import read_frozen  # noqa: E402
from population import input_file_hashes  # noqa: E402


def test_no_recorded_input_has_changed():
    current = input_file_hashes()
    changed = sorted(path for path, digest in read_frozen().items() if current.get(path) != digest)
    assert changed == [], "write a new version of these instead of editing them"


def test_every_input_is_recorded():
    missing = sorted(input_file_hashes().keys() - read_frozen().keys())
    assert missing == [], "run scripts/freeze_catalog_inputs.py to record new versions"
