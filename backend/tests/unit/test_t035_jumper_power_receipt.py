"""Spec 003 T035: the jumper-power receipt is well formed and every value carries its quote.

The receipt records each setting's draws from a free re-fetch of the maker pages.
A value with no verbatim quote, or a quote that is not part of the page's power
block, would be an invented hardware fact.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "data" / "synth-catalog"
RECEIPT = CATALOG / "receipts" / "t035-jumper-power.json"
RAILS = ("+12V", "-12V", "+5V")
KINDS = {"jumper", "configuration", "load_condition", "single"}
STATUSES = {"stated", "not_used", "not_stated"}


@pytest.fixture(scope="module")
def receipt() -> dict:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_receipt_records_a_free_run_with_no_blocks(receipt: dict) -> None:
    assert receipt["mode"] == "free"
    assert receipt["fetch"]["method"] == "free_http"
    assert receipt["fetch"]["paid_credits"] == 0
    assert receipt["fetch"]["paid_backends_used"] == []
    assert receipt["fetch"]["raw_html_committed"] is False
    assert receipt["fetch"]["min_spacing_s"] >= 2
    hosts = {p["url"].split("/")[2] for p in receipt["pages"]}
    robots = {r["host"]: r for r in receipt["robots"]}
    assert hosts == set(robots)
    for r in robots.values():
        assert r["http_status"] == 200
        assert r["target_pages_allowed"] is True
        assert re.fullmatch(r"[0-9a-f]{64}", r["content_sha256"])
        if r["crawl_delay_s"]:
            assert receipt["fetch"]["host_spacing_s"][r["host"]] >= r["crawl_delay_s"]
    assert receipt["blocks"] == [] or all(b.get("host") for b in receipt["blocks"])


def test_page_list_matches_committed_crawl(receipt: dict) -> None:
    crawl = json.loads(
        (CATALOG / "hermes-research" / "maker-crawl-v2.json").read_text(encoding="utf-8")
    )
    expected = set()
    for brand in crawl["brands"]:
        for row in brand["modules"]:
            if brand["brand"] == "4ms Company" and "row power" not in row["name"].lower():
                expected.add(row["source_url"])
            elif brand["brand"] in ("Dave Jones Design", "Velectronic"):
                expected.add(row["source_url"])
    urls = [p["url"] for p in receipt["pages"]]
    assert len(urls) == len(set(urls))
    assert set(urls) == expected
    assert receipt["page_list"]["counts"]["total"] == len(urls)
    assert receipt["counts"]["pages_fetched"] == len(urls)


def test_no_denied_host(receipt: dict) -> None:
    for page in receipt["pages"]:
        assert "modulargrid" not in page["url"].lower()
        assert "modulargrid" not in page["final_url"].lower()


def test_each_page_has_fetch_evidence(receipt: dict) -> None:
    for page in receipt["pages"]:
        assert page["fetch_method"] == "free_http"
        assert page["http_status"] == 200
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", page["fetched_at"])
        assert re.fullmatch(r"[0-9a-f]{64}", page["content_sha256"])
        assert page["bytes"] > 0
        assert page["quote"].strip()
        assert page["settings"]


def test_every_value_has_a_verbatim_quote(receipt: dict) -> None:
    checked = 0
    for page in receipt["pages"]:
        block = page["quote"]
        for setting in page["settings"]:
            assert setting["kind"] in KINDS
            assert set(setting["rails"]) == set(RAILS)
            if setting["label_on_page"]:
                assert setting["label"] and setting["label"] in block, (
                    page["name"],
                    setting["label"],
                )
            for rail, value in setting["rails"].items():
                assert value["status"] in STATUSES, (page["name"], rail)
                if value["status"] == "not_stated":
                    assert value["ma"] is None and value["quote"] is None, (page["name"], rail)
                    continue
                quote = value["quote"]
                assert quote and quote in block, (page["name"], rail, quote)
                if value["ma"] is not None:
                    assert isinstance(value["ma"], int) and value["ma"] >= 0
                    assert re.search(rf"(?<!\d){value['ma']}(?!\d)", quote.split("\n")[-1]), (
                        page["name"],
                        rail,
                    )
                    checked += 1
                if value["status"] == "stated":
                    assert value["ma"] is not None, (page["name"], rail)
            draw = setting["unattributed_draw"]
            if draw is not None:
                assert draw["quote"] in block and str(draw["ma"]) in draw["quote"]
        for extra in page["supporting_quotes"]:
            assert extra.strip()
    assert checked > 0


def _unit_shown(ma: int, quote: str) -> bool:
    """True when the quote's value line prints the unit right after the number ("80mA", "170 mA", "10ma").

    "max" must not count as the unit: "80 max" states no unit.
    """
    line = quote.split("\n")[-1]
    return re.search(rf"(?<!\d){ma}\s*ma(?![a-z])", line, re.IGNORECASE) is not None


@pytest.mark.parametrize(
    ("ma", "quote", "expected"),
    [
        (80, "+12V rail:\n80 max with jumper selecting external 5V", False),
        (110, "110mA max with jumper selecting internal 5V.", True),
        (170, "+5v = 170 mA", True),
        (10, "+12v rail: 10ma", True),
        (40, "40 maximum", False),
    ],
)
def test_unit_rule(ma: int, quote: str, expected: bool) -> None:
    assert _unit_shown(ma, quote) is expected


def test_unit_stated_matches_each_quote(receipt: dict) -> None:
    checked = 0
    for page in receipt["pages"]:
        for setting in page["settings"]:
            for rail, value in setting["rails"].items():
                if value["ma"] is None:
                    assert value["unit_stated"] is None, (page["name"], setting["label"], rail)
                    continue
                expected = _unit_shown(value["ma"], value["quote"])
                assert value["unit_stated"] is expected, (
                    page["name"],
                    setting["label"],
                    rail,
                    value["quote"],
                )
                checked += 1
    assert checked > 0


def test_jumper_flag_and_counts_agree(receipt: dict) -> None:
    pages = receipt["pages"]
    for page in pages:
        has_jumper = any(s["kind"] == "jumper" for s in page["settings"])
        assert page["jumper_dependent"] is has_jumper
    counts = receipt["counts"]
    assert counts["jumper_dependent_pages"] == sum(p["jumper_dependent"] for p in pages)
    assert counts["http_200"] == sum(p["http_status"] == 200 for p in pages)
    assert counts["rails_not_stated"] == sum(
        v["status"] == "not_stated"
        for p in pages
        for s in p["settings"]
        for v in s["rails"].values()
    )
