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
        "4ms Row Power 30",
        "Boulder Folder (Pedal)",
        "Bartender V1 Upgrade",
        "Pixie Aluminum Panel",
        "Warp Drive (1.25A)",
        "Teensy 3.2",
        "EURORACK 104 Case",
        "A-100 Kofferversionen",
    ],
)
def test_store_products_that_are_not_modules(name: str) -> None:
    assert b.NOT_MODULE_NAME.search(name)


def test_real_module_names_pass() -> None:
    for name in ("Maths", "Quad VCA", "Send VCA", "Plonk", "Panel Mixer 4"):
        assert not b.NOT_MODULE_NAME.search(name), name


@pytest.mark.parametrize("version", [3, 4, 5, 6])
def test_committed_overlays_respect_fr007_and_tag_official_rows(version: int) -> None:
    overlays = ROOT / "data" / "synth-catalog" / "overlays"
    rows = json.loads((overlays / f"catalog-additions-v{version}.json").read_text())["rows"]
    assert rows and all(b.HP_MIN <= r["hp"] <= b.HP_MAX for r in rows)
    assert {r["access_basis"] for r in rows} == {"official_publication"}
    assert {r["source"] for r in rows} == {"ManufacturerCrawl"}
    assert not any("modulargrid" in (r["manufacturer_url"] or "") for r in rows)


T026_BRANDS = {"4ms Company", "Erica Synths", "Pittsburgh Modular"}


def test_t026_overlays_hold_only_the_partial_pass_and_repeat_nothing() -> None:
    overlays = ROOT / "data" / "synth-catalog" / "overlays"
    load = lambda name, key: json.loads((overlays / name).read_text())[key]  # noqa: E731
    v4, v12 = load("catalog-additions-v4.json", "rows"), load("module-power-depth-v12.json", "entries")
    assert {r["brand"] for r in v4} == T026_BRANDS and {e["brand"] for e in v12} == T026_BRANDS
    v3 = {(r["brand"].lower(), r["name"].lower()) for r in load("catalog-additions-v3.json", "rows")}
    v11 = {(e["brand"], e["name"]) for e in load("module-power-depth-v11.json", "entries")}
    assert not v3 & {(r["brand"].lower(), r["name"].lower()) for r in v4}
    assert not v11 & {(e["brand"], e["name"]) for e in v12}


@pytest.mark.parametrize(
    "name,tags,expected",
    [
        ("Pico SEQ", [], "SEQ"),
        ("4ms PEG", [], "ENV"),
        ("Hexinverter Mutant Clap", [], "VCO"),
        ("12V Motor Drive", [], None),
        ("WF2 Wavefolder and E2 Expander", [], "FX"),
        # Whole words only: these names are not what the keyword says (Codex review on #77).
        ("Black Octasource", [], None),  # an LFO; its category comes from maker-review-v1
        ("Hexinverter Mindphaser", [], None),  # a complex oscillator
        ("KickAid", [], None),  # processes a kick; not a kick voice
        ("Demux Phaser", [], "FX"),
        ("Kick", [], "VCO"),
        # The name fallback never overrides what the tag and name rules assign.
        ("Gesture Recorder", ["lfo", "envelope"], "ENV"),
    ],
)
def test_name_fallback_only_fills_a_missing_category(name: str, tags: list[str], expected: str | None) -> None:
    assert b.category(tags, name) == expected


A3_ROWS = {
    ("2hp", "Mix"),
    ("Bastl Instruments", "Aikido"),
    ("Bastl Instruments", "Citadel Alchemist"),
    ("Bastl Instruments", "Citadel FX Wizard"),
    ("Bastl Instruments", "Citadel Wave Bard"),
    ("Tubbutec", "USB bridge A"),
}


def test_a3_overlays_hold_only_the_new_crawl_rows() -> None:
    """--only-new: the six modules no earlier overlay held, and no power entry for a matched row."""
    overlays = ROOT / "data" / "synth-catalog" / "overlays"
    load = lambda name, key: json.loads((overlays / name).read_text())[key]  # noqa: E731
    v6, v14 = load("catalog-additions-v6.json", "rows"), load("module-power-depth-v14.json", "entries")
    assert {(r["brand"], r["name"]) for r in v6} == A3_ROWS
    assert {(e["brand"], e["name"]) for e in v14} == A3_ROWS
    earlier = {
        (r["brand"], r["name"])
        for n in range(1, 6)
        if (path := overlays / f"catalog-additions-v{n}.json").is_file()
        for r in json.loads(path.read_text())["rows"]
    }
    assert not A3_ROWS & earlier
