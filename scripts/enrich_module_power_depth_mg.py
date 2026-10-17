#!/usr/bin/env python3
"""OBSERVED power/depth enrichment for modules via ModularGrid direct HTTP.

Fill-null only when applying. Never invents rails or depth.
Firecrawl-independent (credits may be 0).
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

MG_BRAND = {
    "ADDAC System": "addac-system",
    "Acid Rain Technology": "acid-rain-technology",
    "Bastl Instruments": "bastl-instruments",
    "Endorphin.es": "endorphin-es",
    "Erica Synths": "erica-synths",
    "Expert Sleepers": "expert-sleepers",
    "Mutable Instruments": "mutable-instruments",
    "Make Noise": "make-noise",
    "ALM Busy Circuits": "alm-busy-circuits",
    "Noise Engineering": "noise-engineering",
    "TipTop Audio": "tiptop-audio",
    "Tiptop Audio": "tiptop-audio",
}


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def mg_brand_slug(brand: str) -> str:
    return MG_BRAND.get(brand) or slugify(brand)


def fetch(url: str, timeout: int = 25) -> str:
    import os
    import sys

    root = Path(__file__).resolve().parents[1]
    catalog = str(root / "data" / "synth-catalog")
    if catalog not in sys.path:
        sys.path.insert(0, catalog)
    from catalog_scrape import CatalogScraper

    scraper = getattr(fetch, "_scraper", None)
    if scraper is None:
        scraper = CatalogScraper.for_repo(max_paid_fetches=int(os.environ.get("PATCHHIVE_MAX_PAID_FETCHES", "0")))
        fetch._scraper = scraper
    result = scraper.fetch(url, timeout=timeout)
    return result.text or ""


def html_to_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def extract_power_depth(html: str) -> dict[str, Any]:
    """Parse ModularGrid-style Dimensions + Current Draw blocks."""
    text = html_to_text(html or "")
    out: dict[str, Any] = {
        "power_12v_ma": None,
        "power_neg12v_ma": None,
        "power_5v_ma": None,
        "depth_mm": None,
        "hp": None,
    }
    # "50 mA +12V 5 mA -12V 0 mA 5V"
    m = re.search(
        r"(\d+)\s*mA\s*\+\s*12V\s+(\d+)\s*mA\s*-\s*12V\s+(\d+)\s*mA\s*5V",
        text,
        re.I,
    )
    if m:
        out["power_12v_ma"] = int(m.group(1))
        out["power_neg12v_ma"] = int(m.group(2))
        out["power_5v_ma"] = int(m.group(3))
    else:
        m12 = re.search(r"(\d+)\s*mA\s*\+\s*12V", text, re.I)
        mn12 = re.search(r"(\d+)\s*mA\s*-\s*12V", text, re.I)
        m5 = re.search(r"(\d+)\s*mA\s*5V", text, re.I)
        if m12:
            out["power_12v_ma"] = int(m12.group(1))
        if mn12:
            out["power_neg12v_ma"] = int(mn12.group(1))
        if m5:
            out["power_5v_ma"] = int(m5.group(1))

    m = re.search(r"(\d+)\s*HP\s+(\d+(?:\.\d+)?)\s*mm\s*deep", text, re.I)
    if m:
        out["hp"] = int(m.group(1))
        out["depth_mm"] = float(m.group(2))
    else:
        m = re.search(r"Dimensions\s+(\d+)\s*HP", text, re.I)
        if m:
            out["hp"] = int(m.group(1))
        m = re.search(r"(\d+(?:\.\d+)?)\s*mm\s*deep", text, re.I)
        if m:
            out["depth_mm"] = float(m.group(1))
    return out


def candidate_urls(
    brand: str,
    name: str,
    catalog_slug: str | None = None,
    alt_slugs: list[str] | None = None,
) -> list[str]:
    n = slugify(name)
    mb = mg_brand_slug(brand)
    urls: list[str] = []
    for s in alt_slugs or []:
        if s:
            urls.append(f"https://modulargrid.net/e/{s}")
    if catalog_slug:
        urls.append(f"https://modulargrid.net/e/{catalog_slug}")
    urls.append(f"https://modulargrid.net/e/{mb}-{n}")
    # unicode µ → u
    if "µ" in name or "μ" in name:
        alt = slugify(name.replace("µ", "u").replace("μ", "u"))
        urls.append(f"https://modulargrid.net/e/{mb}-{alt}")
        urls.append(f"https://modulargrid.net/e/{mb}-%C2%B5{n.lstrip('u').lstrip('-')}")
    if brand == "Doepfer":
        m = re.match(r"A-?(\d+)(?:-(\d+))?", name.strip(), re.I)
        if m:
            a, b = m.group(1), m.group(2)
            if b:
                urls.append(f"https://modulargrid.net/e/doepfer-a-{a}-{b}")
                urls.append(f"https://modulargrid.net/e/doepfer-a-{a}-{b}-")
            urls.append(f"https://modulargrid.net/e/doepfer-a-{a}")
    # de-dupe
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def process_one(target: dict[str, Any], sleep_s: float) -> dict[str, Any]:
    brand = target["brand"]
    name = target["name"]
    slug = target.get("catalog_slug") or target.get("slug")
    mid = target.get("module_id")
    print(f"→ [{mid}] {brand} / {name}", flush=True)

    alts = target.get("alt_slugs") or []
    for url in candidate_urls(brand, name, catalog_slug=slug, alt_slugs=alts)[:10]:
        html = fetch(url)
        time.sleep(sleep_s)
        if not html or len(html) < 300:
            continue
        # light name presence for MG
        token = re.sub(r"[^a-z0-9]+", "", name.lower())[:5]
        if token and token not in re.sub(r"[^a-z0-9]+", "", html.lower()):
            # Doepfer numeric ok
            if brand == "Doepfer":
                m = re.match(r"A-?(\d+)", name, re.I)
                if m and m.group(1) not in html:
                    continue
            else:
                continue
        fields = extract_power_depth(html)
        if fields["power_12v_ma"] is None and fields["depth_mm"] is None:
            continue
        # require Dimensions-ish page
        if "Dimensions" not in html and "Current" not in html and "mA" not in html:
            continue
        return {
            "module_id": mid,
            "brand": brand,
            "name": name,
            "catalog_slug": slug,
            "source_url": url,
            "power_12v_ma": fields["power_12v_ma"],
            "power_neg12v_ma": fields["power_neg12v_ma"],
            "power_5v_ma": fields["power_5v_ma"],
            "depth_mm": fields["depth_mm"],
            "hp_observed": fields["hp"],
            "status": "found",
            "provenance": "OBSERVED",
            "notes": "source_class=modulargrid;method=direct_http;power_depth",
        }

    return {
        "module_id": mid,
        "brand": brand,
        "name": name,
        "catalog_slug": slug,
        "status": "not_found",
        "provenance": "NOT_COMPUTABLE",
        "notes": "no power/depth via MG candidates",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)

    payload = json.loads(args.targets.read_text(encoding="utf-8"))
    targets = list(payload.get("targets") or [])
    if args.limit:
        targets = targets[: args.limit]

    done: dict[str, dict] = {}
    if args.resume and args.out.is_file():
        prev = json.loads(args.out.read_text(encoding="utf-8"))
        for r in prev.get("results") or []:
            key = str(r.get("module_id") or r.get("catalog_slug") or "")
            if key:
                done[key] = r
        print(f"resume: {len(done)} already done", flush=True)

    results: list[dict[str, Any]] = []
    for t in targets:
        key = str(t.get("module_id") or t.get("catalog_slug") or "")
        if key in done:
            results.append(done[key])
            continue
        r = process_one(t, args.sleep)
        results.append(r)
        print(
            f"  {r['status']} p12={r.get('power_12v_ma')} depth={r.get('depth_mm')} {r.get('source_url')}",
            flush=True,
        )
        found = sum(1 for x in results if x.get("status") == "found")
        out = {
            "batch": payload.get("batch", "power-depth"),
            "generated_by": "enrich-module-power-depth-mg",
            "results": results,
            "summary": {
                "targets": len(targets),
                "processed": len(results),
                "found": found,
                "not_found": len(results) - found,
            },
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    found = sum(1 for r in results if r.get("status") == "found")
    print(
        json.dumps(
            {"targets": len(results), "found": found, "not_found": len(results) - found},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
