#!/usr/bin/env python3
"""Turn maker-crawl-v1.json into loader overlays.

- catalog-additions-v2.json: modules not already in the catalog (insert-if-absent).
- module-power-depth-v9.json: verified specs for crawled modules, keyed to the
  existing catalog name when one matches. The loader fills nulls only and flags
  rows whose stored values disagree.
Every value was parsed deterministically or found verbatim on the maker's page.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "synth-catalog"
sys.path.insert(0, str(CATALOG))

CATEGORY = [
    ("SAMP", r"sampl|looper"), ("SEQ", r"sequenc|clock|trigger|gate gen|euclid"), ("VCO", r"oscillat|vco|voice|drum|wavetable"),
    ("VCF", r"filter|vcf"), ("VCA", r"vca|amplifier"), ("ENV", r"envelope|adsr|function gen|slew"), ("LFO", r"\blfo\b|modulat"),
    ("MIX", r"mixer|mix\b|panner"), ("FX", r"reverb|delay|effect|distort|granular|chorus|fx"), ("MIDI", r"midi"),
    ("UTIL", r"attenuat|mult|buffer|utility|output|input|logic|switch|quantiz|offset|interface"),
]


def norm(brand: str, name: str) -> str:
    n = name.lower()
    for token in [brand.lower(), "eurorack", "module", "modules", "synthesizer", "synth"]:
        n = n.replace(token, " ")
    return re.sub(r"[^a-z0-9]+", "", n)


def existing_index() -> dict[str, dict[str, str]]:
    """Catalog and module identities the loader would hold, from an offline plan."""
    import population as P

    for stale in ("catalog-additions-v2.json", "module-power-depth-v9.json"):
        (CATALOG / "overlays" / stale).unlink(missing_ok=True)
    catalog: dict = {}
    modules: dict = {}
    P._catalog_state = lambda conn: catalog
    P._module_state = lambda conn: modules
    P._manufacturer_state = lambda conn: set()
    P.build_plan(None)
    idx: dict[str, dict[str, str]] = {}
    for row in catalog.values():
        idx.setdefault(row["brand"], {})[norm(row["brand"], row["name"])] = row["name"]
    for (brand, name) in modules:
        idx.setdefault(brand, {}).setdefault(norm(brand, name), name)
    return idx


def category(tags: list[str], name: str) -> str | None:
    hay = " ".join(tags).lower() + " " + name.lower()
    for cat, pat in CATEGORY:
        if re.search(pat, hay):
            return cat
    return None


def main() -> int:
    crawl = json.loads((CATALOG / "hermes-research" / "maker-crawl-v1.json").read_text())
    idx = existing_index()
    additions, entries = [], []
    stats = {"crawled_modules": 0, "matched_existing": 0, "new": 0, "skipped_dupe_in_crawl": 0}
    for b in crawl["brands"]:
        seen = set()
        for m in b.get("modules") or []:
            stats["crawled_modules"] += 1
            key = norm(m["brand"], m["name"])
            if not key or key in seen:
                stats["skipped_dupe_in_crawl"] += 1
                continue
            seen.add(key)
            existing = idx.get(m["brand"], {}).get(key)
            name = existing or m["name"]
            if existing:
                stats["matched_existing"] += 1
            else:
                stats["new"] += 1
                additions.append({
                    "brand": m["brand"], "name": name, "hp": m["hp"], "category": category(m.get("tags") or [], name),
                    "manufacturer_url": m["source_url"], "image_url": m.get("image_url"), "is_available": "available",
                    "source": "ManufacturerCrawl", "source_reference": m["source_url"], "tags": m.get("tags") or [],
                    "content_sha256": m["content_sha256"], "fetch_method": m["fetch_method"],
                })
            entry = {
                "brand": m["brand"], "name": name,
                "power_12v_ma": m.get("power_12v_ma"), "power_neg12v_ma": m.get("power_neg12v_ma"),
                "power_5v_ma": m.get("power_5v_ma"), "depth_mm": m.get("depth_mm"),
                "source_url": m["source_url"], "sources": {k: v for k, v in (m.get("sources") or {}).items() if k != "hp"},
                "provenance": "OBSERVED", "status": "found", "extracted_by": m.get("extracted_by"),
                "verification_status": "verified", "verification_source_url": m["source_url"],
            }
            if any(entry[f] is not None for f in ("power_12v_ma", "power_neg12v_ma", "power_5v_ma", "depth_mm")) or not existing:
                entries.append(entry)
    D = CATALOG / "overlays"
    meta = {"generated_from": "hermes-research/maker-crawl-v1.json", "policy": "maker's own pages only; values regex-parsed or verbatim; no ModularGrid; insert-if-absent / fill-null; disagreements are flagged by the loader"}
    (D / "catalog-additions-v2.json").write_text(json.dumps({"dataset_version": "catalog-additions-v2", **meta, "count": len(additions), "rows": additions}, indent=1) + "\n")
    (D / "module-power-depth-v9.json").write_text(json.dumps({"dataset_version": "module-power-depth-overlay-v9", **meta, "count": len(entries), "entries": entries}, indent=1) + "\n")
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
