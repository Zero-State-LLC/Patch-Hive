"""Mock-HTTP tests for the in-repo catalog scraper."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

from catalog_scrape import (  # noqa: E402
    CONTEXT_SCRAPE_URL,
    CatalogScraper,
    HttpRequest,
    HttpResponse,
    default_transport,
    parse_robots,
)


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[HttpRequest] = []
        self.routes: dict[str, tuple[int, bytes] | object] = {}

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.calls.append(request)
        handler = self.routes.get(request.url)
        if handler is None and request.url.endswith("/robots.txt"):
            return HttpResponse(404, b"", {})
        if handler is None:
            return HttpResponse(200, b"<html>page</html>", {})
        if callable(handler):
            return handler(request)
        status, body = handler
        return HttpResponse(status, body if isinstance(body, bytes) else body.encode(), {})


def _scraper(tmp_path: Path, transport: FakeTransport, **kwargs) -> CatalogScraper:
    clock = {"mono": 0.0, "wall": 1_700_000_000.0}

    def sleeper(seconds: float) -> None:
        clock["mono"] += seconds

    def monotonic() -> float:
        clock["mono"] += 0.001
        return clock["mono"]

    return CatalogScraper(
        cache_dir=tmp_path / "cache",
        ledger_path=tmp_path / "ledger.json",
        transport=transport,
        sleeper=sleeper,
        monotonic=monotonic,
        wall_clock=lambda: clock["wall"],
        resolve_hosts=False,
        min_interval_s=0,
        host_intervals={},
        **kwargs,
    )


def test_free_fetch_caches_and_receipt_has_no_body(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.routes["https://example.com/module"] = (200, b"<html>Bitbox secret-body</html>")
    scraper = _scraper(tmp_path, transport)
    first = scraper.fetch("https://example.com/module")
    second = scraper.fetch("https://example.com/module")
    assert first.ok
    assert first.receipt["method"] == "free_http"
    assert second.receipt["method"] == "cache"
    assert second.from_cache or second.receipt["method"] == "cache"
    page_gets = [call for call in transport.calls if call.url == "https://example.com/module"]
    assert len(page_gets) == 1
    for receipt in scraper.receipts:
        assert set(receipt) >= {"url", "method", "status", "sha256", "timestamp"}
        assert "secret-body" not in json.dumps(receipt)
    assert "secret-body" not in (tmp_path / "ledger.json").read_text()


def test_robots_disallow_skips_free_fetch(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.routes["https://example.com/robots.txt"] = (200, b"User-agent: *\nDisallow: /secret\n")
    scraper = _scraper(tmp_path, transport)
    result = scraper.fetch("https://example.com/secret")
    assert result.receipt["method"] == "robots_disallowed"
    assert not any(call.url == "https://example.com/secret" for call in transport.calls)


def test_404_does_not_call_paid_backends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "ctxt_secret_test")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-secret")
    transport = FakeTransport()
    transport.routes["https://example.com/missing"] = (404, b"missing")
    scraper = _scraper(tmp_path, transport, max_paid_fetches=5)
    result = scraper.fetch("https://example.com/missing")
    assert result.receipt["status"] == 404
    assert scraper.paid_attempts == 0
    assert not any("api.context.dev" in call.url or "api.firecrawl.dev" in call.url for call in transport.calls)
    blob = json.dumps(scraper.receipts)
    assert "ctxt_secret_test" not in blob
    assert "fc-test-secret" not in blob


def test_retries_then_context_when_key_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "ctxt_secret_test")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    transport = FakeTransport()
    transport.routes["https://example.com/blocked"] = (503, b"nope")
    transport.routes["https://api.context.dev/v1/web/scrape"] = (
        200,
        json.dumps({"markdown": {"success": True, "data": "350 mA +12V"}, "credits": 1}).encode(),
    )
    scraper = _scraper(tmp_path, transport, max_paid_fetches=1)
    result = scraper.fetch("https://example.com/blocked")
    assert result.ok
    assert result.receipt["method"] == "context_dev"
    assert "350 mA" in (result.text or "")
    assert scraper.paid_attempts == 1
    assert sum(1 for call in transport.calls if call.url == "https://example.com/blocked") == 3
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert ledger["paid_fetches"] == 1
    assert "ctxt_secret_test" not in json.dumps(ledger)


def test_missing_keys_skip_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONTEXT_DEV_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    transport = FakeTransport()
    transport.routes["https://example.com/blocked"] = (503, b"nope")
    scraper = _scraper(tmp_path, transport, max_paid_fetches=4)
    result = scraper.fetch("https://example.com/blocked")
    assert not result.ok
    assert any(item["method"] == "skipped_no_key" for item in scraper.receipts)
    assert scraper.paid_attempts == 0


def test_paid_cap_blocks_even_when_keys_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "ctxt_secret_test")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-secret")
    transport = FakeTransport()
    transport.routes["https://example.com/blocked"] = (503, b"nope")

    def boom(request: HttpRequest) -> HttpResponse:
        if "Authorization" in request.headers:
            raise RuntimeError(request.headers["Authorization"])
        return HttpResponse(503, b"nope", {})

    transport.routes["https://example.com/blocked"] = boom
    scraper = _scraper(tmp_path, transport, max_paid_fetches=0)
    result = scraper.fetch("https://example.com/blocked")
    assert not result.ok
    assert any(item["method"] == "skipped_paid_cap" for item in scraper.receipts)
    assert not any(call.url.startswith("https://api.") for call in transport.calls)
    assert "ctxt_secret_test" not in json.dumps(scraper.receipts)


def test_robots_disallow_does_not_escalate_to_paid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "ctxt_secret_test")
    transport = FakeTransport()
    transport.routes["https://example.com/robots.txt"] = (200, b"User-agent: *\nDisallow: /secret\n")
    scraper = _scraper(tmp_path, transport, max_paid_fetches=2)
    result = scraper.fetch("https://example.com/secret")
    assert result.receipt["method"] == "robots_disallowed"
    assert scraper.paid_attempts == 0
    assert not any(call.url.startswith("https://api.") for call in transport.calls)


def test_robots_unavailable_may_use_paid_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "ctxt_secret_test")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    transport = FakeTransport()
    transport.routes["https://example.com/robots.txt"] = (503, b"nope")
    transport.routes["https://api.context.dev/v1/web/scrape"] = (
        200,
        json.dumps({"markdown": {"success": True, "data": "observed spec"}, "credits": 1}).encode(),
    )
    scraper = _scraper(tmp_path, transport, max_paid_fetches=1)
    result = scraper.fetch("https://example.com/module")
    assert result.ok
    assert result.receipt["method"] == "context_dev"
    assert not any(call.url == "https://example.com/module" for call in transport.calls)
    assert "ctxt_secret_test" not in json.dumps(scraper.receipts)


def test_parse_robots_star_group() -> None:
    rules = "User-agent: *\nDisallow: /private\nAllow: /private/ok\n"
    assert parse_robots(rules, "PatchHiveCatalogBot/1.0", "/e/module")
    assert not parse_robots(rules, "PatchHiveCatalogBot/1.0", "/private/page")
    assert parse_robots(rules, "PatchHiveCatalogBot/1.0", "/private/ok")


def test_private_url_is_blocked(tmp_path: Path) -> None:
    scraper = _scraper(tmp_path, FakeTransport())
    result = scraper.fetch("http://127.0.0.1/secret")
    assert result.receipt["method"] == "blocked_url"
    assert scraper.transport.calls == []  # type: ignore[attr-defined]


def test_fake_ip_range_only_trusted_with_opt_in(monkeypatch):
    import ipaddress
    import catalog_scrape as cs

    ip = ipaddress.ip_address("198.18.0.1")
    monkeypatch.delenv("PATCHHIVE_SCRAPE_TRUST_FAKE_IP", raising=False)
    assert cs._trusted_fake_ip(ip) is False
    monkeypatch.setenv("PATCHHIVE_SCRAPE_TRUST_FAKE_IP", "1")
    assert cs._trusted_fake_ip(ip) is True
    assert cs._trusted_fake_ip(ipaddress.ip_address("10.0.0.1")) is False
    assert cs._trusted_fake_ip(ipaddress.ip_address("127.0.0.1")) is False


# ---- FR-003: paid fetches need a matching unexpired approval entry ----

FUTURE = "2099-01-01T00:00:00Z"


def _approval(**over) -> dict:
    entry = {
        "id": "t", "approver": "owner", "expires_at": FUTURE, "brands": ["Acme"],
        "cap_fetches": 5, "cap_credits": 10,
    }
    entry.update(over)
    return entry


def _gated(tmp_path: Path, entries: list, transport: FakeTransport, ledger: dict | None = None, **kwargs):
    approvals = tmp_path / "fetch-approvals.json"
    approvals.write_text(json.dumps({"entries": entries}))
    if ledger is not None:
        (tmp_path / "ledger.json").write_text(json.dumps(ledger))
    return _scraper(tmp_path, transport, max_paid_fetches=5, approvals_path=approvals, **kwargs)


def _overloaded_site() -> FakeTransport:
    transport = FakeTransport()
    transport.routes["https://ex.com/p"] = (503, b"busy")
    return transport


def _paid_calls(transport: FakeTransport) -> list:
    return [c for c in transport.calls if "api.context.dev" in c.url or "api.firecrawl.dev" in c.url]


def test_paid_fetch_refused_without_matching_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    for entries in ([], [_approval(expires_at="2000-01-01T00:00:00Z")], [_approval(brands=["Other"])], [_approval(approver="")]):
        transport = _overloaded_site()
        scraper = _gated(tmp_path, entries, transport, brands=("Acme",))
        scraper.fetch("https://ex.com/p")
        assert _paid_calls(transport) == []
        assert any(r["method"] == "skipped_no_approval" for r in scraper.receipts)


def test_paid_fetch_refused_when_approvals_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    transport = _overloaded_site()
    scraper = _scraper(tmp_path, transport, max_paid_fetches=5, approvals_path=tmp_path / "absent.json")
    scraper.fetch("https://ex.com/p")
    assert _paid_calls(transport) == []


def test_paid_fetch_allowed_with_matching_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    transport = _overloaded_site()
    transport.routes["https://api.context.dev/v1/web/scrape"] = (200, json.dumps({"html": "<html>paid</html>"}))
    scraper = _gated(tmp_path, [_approval()], transport, brands=("Acme",))
    assert scraper.fetch("https://ex.com/p").ok
    assert len(_paid_calls(transport)) == 1


def test_wildcard_entry_covers_unscoped_run(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    transport = _overloaded_site()
    scraper = _gated(tmp_path, [_approval(brands=["*"])], transport)
    scraper.fetch("https://ex.com/p")
    assert len(_paid_calls(transport)) == 1


def test_ledger_at_entry_cap_blocks_paid_fetch(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    for ledger, over in (
        ({"paid_fetches": 5, "credits_by_backend": {"context_dev": 1}}, {}),
        ({"paid_fetches": 1, "credits_by_backend": {"context_dev": 10}}, {}),
        # Spend before the approval (baseline) does not count against the cap.
        ({"paid_fetches": 105, "credits_by_backend": {"context_dev": 1}}, {"ledger_baseline_fetches": 100}),
    ):
        transport = _overloaded_site()
        scraper = _gated(tmp_path, [_approval(**over)], transport, ledger=ledger, brands=("Acme",))
        scraper.fetch("https://ex.com/p")
        assert _paid_calls(transport) == []


def test_ledger_baseline_leaves_headroom(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    transport = _overloaded_site()
    ledger = {"paid_fetches": 102, "credits_by_backend": {"context_dev": 50}}
    scraper = _gated(
        tmp_path, [_approval(ledger_baseline_fetches=100, ledger_baseline_credits=48)], transport,
        ledger=ledger, brands=("Acme",),
    )
    scraper.fetch("https://ex.com/p")
    assert len(_paid_calls(transport)) == 1


def test_free_fetch_unaffected_by_approval_gate(tmp_path):
    transport = FakeTransport()
    scraper = _gated(tmp_path, [], transport)
    assert scraper.fetch("https://ex.com/p").ok
    assert _paid_calls(transport) == []


def test_committed_approvals_file_has_only_the_owner_approved_corpus_photo_entry():
    """The committed file holds exactly the owner's 2026-11-02 approval (300 context.dev searches
    for 007 corpus photos), with its baseline at the ledger totals of that day."""
    doc = json.loads((ROOT / "data" / "synth-catalog" / "receipts" / "fetch-approvals.json").read_text())
    assert doc["entries"] == [
        {
            "id": "corpus-photos-2026-11",
            "approver": "Daniel Meyer (owner; approved in chat 2026-11-02: 300 searches, context.dev)",
            "approved_at": "2026-11-02T11:00:00Z",
            "expires_at": "2026-11-30T23:59:59Z",
            "brands": ["corpus-photos-2026-11"],
            "cap_fetches": 300,
            "cap_credits": 300,
            "ledger_baseline_fetches": 2569,
            "ledger_baseline_credits": 1149,
        }
    ]


def test_parallel_reservations_cannot_overspend_the_approval(tmp_path):
    """Granted-but-unbooked paid calls count against the cap, so workers sharing one
    scraper cannot all pass on the same remaining allowance."""
    scraper = _gated(tmp_path, [_approval(cap_fetches=2, cap_credits=100)], FakeTransport(), brands=("Acme",))
    assert scraper._reserve_paid() is None
    assert scraper._reserve_paid() is None
    assert scraper._reserve_paid() == "skipped_no_approval"
    scraper._bump_ledger("context_dev", 1)
    scraper._bump_ledger("context_dev", 1)
    assert scraper._paid_in_flight == 0
    assert scraper._reserve_paid() == "skipped_no_approval"


def test_unknown_spend_refuses_instead_of_counting_as_zero(tmp_path):
    import catalog_scrape as cs

    approvals = tmp_path / "fetch-approvals.json"
    approvals.write_text(json.dumps({"entries": [_approval(brands=["*"])]}))
    ledger = tmp_path / "ledger.json"
    for broken in ("{not json", "[]", json.dumps({"paid_fetches": "lots"})):
        ledger.write_text(broken)
        ok, reason = cs.check_paid_approval(approvals, ledger)
        assert not ok and "ledger" in reason
    ledger.write_text(json.dumps({"paid_fetches": 3, "credits_by_backend": {"context_dev": 3}}))
    approvals.write_text(json.dumps({"entries": [_approval(brands=["*"], ledger_baseline_fetches=10)]}))
    ok, reason = cs.check_paid_approval(approvals, ledger)
    assert not ok and "below its baseline" in reason
    ledger.unlink()
    approvals.write_text(json.dumps({"entries": [_approval(brands=["*"])]}))
    assert cs.check_paid_approval(approvals, ledger)[0]


def test_the_corpus_photo_approval_admits_only_its_own_scope(tmp_path):
    """The owner approved 300 searches for corpus photos, not catalog crawls: the entry's only
    brand is its scope, so a crawl with real brands or no brands is refused by it."""
    import catalog_scrape as cs

    approvals = ROOT / "data" / "synth-catalog" / "receipts" / "fetch-approvals.json"
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"paid_fetches": 2569, "credits_by_backend": {"context_dev": 1149}}))
    from datetime import datetime, timezone

    now = datetime(2026, 11, 15, tzinfo=timezone.utc).timestamp()  # inside the approval window
    assert cs.check_paid_approval(approvals, ledger, ("corpus-photos-2026-11",), now=now)[0]
    assert not cs.check_paid_approval(approvals, ledger, ("Make Noise",), now=now)[0]
    assert not cs.check_paid_approval(approvals, ledger, (), now=now)[0]


def test_a_blocked_free_search_is_not_scraped_through_a_paid_backend(tmp_path, monkeypatch):
    """Codex review: a DuckDuckGo 403 must not spend a paid scrape of the results page; the only
    paid call is the paid search API itself."""
    import catalog_scrape as cs

    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    import urllib.parse

    query = "acme vco eurorack"
    transport = FakeTransport()
    transport.routes[cs.DDG_LITE + "?" + urllib.parse.urlencode({"q": query})] = (403, b"blocked")
    transport.routes[cs.CONTEXT_SEARCH_URL] = (
        200, json.dumps({"results": [{"url": "https://commons.wikimedia.org/wiki/File:X.jpg"}]})
    )
    scraper = _scraper(tmp_path, transport, max_paid_fetches=1)
    scraper.search(query, limit=3)
    paid = [c.url for c in transport.calls if "api.context.dev" in c.url]
    assert paid == [cs.CONTEXT_SEARCH_URL]
    assert cs.CONTEXT_SCRAPE_URL not in paid


def _firecrawl_site() -> FakeTransport:
    transport = _overloaded_site()
    transport.routes["https://api.firecrawl.dev/v1/scrape"] = (200, json.dumps({"data": {"html": "<p>12 HP</p>"}}))
    return transport


def test_a_non_basic_proxy_tier_needs_an_entry_that_names_it(tmp_path, monkeypatch):
    """A stealth or auto Firecrawl fetch runs only under an approval that names that tier."""
    monkeypatch.delenv("CONTEXT_DEV_API_KEY", raising=False)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc")
    for entries in ([_approval()], [_approval(proxy_tier="auto")]):
        transport = _firecrawl_site()
        scraper = _gated(tmp_path, entries, transport, brands=("Acme",), firecrawl_proxy="stealth")
        assert not scraper.fetch("https://ex.com/p").ok
        assert _paid_calls(transport) == []
        assert any(r["method"] == "skipped_no_approval" for r in scraper.receipts)

    transport = _firecrawl_site()
    scraper = _gated(tmp_path, [_approval(proxy_tier="stealth")], transport, brands=("Acme",), firecrawl_proxy="stealth")
    assert scraper.fetch("https://ex.com/p").ok
    assert json.loads(_paid_calls(transport)[0].body)["proxy"] == "stealth"


def test_a_non_basic_proxy_tier_is_refused_without_an_approvals_file(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTEXT_DEV_API_KEY", raising=False)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc")
    transport = _firecrawl_site()
    scraper = _scraper(tmp_path, transport, max_paid_fetches=5, firecrawl_proxy="auto")
    assert not scraper.fetch("https://ex.com/p").ok
    assert _paid_calls(transport) == []
    assert [r["note"] for r in scraper.receipts if r["method"] == "skipped_proxy_unapproved"] == ["firecrawl"]


def test_the_basic_tier_needs_no_proxy_approval(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTEXT_DEV_API_KEY", raising=False)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc")
    monkeypatch.delenv("PATCHHIVE_FIRECRAWL_PROXY", raising=False)
    transport = _firecrawl_site()
    scraper = _gated(tmp_path, [_approval()], transport, brands=("Acme",))
    assert scraper.fetch("https://ex.com/p").ok
    assert json.loads(_paid_calls(transport)[0].body)["proxy"] == "basic"


def test_a_bot_challenge_is_never_sent_to_a_paid_backend(tmp_path, monkeypatch):
    """Spec 003 D7: a refused site stays refused; no paid render or proxy routes around it."""
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc")
    transport = FakeTransport()
    transport.routes["https://ex.com/p"] = (200, b"<html><title>Just a moment...</title>cf-chl-x</html>")
    scraper = _gated(tmp_path, [_approval(brands=["*"], proxy_tier="stealth")], transport, firecrawl_proxy="stealth")
    result = scraper.fetch("https://ex.com/p")
    assert not result.ok and result.text is None
    assert _paid_calls(transport) == []
    assert [r.get("note") for r in scraper.receipts] == ["challenge"]


# ---- Owner decision 3 (2026-11-04), spec 003 D7 and FR-008: a refusal never reaches a paid backend ----

PAGE = "https://ex.com/p"
BOT_CHECK = b"<html><title>Just a moment...</title>cf-chl-x</html>"
PAID_ANSWER = json.dumps({"markdown": {"success": True, "data": "observed spec"}, "credits": 1})


@pytest.fixture
def paid_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc")


def _would_pay(tmp_path: Path, transport: FakeTransport) -> CatalogScraper:
    """Keys set, budget left and an approval for every brand and tier: only the refusal can stop it."""
    entries = [_approval(brands=["*"], proxy_tier="stealth")]
    return _gated(tmp_path, entries, transport, firecrawl_proxy="stealth")


@pytest.mark.parametrize("status", [401, 403, 451])
def test_a_refused_page_never_reaches_a_paid_backend(tmp_path, paid_keys, status):
    transport = FakeTransport()
    transport.routes[PAGE] = (status, b"no")
    scraper = _would_pay(tmp_path, transport)
    result = scraper.fetch(PAGE)
    assert not result.ok and result.text is None
    assert _paid_calls(transport) == []
    assert scraper.paid_attempts == 0
    assert [(r["method"], r["status"], r.get("note")) for r in scraper.receipts] == [
        ("free_http", status, "refused")
    ]


@pytest.mark.parametrize("answer", [(401, b"no"), (403, b"no"), (451, b"no"), (200, BOT_CHECK)])
def test_a_refused_page_is_not_rendered_through_a_paid_backend_later(tmp_path, paid_keys, answer):
    """render=True skips the free GET, so it must not forget a refusal this run already saw."""
    transport = FakeTransport()
    transport.routes[PAGE] = answer
    scraper = _would_pay(tmp_path, transport)
    scraper.fetch(PAGE)
    result = scraper.fetch(PAGE, render=True)
    assert not result.ok and result.text is None
    assert result.receipt["note"] in {"refused", "challenge"}
    assert _paid_calls(transport) == []
    assert [c.url for c in transport.calls].count(PAGE) == 1


@pytest.mark.parametrize(
    ("answer", "note"),
    [((401, b"no"), "refused"), ((403, b"no"), "refused"), ((451, b"no"), "refused"), ((200, BOT_CHECK), "challenge")],
)
def test_render_asks_the_site_first_and_stops_on_a_refusal(tmp_path, paid_keys, answer, note):
    """An adapter with `render` must not route around a refusal it never asked about. Befaco's does,
    and www.befaco.org answered 403 to a plain GET (docs/evidence/OWNER_ACTIONS_2026-11-02.md)."""
    transport = FakeTransport()
    transport.routes[PAGE] = answer
    scraper = _would_pay(tmp_path, transport)
    result = scraper.fetch(PAGE, render=True)
    assert not result.ok and result.text is None
    assert _paid_calls(transport) == []
    assert scraper.paid_attempts == 0
    assert [(r["method"], r["status"], r.get("note")) for r in scraper.receipts] == [("free_http", answer[0], note)]


@pytest.mark.parametrize("answer", [(200, b"<html><div id=app></div></html>"), (503, b"busy"), (404, b"gone")])
def test_render_still_renders_when_the_site_does_not_refuse(tmp_path, monkeypatch, answer):
    """One free request records what the site said; its body is not used and it is not retried."""
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    transport = FakeTransport()
    transport.routes[PAGE] = answer
    transport.routes[CONTEXT_SCRAPE_URL] = (200, PAID_ANSWER)
    scraper = _scraper(tmp_path, transport, max_paid_fetches=1)
    result = scraper.fetch(PAGE, render=True)
    assert result.ok and result.receipt["method"] == "context_dev" and result.text == "observed spec"
    assert [c.url for c in transport.calls].count(PAGE) == 1
    assert [(r["method"], r["status"], r.get("note")) for r in scraper.receipts][0] == (
        "free_http", answer[0], "render_check"
    )


def test_a_refusal_is_not_kept_for_the_next_run(tmp_path, paid_keys):
    """Only this run remembers it: a maker that lifts the block can be read again."""
    transport = FakeTransport()
    transport.routes[PAGE] = (403, b"no")
    assert not _would_pay(tmp_path, transport).fetch(PAGE).ok
    transport.routes[PAGE] = (200, b"<html>12 HP</html>")
    assert _would_pay(tmp_path, transport).fetch(PAGE).ok


@pytest.mark.parametrize("render", [False, True])
@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_robots_txt_never_reaches_a_paid_backend(tmp_path, paid_keys, status, render):
    transport = FakeTransport()
    transport.routes["https://ex.com/robots.txt"] = (status, b"no")
    scraper = _would_pay(tmp_path, transport)
    result = scraper.fetch(PAGE, render=render)
    assert not result.ok and result.text is None
    assert _paid_calls(transport) == []
    assert scraper.paid_attempts == 0
    assert [c.url for c in transport.calls] == ["https://ex.com/robots.txt"]  # nor is the page fetched
    assert [(r["method"], r.get("note")) for r in scraper.receipts] == [
        ("robots_refused", f"robots.txt answered {status}")
    ]
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert ledger["calls_by_method"]["robots_refused"] == 1


def test_a_refused_robots_txt_refuses_every_page_on_that_origin(tmp_path, paid_keys):
    transport = FakeTransport()
    transport.routes["https://ex.com/robots.txt"] = (403, b"no")
    scraper = _would_pay(tmp_path, transport)
    assert scraper.robots_info(PAGE) == (False, [], 0.0)
    assert not scraper.fetch(PAGE).ok
    assert not scraper.fetch("https://ex.com/q", render=True).ok
    assert _paid_calls(transport) == []
    assert [c.url for c in transport.calls] == ["https://ex.com/robots.txt"]


@pytest.mark.parametrize("status", [429, 500, 503])
def test_load_is_not_a_refusal_and_stays_eligible_for_a_paid_retry(tmp_path, monkeypatch, status):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    transport = FakeTransport()
    transport.routes[PAGE] = (status, b"busy")
    transport.routes[CONTEXT_SCRAPE_URL] = (200, PAID_ANSWER)
    result = _scraper(tmp_path, transport, max_paid_fetches=1).fetch(PAGE)
    assert result.ok and result.receipt["method"] == "context_dev"


@pytest.mark.parametrize("error", [ConnectionRefusedError("refused"), TimeoutError("timed out")])
def test_a_refused_connection_cannot_be_told_from_a_timeout(tmp_path, monkeypatch, error):
    """Decision 3 leaves refused connections out until the transport can tell them apart. Both are
    status 0 today, so both stay eligible for a paid retry, and such a host stays excluded by name (D7)."""
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")

    class Opener:
        def open(self, *_args, **_kwargs):
            raise urllib.error.URLError(error)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *_handlers: Opener())
    answer = default_transport(HttpRequest("GET", PAGE, {}, None, 1.0))
    assert (answer.status, answer.body, answer.headers) == (0, b"", {})

    def fail(_request: HttpRequest) -> HttpResponse:
        raise error

    transport = FakeTransport()
    transport.routes[PAGE] = fail
    transport.routes[CONTEXT_SCRAPE_URL] = (200, PAID_ANSWER)
    result = _scraper(tmp_path, transport, max_paid_fetches=1).fetch(PAGE)
    assert result.ok and result.receipt["method"] == "context_dev"
