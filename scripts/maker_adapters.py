"""Per-maker product enumeration for the manufacturer crawl (spec 003 D2).

Adapters list a maker's own products from structured endpoints the maker
publishes (Shopify, Squarespace and WooCommerce store feeds) or from its own
index pages. Every request goes through the shared in-repo router
(`data/synth-catalog/catalog_scrape.py`): robots.txt, the deny list, the
per-host delay, the cache, and the context.dev then Firecrawl paid fallback
under one cap. Adapters only enumerate; values are still parsed
deterministically from the maker's text by the crawler.

Curated homepages and adapter configs live in
`data/synth-catalog/maker-sources.json`.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "synth-catalog" / "maker-sources.json"
KINDS = ("shopify", "squarespace", "woocommerce", "listing")
FEED_PAGES = 20  # pages per store feed; 20 x 250 Shopify products is far beyond any maker
HREF = re.compile(r"""href\s*=\s*["']?([^"'#\s>]+)""", re.I)
# Merch, spares and services, by product handle or title. Modules that slip through
# are still dropped when no HP is stated on the maker's page.
NOT_MODULE = re.compile(
    r"(t-shirt|tshirt|shirt|hoodie|sweater|beanie|sticker|poster|mug|tote|merch|gift|voucher|"
    r"cable|skiff|\bcase\b|enclosure|power[- ]supply|\bpsu\b|busboard|bus[- ]board|blank panel|"
    r"b-stock|bstock|refurb|repair|service|spare|knob|screw|rail|shipping|warranty|faceplate|"
    r"replacement|lid for|pcb|kit only)",
    re.I,
)


@dataclass
class Candidate:
    url: str
    name: str | None = None
    text: str | None = None  # maker-published product text when the feed carries it


def load_sources(path: Path = SOURCES) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for brand, cfg in (data.get("adapters") or {}).items():
        if cfg.get("kind") not in KINDS:
            raise ValueError(f"{brand}: adapter kind must be one of {KINDS}")
        if cfg["kind"] == "listing" and not cfg.get("product"):
            raise ValueError(f"{brand}: listing adapter needs a product pattern")
    return data


def strip_html(markup: str) -> str:
    text = re.sub(r"<(script|style|noscript)\b[\s\S]*?</\1\b[^>]*>", " ", markup or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).replace("−", "-").replace("–", "-").strip()


def _same_site(url: str, home: str) -> bool:
    return (urlparse(url).hostname or "").removeprefix("www.") == (urlparse(home).hostname or "").removeprefix("www.")


def _json(scraper, url: str):
    res = scraper.fetch(url)
    if not res.ok or not res.text:
        return None
    try:
        return json.loads(res.text)
    except ValueError:
        return None


def _shopify(scraper, home: str, cfg: dict) -> list[Candidate]:
    out: list[Candidate] = []
    for page in range(1, FEED_PAGES + 1):
        data = _json(scraper, urljoin(home, f"/products.json?limit=250&page={page}"))
        products = data.get("products") if isinstance(data, dict) else None
        if not products:
            break
        for p in products:
            label = f"{p.get('handle', '')} {p.get('title', '')} {p.get('product_type', '')}"
            if NOT_MODULE.search(label):
                continue
            out.append(Candidate(urljoin(home, f"/products/{p['handle']}"), p.get("title"), strip_html(p.get("body_html") or "")))
    return out


def _squarespace(scraper, home: str, cfg: dict) -> list[Candidate]:
    out: list[Candidate] = []
    for collection in cfg.get("collections") or ["/shop"]:
        url: str | None = urljoin(home, collection) + "?format=json"
        for _ in range(FEED_PAGES):
            data = _json(scraper, url) if url else None
            if not isinstance(data, dict):
                break
            for item in data.get("items") or []:
                if not item.get("fullUrl") or NOT_MODULE.search(f"{item.get('fullUrl')} {item.get('title', '')}"):
                    continue
                body = strip_html(f"{item.get('excerpt') or ''} {item.get('body') or ''}")
                out.append(Candidate(urljoin(home, item["fullUrl"]), item.get("title"), body))
            nxt = (data.get("pagination") or {}).get("nextPageUrl")
            url = urljoin(home, nxt) + ("&" if "?" in nxt else "?") + "format=json" if nxt else None
    return out


def _woocommerce(scraper, home: str, cfg: dict) -> list[Candidate]:
    wanted = set(cfg.get("categories") or [])
    out: list[Candidate] = []
    for page in range(1, FEED_PAGES + 1):
        data = _json(scraper, urljoin(home, f"/wp-json/wc/store/v1/products?per_page=100&page={page}"))
        if not isinstance(data, list) or not data:
            break
        for p in data:
            cats = {c.get("slug") for c in p.get("categories") or []}
            if wanted and not cats & wanted:
                continue
            if NOT_MODULE.search(f"{p.get('permalink', '')} {p.get('name', '')}"):
                continue
            text = strip_html(f"{p.get('short_description') or ''} {p.get('description') or ''}")
            out.append(Candidate(p["permalink"], html.unescape(p.get("name") or "") or None, text))
    return out


def _listing(scraper, home: str, cfg: dict) -> list[Candidate]:
    product = re.compile(cfg["product"], re.I)
    follow = re.compile(cfg["follow"], re.I) if cfg.get("follow") else None
    exclude = re.compile(cfg["exclude"], re.I) if cfg.get("exclude") else None
    frontier = [urljoin(home, e) for e in cfg.get("entries") if e] if "entries" in cfg else [home]
    found: dict[str, Candidate] = {}
    seen: set[str] = set()
    if cfg.get("sitemap"):
        # Sitemap URLs are filtered, never crawled: only product and follow pages are kept.
        for url in sitemap_urls(scraper, home):
            path = urlparse(url).path
            if exclude and exclude.search(path):
                continue
            if product.search(path):
                found.setdefault(url, Candidate(url))
            elif follow and follow.search(path):
                frontier.append(url)
    for _ in range(int(cfg.get("depth") or 1)):
        nxt: list[str] = []
        for page in frontier:
            if page in seen:
                continue
            seen.add(page)
            path = urlparse(page).path
            if product.search(path) and not (exclude and exclude.search(path)):
                found.setdefault(page, Candidate(page))
                continue
            res = scraper.fetch(page)
            for href in HREF.findall(res.text or "") if res.ok else []:
                url = urljoin(page, html.unescape(href)).split("?")[0].split("#")[0]
                path = urlparse(url).path
                if not _same_site(url, home) or (exclude and exclude.search(path)):
                    continue
                if product.search(path):
                    found.setdefault(url, Candidate(url))
                elif follow and follow.search(path):
                    nxt.append(url)
        frontier = nxt
    out = [c for c in found.values() if not NOT_MODULE.search(urlparse(c.url).path)]
    if cfg.get("name_from") == "slug":  # sites whose page titles are all the same
        for c in out:
            c.name = urlparse(c.url).path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
    return out


def sitemap_urls(scraper, home: str, max_maps: int = 15) -> list[str]:
    _, maps, _ = scraper.robots_info(home)
    queue = list(dict.fromkeys(maps or [urljoin(home, "/sitemap.xml")]))
    seen: set[str] = set()
    urls: list[str] = []
    while queue and len(seen) < max_maps:
        sm = queue.pop(0)
        if sm in seen or not _same_site(sm, home):
            continue
        seen.add(sm)
        res = scraper.fetch(sm)
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", res.text or "", re.I) if res.ok else []:
            loc = html.unescape(loc)
            (queue if loc.endswith(".xml") or "sitemap" in loc.lower() else urls).append(loc)
    return urls


ENUMERATORS = {"shopify": _shopify, "squarespace": _squarespace, "woocommerce": _woocommerce, "listing": _listing}


def enumerate_products(scraper, cfg: dict) -> list[Candidate]:
    """Every candidate product for one maker, de-duplicated by URL, in the adapter's order."""
    home = cfg["homepage"]
    seen: set[str] = set()
    out: list[Candidate] = []
    for cand in ENUMERATORS[cfg["kind"]](scraper, home, cfg):
        if cand.url not in seen and _same_site(cand.url, home):
            seen.add(cand.url)
            out.append(cand)
    return out[: int(cfg.get("max_pages") or 10_000)]
