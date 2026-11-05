"""Spec 003 T031 offline pass: whole-tag rules for tagged rows, held video and power rows."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import build_category_overlay as c  # noqa: E402

OVERLAYS = ROOT / "data" / "synth-catalog" / "overlays"
CATEGORIES = {"VCO", "VCF", "VCA", "ENV", "LFO", "MIX", "FX", "SEQ", "UTIL", "SAMP", "MIDI"}

T031 = OVERLAYS / "module-catalog-category-v3.json"


@pytest.mark.parametrize(
    "tags,expected",
    [
        (["phase shifter", "eurorack"], "FX"),
        (["drive", "clipper", "stereo"], "FX"),
        (["speech", "synthesizer", "DIY"], "VCO"),
        (["glide", "quad"], "ENV"),
        (["gate", "pattern", "generator"], "SEQ"),
        (["panning", "stereo", "cv"], "MIX"),
        (["VU meter", "1U"], "UTIL"),
        (["inverter", "adder"], "UTIL"),
    ],
)
def test_t031_whole_tag_rules(tags, expected) -> None:
    assert c.classify(tags, "Widget", "") == (expected, "crawl_tag")


@pytest.mark.parametrize(
    "tags",
    [
        ["percussion", "dual decay", "CV"],  # a voice or an envelope: left empty
        ["rectifier", "CV"],  # no rule: makers file rectifiers under FX and UTIL alike
        ["headphone", "feedback"],  # only the plural is the headphone-output utility
    ],
)
def test_t031_rules_leave_unsettled_rows_empty(tags) -> None:
    assert c.classify(tags, "Widget", "") is None


def test_video_and_power_rows_are_held_for_the_owner() -> None:
    assert c.held(["video", "keyer"], "Acme", set()) == "video"
    assert c.held(["phase shifter", "ramp"], "Syntonie", {"Syntonie"}) == "video"
    assert c.held(["power", "usb-c", "supply"], "Acme", set()) == "power"
    assert c.held(["phase shifter"], "Acme", set()) is None
    crawl = {"brands": [
        {"brand": "Vid", "modules": [{"tags": ["video"]}, {"tags": ["Video", "sync"]}, {"tags": ["ramp"]}]},
        {"brand": "Half", "modules": [{"tags": ["video"]}, {"tags": ["scope"]}]},
    ]}
    assert c.video_brands(crawl) == {"Vid"}


def test_t031_overlay_classifies_live_rows_only_and_lists_the_held_ones() -> None:
    data = json.loads(T031.read_text())
    entries, held = data["entries"], data["held"]
    assert data["count"] == len(entries) > 0
    assert len({e["slug"] for e in entries}) == len(entries)
    assert {e["category"] for e in entries} <= CATEGORIES
    assert all(e["basis"] == "crawl_tag" for e in entries)  # the new rules decide every v3 row
    assert {h["held_for"] for h in held} == {"video", "power"}
    assert not {e["slug"] for e in entries} & {h["slug"] for h in held}
    earlier = {
        e["slug"]
        for path in OVERLAYS.glob("module-catalog-category-v*.json")
        if path != T031
        for e in json.loads(path.read_text())["entries"]
    }
    assert not {e["slug"] for e in entries} & earlier
    assert "modulargrid" not in json.dumps([entries, held]).lower()
