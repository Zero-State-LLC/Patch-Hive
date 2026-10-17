"""Parser tests for batch 8. No network."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

from batch8 import (  # noqa: E402
    extract_h1,
    extract_vendor,
    name_from_title,
    page_mentions,
    parse_specs,
    verify_candidate,
)
from catalog_scrape import FetchResult  # noqa: E402


class _Stub:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def fetch(self, url: str, timeout: float = 25) -> FetchResult:
        del timeout
        body = self.pages.get(url)
        if body is None:
            return FetchResult(False, None, {"url": url, "method": "free_http", "status": 404, "sha256": None, "timestamp": "t"})
        return FetchResult(True, body, {"url": url, "method": "free_http", "status": 200, "sha256": "abc", "timestamp": "t"})


PAGE = """
<html><div class="module-view-header"><h1>Bitbox 2.0</h1></div>
<span class="vendor-name">1010 Music</span>
350 mA +12V 0 mA -12V 0 mA 5V
25 mm deep
</html>
"""


def test_parse_specs_keeps_zero_and_single_depth() -> None:
    specs = parse_specs(PAGE)
    assert specs["power_12v_ma"] == 350
    assert specs["power_neg12v_ma"] == 0
    assert specs["power_5v_ma"] == 0
    assert specs["depth_mm"] == 25.0


def test_parse_specs_reads_a_three_rail_line() -> None:
    specs = parse_specs("10 mA +12V 20 mA -12V 30 mA 5V")
    assert specs == {
        "power_12v_ma": 10,
        "power_neg12v_ma": 20,
        "power_5v_ma": 30,
        "depth_mm": None,
    }


def test_parse_specs_drops_disagreeing_values() -> None:
    specs = parse_specs("10 mA +12V and later 20 mA +12V")
    assert specs["power_12v_ma"] is None


def test_extractors_and_name() -> None:
    assert extract_vendor(PAGE) == "1010 Music"
    assert extract_h1(PAGE) == "Bitbox 2.0"
    assert name_from_title("1010 Music Bitbox 2.0 - Eurorack Module on ModularGrid", "1010 Music") == "Bitbox 2.0"


def test_verify_candidate_statuses() -> None:
    url = "https://modulargrid.net/e/1010-music-bitbox-2-0"
    row = {"brand": "1010 Music", "page_title": "1010 Music Bitbox 2.0 - Eurorack Module on ModularGrid", "source_url": url, "hp": 26}
    verified = verify_candidate(_Stub({url: PAGE}), row, set())
    assert verified["verification_status"] == "verified"
    assert verified["effective_brand"] == "1010 Music"
    assert verified["module_name"] == "Bitbox 2.0"
    assert verified["provenance"] == "OBSERVED"
    assert verified["catalog_match"] == "new"

    corrected_page = PAGE.replace("1010 Music", "Other Brand")
    corrected = verify_candidate(_Stub({url: corrected_page}), row, {"other-brand-bitbox-2-0"})
    assert corrected["verification_status"] == "corrected"
    assert corrected["effective_brand"] == "Other Brand"
    assert corrected["catalog_match"] == "duplicate"

    flagged = verify_candidate(_Stub({}), row, set())
    assert flagged["verification_status"] == "flagged"
    assert flagged["provenance"] == "NOT_COMPUTABLE"


def test_page_mentions_requires_name_and_brand_for_short_names() -> None:
    assert page_mentions("<p>Doepfer A-101-4 draws 30 mA +12V</p>", "Doepfer", "A-101-4")
    assert not page_mentions("<p>some other module 30 mA +12V</p>", "Doepfer", "A-101-4")
    assert not page_mentions("<p>AP-1 only</p>", "Cwejman", "AP-1")
    assert page_mentions("<p>Cwejman AP-1</p>", "Cwejman", "AP-1")
