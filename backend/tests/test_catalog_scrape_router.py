"""Mock-HTTP tests for the in-repo catalog scraper."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

from catalog_scrape import (  # noqa: E402
    CatalogScraper,
    HttpRequest,
    HttpResponse,
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


def _blocked_site() -> FakeTransport:
    transport = FakeTransport()
    transport.routes["https://ex.com/p"] = (403, b"no")
    return transport


def _paid_calls(transport: FakeTransport) -> list:
    return [c for c in transport.calls if "api.context.dev" in c.url or "api.firecrawl.dev" in c.url]


def test_paid_fetch_refused_without_matching_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    for entries in ([], [_approval(expires_at="2000-01-01T00:00:00Z")], [_approval(brands=["Other"])], [_approval(approver="")]):
        transport = _blocked_site()
        scraper = _gated(tmp_path, entries, transport, brands=("Acme",))
        scraper.fetch("https://ex.com/p")
        assert _paid_calls(transport) == []
        assert any(r["method"] == "skipped_no_approval" for r in scraper.receipts)


def test_paid_fetch_refused_when_approvals_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    transport = _blocked_site()
    scraper = _scraper(tmp_path, transport, max_paid_fetches=5, approvals_path=tmp_path / "absent.json")
    scraper.fetch("https://ex.com/p")
    assert _paid_calls(transport) == []


def test_paid_fetch_allowed_with_matching_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    transport = _blocked_site()
    transport.routes["https://api.context.dev/v1/web/scrape"] = (200, json.dumps({"html": "<html>paid</html>"}))
    scraper = _gated(tmp_path, [_approval()], transport, brands=("Acme",))
    assert scraper.fetch("https://ex.com/p").ok
    assert len(_paid_calls(transport)) == 1


def test_wildcard_entry_covers_unscoped_run(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    transport = _blocked_site()
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
        transport = _blocked_site()
        scraper = _gated(tmp_path, [_approval(**over)], transport, ledger=ledger, brands=("Acme",))
        scraper.fetch("https://ex.com/p")
        assert _paid_calls(transport) == []


def test_ledger_baseline_leaves_headroom(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "k")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    transport = _blocked_site()
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


def test_committed_approvals_file_has_no_active_entries():
    doc = json.loads((ROOT / "data" / "synth-catalog" / "receipts" / "fetch-approvals.json").read_text())
    assert doc["entries"] == []
