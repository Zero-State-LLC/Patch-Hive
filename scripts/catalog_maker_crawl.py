#!/usr/bin/env python3
"""Manufacturer-site catalog crawl (spec 003 D2; v1 approved by Danny 2026-10-17, $15 combined cap).

Stages: resolve (curated homepage, else the v1 crawl's homepage, else search) ->
discover (a per-maker adapter from maker-sources.json, else robots sitemaps, the
Shopify feed and homepage links) -> fetch -> extract (deterministic regex; on the
generic path an open-weights model confirms, and every accepted value must be
parsed deterministically or appear verbatim on the maker's page).

Every request goes through the shared in-repo router, the same one the catalog
scrapers use (`data/synth-catalog/catalog_scrape.py`): polite free HTTP with
robots.txt, the ModularGrid deny list and a per-host delay, then context.dev,
then Firecrawl with its managed proxy tier, under one paid-fetch cap and one
ledger. Resellers are never fetched. Keys come from the environment and are
never printed. Spend is tracked as projected overage beyond included plan
credits plus model cost, with a hard stop.

`--dry-run` makes no paid call and no model call. It writes a receipt with the
yield per maker and the projected paid fetches, searches and model spend of the
real run, so the paid run can be approved against numbers.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import html
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "synth-catalog"
sys.path.insert(0, str(CATALOG))
sys.path.insert(0, str(ROOT / "scripts"))

import maker_adapters  # noqa: E402
from catalog_scrape import CatalogScraper  # noqa: E402

WORK = CATALOG / ".cache" / "maker-crawl"
OUT = CATALOG / "hermes-research"
RECEIPTS = CATALOG / "receipts"
PRIOR_CRAWL = OUT / "maker-crawl-v1.json"
MODEL = os.environ.get("PATCHHIVE_CRAWL_MODEL", "deepseek/deepseek-v4.1-flash")
MODEL_IN, MODEL_OUT = 0.15 / 1e6, 0.60 / 1e6  # live OpenRouter price 2026-10-17
# Measured in the v1 run (4,372 calls, $0.7816): used to project model spend from a dry run.
V1_COST_PER_LLM_CALL = 0.7816 / 4372
CTX_OVERAGE_USD, FC_OVERAGE_USD = 0.0022, 0.005  # per credit beyond the plan's included credits
DEFAULT_MAX_PAGES = 250  # per maker; v1 stopped at 80 model-picked pages plus 60 one-hop pages

EXCLUDED = re.compile(
    r"(modulargrid|reverb\.com|ebay\.|amazon\.|thomann|perfectcircuit|sweetwater|schneidersladen|"
    r"signalsounds|control-voltage|detroitmodular|analoguehaven|juno\.co|andertons|gear4music|"
    r"facebook\.|instagram\.|youtube\.|youtu\.be|reddit\.|modwiggler|muffwiggler|gearspace|kvraudio|"
    r"twitter\.|x\.com|tiktok|bandcamp|soundcloud|wikipedia|manualslib|patreon|kickstarter|"
    r"etsy\.|tindie\.|github\.com|linkedin|pinterest|discord|elevatorsound|noisebug|synthcube|"
    r"exploding-shed|modularsquare|vintagesynth|attackmagazine|musicradar|synthtopia|"
    r"gearnews|rhythmtoolbox|sonicstate|cdm\.link|soundonsound|bax-shop|musicstore|kraftmusic|"
    r"guitarcenter|musiciansfriend|zzounds|ajaxsoundstudio|patchwerks|modular-addict|"
    r"herzlichlabs|sinesquares|engadget|thomannmusic|notice-facile|manua\.ls|duckduckgo|google\.)",
    re.I,
)
EXCLUDED_HOST = re.compile(r"(?:^|\.)" + EXCLUDED.pattern, re.I)

def excluded(url: str) -> bool:
    """Reseller, marketplace, social or database host. Matched at a host label boundary, so the
    `x.com` entry does not catch makers whose domain ends in x.com (metasonix.com, qubitelectronix.com)."""
    host = (urllib.parse.urlparse(url).hostname or url).lower()
    return EXCLUDED_HOST.search(host) is not None


NON_MODULE = re.compile(
    r"(t-shirt|tshirt|shirt|hoodie|crewneck|sweater|hat|cap-|beanie|sticker|poster|mug|tote|merch|"
    r"gift|card|cable|patch-cable|skiff|case|rack|enclosure|power-supply|psu|busboard|bus-board|"
    r"blank|b-stock|bstock|refurb|demo-unit|rma|repair|service|spare|knob|jack|screw|rail|"
    r"bundle|voucher|shipping|warranty|faq|blog|news|about|contact|cart|account|login|privacy|"
    r"terms|policy|dealers|distributors|press|careers|tag/|category/|author/|page/\d)",
    re.I,
)
HP_LABELLED = [
    r"(?:[Ww]idth|[Ss]ize|[Pp]anel)\s*[:=\-]?\s*(\d{1,3})\s*(?:HP|TE)\b",
    r"(\d{1,3})\s*(?:HP|TE)\s+(?:wide|width)\b",
]
PRODUCTISH = re.compile(r"(product|module|eurorack|shop|store|item|/p/|/e/|catalog)", re.I)

HP = [r"(\d{1,3})\s*(?:HP|hp|Hp)\b", r"(\d{1,3})\s*TE\b"]
P12 = [
    r"(\d{1,4})\s*mA\s*(?:@|at|on|from)?\s*\+?\s*12\s*V",
    r"\+\s*12\s*V?\s*(?:rail)?\s*[:=]?\s*(\d{1,4})\s*mA",
    r"\+(\d{1,4})\s*mA\s*\(\+12V\)",
]
N12 = [
    r"(\d{1,4})\s*mA\s*(?:@|at|on|from)?\s*[-\u2212\u2013]\s*12\s*V",
    r"[-\u2212\u2013]\s*12\s*V?\s*(?:rail)?\s*[:=]?\s*(\d{1,4})\s*mA",
    r"-(\d{1,4})\s*mA\s*\(-12V\)",
]
P5 = [r"(\d{1,4})\s*mA\s*(?:@|at|on|from)?\s*\+?\s*5\s*V\b", r"\+\s*5\s*V\s*[:=]?\s*(\d{1,4})\s*mA"]
DEPTH = [
    r"[Dd]epth[^0-9]{0,40}(\d{1,3}(?:\.\d+)?)\s*mm",
    r"(\d{1,3}(?:\.\d+)?)\s*mm\s*(?:deep|depth)",
    r"[Dd]epth[^0-9]{0,30}(\d(?:\.\d+)?)\s*(?:in|inch|inches|\")\b",
]


class Budget:
    def __init__(self, cap: float, ctx_start: float, fc_start: float):
        self.cap, self.ctx_start, self.fc_start = cap, ctx_start, fc_start
        self.ctx_used = self.fc_used = 0.0
        self.tok_in = self.tok_out = 0
        self.llm_cost = 0.0
        self.calls = {"search": 0, "ctx_scrape": 0, "fc_scrape": 0, "llm": 0}
        # Dry run: what the real run would have spent.
        self.would = {"paid_fetch_urls": 0, "paid_searches": 0, "llm_calls": 0}
        self.lock = threading.Lock()

    def overage(self) -> float:
        ctx = max(0.0, self.ctx_used - self.ctx_start) * CTX_OVERAGE_USD
        fc = max(0.0, self.fc_used - self.fc_start) * FC_OVERAGE_USD
        return ctx + fc

    def projected(self) -> float:
        return self.overage() + self.llm_cost

    def can_spend(self, margin: float = 0.25) -> bool:
        with self.lock:
            return self.projected() + margin < self.cap

    def bump(self, key: str, n: int = 1) -> None:
        with self.lock:
            self.would[key] += n

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "context_dev_credits": self.ctx_used,
                "firecrawl_credits": self.fc_used,
                "context_dev_included_at_start": self.ctx_start,
                "firecrawl_included_at_start": self.fc_start,
                "paid_overage_usd": round(self.overage(), 4),
                "model": MODEL,
                "model_tokens_in": self.tok_in,
                "model_tokens_out": self.tok_out,
                "model_cost_usd": round(self.llm_cost, 4),
                "projected_total_usd": round(self.projected(), 4),
                "cap_usd": self.cap,
                "calls": dict(self.calls),
            }


BUDGET: Budget | None = None
SCRAPER: CatalogScraper | None = None
DRY_RUN = False
NO_MODEL = False  # paid fetches without OpenRouter: generic rows stay unconfirmed
SOURCES: dict = {}
PRIOR: dict[str, str] = {}
ASSET = re.compile(r"\.(jpe?g|png|gif|webp|svg|pdf|zip|mp3|wav|mp4|mov|css|js|xml|txt|stl|syx|bin|hex|dmg|exe)(\?|$)", re.I)


def _host(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


def _cache_path(kind: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode()).hexdigest()
    return WORK / kind / digest[:2] / f"{digest}.json"


def cached(kind: str, key: str):
    path = _cache_path(kind, key)
    if path.is_file():
        try:
            return json.loads(path.read_text())
        except Exception:
            return None
    return None


def store(kind: str, key: str, value) -> None:
    path = _cache_path(kind, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def _account(rec: dict) -> None:
    """Router receipt hook: book credits by backend, and in a dry run the paid fetches skipped."""
    method = rec.get("method")
    with BUDGET.lock:
        if method == "context_dev":
            BUDGET.ctx_used += float(rec.get("credits") or 0)
            BUDGET.calls["ctx_scrape"] += 1
        elif method == "firecrawl":
            BUDGET.fc_used += float(rec.get("credits") or 0)
            BUDGET.calls["fc_scrape"] += 1
        elif DRY_RUN and method in ("skipped_paid_cap", "skipped_no_key") and rec.get("note") == "context_dev":
            BUDGET.would["paid_fetch_urls"] += 1


class _Fetcher:
    """Thin view over the shared router that books each call's receipts."""

    def fetch(self, url: str, render: bool = False):
        if excluded(url):
            return SCRAPER._finish(url, "excluded_reseller", None, b"", ok=False, remember=False)
        if not BUDGET.can_spend():
            return SCRAPER._finish(url, "budget_stop", None, b"", ok=False, remember=False)
        return SCRAPER.fetch(url, render=render and not DRY_RUN)

    def robots_info(self, url: str):
        return SCRAPER.robots_info(url)


FETCH = _Fetcher()


def fetch_text(url: str, render: bool = False) -> tuple[str, str]:
    res = FETCH.fetch(url, render=render)
    return (res.text or "", res.receipt.get("method") or "?") if res.ok else ("", res.receipt.get("method") or "failed")


def search(query: str) -> list[str]:
    hit = cached("search", query)
    if hit is not None:
        return hit
    if DRY_RUN:
        BUDGET.bump("paid_searches")
        return []
    if not BUDGET.can_spend():
        return []
    res = SCRAPER.search(query, limit=8)
    with BUDGET.lock:
        BUDGET.calls["search"] += 1
    urls = [u for u in res.urls if not excluded(u)]
    store("search", query, urls)
    return urls


def _post(url: str, payload: dict, key: str, timeout: float = 90) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            return exc.code, {}
    except Exception:
        return 0, {}


def llm(system: str, user: str, max_tokens: int = 300) -> dict | None:
    key = system[:40] + "\n" + user
    hit = cached("llm", key)
    if hit is not None:
        return hit
    if DRY_RUN or NO_MODEL:
        BUDGET.bump("llm_calls")
        return None
    if not BUDGET.can_spend():
        return None
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    status, data = _post("https://openrouter.ai/api/v1/chat/completions", payload, os.environ["OPENROUTER_API_KEY"], timeout=120)
    usage = data.get("usage") or {}
    tin, tout = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
    cost = usage.get("cost")
    cost = float(cost) if isinstance(cost, (int, float)) else tin * MODEL_IN + tout * MODEL_OUT
    with BUDGET.lock:
        BUDGET.tok_in += tin
        BUDGET.tok_out += tout
        BUDGET.llm_cost += cost
        BUDGET.calls["llm"] += 1
    try:
        content = data["choices"][0]["message"]["content"]
        content = re.sub(r"^```(?:json)?|```$", "", content.strip()).strip()
        out = json.loads(content)
    except Exception:
        return None
    store("llm", key, out)
    return out


def page_text(page: str) -> str:
    t = re.sub(r"<(script|style|noscript)\b[\s\S]*?</\1\b[^>]*>", " ", page or "", flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).replace("\u2212", "-").replace("\u2013", "-")


def first_num(patterns: list[str], text: str) -> float | None:
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            try:
                return float(m.group(1))
            except (TypeError, ValueError):
                continue
    return None


def spec_window(text: str, size: int = 1400) -> str:
    keys = [m.start() for m in re.finditer(r"(\bmA\b|\bHP\b|[Dd]epth|[Ww]idth|[Ss]pecification|[Pp]ower|[Cc]urrent)", text)]
    if not keys:
        return text[:size]
    start = max(0, keys[0] - 300)
    return text[start:start + size]


def norm_name(brand: str, name: str) -> str:
    n = name.lower()
    for token in [brand.lower(), "eurorack", "module", "modules", "synthesizer", "synth"]:
        n = n.replace(token, " ")
    return re.sub(r"[^a-z0-9]+", "", n)


def domain_matches_brand(url: str, brand: str, title: str = "") -> bool:
    host = _host(url).replace("www.", "")
    tokens = [t for t in re.findall(r"[a-z0-9]+", brand.lower()) if len(t) >= 3 and t not in {"audio", "music", "modular", "synth", "synths", "electronics", "design", "devices", "labs", "instruments", "the", "and"}]
    compact = re.sub(r"[^a-z0-9]", "", brand.lower())
    hostc = re.sub(r"[^a-z0-9]", "", host.split(".")[0] if host.count(".") <= 1 else "".join(host.split(".")[:-1]))
    if compact and (compact in hostc or (len(hostc) >= 4 and hostc in compact)):
        return True
    if tokens and any(t in hostc for t in tokens):
        return True
    return False


RESOLVE_SYS = (
    "You pick a Eurorack manufacturer's own official website from search results. "
    "Never pick resellers, marketplaces, forums, social media, databases (ModularGrid), or press. "
    'Reply JSON {"index": <int or -1>}. Use -1 if none is clearly the maker\'s own site.'
)


PICK_SYS = (
    "You select URLs that are individual Eurorack MODULE product pages for one manufacturer "
    "(not cases, power, cables, merch, accessories, blog, category or listing pages). "
    'Reply JSON {"pick": [<indices>]} with at most 80 indices.'
)


EXTRACT_SYS = (
    "You read trimmed text from a manufacturer's product page. Decide if it is a single Eurorack module "
    "and copy its specs EXACTLY as written. Never guess: use null if a value is not stated. "
    'Reply JSON {"is_module": bool, "name": str|null, "hp": num|null, "power_12v_ma": num|null, '
    '"power_neg12v_ma": num|null, "power_5v_ma": num|null, "depth_mm": num|null, "tags": [<=4 short function words]}.'
)


def verbatim(value: float, unit_pat: str, text: str) -> bool:
    v = int(value) if float(value).is_integer() else value
    return re.search(rf"(?<![\d.]){re.escape(str(v))}\s*{unit_pat}", text, re.I) is not None or re.search(rf"{unit_pat}[^0-9]{{0,12}}{re.escape(str(v))}(?![\d.])", text, re.I) is not None


def extract(brand: str, url: str, body: str, method: str) -> dict | None:
    text = page_text(body)
    if len(text) < 200:
        return None
    det = {"hp": first_num(HP, text), "power_12v_ma": first_num(P12, text), "power_neg12v_ma": first_num(N12, text), "power_5v_ma": first_num(P5, text), "depth_mm": first_num(DEPTH, text)}
    m = re.search(DEPTH[2], text)
    if m and det["depth_mm"] is not None and float(m.group(1)) == det["depth_mm"]:
        det["depth_mm"] = round(det["depth_mm"] * 25.4)
    title_m = re.search(r'property="og:title"\s+content="([^"]+)"', body) or re.search(r"<title[^>]*>([^<]+)</title>", body, re.I)
    title = html.unescape(title_m.group(1)).strip() if title_m else ""
    if det["hp"] is None and det["power_12v_ma"] is None and det["power_neg12v_ma"] is None:
        return None  # no spec signal: not worth a model call
    window = spec_window(text)
    res = llm(EXTRACT_SYS, f"Brand: {brand}\nTitle: {title[:120]}\nText: {window}", 200) or {}
    if not res.get("is_module"):
        return None
    units = {"hp": r"(?:HP|TE)\b", "power_12v_ma": r"mA", "power_neg12v_ma": r"mA", "power_5v_ma": r"mA", "depth_mm": r"(?:mm|in|inch)"}
    out: dict = {}
    sources: dict = {}
    for field, unit in units.items():
        mv, dv = res.get(field), det.get(field)
        val = None
        if isinstance(mv, (int, float)) and mv >= 0:
            if dv is not None and float(mv) == float(dv):
                val = float(mv)
            elif verbatim(float(mv), unit, text):
                val = float(mv)
        elif dv is not None and mv is None and field in ("hp",):
            val = dv
        out[field] = val
        if val is not None:
            sources[field] = url
    if out["hp"] is None or not (1 <= out["hp"] <= 104):
        return None
    if out["depth_mm"] is not None and not (5 <= out["depth_mm"] <= 200):
        out["depth_mm"] = None
        sources.pop("depth_mm", None)
    name = res.get("name") if isinstance(res.get("name"), str) else None
    if not name or (name.lower() not in text.lower() and name.lower() not in title.lower()):
        name = re.split(r"\s+[|\u2013\u2014-]\s+", title)[0].strip() or None
    if name:
        name = re.split(r"\s+[|\u2013\u2014-]\s+", name)[0]
        name = re.sub(rf"^{re.escape(brand)}\s+", "", name, flags=re.I).strip()[:120]
    if not name:
        return None
    img = re.search(r'property="og:image"\s+content="([^"]+)"', body)
    tags = [t for t in (res.get("tags") or []) if isinstance(t, str) and t.lower() in text.lower()][:4]
    return {
        "brand": brand, "name": name, **{k: (int(v) if v is not None and float(v).is_integer() else v) for k, v in out.items()},
        "image_url": img.group(1) if img else None, "source_url": url, "sources": sources, "tags": tags,
        "fetch_method": method, "content_sha256": hashlib.sha256(body.encode("utf-8", "ignore")).hexdigest(),
        "provenance": "OBSERVED", "extracted_by": f"regex+{MODEL}",
    }


# ---------------------------------------------------------------- stage 1
def brand_on_page(brand: str, text: str) -> bool:
    tokens = [t for t in re.findall(r"[a-z0-9]+", brand.lower()) if len(t) >= 3 and t not in {"modular", "audio", "music", "synth", "synths", "electronics", "instruments", "labs", "technology", "systems", "devices", "modules"}]
    low = re.sub(r"[^a-z0-9]", "", text.lower()[:200_000])
    return any(t in low for t in tokens or [re.sub(r"[^a-z0-9]", "", brand.lower())])


def resolve_brand(brand: str) -> dict:
    """Homepage in order: adapter, curated list, the v1 crawl's resolved site, then search."""
    adapter = (SOURCES.get("adapters") or {}).get(brand)
    if adapter:
        return {"brand": brand, "homepage": adapter["homepage"], "status": "resolved", "how": f"adapter:{adapter['kind']}"}
    curated = (SOURCES.get("homepages") or {}).get(brand)
    if curated:
        if curated["status"] in ("rejected", "robots_disallowed"):
            return {"brand": brand, "homepage": None, "status": f"curated_{curated['status']}"}
        if curated["status"] == "verified_free":
            return {"brand": brand, "homepage": curated["homepage"], "status": "resolved", "how": "curated"}
        body, _ = fetch_text(curated["homepage"])  # candidate: must show the brand first
        if body and brand_on_page(brand, body):
            return {"brand": brand, "homepage": curated["homepage"], "status": "resolved", "how": "curated_confirmed"}
        return {"brand": brand, "homepage": None, "status": "curated_unconfirmed", "candidate": curated["homepage"]}
    if PRIOR.get(brand):
        return {"brand": brand, "homepage": PRIOR[brand], "status": "resolved", "how": "v1_crawl"}
    hit = cached("resolve", brand)
    if hit is not None:
        return hit
    urls = [u for u in search(f"{brand} eurorack modules official website") if not excluded(u)]
    out = {"brand": brand, "homepage": None, "status": "needs_search" if DRY_RUN else "no_candidates"}
    if urls:
        cand = next((u for u in urls[:8] if domain_matches_brand(u, brand)), None)
        how = "domain_match"
        if cand is None:
            listing = "\n".join(f"{i}. {u}" for i, u in enumerate(urls[:8]))
            pick = llm(RESOLVE_SYS, f"Brand: {brand}\nResults:\n{listing}", 150) or {}
            idx = pick.get("index", -1) if isinstance(pick.get("index"), int) else -1
            if 0 <= idx < len(urls[:8]):
                body, _ = fetch_text(urls[idx])
                if body and brand_on_page(brand, body):
                    cand, how = urls[idx], "model_pick_confirmed"
                else:
                    out = {"brand": brand, "homepage": None, "status": "model_pick_unconfirmed", "candidate": urls[idx]}
            elif out["status"] == "no_candidates":
                out = {"brand": brand, "homepage": None, "status": "model_none"}
        if cand is not None:
            parsed = urllib.parse.urlparse(cand)
            out = {"brand": brand, "homepage": f"{parsed.scheme}://{parsed.netloc}/", "status": "resolved", "how": how, "evidence": cand}
        store("resolve", brand, out)
    return out


# ---------------------------------------------------------------- stage 2
def discover(home: str, limit: int = 4000) -> list[str]:
    hit = cached("discover", home)
    if hit is not None:
        return hit
    host = _host(home).replace("www.", "")
    urls = maker_adapters.sitemap_urls(FETCH, home)
    for cand in maker_adapters.enumerate_products(FETCH, {"homepage": home, "kind": "shopify"}):
        urls.append(cand.url)
    body, _ = fetch_text(home)
    for href in maker_adapters.HREF.findall(body):
        urls.append(urllib.parse.urljoin(home, html.unescape(href)).split("?")[0].split("#")[0])
    urls = list(dict.fromkeys(u for u in urls if _host(u).replace("www.", "") == host and not excluded(u)))[:limit]
    if urls:  # an empty result is usually a failed fetch: retry it next run
        store("discover", home, urls)
    return urls


def choose_links(brand: str, urls: list[str], cap: int) -> list[str]:
    cand = [u for u in urls if not NON_MODULE.search(urllib.parse.urlparse(u).path) and not ASSET.search(u)]
    productish = [u for u in cand if PRODUCTISH.search(u)]
    pool = productish if len(productish) >= 5 else cand
    pool = list(dict.fromkeys(pool))[: max(300, cap)]
    if len(pool) <= 12:
        return pool
    if DRY_RUN or NO_MODEL:
        BUDGET.bump("llm_calls")  # a model run picks from this pool
        return pool[:cap]
    listing = "\n".join(f"{i}. {urllib.parse.urlparse(u).path}" for i, u in enumerate(pool))
    res = llm(PICK_SYS.replace("at most 80", f"at most {cap}"), f"Manufacturer: {brand}\n{listing}", min(4000, 400 + 4 * cap)) or {}
    picks = [pool[i] for i in res.get("pick", []) if isinstance(i, int) and 0 <= i < len(pool)]
    return picks[:cap] if picks else pool[: min(cap, 40)]


# ---------------------------------------------------------------- stage 3/4
def deterministic(brand: str, url: str, text: str, name: str | None, body: str = "") -> dict | None:
    """Values parsed straight from the maker's text; no model. HP must be unambiguous."""
    if len(text) < 8:
        return None
    window = spec_window(text, 2400)
    # A labelled width wins over stray mentions (menus list cases as "104HP").
    hps = {int(m) for pat in HP_LABELLED for m in re.findall(pat, text, re.I) if 1 <= int(m) <= 104}
    if not hps:
        hps = {int(m) for pat in HP for m in re.findall(pat, window, re.I) if 1 <= int(m) <= 104}
    if len(hps) != 1:
        return {"ambiguous_hp": sorted(hps)} if hps else None
    det = {"hp": hps.pop(), "power_12v_ma": first_num(P12, window), "power_neg12v_ma": first_num(N12, window), "power_5v_ma": first_num(P5, window), "depth_mm": first_num(DEPTH, window)}
    m = re.search(DEPTH[2], window)
    if m and det["depth_mm"] is not None and float(m.group(1)) == det["depth_mm"]:
        det["depth_mm"] = round(det["depth_mm"] * 25.4)
    if det["depth_mm"] is not None and not (5 <= det["depth_mm"] <= 200):
        det["depth_mm"] = None
    if not name:
        title_m = re.search(r'property="og:title"\s+content="([^"]+)"', body) or re.search(r"<title[^>]*>([^<]+)</title>", body, re.I)
        name = html.unescape(title_m.group(1)).strip() if title_m else None
    if name:
        name = re.split(r"\s+[|–—-]\s+", name)[0]
        name = re.sub(rf"^{re.escape(brand)}\s+", "", name, flags=re.I).strip()[:120]
    if not name:
        return None
    img = re.search(r'property="og:image"\s+content="([^"]+)"', body)
    return {
        "brand": brand, "name": name, **{k: (int(v) if v is not None and float(v).is_integer() else v) for k, v in det.items()},
        "image_url": img.group(1) if img else None, "source_url": url,
        "sources": {k: url for k, v in det.items() if v is not None}, "tags": [],
        "content_sha256": hashlib.sha256((body or text).encode("utf-8", "ignore")).hexdigest(),
        "provenance": "OBSERVED", "extracted_by": "regex",
    }


def crawl_adapter(brand: str, cfg: dict, cap: int, rec: dict) -> None:
    # An adapter may set its own page budget (e.g. Behringer lists its whole range).
    cands = maker_adapters.enumerate_products(FETCH, {**cfg, "max_pages": int(cfg.get("max_pages") or cap)})
    rec["discovered"] = len(cands)
    for cand in cands:
        row = deterministic(brand, cand.url, cand.text or "", cand.name) if cand.text else None
        method = "feed"
        if row is None or "ambiguous_hp" in row:
            body, method = fetch_text(cand.url, render=bool(cfg.get("render")))
            rec["pages"] += 1
            rec["methods"][method] = rec["methods"].get(method, 0) + 1
            if not body:
                continue
            text = page_text(body)
            row = deterministic(brand, cand.url, text, cand.name, body)
            if row and "ambiguous_hp" in row:
                rec["ambiguous_hp"] += 1
                # The model may settle it only when its value appears verbatim (same rule as v1).
                row = None if DRY_RUN or NO_MODEL else extract(brand, cand.url, body, method)
        if row and "ambiguous_hp" not in row:
            row["fetch_method"] = method
            rec["modules"].append(row)


def crawl_generic(brand: str, home: str, cap: int, rec: dict) -> None:
    urls = discover(home)
    picks = choose_links(brand, urls, cap)
    rec["discovered"], rec["picked"] = len(urls), len(picks)
    for url in picks:
        if not BUDGET.can_spend():
            rec["status"] = "budget_stop"
            break
        body, method = fetch_text(url)
        rec["methods"][method] = rec["methods"].get(method, 0) + 1
        rec["pages"] += 1
        if not body:
            continue
        if DRY_RUN or NO_MODEL:
            row = deterministic(brand, url, page_text(body), None, body)
            if row and "ambiguous_hp" not in row:
                BUDGET.bump("llm_calls")  # a model run confirms each generic row
                if DRY_RUN:
                    rec["modules"].append(row)
                else:  # paid without a model: kept for a later confirmation pass, never loaded as-is
                    row["confirmed"] = False
                    rec["unconfirmed"].append(row)
            elif row:
                rec["ambiguous_hp"] += 1
        else:
            row = extract(brand, url, body, method)
            if row:
                rec["modules"].append(row)


def crawl_brand(brand: str, cap: int) -> dict:
    rec = {"brand": brand, "modules": [], "unconfirmed": [], "pages": 0, "status": None, "methods": {}, "ambiguous_hp": 0}
    if not BUDGET.can_spend():
        rec["status"] = "budget_stop"
        return rec
    r = resolve_brand(brand)
    rec["resolved_by"] = r.get("how")
    if not r.get("homepage"):
        rec["status"] = r["status"]
        return rec
    home = rec["homepage"] = r["homepage"]
    readable, _, delay = FETCH.robots_info(home)
    if readable:
        SCRAPER.host_intervals[_host(home)] = max(2.0, min(delay, 15.0))
    adapter = (SOURCES.get("adapters") or {}).get(brand)
    rec["path"] = f"adapter:{adapter['kind']}" if adapter else "generic"
    if adapter:
        crawl_adapter(brand, adapter, cap, rec)
    else:
        crawl_generic(brand, home, cap, rec)
    rec["status"] = rec["status"] or "done"
    seen: set[str] = set()
    rec["modules"] = [m for m in rec["modules"] if not (norm_name(brand, m["name"]) in seen or seen.add(norm_name(brand, m["name"])))]
    return rec


# ---------------------------------------------------------------- run
def summarize(results: list[dict], budget: dict, args) -> dict:
    by_path: dict[str, dict] = {}
    for r in results:
        key = r.get("path") or "unresolved"
        agg = by_path.setdefault(key, {"brands": 0, "brands_with_modules": 0, "modules": 0, "with_power": 0})
        agg["brands"] += 1
        agg["brands_with_modules"] += 1 if r["modules"] else 0
        agg["modules"] += len(r["modules"])
        agg["with_power"] += sum(1 for m in r["modules"] if m.get("power_12v_ma") is not None)
    methods: dict[str, int] = {}
    for r in results:
        for k, v in (r.get("methods") or {}).items():
            methods[k] = methods.get(k, 0) + v
    statuses: dict[str, int] = {}
    for r in results:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    would = BUDGET.would
    # Worst case: every would-pay URL costs one context.dev credit and then one Firecrawl credit.
    proj_credits = would["paid_fetch_urls"] + would["paid_searches"]
    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mode": "dry-run" if DRY_RUN else "paid",
        "max_pages_per_brand": args.max_pages,
        "brands": len(results),
        "statuses": dict(sorted(statuses.items())),
        "yield_by_path": by_path,
        "modules_total": sum(len(r["modules"]) for r in results),
        "unconfirmed_generic": sum(len(r.get("unconfirmed") or []) for r in results),
        "modules_with_power": sum(1 for r in results for m in r["modules"] if m.get("power_12v_ma") is not None),
        "fetch_methods": dict(sorted(methods.items(), key=lambda kv: -kv[1])),
        "budget": budget,
        "per_brand": [
            {k: r.get(k) for k in ("brand", "status", "path", "resolved_by", "homepage", "discovered", "picked", "pages", "ambiguous_hp")}
            | {"modules": len(r["modules"]), "unconfirmed": len(r.get("unconfirmed") or [])}
            for r in results
        ],
    }
    if NO_MODEL:
        out["model_calls_skipped"] = BUDGET.would["llm_calls"]
    if DRY_RUN:
        out["projection"] = {
            "paid_fetch_urls": would["paid_fetch_urls"],
            "paid_searches": would["paid_searches"],
            "llm_calls": would["llm_calls"],
            "llm_usd": round(would["llm_calls"] * V1_COST_PER_LLM_CALL, 2),
            "credits_low": proj_credits,
            "credits_worst_case": proj_credits * 2,
            "overage_usd_if_no_included_credits": round(proj_credits * CTX_OVERAGE_USD + proj_credits * FC_OVERAGE_USD, 2),
            "basis": "would-pay URLs are free fetches the router would hand to context.dev (then Firecrawl); model cost uses the v1 run's measured $/call",
        }
    return out


def render_receipt(summary: dict) -> str:
    """Indented JSON with one line per brand, so receipts diff by brand."""
    body = {k: v for k, v in summary.items() if k != "per_brand"}
    rows = ",\n  ".join(json.dumps(row, ensure_ascii=False) for row in summary["per_brand"])
    return json.dumps(body, indent=1, ensure_ascii=False)[:-2] + ',\n "per_brand": [\n  ' + rows + "\n ]\n}\n"


def main(argv: list[str] | None = None) -> int:
    global BUDGET, SCRAPER, DRY_RUN, NO_MODEL, SOURCES, PRIOR
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="no paid fetch, search or model call; write a yield/spend receipt")
    ap.add_argument("--no-model", action="store_true", help="paid fetches without OpenRouter; generic-path rows are kept unconfirmed")
    ap.add_argument("--cap", type=float, default=14.5)
    ap.add_argument("--ctx-start", type=float, default=0.0, help="included context.dev credits remaining at start")
    ap.add_argument("--fc-start", type=float, default=0.0, help="included Firecrawl credits remaining at start")
    ap.add_argument("--max-paid-fetches", type=int, default=0, help="router paid-call cap (fetches and searches)")
    ap.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help="pages per maker")
    ap.add_argument("--brands", default="", help="comma-separated brand subset")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=24)
    args = ap.parse_args(argv)
    if not args.dry_run and args.max_paid_fetches <= 0:
        print("paid run needs --max-paid-fetches (approved cap); use --dry-run to measure first", file=sys.stderr)
        return 2
    if not args.dry_run and not args.no_model and not os.environ.get("OPENROUTER_API_KEY"):
        print("paid run needs OPENROUTER_API_KEY for the generic path's model checks (or --no-model)", file=sys.stderr)
        return 2
    DRY_RUN, NO_MODEL = args.dry_run, args.no_model and not args.dry_run
    BUDGET = Budget(args.cap, args.ctx_start, args.fc_start)
    WORK.mkdir(parents=True, exist_ok=True)
    SCRAPER = CatalogScraper(
        cache_dir=CATALOG / ".cache" / "http",
        # A dry run keeps its call counts out of the committed spend ledger.
        ledger_path=(WORK / "ledger.dry-run.json") if DRY_RUN else (RECEIPTS / "scrape-ledger.json"),
        max_paid_fetches=0 if DRY_RUN else args.max_paid_fetches,
        min_interval_s=2.0,
        max_age_s=7 * 86400,
        max_retries=2,
        on_receipt=_account,
    )
    SOURCES = maker_adapters.load_sources()
    if PRIOR_CRAWL.is_file():
        PRIOR = {b["brand"]: b["homepage"] for b in json.loads(PRIOR_CRAWL.read_text())["brands"] if b.get("homepage") and b.get("status") == "done"}
    brands = json.loads((CATALOG / "seed-phase2-v1.json").read_text())["brands"] + list(SOURCES.get("extra_brands") or [])
    brands = [b for b in dict.fromkeys(brands) if b != "Other/unknown"]
    if args.brands:
        wanted = {b.strip() for b in args.brands.split(",")}
        brands = [b for b in brands if b in wanted]
    if args.limit:
        brands = brands[: args.limit]
    results = []
    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(crawl_brand, b, args.max_pages): b for b in brands}
        for fut in cf.as_completed(futs):
            try:
                results.append(fut.result())
            except Exception as exc:  # keep crawling
                results.append({"brand": futs[fut], "status": f"error:{exc.__class__.__name__}", "modules": [], "methods": {}})
            done += 1
            if done % 20 == 0 or done == len(brands):
                snap = BUDGET.snapshot()
                mods = sum(len(r.get("modules", [])) for r in results)
                print(f"[{time.strftime('%H:%M:%S')}] brands {done}/{len(brands)} modules {mods} spend ${snap['projected_total_usd']} would-pay {BUDGET.would}", flush=True)
                (WORK / "progress.json").write_text(json.dumps({"budget": snap, "would": BUDGET.would, "done": done}, indent=1))
    results.sort(key=lambda r: r["brand"].lower())
    budget = BUDGET.snapshot()
    summary = summarize(results, budget, args)
    if DRY_RUN:
        (WORK / "maker-crawl-v2.dry-run.rows.json").write_text(json.dumps(results, indent=1) + "\n")
        (RECEIPTS / "maker-crawl-v2.dry-run.json").write_text(render_receipt(summary))
    else:
        (OUT / "maker-crawl-v2.json").write_text(json.dumps({"generated_at": summary["generated_at"], "budget": budget, "brands": results}, indent=1) + "\n")
        (RECEIPTS / "maker-crawl-v2.json").write_text(render_receipt(summary))
    print(json.dumps({k: summary[k] for k in ("modules_total", "unconfirmed_generic", "modules_with_power", "yield_by_path", "statuses")} | {"projection": summary.get("projection"), "budget": budget}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
