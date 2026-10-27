#!/usr/bin/env python3
"""Manufacturer-site catalog crawl (approved by Danny 2026-10-17, $15 combined cap).

Stages: resolve (brand -> official site) -> discover (robots, sitemaps, Shopify
feeds, homepage links) -> fetch (free, then the shared scrape-router: context.dev, then Firecrawl, under its caps and ledger) ->
extract (deterministic regex + open-weights model; every accepted value must be
parsed deterministically or appear verbatim on the maker's page).

ModularGrid and resellers are never fetched. robots.txt is honoured for every
host, including paid fetches. Keys come from the environment and are never
printed. Spend is tracked as projected overage beyond included plan credits plus
model cost, with a hard stop.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import gzip
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
import urllib.robotparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "synth-catalog"
WORK = CATALOG / ".cache" / "maker-crawl"
OUT = CATALOG / "hermes-research"
UA = "PatchHiveCatalogBot/1.0 (+https://github.com/Zero-State-LLC/Patch-Hive)"
MODEL = os.environ.get("PATCHHIVE_CRAWL_MODEL", "deepseek/deepseek-v4.1-flash")
MODEL_IN, MODEL_OUT = 0.15 / 1e6, 0.60 / 1e6  # live OpenRouter price 2026-10-17

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
NON_MODULE = re.compile(
    r"(t-shirt|tshirt|shirt|hoodie|crewneck|sweater|hat|cap-|beanie|sticker|poster|mug|tote|merch|"
    r"gift|card|cable|patch-cable|skiff|case|rack|enclosure|power-supply|psu|busboard|bus-board|"
    r"blank|b-stock|bstock|refurb|demo-unit|rma|repair|service|spare|knob|jack|screw|rail|"
    r"bundle|voucher|shipping|warranty|faq|blog|news|about|contact|cart|account|login|privacy|"
    r"terms|policy|dealers|distributors|press|careers|tag/|category/|author/|page/\d)",
    re.I,
)
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
        self.calls = {"ctx_search": 0, "ctx_scrape": 0, "fc_scrape": 0, "llm": 0}
        self.lock = threading.Lock()

    def overage(self) -> float:
        ctx = max(0.0, self.ctx_used - self.ctx_start) * 0.0022
        fc = max(0.0, self.fc_used - self.fc_start) * 0.005
        return ctx + fc

    def projected(self) -> float:
        return self.overage() + self.llm_cost

    def can_spend(self, margin: float = 0.25) -> bool:
        with self.lock:
            return self.projected() + margin < self.cap

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
HOST_LOCKS: dict[str, threading.Lock] = {}
HOST_NEXT: dict[str, float] = {}
GLOBAL_LOCK = threading.Lock()
CTX_SEM = threading.Semaphore(8)
FC_SEM = threading.Semaphore(4)
ASSET = re.compile(r"\.(jpe?g|png|gif|webp|svg|pdf|zip|mp3|wav|mp4|mov|css|js|xml|txt|stl|syx|bin|hex|dmg|exe)(\?|$)", re.I)


def _host(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


def polite_wait(url: str, delay: float) -> None:
    host = _host(url)
    with GLOBAL_LOCK:
        lock = HOST_LOCKS.setdefault(host, threading.Lock())
    with lock:
        now = time.monotonic()
        wait = HOST_NEXT.get(host, 0) - now
        if wait > 0:
            time.sleep(wait)
        HOST_NEXT[host] = time.monotonic() + delay


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


def http_get(url: str, timeout: float = 25, max_bytes: int = 3_000_000) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xml,application/json;q=0.9,*/*;q=0.5", "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes)
            if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, raw.decode("utf-8", errors="replace"), ctype
    except urllib.error.HTTPError as exc:
        return exc.code, "", ""
    except Exception:
        return 0, "", ""


def _post(url: str, payload: dict, key: str, timeout: float = 90) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": UA})
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


_ROUTER = None
_ROUTER_LOCK = threading.Lock()
ROUTER_CALLER = "patchhive-catalog-maker-crawl"


def router():
    """Shared scrape-router (budget caps, min-balance floors, ledger, receipts).

    Paid search and paid fetch go through it; this script never calls
    context.dev or Firecrawl directly. Set SCRAPE_ROUTER_SITE to the router's
    site-packages if it is not importable. Without the router, paid calls are off.
    """
    global _ROUTER
    with _ROUTER_LOCK:
        if _ROUTER is None:
            site = os.environ.get("SCRAPE_ROUTER_SITE", "").strip()
            if site and site not in sys.path:
                sys.path.insert(0, site)
            try:
                from scrape_router.router import Router  # type: ignore

                _ROUTER = Router.from_config()
            except Exception:
                _ROUTER = False
                print("scrape-router not importable: paid search/fetch disabled", file=sys.stderr)
        return _ROUTER or None


def _account(res) -> None:
    receipt = getattr(res, "receipt", None)
    spent = dict(getattr(receipt, "credits_by_backend", None) or {})
    with BUDGET.lock:
        BUDGET.ctx_used += float(spent.get("context_dev") or 0)
        BUDGET.fc_used += float(spent.get("firecrawl") or 0)


def ctx_search(query: str) -> list[dict]:
    hit = cached("search", query)
    if hit is not None:
        return hit
    r = router()
    if r is None or not BUDGET.can_spend():
        return []
    res = r.search(query, limit=10, caller=ROUTER_CALLER, allow="paid")
    _account(res)
    with BUDGET.lock:
        BUDGET.calls["ctx_search"] += 1
    if not res.ok:
        return []
    try:
        raw = json.loads(res.text or "[]")
    except (TypeError, ValueError):
        raw = res.data or []
    if isinstance(raw, dict):
        raw = raw.get("results") or raw.get("data") or raw.get("web") or []
    results = [
        {
            "url": r_.get("url") or r_.get("link"),
            "title": (r_.get("title") or "")[:120],
            "desc": (r_.get("description") or r_.get("snippet") or "")[:160],
        }
        for r_ in raw
        if isinstance(r_, dict) and (r_.get("url") or r_.get("link"))
    ]
    store("search", query, results)
    return results


def paid_fetch(url: str) -> tuple[str, str]:
    """Paid fetch through the scrape-router (context.dev, then Firecrawl, within its caps)."""
    if EXCLUDED.search(url):
        return "", "failed"
    r = router()
    if r is None or not BUDGET.can_spend():
        return "", "failed"
    res = r.fetch(url, caller=ROUTER_CALLER, allow="paid", fmt="html")
    _account(res)
    with BUDGET.lock:
        if res.backend == "firecrawl":
            BUDGET.calls["fc_scrape"] += 1
        else:
            BUDGET.calls["ctx_scrape"] += 1
    if res.ok and res.text:
        return res.text, res.backend or "router"
    return "", "failed"


def llm(system: str, user: str, max_tokens: int = 300) -> dict | None:
    key = system[:40] + "\n" + user
    hit = cached("llm", key)
    if hit is not None:
        return hit
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


# ---------------------------------------------------------------- stage 1
RESOLVE_SYS = (
    "You pick a Eurorack manufacturer's own official website from search results. "
    "Never pick resellers, marketplaces, forums, social media, databases (ModularGrid), or press. "
    'Reply JSON {"index": <int or -1>}. Use -1 if none is clearly the maker\'s own site.'
)


def resolve_brand(brand: str) -> dict:
    hit = cached("resolve", brand)
    if hit is not None:
        return hit
    results = [r for r in ctx_search(f"{brand} eurorack modules official website") if not EXCLUDED.search(r["url"] or "")]
    out = {"brand": brand, "homepage": None, "status": "no_candidates"}
    if results:
        direct = next((r for r in results[:8] if domain_matches_brand(r["url"], brand, r["title"])), None)
        cand, how = direct, "domain_match"
        if cand is None:
            listing = "\n".join(f"{i}. {r['url']} | {r['title']} | {r['desc'][:100]}" for i, r in enumerate(results[:8]))
            pick = llm(RESOLVE_SYS, f"Brand: {brand}\nResults:\n{listing}", 150) or {}
            idx = pick.get("index", -1) if isinstance(pick.get("index"), int) else -1
            if 0 <= idx < len(results[:8]):
                cand, how = results[idx], "model_pick"
                brand_c = re.sub(r"[^a-z0-9]", "", brand.lower())
                if brand_c not in re.sub(r"[^a-z0-9]", "", (cand["title"] + cand["desc"]).lower()):
                    out = {"brand": brand, "homepage": None, "status": "model_pick_unconfirmed", "candidate": cand["url"]}
                    cand = None
            elif out["status"] == "no_candidates":
                out = {"brand": brand, "homepage": None, "status": "model_none"}
        if cand is not None:
            parsed = urllib.parse.urlparse(cand["url"])
            out = {"brand": brand, "homepage": f"{parsed.scheme}://{parsed.netloc}/", "status": "resolved", "how": how, "evidence": cand["url"]}
    if results:
        store("resolve", brand, out)
    return out


# ---------------------------------------------------------------- stage 2
def robots_for(home: str):
    hit = cached("robots", home)
    rp = urllib.robotparser.RobotFileParser()
    if hit is None:
        status, body, _ = http_get(urllib.parse.urljoin(home, "/robots.txt"), timeout=20)
        hit = {"status": status, "body": body[:200_000]}
        store("robots", home, hit)
    status, body = hit["status"], hit["body"]
    if status == 0 or status >= 500:
        return None, 0.0, []  # unreachable or erroring: skip host (conservative)
    rp.parse(body.splitlines() if 200 <= status < 300 else [])
    delay = rp.crawl_delay(UA) or rp.crawl_delay("*") or 0
    sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", body) if 200 <= status < 300 else []
    return rp, float(delay or 0), sitemaps


def allowed(rp, url: str) -> bool:
    return rp is not None and rp.can_fetch(UA, url) and not EXCLUDED.search(url)


def _locs(xml: str) -> list[str]:
    return [html.unescape(u.strip()) for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml or "", re.I)]


def discover(home: str, rp, delay: float, sitemaps: list[str], limit: int = 4000) -> list[str]:
    hit = cached("discover", home)
    if hit is not None:
        return hit
    host = _host(home)
    seen: set[str] = set()
    urls: list[str] = []
    queue = list(dict.fromkeys(sitemaps + [urllib.parse.urljoin(home, p) for p in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml")]))
    fetched_maps = 0
    while queue and fetched_maps < 12 and len(urls) < limit:
        sm = queue.pop(0)
        if sm in seen or not allowed(rp, sm) or _host(sm).replace("www.", "") != host.replace("www.", ""):
            continue
        seen.add(sm)
        polite_wait(sm, delay)
        status, body, _ = http_get(sm)
        fetched_maps += 1
        if status != 200:
            continue
        for loc in _locs(body):
            if loc.endswith(".xml") or "sitemap" in loc.lower():
                if any(k in loc.lower() for k in ("product", "page", "post", "module", "sitemap_index", "sitemap.xml", "index")) and "blog" not in loc.lower():
                    queue.append(loc)
            elif _host(loc).replace("www.", "") == host.replace("www.", ""):
                urls.append(loc)
    feed = urllib.parse.urljoin(home, "/products.json?limit=250")
    if allowed(rp, feed):
        polite_wait(feed, delay)
        status, body, ctype = http_get(feed)
        if status == 200 and "json" in ctype:
            try:
                for p in json.loads(body).get("products", []):
                    urls.append(urllib.parse.urljoin(home, f"/products/{p['handle']}"))
            except Exception:
                pass
    if allowed(rp, home):
        polite_wait(home, delay)
        status, body, _ = http_get(home)
        if status == 200:
            for href in re.findall(r'href="([^"#]+)"', body):
                u = urllib.parse.urljoin(home, html.unescape(href))
                if _host(u).replace("www.", "") == host.replace("www.", ""):
                    urls.append(u.split("?")[0])
    urls = list(dict.fromkeys(u for u in urls if allowed(rp, u)))[:limit]
    store("discover", home, urls)
    return urls


PICK_SYS = (
    "You select URLs that are individual Eurorack MODULE product pages for one manufacturer "
    "(not cases, power, cables, merch, accessories, blog, category or listing pages). "
    'Reply JSON {"pick": [<indices>]} with at most 80 indices.'
)


def choose_links(brand: str, urls: list[str]) -> list[str]:
    cand = [u for u in urls if not NON_MODULE.search(urllib.parse.urlparse(u).path) and not ASSET.search(u)]
    productish = [u for u in cand if PRODUCTISH.search(u)]
    pool = productish if len(productish) >= 5 else cand
    pool = list(dict.fromkeys(pool))[:300]
    if not pool:
        return []
    if len(pool) <= 12:
        return pool
    listing = "\n".join(f"{i}. {urllib.parse.urlparse(u).path}" for i, u in enumerate(pool))
    res = llm(PICK_SYS, f"Manufacturer: {brand}\n{listing}", 400) or {}
    picks = [pool[i] for i in res.get("pick", []) if isinstance(i, int) and 0 <= i < len(pool)]
    return picks[:80] if picks else pool[:40]


# ---------------------------------------------------------------- stage 3/4
EXTRACT_SYS = (
    "You read trimmed text from a manufacturer's product page. Decide if it is a single Eurorack module "
    "and copy its specs EXACTLY as written. Never guess: use null if a value is not stated. "
    'Reply JSON {"is_module": bool, "name": str|null, "hp": num|null, "power_12v_ma": num|null, '
    '"power_neg12v_ma": num|null, "power_5v_ma": num|null, "depth_mm": num|null, "tags": [<=4 short function words]}.'
)


def verbatim(value: float, unit_pat: str, text: str) -> bool:
    v = int(value) if float(value).is_integer() else value
    return re.search(rf"(?<![\d.]){re.escape(str(v))}\s*{unit_pat}", text, re.I) is not None or re.search(rf"{unit_pat}[^0-9]{{0,12}}{re.escape(str(v))}(?![\d.])", text, re.I) is not None


def fetch_page(url: str, delay: float) -> tuple[str, str]:
    hit = cached("page", url)
    if hit is not None:
        return hit["body"], hit["method"]
    polite_wait(url, delay)
    status, body, ctype = http_get(url)
    if status == 0 and url.startswith("http://"):
        url_s = "https://" + url[len("http://"):]
        polite_wait(url_s, delay)
        status, body, ctype = http_get(url_s)
    method = "free_http"
    is_html = "html" in ctype or body.lstrip()[:1] == "<"
    challenge = bool(re.search(r"(cf-chl|Just a moment\.\.\.|captcha|Access denied)", body[:5000], re.I))
    if status in (0, 403, 429, 503) or challenge:
        body, method = paid_fetch(url)
    elif status != 200 or not is_html:
        body, method = "", f"http_{status}"
    store("page", url, {"body": body[:600_000], "method": method})
    return body, method


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


def crawl_brand(brand: str) -> dict:
    rec = {"brand": brand, "modules": [], "pages": 0, "status": None}
    if not BUDGET.can_spend():
        rec["status"] = "budget_stop"
        return rec
    r = resolve_brand(brand)
    if not r.get("homepage"):
        rec["status"] = r["status"]
        return rec
    home = r["homepage"]
    rec["homepage"] = home
    rp, delay, sitemaps = robots_for(home)
    if rp is None:
        rec["status"] = "robots_unreachable"
        return rec
    if not allowed(rp, home):
        rec["status"] = "robots_disallowed"
        return rec
    delay = max(2.0, min(delay, 15.0))
    urls = discover(home, rp, delay, sitemaps)
    picks = choose_links(brand, urls)
    rec["discovered"], rec["picked"] = len(urls), len(picks)
    methods: dict = {}
    for url in picks:
        if not BUDGET.can_spend():
            rec["status"] = "budget_stop"
            break
        body, method = fetch_page(url, delay)
        methods[method] = methods.get(method, 0) + 1
        rec["pages"] += 1
        if body:
            row = extract(brand, url, body, method)
            if row:
                rec["modules"].append(row)
    if len(rec["modules"]) < 3 and rec["status"] is None:
        hop: list[str] = []
        for url in picks[:30]:
            h = cached("page", url)
            for href in re.findall(r'href="([^"#]+)"', (h or {}).get("body", "")):
                u = urllib.parse.urljoin(url, html.unescape(href)).split("?")[0]
                if _host(u).replace("www.", "") == _host(home).replace("www.", "") and u not in picks and allowed(rp, u):
                    hop.append(u)
        hop_picks = choose_links(brand, list(dict.fromkeys(hop)))[:60]
        rec["hop_picked"] = len(hop_picks)
        for url in hop_picks:
            if not BUDGET.can_spend():
                rec["status"] = "budget_stop"
                break
            body, method = fetch_page(url, delay)
            methods[method] = methods.get(method, 0) + 1
            rec["pages"] += 1
            if body:
                row = extract(brand, url, body, method)
                if row:
                    rec["modules"].append(row)
    rec["methods"] = methods
    rec["status"] = rec["status"] or "done"
    seen = set()
    rec["modules"] = [m for m in rec["modules"] if not (norm_name(brand, m["name"]) in seen or seen.add(norm_name(brand, m["name"])))]
    return rec


def main() -> int:
    global BUDGET
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=float, default=14.5)
    ap.add_argument("--ctx-start", type=float, required=True, help="included context.dev credits remaining at start")
    ap.add_argument("--fc-start", type=float, required=True, help="included Firecrawl credits remaining at start")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=24)
    args = ap.parse_args()
    BUDGET = Budget(args.cap, args.ctx_start, args.fc_start)
    brands = json.loads((CATALOG / "seed-phase2-v1.json").read_text())["brands"]
    if args.limit:
        brands = brands[: args.limit]
    WORK.mkdir(parents=True, exist_ok=True)
    results = []
    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(crawl_brand, b): b for b in brands}
        for fut in cf.as_completed(futs):
            try:
                results.append(fut.result())
            except Exception as exc:  # keep crawling
                results.append({"brand": futs[fut], "status": f"error:{exc.__class__.__name__}", "modules": []})
            done += 1
            if done % 20 == 0 or done == len(brands):
                snap = BUDGET.snapshot()
                mods = sum(len(r.get("modules", [])) for r in results)
                print(f"[{time.strftime('%H:%M:%S')}] brands {done}/{len(brands)} modules {mods} spend ${snap['projected_total_usd']} ctx {snap['context_dev_credits']} fc {snap['firecrawl_credits']} llm ${snap['model_cost_usd']}", flush=True)
                (WORK / "progress.json").write_text(json.dumps({"budget": snap, "done": done}, indent=1))
    results.sort(key=lambda r: r["brand"].lower())
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "budget": BUDGET.snapshot(), "brands": results}
    (OUT / "maker-crawl-v1.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out["budget"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
