"""In-repo catalog fetch router.

Free HTTP first (polite UA, robots, per-host delay, disk cache, retries), then
context.dev, then Firecrawl. Keys are read from the environment at call time
and are never written to receipts, the ledger, or exceptions.

Page bodies stay in the disk cache. Receipts store url, method, status, sha256,
and timestamp only.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import random
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

USER_AGENT = (
    "PatchHiveCatalogBot/1.0 (+https://github.com/Zero-State-LLC/Patch-Hive; "
    "catalog research; respects robots.txt)"
)
# Never fetched (Danny 2026-10-17): ModularGrid terms forbid scraping, and
# Patch Hive specs must come from manufacturer pages. Checked before any
# free or paid fetch.
DENY_HOSTS = ("modulargrid.net",)
CONTEXT_SCRAPE_URL = "https://api.context.dev/v1/web/scrape"
CONTEXT_SEARCH_URL = "https://api.context.dev/v1/web/search"
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v1/search"
# Firecrawl's managed proxy tiers (v1 scrape `proxy`). Proxies change where a paid fetch comes
# from, never what may be fetched: robots, the deny list and the paid cap still apply first.
# basic is the default; stealth and auto are used only under a fetch-approvals entry that names
# the tier (`proxy_tier`). context.dev routes through its own managed network; its scrape API has
# no proxy field.
FIRECRAWL_PROXY_TIERS = ("basic", "stealth", "auto")
# Paid backends render the page (browser, proxies), which routinely takes longer than a plain GET.
# A 25 s timeout made most context.dev calls fail in the first v2 run while still using the paid cap.
PAID_TIMEOUT_S = 120.0
DDG_LITE = "https://lite.duckduckgo.com/lite/"

RETRY_STATUSES = {0, 429, 500, 502, 503, 504}
# A 200 that is really a bot check. A refusal (spec 003 D7): recorded as a failed free fetch,
# never parsed as content and never retried through a paid backend that renders or proxies.
CHALLENGE = re.compile(
    rb"(cf-chl-|challenge-platform|<title>\s*(?:Just a moment|Attention Required|Access denied|Are you a robot))", re.I
)
# The site said no (owner decision 3, 2026-11-04; spec 003 D7 and FR-008): recorded, never sent to a
# paid backend. 429, 5xx and timeouts are load, not refusal, and stay eligible for a paid retry. A
# refused connection is not listed because it cannot be told from a timeout: both are status 0.
PAGE_REFUSAL_STATUSES = frozenset({401, 403, 451})
ROBOTS_REFUSAL_STATUSES = frozenset({401, 403})
REFUSAL_NOTES = frozenset({"refused", "challenge"})
RECEIPT_KEYS = ("url", "method", "status", "sha256", "timestamp")


@dataclass
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None
    timeout: float


@dataclass
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str]


@dataclass
class FetchResult:
    ok: bool
    text: str | None
    receipt: dict
    from_cache: bool = False


@dataclass
class SearchResult:
    ok: bool
    urls: list[str]
    receipts: list[dict] = field(default_factory=list)


def public_http_url(url: str) -> bool:
    """True for http(s) URLs whose host is not a literal local or private address."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost."} or host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def denied_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in DENY_HOSTS)


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now_iso(wall: Callable[[], float]) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(wall()))


def _decode(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def _redact(text: str) -> str:
    cleaned = re.sub(r"ctxt_secret_[A-Za-z0-9_\-]+", "[redacted]", text)
    cleaned = re.sub(r"fc-[A-Za-z0-9_\-]+", "[redacted]", cleaned)
    cleaned = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [redacted]", cleaned)
    return cleaned


class _PublicRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not public_http_url(newurl):
            raise urllib.error.HTTPError(req.full_url, code, "refusing non-public redirect", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# What a direct fetch may bring back (spec 003 FR-011): pages, sitemaps, robots.txt
# and JSON feeds, at most MAX_BODY_BYTES. Anything else is refused, not read.
MAX_BODY_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
        "text/xml",
        "application/xml",
        "application/rss+xml",
        "application/atom+xml",
        "application/json",
        "application/ld+json",
        "text/plain",
        "application/gzip",
        "application/x-gzip",
    }
)
REFUSED_HEADER = "x-patchhive-refused"


def _refused(code: str, headers: dict[str, str]) -> HttpResponse:
    return HttpResponse(0, b"", {**headers, REFUSED_HEADER: code})


def _bounded_read(resp, headers: dict[str, str]) -> bytes | None:
    """Read at most MAX_BODY_BYTES; None when the body is larger."""
    declared = headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return None
    body = resp.read(MAX_BODY_BYTES + 1)
    return None if len(body) > MAX_BODY_BYTES else body


def default_transport(request: HttpRequest) -> HttpResponse:
    if not public_http_url(request.url):
        return HttpResponse(0, b"", {})
    opener = urllib.request.build_opener(_PublicRedirectHandler)
    raw = urllib.request.Request(
        request.url,
        data=request.body,
        headers=request.headers,
        method=request.method,
    )
    try:
        with opener.open(raw, timeout=request.timeout) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            media = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            # Some servers send no type at all; those are read, still size-bounded.
            if media and media not in ALLOWED_CONTENT_TYPES:
                return _refused("MIME_NOT_ALLOWED", headers)
            body = _bounded_read(resp, headers)
            if body is None:
                return _refused("BODY_TOO_LARGE", headers)
            return HttpResponse(getattr(resp, "status", 200), body, headers)
    except urllib.error.HTTPError as exc:
        headers = {k.lower(): v for k, v in (exc.headers or {}).items()}
        payload = exc.read(MAX_BODY_BYTES) if exc.fp else b""
        return HttpResponse(exc.code, payload, headers)
    except Exception:
        return HttpResponse(0, b"", {})


def parse_robots(text: str, user_agent: str, path: str) -> bool:
    """Return True when the path is allowed for this user agent."""
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []

    def flush() -> None:
        nonlocal agents, rules
        if agents:
            groups.append((agents, rules))
        agents, rules = [], []

    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            if rules:
                flush()
            agents.append(value)
        elif key in {"allow", "disallow"} and agents:
            rules.append((key, value))
    flush()

    ua = user_agent.lower()
    chosen: list[tuple[str, str]] | None = None
    star: list[tuple[str, str]] | None = None
    best = -1
    for agents, rules in groups:
        for agent in agents:
            if agent == "*":
                star = rules
            elif agent and agent in ua and len(agent) > best:
                chosen = rules
                best = len(agent)
    rules = chosen if chosen is not None else (star or [])
    allow_len = -1
    disallow_len = -1
    for kind, rule in rules:
        if not rule:
            if kind == "disallow":
                allow_len = max(allow_len, 0)
            continue
        if path.startswith(rule):
            if kind == "allow":
                allow_len = max(allow_len, len(rule))
            else:
                disallow_len = max(disallow_len, len(rule))
    if disallow_len < 0:
        return True
    return allow_len >= disallow_len


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        data = {k.lower(): (v or "") for k, v in attrs}
        href = data.get("href", "")
        if href:
            self.hrefs.append(href)


def parse_duckduckgo_links(html: str, limit: int) -> list[str]:
    parser = _LinkParser()
    parser.feed(html or "")
    found: list[str] = []
    seen: set[str] = set()
    for href in parser.hrefs:
        url = href
        parsed = urlparse(href)
        if "uddg" in urllib.parse.parse_qs(parsed.query):
            url = urllib.parse.parse_qs(parsed.query)["uddg"][0]
        url = urllib.parse.unquote(url)
        if not url.startswith("http"):
            continue
        host = (urlparse(url).hostname or "").lower()
        if "duckduckgo." in host or not public_http_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        found.append(url)
        if len(found) >= limit:
            break
    return found


def _json_urls(payload: dict, limit: int) -> list[str]:
    blobs = payload.get("results") or payload.get("data") or []
    urls: list[str] = []
    if isinstance(blobs, dict):
        blobs = blobs.get("results") or blobs.get("web") or []
    for item in blobs:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("link")
        if isinstance(url, str) and public_http_url(url):
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


class CatalogScraper:
    def __init__(
        self,
        *,
        cache_dir: Path,
        ledger_path: Path,
        max_paid_fetches: int = 0,
        min_interval_s: float = 1.0,
        host_intervals: dict[str, float] | None = None,
        user_agent: str = USER_AGENT,
        transport: Callable[[HttpRequest], HttpResponse] | None = None,
        sleeper: Callable[[float], None] | None = None,
        monotonic: Callable[[], float] | None = None,
        wall_clock: Callable[[], float] | None = None,
        max_age_s: float = 86400,
        resolve_hosts: bool = True,
        max_retries: int = 3,
        firecrawl_proxy: str | None = None,
        on_receipt: Callable[[dict], None] | None = None,
        approvals_path: Path | None = None,
        brands: tuple[str, ...] = (),
    ) -> None:
        self.firecrawl_proxy = firecrawl_proxy_tier(firecrawl_proxy)
        self.cache_dir = cache_dir
        self.ledger_path = ledger_path
        self.max_paid_fetches = max(0, int(max_paid_fetches))
        # FR-003: with an approvals file set, a paid call needs a matching unexpired entry whose caps
        # the ledger has not reached. None leaves the gate off (tests and free-only callers).
        self.approvals_path = approvals_path
        self.brands = tuple(brands)
        self.min_interval_s = min_interval_s
        self.host_intervals = host_intervals or {}
        self.user_agent = user_agent
        self.transport = transport or default_transport
        self.sleeper = sleeper or time.sleep
        self.monotonic = monotonic or time.monotonic
        self.wall_clock = wall_clock or time.time
        self.max_age_s = max_age_s
        self.resolve_hosts = resolve_hosts
        self.max_retries = max_retries
        self.receipts: list[dict] = []
        # Called with every new receipt (fetch, paid attempt, skip, search), e.g. to book spend.
        self.on_receipt = on_receipt
        self._memory: dict[str, FetchResult] = {}
        self._next_ok: dict[str, float] = {}
        self._robots: dict[str, str | None] = {}
        # Origins whose robots.txt refused us, with the status it answered.
        self._robots_refused: dict[str, int] = {}
        self.paid_attempts = 0
        # Paid calls granted but not yet booked in the ledger. The approval check counts them,
        # so parallel workers cannot all pass on the same remaining allowance.
        self._paid_in_flight = 0
        # One scraper may be shared by worker threads: the lock guards the paid cap and the ledger file.
        self._lock = threading.RLock()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_repo(cls, max_paid_fetches: int = 0, **kwargs: object) -> CatalogScraper:
        root = Path(__file__).resolve().parents[2]
        catalog = root / "data" / "synth-catalog"
        return cls(
            cache_dir=catalog / ".cache" / "http",
            ledger_path=catalog / "receipts" / "scrape-ledger.json",
            max_paid_fetches=max_paid_fetches,
            approvals_path=catalog / "receipts" / "fetch-approvals.json",
            **kwargs,  # type: ignore[arg-type]
        )

    def fetch(
        self,
        url: str,
        timeout: float = 25,
        *,
        check_robots: bool = True,
        render: bool = False,
        allow_paid: bool = True,
    ) -> FetchResult:
        """Free first, then paid. `render=True` is for script-rendered pages whose plain HTML is an empty
        shell: it returns the paid body and ignores a cached copy that came from a free GET. Robots still
        apply, and one free GET still asks first, because only that can see the site refuse.
        `allow_paid=False` never falls back to a paid backend (used for the free search engine, whose
        paid counterpart is the paid search API, not a scrape of its results page).

        A refusal the router can see never reaches a paid backend. When robots.txt is unreadable for
        another reason (5xx, 429, a timeout) the page is not fetched directly, so its own answer is unseen."""
        cached = self._memory.get(url)
        free_shell = (
            cached is not None
            and cached.receipt.get("method") == "free_http"
            and cached.receipt.get("note") not in REFUSAL_NOTES
        )
        if cached is not None and not (render and free_shell):
            receipt = dict(cached.receipt)
            receipt["method"] = "cache"
            receipt["timestamp"] = _now_iso(self.wall_clock)
            self.receipts.append(receipt)
            self._bump_ledger("cache", 0)
            return FetchResult(cached.ok, cached.text, receipt, from_cache=True)

        blocked = self._block_reason(url)
        if blocked:
            return self._finish(url, blocked, None, b"", ok=False)

        disk = self._read_cache(url, skip_free=render)
        if disk is not None:
            self._memory[url] = disk
            self.receipts.append(disk.receipt)
            self._bump_ledger("cache", 0)
            return disk

        if check_robots:
            allowed, reason = self._robots_allow(url, timeout)
            if not allowed and reason == "robots_unavailable":
                # Do not free-fetch when robots.txt could not be read. A paid
                # backend may still run when a key is set and the cap allows.
                skipped = self._finish(url, "robots_unavailable", None, b"", ok=False, remember=False)
                paid = self._paid_fetch(url, timeout) if allow_paid else None
                return paid if paid is not None else skipped
            if not allowed and reason == "robots_refused":
                # The status belongs to robots.txt, not to this URL, so it goes in the note.
                note = f"robots.txt answered {self._robots_refused[_origin(url)]}"
                return self._finish(url, "robots_refused", None, b"", ok=False, note=note)
            if not allowed:
                return self._finish(url, reason or "robots_disallowed", None, b"", ok=False)

        if render:
            status, body = self._free_get(url, timeout, attempts=1)
            refused = self._refusal(url, status, body)
            if refused is not None:
                return refused
            self._finish(url, "free_http", status, b"", ok=False, note="render_check", remember=False)
            paid = self._paid_fetch(url, timeout) if allow_paid else None
            return paid if paid is not None else self._finish(url, "render_unavailable", None, b"", ok=False, remember=False)

        status, body = self._free_get(url, timeout)
        refused = self._refusal(url, status, body)
        if refused is not None:
            return refused
        if status == 200 and body:
            result = self._finish(url, "free_http", status, body, ok=True)
            self._write_cache(url, result, body)
            return result
        if status == 404:
            result = self._finish(url, "free_http", status, body, ok=False)
            self._write_cache(url, result, body)
            return result

        free_result = self._finish(url, "free_http", status, body, ok=False)
        paid = self._paid_fetch(url, timeout) if allow_paid else None
        return paid if paid is not None else free_result

    def _refusal(self, url: str, status: int, body: bytes) -> FetchResult | None:
        """The recorded refusal when a free answer is the site saying no (spec 003 D7), else None.
        Remembered for this run, so no later call reaches a paid backend. Never written to the disk
        cache, so the next run asks again."""
        if status in PAGE_REFUSAL_STATUSES:
            note = "refused"
        elif status == 200 and body and body.lstrip()[:1] == b"<" and CHALLENGE.search(body[:8000]):
            note = "challenge"
        else:
            return None
        return self._finish(url, "free_http", status, b"", ok=False, note=note)

    def search(self, query: str, limit: int = 5, timeout: float = 25) -> SearchResult:
        limit = max(1, min(int(limit), 10))
        ddg = DDG_LITE + "?" + urllib.parse.urlencode({"q": query})
        # A blocked or challenged free search is not scraped through a paid backend: that would
        # spend the paid budget routing around the block. The paid search API below is the fallback.
        free = self.fetch(ddg, timeout=timeout, allow_paid=False)
        urls = parse_duckduckgo_links(free.text or "", limit) if free.ok else []
        receipts = [free.receipt]
        if len(urls) >= limit:
            return SearchResult(True, urls[:limit], receipts)
        paid_urls, paid_receipts = self._paid_search(query, limit, timeout)
        receipts.extend(paid_receipts)
        merged: list[str] = []
        seen: set[str] = set()
        for url in urls + paid_urls:
            if url not in seen:
                seen.add(url)
                merged.append(url)
        return SearchResult(bool(merged), merged[:limit], receipts)

    def _paid_fetch(self, url: str, timeout: float) -> FetchResult | None:
        for method, key_name, caller in (
            ("context_dev", "CONTEXT_DEV_API_KEY", self._context_fetch),
            ("firecrawl", "FIRECRAWL_API_KEY", self._firecrawl_fetch),
        ):
            key = os.environ.get(key_name, "").strip()
            if not key:
                self._finish(url, "skipped_no_key", None, b"", ok=False, note=method, remember=False)
                continue
            denied = self._reserve_paid(self.firecrawl_proxy if method == "firecrawl" else "basic")
            if denied:
                self._finish(url, denied, None, b"", ok=False, note=method, remember=False)
                continue
            status, body, credits = caller(url, key, max(timeout, PAID_TIMEOUT_S))
            self._bump_ledger(method, credits)
            ok = status == 200 and bool(body)
            note = f"proxy={self.firecrawl_proxy}" if method == "firecrawl" else None
            result = self._finish(
                url, method, status, body, ok=ok, credits=credits, note=note, remember=ok
            )
            if ok:
                self._write_cache(url, result, body)
                return result
        return None

    def _context_fetch(self, url: str, key: str, timeout: float) -> tuple[int, bytes, float]:
        payload = {
            "url": url,
            "formats": {"markdown": True, "html": True},
            "sharedParams": {"mainContentOnly": False},
        }
        status, raw = self._post_json(CONTEXT_SCRAPE_URL, key, payload, timeout)
        if status != 200:
            return status, b"", 0.0
        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return status, b"", 1.0
        text = _context_body(data)
        credits = _credits(data, default=1.0)
        return status, text.encode("utf-8"), credits

    def _firecrawl_fetch(self, url: str, key: str, timeout: float) -> tuple[int, bytes, float]:
        payload = {
            "url": url,
            "formats": ["html", "markdown"],
            "onlyMainContent": False,
            "proxy": self.firecrawl_proxy,
        }
        status, raw = self._post_json(FIRECRAWL_SCRAPE_URL, key, payload, timeout)
        if status != 200:
            return status, b"", 0.0
        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return status, b"", 1.0
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        text = ""
        if isinstance(inner, dict):
            text = inner.get("html") or inner.get("markdown") or inner.get("content") or ""
        return status, str(text).encode("utf-8"), _credits(data, default=1.0)

    def _paid_search(self, query: str, limit: int, timeout: float) -> tuple[list[str], list[dict]]:
        receipts: list[dict] = []
        urls: list[str] = []
        attempts = (
            ("context_dev", "CONTEXT_DEV_API_KEY", CONTEXT_SEARCH_URL, {"query": query, "numResults": 10}),
            ("firecrawl", "FIRECRAWL_API_KEY", FIRECRAWL_SEARCH_URL, {"query": query, "limit": limit}),
        )
        for method, key_name, endpoint, payload in attempts:
            if len(urls) >= limit:
                break
            key = os.environ.get(key_name, "").strip()
            target = endpoint
            if not key:
                receipts.append(self._receipt(target, "skipped_no_key", None, None, note=method))
                continue
            denied = self._reserve_paid()
            if denied:
                receipts.append(self._receipt(target, denied, None, None, note=method))
                continue
            status, raw = self._post_json(endpoint, key, payload, max(timeout, PAID_TIMEOUT_S))
            body_hash = _sha256(raw) if raw else None
            credits = 0.0
            found: list[str] = []
            if status == 200 and raw:
                try:
                    data = json.loads(raw.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    data = {}
                credits = _credits(data, default=1.0)
                found = _json_urls(data, limit)
            self._bump_ledger(method, credits)
            receipts.append(self._receipt(target, method, status, body_hash, credits=credits))
            urls.extend(found)
        return urls[:limit], receipts

    def _reserve_paid(self, proxy_tier: str = "basic") -> str | None:
        """Reserve one paid call. None when granted, else the receipt method naming the refusal.
        A non-basic proxy tier needs an approvals entry that names it, so with no approvals file
        it is refused."""
        with self._lock:
            if self.paid_attempts >= self.max_paid_fetches:
                return "skipped_paid_cap"
            if proxy_tier != "basic" and self.approvals_path is None:
                return "skipped_proxy_unapproved"
            if self.approvals_path is not None:
                ok, _ = check_paid_approval(
                    self.approvals_path,
                    self.ledger_path,
                    self.brands,
                    now=self.wall_clock(),
                    pending_fetches=self._paid_in_flight,
                    proxy_tier=proxy_tier,
                )
                if not ok:
                    return "skipped_no_approval"
                self._paid_in_flight += 1
            self.paid_attempts += 1
            return None

    def robots_info(self, url: str, timeout: float = 25) -> tuple[bool, list[str], float]:
        """(robots readable, Sitemap: lines, crawl-delay for our UA or *) for the URL's origin."""
        origin = _origin(url)
        self._robots_allow(origin + "/", timeout)
        rules = self._robots.get(origin)
        if rules is None:
            return False, [], 0.0
        sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", rules)
        delay = 0.0
        agent = None
        for raw in rules.splitlines():
            line = raw.split("#", 1)[0].strip()
            key, _, value = line.partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "user-agent":
                agent = value.lower()
            elif key == "crawl-delay" and agent in ("*", "patchhivecatalogbot"):
                try:
                    delay = max(delay, float(value))
                except ValueError:
                    pass
        return True, sitemaps, delay

    def _post_json(self, url: str, key: str, payload: dict, timeout: float) -> tuple[int, bytes]:
        body = json.dumps(payload).encode("utf-8")
        try:
            response = self.transport(
                HttpRequest(
                    "POST",
                    url,
                    {
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": self.user_agent,
                    },
                    body,
                    timeout,
                )
            )
        except Exception:
            return 0, b""
        return response.status, response.body

    def _free_get(self, url: str, timeout: float, attempts: int | None = None) -> tuple[int, bytes]:
        status = 0
        body = b""
        attempts = self.max_retries if attempts is None else attempts
        for attempt in range(attempts):
            self._wait(url)
            try:
                response = self.transport(
                    HttpRequest(
                        "GET",
                        url,
                        {"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
                        None,
                        timeout,
                    )
                )
            except Exception:
                response = HttpResponse(0, b"", {})
            status, body = response.status, response.body
            if status not in RETRY_STATUSES:
                break
            if attempt + 1 < attempts:
                self.sleeper(0.5 * (2**attempt) + random.uniform(0, 0.05))
        return status, body

    def _robots_allow(self, url: str, timeout: float) -> tuple[bool, str | None]:
        parsed = urlparse(url)
        origin = _origin(url)
        if origin not in self._robots:
            robots_url = origin + "/robots.txt"
            status, body = self._free_get(robots_url, timeout)
            if status == 404:
                self._robots[origin] = ""
            elif status == 200:
                self._robots[origin] = _decode(body)
            else:
                # In this order: a worker sharing this scraper must not see "unreadable" (which may
                # still use a paid backend) before it can see the refusal.
                if status in ROBOTS_REFUSAL_STATUSES:
                    self._robots_refused[origin] = status
                self._robots[origin] = None
        if origin in self._robots_refused:
            return False, "robots_refused"
        rules = self._robots[origin]
        if rules is None:
            return False, "robots_unavailable"
        path = parsed.path or "/"
        if parsed.query:
            path = path + "?" + parsed.query
        if parse_robots(rules, self.user_agent, path):
            return True, None
        return False, "robots_disallowed"

    def _wait(self, url: str) -> None:
        host = (urlparse(url).hostname or "").lower()
        interval = self.host_intervals.get(host, self.min_interval_s)
        # Reserve the next slot for this host atomically, so threads sharing a host
        # are spaced `interval` apart instead of waking at the same deadline.
        with self._lock:
            now = self.monotonic()
            slot = max(now, self._next_ok.get(host, 0.0))
            self._next_ok[host] = slot + interval
        if slot > now:
            self.sleeper(slot - now)

    def _block_reason(self, url: str) -> str | None:
        if denied_host(url):
            return "denied_host"
        if not public_http_url(url):
            return "blocked_url"
        if not self.resolve_hosts:
            return None
        host = urlparse(url).hostname or ""
        try:
            infos = socket_getaddrinfo(host)
        except Exception:
            return "blocked_url"
        for ip_text in infos:
            try:
                ip = ipaddress.ip_address(ip_text)
            except ValueError:
                return "blocked_url"
            if _trusted_fake_ip(ip):
                continue
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return "blocked_url"
        return None

    def _finish(
        self,
        url: str,
        method: str,
        status: int | None,
        body: bytes,
        *,
        ok: bool,
        credits: float = 0.0,
        note: str | None = None,
        remember: bool = True,
    ) -> FetchResult:
        digest = _sha256(body) if body else None
        receipt = self._receipt(url, method, status, digest, credits=credits, note=note)
        text = _decode(body) if body else None
        result = FetchResult(ok, text, receipt)
        if remember:
            self._memory[url] = result
        if method == "free_http":
            self._bump_ledger("free_http", 0)
        elif method in {"skipped_no_key", "skipped_paid_cap", "skipped_no_approval", "skipped_proxy_unapproved",
                        "robots_disallowed", "robots_unavailable", "robots_refused", "blocked_url"}:
            self._bump_ledger(method, 0)
        return result

    def _receipt(
        self,
        url: str,
        method: str,
        status: int | None,
        digest: str | None,
        *,
        credits: float = 0.0,
        note: str | None = None,
    ) -> dict:
        receipt = {
            "url": url,
            "method": method,
            "status": status,
            "sha256": digest,
            "timestamp": _now_iso(self.wall_clock),
            "credits": credits,
        }
        if note:
            receipt["note"] = note
        self.receipts.append(receipt)
        if self.on_receipt is not None:
            self.on_receipt(receipt)
        return receipt

    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        digest = _sha256(url.encode("utf-8"))
        folder = self.cache_dir / digest[:2]
        return folder / f"{digest}.body", folder / f"{digest}.meta.json"

    def _read_cache(self, url: str, skip_free: bool = False) -> FetchResult | None:
        body_path, meta_path = self._cache_paths(url)
        if not meta_path.is_file() or not body_path.is_file():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        age = self.wall_clock() - float(meta.get("fetched_at") or 0)
        if age > self.max_age_s or (skip_free and meta.get("method") == "free_http"):
            return None
        body = body_path.read_bytes()
        receipt = {
            "url": url,
            "method": "cache",
            "status": meta.get("status"),
            "sha256": meta.get("sha256") or _sha256(body),
            "timestamp": _now_iso(self.wall_clock),
            "credits": 0,
        }
        ok = meta.get("status") == 200 and bool(body)
        return FetchResult(ok, _decode(body) if body else None, receipt, from_cache=True)

    def _write_cache(self, url: str, result: FetchResult, body: bytes) -> None:
        body_path, meta_path = self._cache_paths(url)
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_bytes(body)
        meta_path.write_text(
            json.dumps(
                {
                    "url": url,
                    "status": result.receipt.get("status"),
                    "sha256": result.receipt.get("sha256"),
                    "fetched_at": self.wall_clock(),
                    "method": result.receipt.get("method"),
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def _bump_ledger(self, method: str, credits: float) -> None:
        with self._lock:
            self._bump_ledger_locked(method, credits)

    def _bump_ledger_locked(self, method: str, credits: float) -> None:
        ledger = {
            "paid_fetches": 0,
            "credits_by_backend": {},
            "calls_by_method": {},
            "updated_at": _now_iso(self.wall_clock),
        }
        if self.ledger_path.is_file():
            try:
                loaded = json.loads(self.ledger_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    ledger.update({k: loaded.get(k, ledger[k]) for k in ledger})
            except json.JSONDecodeError:
                pass
        calls = ledger.setdefault("calls_by_method", {})
        calls[method] = int(calls.get(method) or 0) + 1
        if method in {"context_dev", "firecrawl"}:
            self._paid_in_flight = max(0, self._paid_in_flight - 1)
            ledger["paid_fetches"] = int(ledger.get("paid_fetches") or 0) + 1
            credits_map = ledger.setdefault("credits_by_backend", {})
            credits_map[method] = float(credits_map.get(method) or 0) + float(credits)
        ledger["updated_at"] = _now_iso(self.wall_clock)
        rendered = json.dumps(ledger, indent=2) + "\n"
        assert_no_secrets(rendered)
        self.ledger_path.write_text(rendered, encoding="utf-8")


def _parse_expiry(value: object) -> float | None:
    from datetime import datetime, timezone

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def firecrawl_proxy_tier(value: str | None = None) -> str:
    """The Firecrawl proxy tier: `value`, else PATCHHIVE_FIRECRAWL_PROXY, else basic."""
    tier = (value or os.environ.get("PATCHHIVE_FIRECRAWL_PROXY", "") or "basic").strip().lower()
    if tier not in FIRECRAWL_PROXY_TIERS:
        raise ValueError(f"firecrawl proxy must be one of {FIRECRAWL_PROXY_TIERS}, got {tier!r}")
    return tier


def check_paid_approval(
    approvals_path: Path,
    ledger_path: Path,
    brands: tuple[str, ...] = (),
    *,
    now: float | None = None,
    pending_fetches: int = 0,
    proxy_tier: str = "basic",
) -> tuple[bool, str]:
    """FR-003: is there an unexpired fetch-approvals entry covering `brands` with ledger headroom?

    An entry is {id, approver, expires_at, brands (names or "*"), cap_fetches, cap_credits}, plus
    optional ledger_baseline_fetches / ledger_baseline_credits: the ledger totals when it was approved,
    so the caps count spend since then. A `proxy_tier` other than basic matches only an entry whose
    own `proxy_tier` names it. ``pending_fetches`` are calls already granted but not
    yet booked; each counts as one fetch and at least one credit. A ledger that exists but
    cannot be read, or reads below an entry's baseline, refuses: unknown spend is not zero.
    Returns (ok, reason).
    """
    try:
        doc = json.loads(approvals_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, f"no readable approvals file at {approvals_path.name}"
    entries = doc.get("entries") if isinstance(doc, dict) else None
    if not isinstance(entries, list):
        return False, "approvals file has no entries list"
    ledger: dict = {}
    if ledger_path.exists():
        try:
            loaded = json.loads(ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False, f"spend ledger {ledger_path.name} is unreadable"
        if not isinstance(loaded, dict):
            return False, f"spend ledger {ledger_path.name} is not an object"
        ledger = loaded
    try:
        fetches = int(ledger.get("paid_fetches") or 0)
        credits = sum(float(v or 0) for v in (ledger.get("credits_by_backend") or {}).values())
    except (TypeError, ValueError, AttributeError):
        return False, f"spend ledger {ledger_path.name} has invalid totals"
    stamp = time.time() if now is None else now
    reasons: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("id") or "?")
        expiry = _parse_expiry(entry.get("expires_at"))
        if expiry is None or expiry <= stamp:
            reasons.append(f"{name}: expired or no valid expires_at")
            continue
        if not entry.get("approver"):
            reasons.append(f"{name}: no approver")
            continue
        covered = {str(b) for b in entry.get("brands") or []}
        if "*" not in covered and (not brands or not set(brands) <= covered):
            reasons.append(f"{name}: brands not covered")
            continue
        if proxy_tier != "basic" and str(entry.get("proxy_tier") or "basic").strip().lower() != proxy_tier:
            reasons.append(f"{name}: does not approve the {proxy_tier} proxy tier")
            continue
        try:
            cap_fetches = int(entry["cap_fetches"])
            cap_credits = float(entry["cap_credits"])
        except (KeyError, TypeError, ValueError):
            reasons.append(f"{name}: missing cap_fetches or cap_credits")
            continue
        used_fetches = fetches - int(entry.get("ledger_baseline_fetches") or 0)
        used_credits = credits - float(entry.get("ledger_baseline_credits") or 0)
        if used_fetches < 0 or used_credits < 0:
            reasons.append(f"{name}: ledger reads below its baseline")
            continue
        used_fetches += max(0, pending_fetches)
        used_credits += max(0, pending_fetches)
        if used_fetches >= cap_fetches or used_credits >= cap_credits:
            reasons.append(f"{name}: cap reached ({used_fetches}/{cap_fetches} fetches, {used_credits:g}/{cap_credits:g} credits)")
            continue
        return True, name
    return False, "; ".join(reasons) or "no active approval entry"


def socket_getaddrinfo(host: str) -> list[str]:
    import socket

    infos = socket.getaddrinfo(host, None)
    return [item[4][0] for item in infos]


def _context_body(data: dict) -> str:
    for key in ("html", "markdown"):
        block = data.get(key)
        if isinstance(block, dict) and block.get("success", True) and block.get("data"):
            return str(block["data"])
        if isinstance(block, str) and block:
            return block
    return ""


_FAKE_IP_NET = ipaddress.ip_network("198.18.0.0/15")


def _trusted_fake_ip(ip: ipaddress._BaseAddress) -> bool:
    """Allow the RFC 2544 fake-IP range only when explicitly opted in.

    Some sandboxes resolve every public host to 198.18.0.0/15 and route it
    through an egress proxy. Set PATCHHIVE_SCRAPE_TRUST_FAKE_IP=1 there. All
    other private, loopback, link-local and reserved ranges stay blocked.
    """
    if os.environ.get("PATCHHIVE_SCRAPE_TRUST_FAKE_IP", "").strip() != "1":
        return False
    return ip.version == 4 and ip in _FAKE_IP_NET


def _credits(data: dict, default: float) -> float:
    meta = data.get("key_metadata")  # context.dev reports per-request usage here
    if isinstance(meta, dict) and isinstance(meta.get("credits_consumed"), (int, float)):
        return float(meta["credits_consumed"])
    for key in ("credits", "creditsUsed", "credits_used"):
        if isinstance(data.get(key), (int, float)):
            return float(data[key])
    usage = data.get("usage")
    if isinstance(usage, dict) and isinstance(usage.get("credits"), (int, float)):
        return float(usage["credits"])
    return default


def assert_no_secrets(payload: str) -> None:
    if "ctxt_secret_" in payload or re.search(r"fc-[A-Za-z0-9]{8,}", payload):
        raise RuntimeError("refusing to persist a secret")
    if "Bearer " in payload and "Bearer [redacted]" not in payload:
        raise RuntimeError("refusing to persist an authorization header")
