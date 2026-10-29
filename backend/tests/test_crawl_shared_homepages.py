"""Spec 003 T030: the crawler refuses a homepage another brand holds, before crawling."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import build_maker_overlays as B  # noqa: E402
import catalog_maker_crawl as crawl  # noqa: E402

RESEARCH = ROOT / "data" / "synth-catalog" / "hermes-research"


def _resolutions(name: str) -> dict[str, dict]:
    """Each brand's resolved homepage as a committed crawl recorded it (no fetches)."""
    data = json.loads((RESEARCH / name).read_text())
    return {
        b["brand"]: {"brand": b["brand"], "homepage": b["homepage"], "status": "resolved", "how": b.get("resolved_by")}
        for b in data["brands"]
        if b.get("homepage")
    }


def test_the_committed_v2_resolutions_reproduce_every_known_misattribution() -> None:
    resolved = _resolutions("maker-crawl-v2.json")
    conflicts = crawl.guard_shared_homepages(resolved, known={})
    refused = {b: r["owner"] for b, r in resolved.items() if r["status"] == "shared_homepage"}
    assert refused == {
        "British Noise Electronics": "Noise Engineering",
        "Endangered Audio Research": "ARC",
        "Epicycloid Engineering": "Noise Engineering",
        "Mental Noise": "Make Noise",
        "Phase Engineering": "Noise Engineering",
        "Thonk Synth": "Thonk",
        "Winter Plankton": "Winter Modular",
        "d:Machinery": "Infinite Machinery",
        # No brand named in the host; the adapter-resolved maker owns it.
        "Barcode Circuits": "ALM Busy Circuits",
        "FKMG Circuits": "ALM Busy Circuits",
        "Swizzle Circuits": "ALM Busy Circuits",
        "Warped Circuits": "ALM Busy Circuits",
        # Both spellings are in the host; the curated one owns it.
        "Instruō": "Instruo",
        # No owner at all: every brand on the host is refused.
        "In The Trees": None,
        "Jasmine & Olive Trees": None,
        "Mad Rooster Lab": None,
        "Olitronik_lab": None,
        "Vintage Synth Lab": None,
    }
    owners = {c["owner"] for c in conflicts}
    assert {"Make Noise", "Noise Engineering", "ARC", "ALM Busy Circuits", "Instruo"} <= owners
    assert resolved["ALM Busy Circuits"]["homepage"] == "https://busycircuits.com/"
    # The owner keeps its homepage and is crawled as before.
    assert resolved["Make Noise"]["homepage"] == "https://www.makenoisemusic.com/"
    mental = resolved["Mental Noise"]
    assert mental["homepage"] is None and mental["candidate"] == "https://www.makenoisemusic.com/"
    assert mental["shared_with"] == ["Make Noise"]


def test_the_v1_resolutions_held_the_mistake_already() -> None:
    resolved = _resolutions("maker-crawl-v1.json")
    crawl.guard_shared_homepages(resolved, known={})
    assert resolved["Mental Noise"]["status"] == "shared_homepage"
    assert resolved["Phase Engineering"]["status"] == "shared_homepage"


def test_a_partial_run_checks_against_brands_already_crawled() -> None:
    resolved = {"Mental Noise": {"brand": "Mental Noise", "homepage": "https://www.makenoisemusic.com/", "how": "v1_crawl"}}
    conflicts = crawl.guard_shared_homepages(resolved, known={"Make Noise": "https://www.makenoisemusic.com/"})
    assert [c["owner"] for c in conflicts] == ["Make Noise"]
    assert resolved["Mental Noise"]["status"] == "shared_homepage"


def test_a_host_no_brand_is_named_in_is_refused_for_every_brand() -> None:
    resolved = {
        name: {"brand": name, "homepage": "https://synthshop.example/", "how": "domain_match"}
        for name in ("Alpha Audio", "Beta Labs")
    }
    conflicts = crawl.guard_shared_homepages(resolved, known={})
    assert conflicts == [{"host": "synthshop.example", "brands": ["Alpha Audio", "Beta Labs"], "owner": None}]
    assert all(r["status"] == "shared_homepage" for r in resolved.values())


def test_a_refused_brand_is_recorded_not_crawled() -> None:
    class Budget:
        def can_spend(self) -> bool:
            return True

    crawl.BUDGET = Budget()
    rec = crawl.crawl_brand(
        "Mental Noise", cap=5,
        r={"brand": "Mental Noise", "homepage": None, "status": "shared_homepage", "how": "v1_crawl",
           "candidate": "https://www.makenoisemusic.com/", "owner": "Make Noise", "shared_with": ["Make Noise"]},
    )
    assert rec["status"] == "shared_homepage" and rec["modules"] == [] and rec["pages"] == 0
    assert rec["owner"] == "Make Noise" and rec["candidate"] == "https://www.makenoisemusic.com/"


def test_overlay_builds_still_skip_only_owned_hosts() -> None:
    brands = [
        {"brand": "Make Noise", "homepage": "https://www.makenoisemusic.com/"},
        {"brand": "Mental Noise", "homepage": "https://www.makenoisemusic.com/"},
        {"brand": "Alpha Audio", "homepage": "https://synthshop.example/"},
        {"brand": "Beta Labs", "homepage": "https://synthshop.example/"},
    ]
    assert B.shared_homepage_skips(brands) == {"Mental Noise": "Make Noise"}


def test_a_partial_rerun_keeps_an_earlier_refusal() -> None:
    """Both brands on an unowned host were refused and saved with homepage null."""
    committed = [
        {"brand": "In The Trees", "status": "shared_homepage", "homepage": None,
         "candidate": "https://jasmineandolivetrees.com/"},
        {"brand": "Jasmine & Olive Trees", "status": "shared_homepage", "homepage": None,
         "candidate": "https://jasmineandolivetrees.com/"},
        {"brand": "Make Noise", "status": "done", "homepage": "https://www.makenoisemusic.com/"},
    ]
    known = crawl.committed_claims(committed)
    assert known["Jasmine & Olive Trees"] == "https://jasmineandolivetrees.com/"
    rerun = {"In The Trees": {"brand": "In The Trees", "homepage": "https://jasmineandolivetrees.com/", "how": "v1_crawl"}}
    crawl.guard_shared_homepages(rerun, known)
    assert rerun["In The Trees"]["status"] == "shared_homepage"
    assert rerun["In The Trees"]["shared_with"] == ["Jasmine & Olive Trees"]


def test_a_refused_brand_saved_by_a_real_run_keeps_its_candidate() -> None:
    crawl.BUDGET = type("B", (), {"can_spend": lambda self: True})()
    rec = crawl.crawl_brand("In The Trees", cap=5, r={
        "brand": "In The Trees", "homepage": None, "status": "shared_homepage", "how": "v1_crawl",
        "candidate": "https://jasmineandolivetrees.com/", "owner": None, "shared_with": ["Jasmine & Olive Trees"],
    })
    assert crawl.committed_claims([rec]) == {"In The Trees": "https://jasmineandolivetrees.com/"}
