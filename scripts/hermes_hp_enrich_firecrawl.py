#!/usr/bin/env python3
"""HP enrichment via Firecrawl scrape of official/retailer product pages.

Hermes research pipeline (batch mode). Never invents HP. Prefer OBSERVED
official manufacturer pages, then Perfect Circuit / Thomann.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_SCRAPE = "https://api.firecrawl.dev/v1/scrape"

SOURCE_AUTHORITY_BY_CLASS = {
    "official": "MANUFACTURER_PRIMARY",
    "retailer": "RETAILER_DISTRIBUTOR",
    "modulargrid": "COMMUNITY_CATALOG",
}

HP_PATTERNS = [
    re.compile(r"\b(\d{1,2})\s*[Hh][Pp]\b"),
    re.compile(r"\b[Ww]idth\s*[:\-]?\s*(\d{1,2})\s*[Hh][Pp]\b"),
    re.compile(r"\b[Hh][Pp]\s*[:\-]?\s*(\d{1,2})\b"),
]


def _key() -> str:
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not key:
        raise SystemExit("FIRECRAWL_API_KEY required (source ~/.hermes/.env)")
    return key


def scrape_markdown(url: str, timeout: int = 60) -> str:
    body = json.dumps(
        {"url": url, "formats": ["markdown"], "onlyMainContent": True}
    ).encode()
    req = urllib.request.Request(
        API_SCRAPE,
        data=body,
        headers={
            "Authorization": f"Bearer {_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"  scrape fail {url}: {e}")
        return ""
    payload = data.get("data") or {}
    return payload.get("markdown") or payload.get("content") or ""


def extract_hp(text: str) -> int | None:
    for pat in HP_PATTERNS:
        m = pat.search(text or "")
        if not m:
            continue
        try:
            hp = int(m.group(1))
        except ValueError:
            continue
        if 1 <= hp <= 104:
            return hp
    return None


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def candidate_urls(brand: str, name: str) -> list[tuple[str, str]]:
    """Return (url, provenance_class) candidates. provenance_class: official|retailer.

    Never use search-result pages (they mis-extract HP). Prefer official product pages,
    then Perfect Circuit / Thomann product detail URL patterns only.
    """
    n = slugify(name)
    urls: list[tuple[str, str]] = []

    if brand == "Make Noise":
        urls.append((f"https://www.makenoisemusic.com/modules/{n}", "official"))
    elif brand == "Mutable Instruments":
        base = re.sub(r"-\d{4}.*$", "", n)
        base = base.replace("tides-2014-version", "tides")
        urls.append((f"https://mutable-instruments.net/modules/{base}/", "official"))
        urls.append((f"https://mutable-instruments.net/modules/{n}/", "official"))
    elif brand == "Intellijel":
        urls.append((f"https://intellijel.com/shop/eurorack/{n}/", "official"))
        urls.append((f"https://intellijel.com/shop/1u/{n}/", "official"))
        # strip trailing 1u from path variants
        if n.endswith("-1u"):
            urls.append((f"https://intellijel.com/shop/1u/{n[:-3]}/", "official"))
    elif brand == "Acid Rain Technology":
        urls.append((f"https://acidraintechnology.com/products/{n}", "official"))
    elif brand == "Instruo":
        # Unicode-heavy names → try common product slugs
        ascii_map = {
            "lubadh": "lubadh",
            "lúbadh": "lubadh",
            "dha": "dha",
            "dhà": "dha",
            "dail": "dail",
            "dàil": "dail",
            "ceis-2": "ceis",
            "cèis-2": "ceis",
            "ochd": "ochd",
            "øchd": "ochd",
            "gloc": "gloc",
            "ire": "ire",
            "íre": "ire",
            "arbhar": "arbhar",
            "seashell": "seashell",
        }
        for key, slug in ascii_map.items():
            if key in name.lower() or key in n:
                urls.append((f"https://www.instruomodular.com/product/{slug}/", "official"))
        urls.append((f"https://www.instruomodular.com/product/{n}/", "official"))
    elif brand == "Noise Engineering":
        urls.append((f"https://noiseengineering.us/products/{n}", "official"))
    elif brand == "Erica Synths":
        urls.append((f"https://www.ericasynths.lv/shop/eurorack-modules/{n}/", "official"))
        urls.append((f"https://www.ericasynths.lv/shop/desktop-devices/{n}/", "official"))
        # black / pico series often under path without full slug
        short = n.replace("black-", "").replace("pico-", "pico-")
        urls.append((f"https://www.ericasynths.lv/shop/eurorack-modules/{short}/", "official"))
    elif brand == "Befaco":
        urls.append((f"https://www.befaco.org/en/{n}/", "official"))
        urls.append((f"https://www.befaco.org/{n}/", "official"))
        urls.append((f"https://www.befaco.org/en/{n.replace('-', '')}/", "official"))
    elif brand == "Doepfer":
        # A-110-1 -> a1101 / a110_1 / a110
        raw = name.strip().upper()
        m = re.match(r"A-?(\d+)(?:-(\d+))?", raw)
        if m:
            a, b = m.group(1), m.group(2)
            if b:
                urls.append((f"https://doepfer.de/a{a}{b}.htm", "official"))
                urls.append((f"https://doepfer.de/a{a}_{b}.htm", "official"))
            urls.append((f"https://doepfer.de/a{a}.htm", "official"))
            urls.append((f"https://doepfer.de/a{a}.htm", "official"))
        urls.append((f"https://doepfer.de/{n}.htm", "official"))
        urls.append((f"https://doepfer.de/{n.replace('-', '')}.htm", "official"))
    elif brand == "Expert Sleepers":
        urls.append((f"https://www.expert-sleepers.co.uk/{n}.html", "official"))
        urls.append((f"https://expert-sleepers.co.uk/{n}.html", "official"))
        # Disting / FH often camel
        urls.append((f"https://www.expert-sleepers.co.uk/{name.replace(' ', '')}.html", "official"))
    elif brand == "ALM Busy Circuits":
        urls.append((f"https://busycircuits.com/{n}/", "official"))
        urls.append((f"https://busycircuits.com/alm{n}/", "official"))
    elif brand == "Xaoc Devices":
        urls.append((f"https://xaocdevices.com/main/modules/{n}/", "official"))
        urls.append((f"https://xaocdevices.com/products/{n}", "official"))
    elif brand == "ADDAC System":
        # ADDAC101 .WAV Player -> addac101
        m = re.search(r"addac\s*(\d+)", name, re.I)
        if m:
            code = f"addac{m.group(1)}"
            urls.append((f"https://www.addacsystem.com/en/products/{code}", "official"))
            urls.append((f"https://www.addacsystem.com/product/{code}", "official"))
        urls.append((f"https://www.addacsystem.com/en/products/{n}", "official"))
    elif brand == "Bastl Instruments":
        urls.append((f"https://bastl-instruments.com/eurorack/modules/{n}", "official"))
        urls.append((f"https://bastl-instruments.com/eurorack/{n}", "official"))
    elif brand == "Endorphin.es":
        urls.append((f"https://www.endorphin.es/modules/{n}", "official"))
        urls.append((f"https://www.endorphin.es/products/{n}", "official"))
    elif brand == "Dreadbox":
        urls.append((f"https://www.dreadbox-fx.com/product/{n}/", "official"))
        urls.append((f"https://www.dreadbox-fx.com/{n}/", "official"))
    elif brand == "Cwejman":
        urls.append((f"https://cwejman.net/{n}/", "official"))
        urls.append((f"https://www.cwejman.com/{n}", "official"))

    # Perfect Circuit product detail patterns only (no catalogsearch)
    brand_slug = slugify(brand)
    # common PC patterns
    urls.append((f"https://www.perfectcircuit.com/{brand_slug}-{n}.html", "retailer"))
    urls.append((f"https://www.perfectcircuit.com/{n}.html", "retailer"))
    if brand == "Make Noise":
        urls.append((f"https://www.perfectcircuit.com/make-noise-{n}.html", "retailer"))
    if brand == "Intellijel":
        urls.append((f"https://www.perfectcircuit.com/intellijel-{n}.html", "retailer"))
    if brand == "Erica Synths":
        urls.append((f"https://www.perfectcircuit.com/erica-synths-{n}.html", "retailer"))
    if brand == "Doepfer":
        urls.append((f"https://www.perfectcircuit.com/doepfer-{n}.html", "retailer"))
    if brand == "Bastl Instruments":
        urls.append((f"https://www.perfectcircuit.com/bastl-{n}.html", "retailer"))
    if brand == "Befaco":
        urls.append((f"https://www.perfectcircuit.com/befaco-{n}.html", "retailer"))
    if brand == "ADDAC System":
        m = re.search(r"addac\s*(\d+)", name, re.I)
        if m:
            urls.append(
                (f"https://www.perfectcircuit.com/addac-system-addac{m.group(1)}.html", "retailer")
            )
    if brand == "Expert Sleepers":
        urls.append((f"https://www.perfectcircuit.com/expert-sleepers-{n}.html", "retailer"))
    if brand == "Endorphin.es":
        urls.append((f"https://www.perfectcircuit.com/endorphin-es-{n}.html", "retailer"))
    if brand == "Dreadbox":
        urls.append((f"https://www.perfectcircuit.com/dreadbox-{n}.html", "retailer"))
    if brand == "Acid Rain Technology":
        urls.append((f"https://www.perfectcircuit.com/acid-rain-{n}.html", "retailer"))
    if brand == "Instruo":
        urls.append((f"https://www.perfectcircuit.com/instruo-{n}.html", "retailer"))

    # de-dupe preserve order
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for url, kind in urls:
        if url in seen:
            continue
        seen.add(url)
        out.append((url, kind))
    return out


def process_one(target: dict, sleep_s: float) -> dict:
    brand = target["brand"]
    name = target["name"]
    slug = target["slug"]
    print(f"→ {brand} / {name}", flush=True)

    # Cap attempts so long batches finish (official first, then retailer product pages)
    for url, kind in candidate_urls(brand, name)[:6]:
        md = scrape_markdown(url)
        time.sleep(sleep_s)
        if not md or len(md) < 80:
            continue
        # Reject search pages if any slip through
        if "catalogsearch" in url or "search_dir.html" in url or "/search?" in url:
            continue
        # Product pages should mention the module (or brand for single-product pages)
        token = re.sub(r"[^a-z0-9]+", "", name.lower())[:8]
        md_norm = re.sub(r"[^a-z0-9]+", "", md.lower())
        if token and token not in md_norm and slugify(name).replace("-", "")[:8] not in md_norm:
            # still allow short official pages that use different spelling
            if kind == "retailer":
                continue
        hp = extract_hp(md)
        if hp is None:
            continue
        # Fail-closed module width band (1U tiles can be 2–28; 3U modules rarely >42)
        if hp < 1 or hp > 42:
            continue
        return {
            "brand": brand,
            "name": name,
            "slug": slug,
            "hp": hp,
            "source_url": url,
            # OBSERVED means observed in the cited source, not canonical truth.
            "provenance": "OBSERVED",
            "epistemic_status": "OBSERVED",
            "source_authority": SOURCE_AUTHORITY_BY_CLASS.get(kind, "UNKNOWN_SOURCE_AUTHORITY"),
            "admission_status": "EVIDENCE_ONLY",
            "rights_status": "RIGHTS_UNKNOWN",
            "status": "found",
            "notes": f"source_class={kind}",
        }

    return {
        "brand": brand,
        "name": name,
        "slug": slug,
        "hp": None,
        "source_url": None,
        "provenance": "NOT_COMPUTABLE",
        "epistemic_status": "NOT_COMPUTABLE",
        "source_authority": "UNKNOWN_SOURCE_AUTHORITY",
        "admission_status": "EVIDENCE_ONLY",
        "rights_status": "RIGHTS_UNKNOWN",
        "status": "not_found",
        "notes": "no HP on candidate official/retailer URLs",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--targets",
        type=Path,
        default=Path("data/synth-catalog/hermes-research/hp-enrichment-batch1.json"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(
            "data/synth-catalog/hermes-research/hp-enrichment-batch1-results.json"
        ),
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sleep", type=float, default=0.35)
    parser.add_argument("--resume", action="store_true", help="Skip slugs already in out file")
    args = parser.parse_args(argv)

    payload = json.loads(args.targets.read_text(encoding="utf-8"))
    targets = list(payload.get("targets") or [])
    if args.limit:
        targets = targets[: args.limit]

    done: dict[str, dict] = {}
    if args.resume and args.out.is_file():
        prev = json.loads(args.out.read_text(encoding="utf-8"))
        for r in prev.get("results") or []:
            if r.get("slug"):
                done[r["slug"]] = r
        print(f"resume: {len(done)} already done")

    results: list[dict[str, Any]] = []
    for t in targets:
        slug = t.get("slug")
        if slug in done:
            results.append(done[slug])
            continue
        r = process_one(t, args.sleep)
        results.append(r)
        print(
            f"  {r['status']} hp={r.get('hp')} {r.get('source_url')}",
            flush=True,
        )
        # checkpoint after each
        found = sum(1 for x in results if x.get("status") == "found" and x.get("hp"))
        out = {
            "batch": payload.get("batch", 1),
            "generated_by": "hermes-firecrawl-scrape-pipeline",
            "results": results + [done[s] for s in done if s not in {x.get('slug') for x in results}],
            "summary": {
                "targets": len(targets),
                "processed": len(results),
                "found": found,
                "not_found": len(results) - found,
            },
        }
        # simplify: just write current results list (resume map handled above)
        out["results"] = results
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    found = sum(1 for r in results if r.get("status") == "found" and r.get("hp"))
    print(
        json.dumps(
            {"targets": len(results), "found": found, "not_found": len(results) - found},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
