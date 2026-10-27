"""Manufacturer crawl v2: shared router, adapters, curated sources and the dry run (spec 003 D2)."""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))
sys.path.insert(0, str(ROOT / "scripts"))

import catalog_maker_crawl as crawl  # noqa: E402
import catalog_scrape  # noqa: E402
import maker_adapters  # noqa: E402
from catalog_scrape import CatalogScraper, HttpRequest, HttpResponse  # noqa: E402


class Site:
    """Fake web: url -> (status, body). Unknown robots.txt is 404 (allow all)."""

    def __init__(self, routes: dict[str, tuple[int, str | bytes]] | None = None) -> None:
        self.routes = dict(routes or {})
        self.calls: list[str] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.calls.append(request.url)
        if request.url in self.routes:
            status, body = self.routes[request.url]
            return HttpResponse(status, body if isinstance(body, bytes) else body.encode(), {})
        if request.url.endswith("/robots.txt"):
            return HttpResponse(404, b"", {})
        return HttpResponse(404, b"", {})


def _scraper(tmp_path: Path, site: Site, **kwargs) -> CatalogScraper:
    return CatalogScraper(
        cache_dir=tmp_path / "cache",
        ledger_path=tmp_path / "ledger.json",
        transport=site,
        sleeper=lambda _s: None,
        resolve_hosts=False,
        min_interval_s=0,
        max_retries=1,
        **kwargs,
    )


# --- shared router changes


def test_challenge_page_escalates_to_paid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "ctx-test")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    site = Site(
        {"https://maker.example/p": (200, "<html><title>Just a moment...</title>cf-chl-x</html>")}
    )
    scraper = _scraper(tmp_path, site, max_paid_fetches=1)
    res = scraper.fetch("https://maker.example/p")
    assert not res.ok  # context.dev is not routed in this fake web either
    assert any(r.get("note") == "challenge" for r in scraper.receipts)
    assert catalog_scrape.CONTEXT_SCRAPE_URL in site.calls


def test_json_mentioning_captcha_is_not_a_challenge(tmp_path: Path) -> None:
    body = json.dumps({"items": [{"title": "Blur"}], "website": {"captchaSettings": {}}})
    site = Site({"https://maker.example/modules?format=json": (200, body)})
    res = _scraper(tmp_path, site).fetch("https://maker.example/modules?format=json")
    assert res.ok and json.loads(res.text)["items"][0]["title"] == "Blur"


def test_robots_info_reads_sitemaps_and_crawl_delay(tmp_path: Path) -> None:
    robots = "User-agent: GPTBot\nDisallow: /\nCrawl-delay: 60\n\nUser-agent: *\nCrawl-delay: 5\nSitemap: https://maker.example/sitemap.xml\n"
    site = Site({"https://maker.example/robots.txt": (200, robots)})
    readable, maps, delay = _scraper(tmp_path, site).robots_info("https://maker.example/any")
    assert readable and maps == ["https://maker.example/sitemap.xml"] and delay == 5.0


def test_receipt_hook_and_paid_cap_hold_across_threads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "ctx-test")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    seen: list[dict] = []
    lock = threading.Lock()

    def hook(rec: dict) -> None:
        with lock:
            seen.append(rec)

    site = Site({f"https://m{i}.example/p": (503, "") for i in range(40)})
    scraper = _scraper(tmp_path, site, max_paid_fetches=5, on_receipt=hook)
    threads = [
        threading.Thread(target=scraper.fetch, args=(f"https://m{i}.example/p",)) for i in range(40)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert scraper.paid_attempts == 5
    assert sum(1 for r in seen if r["method"] == "context_dev") == 5
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert ledger["paid_fetches"] == 5


# --- crawler policy


@pytest.mark.parametrize(
    "url,blocked",
    [
        ("https://www.metasonix.com/", False),
        ("https://www.qubitelectronix.com/shop", False),
        ("https://x.com/maker", True),
        ("https://www.thomann.de/x", True),
        ("https://www.perfectcircuit.com/maths", True),
    ],
)
def test_reseller_exclusion_matches_host_labels(url: str, blocked: bool) -> None:
    assert crawl.excluded(url) is blocked


def test_labelled_width_beats_menu_mentions() -> None:
    text = "Cases 62 / 104HP 4U Palette Case 104HP 7U. Specs Width 12HP Depth 38mm Power 170mA @ +12V 20mA @ -12V"
    row = crawl.deterministic(
        "Intellijel", "https://intellijel.com/shop/eurorack/plonk/", text, "Plonk"
    )
    assert row["hp"] == 12 and row["depth_mm"] == 38 and row["power_12v_ma"] == 170
    assert row["extracted_by"] == "regex" and row["sources"]["hp"].endswith("/plonk/")


def test_two_unlabelled_widths_are_ambiguous() -> None:
    assert crawl.deterministic(
        "X", "https://x.example/p", "Fits 8HP or 10HP versions. " * 3, "Y"
    ) == {"ambiguous_hp": [8, 10]}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("+12V current 100mA -12V current 15mA", (100, 15, None)),  # Mutable docs
        ("42HP +12v 140mA -12v 115mA 425g", (140, 115, None)),  # Verbos
        ("-12V 15mA +12V 100mA", (100, 15, None)),
        ("+12V: 70mA / -12V 30mA 6HP", (70, 30, None)),
        ("+12V : 27 mA -12V : 8 mA +5V : 0 mA", (27, 8, 0)),
        ("Power 170mA @ +12V 20mA @ -12V", (170, 20, None)),
        ("170mA +12V, 20mA -12V, 5mA +5V", (170, 20, 5)),
        ("power: 35 mA @ +12V / 21 mA @ -12V", (35, 21, None)),
        ("+50mA (+12V), -20mA (-12V)", (50, 20, None)),
        ("+12: 150 mA, -12: 5 mA. Delivers up to 6 W (500 mA at 12 V)", (150, 5, None)),
        ("Current Draw 5V 0 mA +12V ca. 42mA -12V ca. 42mA", (42, 42, 0)),  # ACL
        ("Power 4mA @ -12V 49mA @ 12V", (49, 4, None)),  # Intellijel
        ("Power consumption: +5V: 180mA +12V: 14mA -12V: 18mA", (14, 18, 180)),  # Likaon
        ("Current draw: +12V | 12mA -12V | 12mA +5V | 590mA", (12, 12, 590)),  # Bard
        ("CV range 0-5V, 10mA max. +12V 30mA", (30, None, None)),
        ("±12V 50mA", (None, None, None)),
        ("+12v - 21mA -12v - 20mA +5v - N/A", (21, 20, None)),  # Fully Wired
        ("8HP / 23mm depth +12V @ 50mA -12V @ 25mA Output is 0-5V", (50, 25, None)),  # Rain City
        ("Width: 12HP Power: +120mA / -45mA @+12V / -12V", (120, 45, None)),  # God's Box
        ("Current Draw: 20 mA +12V | 0 mA -12V | 0 mA 5V Width", (20, 0, 0)),
        ("+12V current draw : 16mA -12V current draw : 15mA", (16, 15, None)),  # Skull & Circuits
        ("Specs: - 8HP - 125mA +12V - 0mA -12V - 0mA +5V - 42mm deep", (125, 0, 0)),  # Syntonie
        ("width: 26hp depth: 25mm 110ma +12v 20ma-12 $525", (110, 20, None)),  # NIIO
        ("The DC power requirement is 120 mA (+12 V), 2.5 mA (-12 V).", (120, 2.5, None)),  # Rare Waves
        ("Power: +12v/-12v Current: 90mA/30mA", (90, 30, None)),  # Erogenous Tones
        ("Power Usage - 20mA, 10mA (+12V / -12V)", (20, 10, None)),  # Nakedboards
        # A rail the page's style does not give stays empty, never borrowed from another style.
        ("20 hp 50 mA +12V 20A -12V 0 mA 5V 28 mm deep", (50, None, 0)),
    ],
)
def test_rails_read_each_page_in_its_own_style(text: str, expected: tuple) -> None:
    got = crawl.rails(text)
    assert (got["power_12v_ma"], got["power_neg12v_ma"], got["power_5v_ma"]) == expected


def test_a_draw_the_parse_and_model_disagree_on_is_not_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    page = (
        "<title>Dim 2</title><p>Dual BNC lamp and dimmer set. 4 HP | +12: 150 mA, -12: 5 mA. "
        "Delivers up to 6 W (500 mA at 12 V) of power from each output. " + "Lamp dimmer. " * 20 + "</p>"
    )
    answer = {"is_module": True, "name": "Dim 2", "hp": 4, "power_12v_ma": 500, "power_neg12v_ma": 5}
    monkeypatch.setattr(crawl, "llm", lambda *a, **k: answer)
    row = crawl.extract("Joranalogue Audio Design", "https://joranalogue.com/products/dim-2", page, "free_http")
    assert row["power_12v_ma"] is None and row["power_neg12v_ma"] == 5


# --- adapters


def _home(site: Site, base: str) -> dict:
    return {"homepage": base}


def test_shopify_pages_and_skips_merch(tmp_path: Path) -> None:
    page1 = {
        "products": [
            {
                "handle": "alm041",
                "title": "Pamela's Pro Workout",
                "product_type": "Module",
                "body_html": "<p>8HP, 70mA @ +12V</p>",
            },
            {"handle": "tote-bag", "title": "Tote", "product_type": "Merch", "body_html": ""},
        ]
    }
    site = Site(
        {
            "https://maker.example/products.json?limit=250&page=1": (200, json.dumps(page1)),
            "https://maker.example/products.json?limit=250&page=2": (
                200,
                json.dumps({"products": []}),
            ),
        }
    )
    cands = maker_adapters.enumerate_products(
        _scraper(tmp_path, site), {"homepage": "https://maker.example/", "kind": "shopify"}
    )
    assert [c.url for c in cands] == ["https://maker.example/products/alm041"]
    assert "8HP" in cands[0].text


def test_squarespace_follows_pagination(tmp_path: Path) -> None:
    p1 = {
        "items": [{"title": "Blur", "fullUrl": "/modules/p/blur", "body": "<p>2HP</p>"}],
        "pagination": {"nextPageUrl": "/modules?offset=1"},
    }
    p2 = {
        "items": [{"title": "Kick", "fullUrl": "/modules/p/kick", "excerpt": "2HP kick"}],
        "pagination": {},
    }
    site = Site(
        {
            "https://maker.example/modules?format=json": (200, json.dumps(p1)),
            "https://maker.example/modules?offset=1&format=json": (200, json.dumps(p2)),
        }
    )
    cands = maker_adapters.enumerate_products(
        _scraper(tmp_path, site),
        {"homepage": "https://maker.example/", "kind": "squarespace", "collections": ["/modules"]},
    )
    assert [c.name for c in cands] == ["Blur", "Kick"]


def test_woocommerce_keeps_wanted_categories(tmp_path: Path) -> None:
    items = [
        {
            "name": "Plonk",
            "permalink": "https://maker.example/shop/eurorack/plonk/",
            "categories": [{"slug": "eurorack"}],
            "description": "Width 12HP",
        },
        {
            "name": "Lid for Jellymix",
            "permalink": "https://maker.example/shop/accessories/lid/",
            "categories": [{"slug": "accessories"}],
        },
    ]
    site = Site(
        {
            "https://maker.example/wp-json/wc/store/v1/products?per_page=100&page=1": (
                200,
                json.dumps(items),
            ),
            "https://maker.example/wp-json/wc/store/v1/products?per_page=100&page=2": (200, "[]"),
        }
    )
    cfg = {"homepage": "https://maker.example/", "kind": "woocommerce", "categories": ["eurorack"]}
    assert [c.name for c in maker_adapters.enumerate_products(_scraper(tmp_path, site), cfg)] == [
        "Plonk"
    ]


def test_listing_follows_index_pages_to_products(tmp_path: Path) -> None:
    site = Site(
        {
            "https://maker.example/shop/": (
                200,
                '<a href="/shop/black-series/">B</a><a href="/about/">A</a>',
            ),
            "https://maker.example/shop/black-series/": (
                200,
                '<a href="/shop/black-series/vco/">V</a><a href="https://other.example/shop/black-series/x/">X</a>',
            ),
        }
    )
    cfg = {
        "homepage": "https://maker.example/",
        "kind": "listing",
        "entries": ["/shop/"],
        "depth": 2,
        "follow": r"^/shop/[^/]+-series/$",
        "product": r"^/shop/[^/]+-series/[^/]+/$",
    }
    assert [c.url for c in maker_adapters.enumerate_products(_scraper(tmp_path, site), cfg)] == [
        "https://maker.example/shop/black-series/vco/"
    ]


def test_listing_adapter_requires_product_pattern(tmp_path: Path) -> None:
    bad = tmp_path / "s.json"
    bad.write_text(
        json.dumps({"adapters": {"X": {"homepage": "https://x.example/", "kind": "listing"}}})
    )
    with pytest.raises(ValueError):
        maker_adapters.load_sources(bad)


# --- curated sources file


def test_curated_sources_are_maker_sites_only() -> None:
    data = maker_adapters.load_sources()
    assert len(data["adapters"]) >= 25
    homes = [c["homepage"] for c in data["adapters"].values()] + [
        h["homepage"] for h in data["homepages"].values()
    ]
    for url in homes:
        assert urlparse(url).scheme == "https", url
        assert not crawl.excluded(url) and not catalog_scrape.denied_host(url), url
    assert {h["status"] for h in data["homepages"].values()} <= set(data["status_meaning"])


def test_resolution_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        crawl,
        "SOURCES",
        {
            "adapters": {"A": {"homepage": "https://a.example/", "kind": "shopify"}},
            "homepages": {
                "B": {"homepage": "https://b.example/", "status": "verified_free"},
                "C": {"homepage": "https://c.example/", "status": "rejected"},
            },
        },
    )
    monkeypatch.setattr(crawl, "PRIOR", {"D": "https://d.example/"})
    assert crawl.resolve_brand("A")["how"] == "adapter:shopify"
    assert crawl.resolve_brand("B")["how"] == "curated"
    assert crawl.resolve_brand("C")["status"] == "curated_rejected"
    assert crawl.resolve_brand("D")["how"] == "v1_crawl"


# --- dry run end to end


def test_dry_run_writes_yield_and_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feed = {
        "products": [
            {
                "handle": "vco",
                "title": "VCO",
                "product_type": "Module",
                "body_html": "Width 10HP. 60mA @ +12V, 50mA @ -12V",
            }
        ]
    }
    site = Site(
        {
            "https://shop.example/products.json?limit=250&page=1": (200, json.dumps(feed)),
            "https://shop.example/products.json?limit=250&page=2": (200, '{"products": []}'),
            "https://blocked.example/robots.txt": (200, "User-agent: *\nAllow: /\n"),
            "https://blocked.example/": (503, ""),
        }
    )
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "seed-phase2-v1.json").write_text(
        json.dumps({"brands": ["ShopMaker", "BlockedMaker", "Unknown Maker"]})
    )
    monkeypatch.setattr(catalog_scrape, "default_transport", site)
    monkeypatch.setattr(catalog_scrape, "socket_getaddrinfo", lambda host: ["93.184.216.34"])
    monkeypatch.setattr(crawl, "CATALOG", catalog)
    monkeypatch.setattr(crawl, "WORK", tmp_path / "work")
    monkeypatch.setattr(crawl, "RECEIPTS", tmp_path / "receipts")
    monkeypatch.setattr(crawl, "PRIOR_CRAWL", tmp_path / "none.json")
    (tmp_path / "receipts").mkdir()
    monkeypatch.setattr(
        crawl.maker_adapters,
        "load_sources",
        lambda: {
            "adapters": {"ShopMaker": {"homepage": "https://shop.example/", "kind": "shopify"}},
            "homepages": {
                "BlockedMaker": {"homepage": "https://blocked.example/", "status": "candidate"}
            },
        },
    )
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "ctx-test")
    assert crawl.main(["--dry-run", "--workers", "1"]) == 0
    receipt = json.loads((tmp_path / "receipts" / "maker-crawl-v2.dry-run.json").read_text())
    assert receipt["mode"] == "dry-run"
    assert receipt["modules_total"] == 1 and receipt["modules_with_power"] == 1
    assert receipt["statuses"] == {"curated_unconfirmed": 1, "done": 1, "needs_search": 1}
    assert receipt["projection"]["paid_fetch_urls"] == 1  # the blocked homepage
    assert receipt["projection"]["paid_searches"] == 1  # the unknown maker
    assert receipt["budget"]["calls"] == {"search": 0, "ctx_scrape": 0, "fc_scrape": 0, "llm": 0}
    assert not any(
        urlparse(c).hostname in ("api.context.dev", "api.firecrawl.dev", "openrouter.ai")
        for c in site.calls
    )


def test_paid_run_needs_an_approved_cap() -> None:
    assert crawl.main(["--workers", "1"]) == 2


def test_listing_filters_sitemap_urls_without_fetching_them(tmp_path: Path) -> None:
    sitemap = "<urlset><url><loc>https://maker.example/en/products/A1</loc></url><url><loc>https://maker.example/fr/products/A1</loc></url></urlset>"
    site = Site({"https://maker.example/sitemap.xml": (200, sitemap)})
    cfg = {
        "homepage": "https://maker.example/",
        "kind": "listing",
        "sitemap": True,
        "entries": [],
        "product": r"^/en/products/[^/]+$",
    }
    cands = maker_adapters.enumerate_products(_scraper(tmp_path, site), cfg)
    assert [c.url for c in cands] == ["https://maker.example/en/products/A1"]
    assert "https://maker.example/fr/products/A1" not in site.calls


def test_context_dev_credits_come_from_key_metadata() -> None:
    assert (
        catalog_scrape._credits(
            {"key_metadata": {"credits_consumed": 2, "credits_remaining": 9}}, 1.0
        )
        == 2.0
    )


def test_no_model_paid_run_keeps_generic_rows_unconfirmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = "<html><title>VCO | Maker</title><body>Specs: Width 10HP, 60mA @ +12V</body></html>"
    site = Site(
        {
            "https://maker.example/": (200, '<a href="/products/vco">VCO</a>'),
            "https://maker.example/products/vco": (200, page),
        }
    )
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "seed-phase2-v1.json").write_text(json.dumps({"brands": ["Maker"]}))
    monkeypatch.setattr(catalog_scrape, "default_transport", site)
    monkeypatch.setattr(catalog_scrape, "socket_getaddrinfo", lambda host: ["93.184.216.34"])
    for name, value in (
        ("CATALOG", catalog),
        ("WORK", tmp_path / "work"),
        ("RECEIPTS", tmp_path / "receipts"),
        ("OUT", tmp_path / "out"),
        ("PRIOR_CRAWL", tmp_path / "none.json"),
    ):
        monkeypatch.setattr(crawl, name, value)
    (tmp_path / "receipts").mkdir()
    (tmp_path / "out").mkdir()
    monkeypatch.setattr(
        crawl.maker_adapters,
        "load_sources",
        lambda: {
            "homepages": {
                "Maker": {"homepage": "https://maker.example/", "status": "verified_free"}
            }
        },
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert crawl.main(["--no-model", "--max-paid-fetches", "5", "--workers", "1"]) == 0
    receipt = json.loads((tmp_path / "receipts" / "maker-crawl-v2.json").read_text())
    assert receipt["modules_total"] == 0 and receipt["unconfirmed_generic"] == 1
    rows = json.loads((tmp_path / "out" / "maker-crawl-v2.json").read_text())["brands"][0][
        "unconfirmed"
    ]
    assert rows[0]["hp"] == 10 and rows[0]["confirmed"] is False
    assert "openrouter.ai" not in " ".join(site.calls)


def test_render_skips_the_free_get_but_not_robots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "ctx-test")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    rendered = json.dumps({"html": "<a href='/p/x'>x</a>", "key_metadata": {"credits_consumed": 1}})
    site = Site(
        {
            catalog_scrape.CONTEXT_SCRAPE_URL: (200, rendered),
            "https://js.example/robots.txt": (200, "User-agent: *\nDisallow: /private\n"),
        }
    )
    scraper = _scraper(tmp_path, site, max_paid_fetches=2)
    res = scraper.fetch("https://js.example/modules", render=True)
    assert res.ok and "/p/x" in res.text and res.receipt["method"] == "context_dev"
    assert "https://js.example/modules" not in site.calls  # no free GET of the shell
    assert not scraper.fetch("https://js.example/private/x", render=True).ok  # robots still applies
    assert scraper.paid_attempts == 1


def test_render_ignores_a_cached_free_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "ctx-test")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    rendered = json.dumps({"html": "<a href='/p/x'>x</a>", "key_metadata": {"credits_consumed": 1}})
    site = Site(
        {
            "https://js.example/modules": (200, "<html><div id=app></div></html>"),
            catalog_scrape.CONTEXT_SCRAPE_URL: (200, rendered),
        }
    )
    assert "/p/x" not in (
        _scraper(tmp_path, site).fetch("https://js.example/modules").text or ""
    )  # free shell, cached
    res = _scraper(tmp_path, site, max_paid_fetches=1).fetch(
        "https://js.example/modules", render=True
    )
    assert res.ok and "/p/x" in res.text


def test_listing_keeps_product_query_and_drops_tracking(tmp_path: Path) -> None:
    index = '<a href="/p.php?p=813">A</a><a href="/p.php?p=814&utm_source=x">B</a><a href="/p.php?p=813#top">A again</a>'
    site = Site({"https://4ms.example/modules.php": (200, index)})
    cfg = {
        "homepage": "https://4ms.example/",
        "kind": "listing",
        "entries": ["/modules.php"],
        "product": r"^/p\.php$",
    }
    urls = [c.url for c in maker_adapters.enumerate_products(_scraper(tmp_path, site), cfg)]
    assert urls == ["https://4ms.example/p.php?p=813", "https://4ms.example/p.php?p=814"]


def test_threads_sharing_a_host_keep_the_interval(tmp_path: Path) -> None:
    import time

    stamps: list[float] = []
    lock = threading.Lock()

    def transport(request: HttpRequest) -> HttpResponse:
        if not request.url.endswith("/robots.txt"):
            with lock:
                stamps.append(time.monotonic())
        return HttpResponse(404, b"", {})

    scraper = CatalogScraper(
        cache_dir=tmp_path / "cache",
        ledger_path=tmp_path / "ledger.json",
        transport=transport,
        resolve_hosts=False,
        min_interval_s=0.15,
        max_retries=1,
    )
    threads = [
        threading.Thread(target=scraper.fetch, args=(f"https://shared.example/p{i}",))
        for i in range(3)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stamps.sort()
    assert len(stamps) == 3
    assert min(b - a for a, b in zip(stamps, stamps[1:])) >= 0.13
