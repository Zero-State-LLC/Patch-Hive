"""Maker-crawl overlay builder (spec 003 T025): names, HP range and non-module filtering."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import build_maker_overlays as b  # noqa: E402


@pytest.mark.parametrize(
    "brand,raw,clean",
    [
        ("Bastl Instruments", "Bastl CRUST Eurorack Module", "CRUST"),
        ("Bastl Instruments", "New Bastl Ciao!! Eurorack Module", "Ciao!!"),
        ("Animal Factory Amplification", "Eurorack: Coma Reactor 2", "Coma Reactor 2"),
        ("Intellijel", "Gx", "Gx"),
        ("Make Noise", "Make Noise Maths", "Maths"),
    ],
)
def test_clean_name(brand: str, raw: str, clean: str) -> None:
    assert b.clean_name(brand, raw) == clean


@pytest.mark.parametrize(
    "name",
    [
        "Boulder Folder (Pedal)",
        "Bartender V1 Upgrade",
        "Pixie Aluminum Panel",
        "Warp Drive (1.25A)",
        "Teensy 3.2",
        "EURORACK 104 Case",
    ],
)
def test_store_products_that_are_not_modules(name: str) -> None:
    assert b.NOT_MODULE_NAME.search(name)


def test_real_module_names_pass() -> None:
    for name in ("Maths", "Quad VCA", "Send VCA", "Plonk", "Panel Mixer 4"):
        assert not b.NOT_MODULE_NAME.search(name), name


def test_committed_overlays_respect_fr007_and_tag_official_rows() -> None:
    overlays = ROOT / "data" / "synth-catalog" / "overlays"
    rows = json.loads((overlays / "catalog-additions-v3.json").read_text())["rows"]
    assert rows and all(b.HP_MIN <= r["hp"] <= b.HP_MAX for r in rows)
    assert {r["access_basis"] for r in rows} == {"official_publication"}
    assert {r["source"] for r in rows} == {"ManufacturerCrawl"}
    assert not any("modulargrid" in (r["manufacturer_url"] or "") for r in rows)
