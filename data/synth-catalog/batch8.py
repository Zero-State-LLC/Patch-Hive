"""Batch 8: verify candidate brands and search unresolved power/depth gaps.

Brand status is verified, corrected, or flagged. Power and depth are recorded
only when a fetched page contains a strict labeled value and the module name.
Nothing is guessed.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from catalog_scrape import CatalogScraper

CATALOG = Path(__file__).resolve().parent
ROOT = CATALOG.parents[1]

VERIFIED = "verified"
CORRECTED = "corrected"
FLAGGED = "flagged"

SKIP_HOSTS = (
    "duckduckgo.",
    "google.",
    "bing.com",
    "facebook.com",
    "youtube.com",
    "reddit.com",
    "modulargrid.net",
    "wikipedia.org",
)


def create_slug(brand: str, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", f"{brand}-{name}".lower())
    return slug.strip("-")


def normalize_brand(value: str) -> str:
    text = html.unescape(value or "").casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def name_from_title(title: str, brand: str) -> str:
    text = re.sub(
        r"\s*[-|–—]\s*Eurorack Module on ModularGrid\s*$",
        "",
        title or "",
        flags=re.I,
    ).strip()
    text = re.sub(r"\s*[-|–—]\s*ModularGrid\s*$", "", text, flags=re.I).strip()
    if brand and text.lower().startswith(brand.lower()):
        text = text[len(brand) :].strip(" -–—")
    return text or (title or "").strip()


def extract_vendor(page: str) -> str | None:
    match = re.search(r'<span class="vendor-name">([^<]+)</span>', page or "", re.I)
    if not match:
        return None
    name = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    if not name or len(name) > 100:
        return None
    return name


def extract_h1(page: str) -> str | None:
    match = re.search(r'<div class="module-view-header">\s*<h1>([^<]+)</h1>', page or "", re.I)
    if not match:
        return None
    name = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return name or None


def load_catalog_slugs() -> set[str]:
    slugs: set[str] = set()
    phase2 = json.loads((CATALOG / "seed-phase2-v1.json").read_text(encoding="utf-8"))
    phase3 = json.loads((CATALOG / "seed-phase3-v1.json").read_text(encoding="utf-8"))
    rows = list(phase2.get("catalog_modules") or []) + list(phase3.get("catalog_modules") or [])
    rows += list(phase2.get("full_spec_modules") or [])
    for row in rows:
        brand = (row.get("brand") or "").strip()
        name = (row.get("name") or "").strip()
        if brand and name:
            slugs.add(create_slug(brand, name))
    return slugs


def verify_candidate(scraper: CatalogScraper, row: dict[str, Any], known_slugs: set[str]) -> dict[str, Any]:
    brand = (row.get("brand") or "").strip()
    source_url = row.get("source_url") or ""
    stored_name = name_from_title(row.get("page_title") or "", brand)
    page = ""
    fetch_status = None
    if source_url:
        result = scraper.fetch(source_url)
        fetch_status = result.receipt.get("status")
        page = result.text or ""
    vendor = extract_vendor(page) if page else None
    observed_name = extract_h1(page) if page else None
    module_name = observed_name or stored_name
    if vendor and normalize_brand(vendor) == normalize_brand(brand):
        status = VERIFIED
        effective = vendor
        provenance = "OBSERVED"
    elif vendor:
        status = CORRECTED
        effective = vendor
        provenance = "OBSERVED"
    else:
        status = FLAGGED
        effective = brand
        provenance = "NOT_COMPUTABLE"
    slug = create_slug(effective, module_name) if module_name else ""
    url_slug = ""
    if source_url:
        url_slug = source_url.rstrip("/").rsplit("/", 1)[-1].lower()
    duplicate = bool(slug and slug in known_slugs) or bool(url_slug and url_slug in known_slugs)
    return {
        "candidate_brand": brand,
        "effective_brand": effective,
        "normalized_brand": normalize_brand(effective),
        "corrected_brand": effective if status == CORRECTED else None,
        "module_name": module_name,
        "slug": slug,
        "source_url": source_url,
        "verification_status": status,
        "catalog_match": "duplicate" if duplicate else "new",
        "fetch_status": fetch_status,
        "provenance": provenance,
        "page_title": row.get("page_title"),
        "hp": row.get("hp"),
        "power_12v_ma": row.get("power_12v_ma"),
        "power_neg12v_ma": row.get("power_neg12v_ma"),
        "power_5v_ma": row.get("power_5v_ma"),
        "depth_mm": row.get("depth_mm"),
    }


def _html_to_text(page: str) -> str:
    text = re.sub(r"<script\b[\s\S]*?</script\b[^>]*>", " ", page or "", flags=re.I)
    text = re.sub(r"<style\b[\s\S]*?</style\b[^>]*>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text)


def _labeled_ints(text: str, patterns: list[re.Pattern[str]]) -> set[int]:
    found: set[int] = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            found.add(int(match.group(1)))
    return found


_PLUS = [
    re.compile(r"(\d+)\s*mA\s*\+\s*12\s*V", re.I),
    re.compile(r"\+\s*12\s*V\s*[:/]\s*(\d+)\s*mA", re.I),
    re.compile(r"(\d+)\s*mA\s*(?:@|at)\s*\+\s*12\s*V", re.I),
]
_NEG = [
    re.compile(r"(\d+)\s*mA\s*-\s*12\s*V", re.I),
    re.compile(r"-\s*12\s*V\s*[:/]\s*(\d+)\s*mA", re.I),
    re.compile(r"(\d+)\s*mA\s*(?:@|at)\s*-\s*12\s*V", re.I),
]
_FIVE = [
    re.compile(r"(\d+)\s*mA\s*\+?\s*5\s*V", re.I),
    re.compile(r"\+\s*5\s*V\s*[:/]\s*(\d+)\s*mA", re.I),
]
_DEPTH = [
    re.compile(r"(\d+(?:\.\d+)?)\s*mm\s*deep", re.I),
    re.compile(r"depth\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*mm", re.I),
]


def parse_specs(page: str) -> dict[str, Any]:
    """Strict labeled +12V/-12V/5V mA and depth. Disagreeing values become null."""
    text = _html_to_text(page)
    specs: dict[str, Any] = {
        "power_12v_ma": None,
        "power_neg12v_ma": None,
        "power_5v_ma": None,
        "depth_mm": None,
    }
    block = re.search(
        r"(\d+)\s*mA\s*\+\s*12V\s+(\d+)\s*mA\s*-\s*12V\s+(\d+)\s*mA\s*5V",
        text,
        re.I,
    )
    plus = _labeled_ints(text, _PLUS)
    neg = _labeled_ints(text, _NEG)
    five = _labeled_ints(text, _FIVE)
    if block:
        plus.add(int(block.group(1)))
        neg.add(int(block.group(2)))
        five.add(int(block.group(3)))
    if len(plus) == 1:
        specs["power_12v_ma"] = next(iter(plus))
    if len(neg) == 1:
        specs["power_neg12v_ma"] = next(iter(neg))
    if len(five) == 1:
        specs["power_5v_ma"] = next(iter(five))
    depths = {float(match.group(1)) for pattern in _DEPTH for match in pattern.finditer(text)}
    if len(depths) == 1:
        specs["depth_mm"] = next(iter(depths))
    return specs


def page_mentions(page: str, brand: str, name: str) -> bool:
    norm = re.sub(r"[^a-z0-9]+", "", _html_to_text(page).lower())
    name_tok = re.sub(r"[^a-z0-9]+", "", name.lower())
    brand_tok = re.sub(r"[^a-z0-9]+", "", brand.lower())
    if not name_tok or name_tok not in norm:
        return False
    if len(name_tok) < 4 and brand_tok not in norm:
        return False
    return True


def _usable_url(url: str) -> bool:
    parsed_host = (url.split("/")[2] if url.startswith("http") else "").lower()
    if any(host in parsed_host for host in SKIP_HOSTS):
        return False
    lowered = url.lower()
    if any(token in lowered for token in ("/search", "catalogsearch", "search?")):
        return False
    return True


def official_candidate_urls(brand: str, name: str) -> list[str]:
    """Manufacturer and retailer URL patterns. A miss is ignored; values are not invented."""
    import sys

    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import hermes_hp_enrich_firecrawl as hp

    urls = [url for url, _kind in hp.candidate_urls(brand, name)]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if brand == "Joranalogue":
        urls.insert(0, f"https://joranalogue.com/products/{slug}")
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen and _usable_url(url):
            seen.add(url)
            deduped.append(url)
    return deduped


def search_power_depth(scraper: CatalogScraper, target: dict[str, Any], *, fetch_cap: int = 6) -> dict[str, Any]:
    brand = target["brand"]
    name = target["name"]
    query = f"\"{brand}\" \"{name}\" eurorack power mA depth manual"
    searched = scraper.search(query, limit=5)
    candidates: list[str] = []
    seen: set[str] = set()
    for url in list(searched.urls) + official_candidate_urls(brand, name):
        if url in seen or not _usable_url(url):
            continue
        seen.add(url)
        candidates.append(url)
        if len(candidates) >= fetch_cap:
            break
    observations: list[dict[str, Any]] = []
    for url in candidates:
        result = scraper.fetch(url)
        if not result.ok or not result.text:
            continue
        if not page_mentions(result.text, brand, name):
            continue
        specs = parse_specs(result.text)
        if all(specs[key] is None for key in specs):
            continue
        observations.append({"source_url": url, **specs, "provenance": "OBSERVED"})
    merged: dict[str, Any] = {
        "module_id": target.get("module_id"),
        "brand": brand,
        "name": name,
        "power_12v_ma": None,
        "power_neg12v_ma": None,
        "power_5v_ma": None,
        "depth_mm": None,
        "sources": {},
        "status": "unresolved",
        "provenance": "NOT_COMPUTABLE",
        "conflicts": [],
    }
    for field in ("power_12v_ma", "power_neg12v_ma", "power_5v_ma", "depth_mm"):
        values = {obs[field] for obs in observations if obs[field] is not None}
        if len(values) == 1:
            merged[field] = next(iter(values))
            merged["sources"][field] = next(obs["source_url"] for obs in observations if obs[field] == merged[field])
        elif len(values) > 1:
            merged["conflicts"].append(field)
    if any(merged[field] is not None for field in ("power_12v_ma", "power_neg12v_ma", "power_5v_ma", "depth_mm")):
        merged["status"] = "found"
        merged["provenance"] = "OBSERVED"
    merged["candidate_urls"] = candidates
    merged["search_hit_count"] = len(searched.urls)
    return merged


def unresolved_power_targets() -> list[dict[str, Any]]:
    results = json.loads((CATALOG / "hermes-research" / "batch7-results.json").read_text(encoding="utf-8"))
    by_id = {row.get("module_id"): row for row in results.get("results") or []}
    targets = json.loads((CATALOG / "hermes-research" / "batch7-targets.json").read_text(encoding="utf-8"))
    pending = []
    for target in targets.get("power_depth") or []:
        row = by_id.get(target.get("module_id"))
        if row and row.get("status") == "found":
            continue
        pending.append(target)
    return pending


def run_batch8(scraper: CatalogScraper, *, fetch_cap: int = 6, limit: int = 0) -> dict[str, Any]:
    candidates = json.loads(
        (CATALOG / "overlays" / "catalog-new-brand-candidates-v1.json").read_text(encoding="utf-8")
    )
    rows = candidates.get("rows") or []
    if limit:
        rows = rows[:limit]
    known = load_catalog_slugs()
    verified_rows = [verify_candidate(scraper, row, known) for row in rows]
    targets = unresolved_power_targets()
    if limit:
        targets = targets[:limit]
    power_rows = [search_power_depth(scraper, target, fetch_cap=fetch_cap) for target in targets]
    brand_counts: dict[str, int] = {}
    for row in verified_rows:
        brand_counts[row["verification_status"]] = brand_counts.get(row["verification_status"], 0) + 1
    return {
        "batch": "batch8",
        "mode": "free-only" if scraper.max_paid_fetches == 0 else "paid",
        "max_paid_fetches": scraper.max_paid_fetches,
        "brand_verification": {
            "rows": verified_rows,
            "summary": {
                "candidates": len(verified_rows),
                "verified": brand_counts.get(VERIFIED, 0),
                "corrected": brand_counts.get(CORRECTED, 0),
                "flagged": brand_counts.get(FLAGGED, 0),
                "duplicates": sum(row["catalog_match"] == "duplicate" for row in verified_rows),
            },
        },
        "power_depth": {
            "rows": power_rows,
            "summary": {
                "targets": len(power_rows),
                "found": sum(row["status"] == "found" for row in power_rows),
                "unresolved": sum(row["status"] != "found" for row in power_rows),
            },
        },
    }
