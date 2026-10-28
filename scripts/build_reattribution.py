#!/usr/bin/env python3
"""Retire catalog rows filed under the wrong brand, and re-add what only they held.

The v1 crawl sometimes gave one brand another maker's homepage ("Mental Noise" got
makenoisemusic.com), so the v2 crawl filed that maker's modules under both names.
`build_maker_overlays.shared_homepage_skips` names each such brand and its owner.

Writes:
- overlays/catalog-retirements-v1.json: every row the loader would hold under a
  misattributed brand, plus the owner-reviewed TLM "ST MODULAR" row. The loader
  tombstones them (never deletes).
- overlays/catalog-additions-v5.json and overlays/module-power-depth-v13.json: the
  modules that exist only under a misattributed brand, filed under their owner, built
  from the same maker pages the same way build_maker_overlays builds rows.

Built from the committed crawl; no fetches.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "synth-catalog"
OVERLAYS = CATALOG / "overlays"
sys.path.insert(0, str(CATALOG))
sys.path.insert(0, str(ROOT / "scripts"))

import build_maker_overlays as B  # noqa: E402

CRAWL = "maker-crawl-v2.json"
RETIREMENTS = OVERLAYS / "catalog-retirements-v1.json"
ADDITIONS = OVERLAYS / "catalog-additions-v5.json"
POWER = OVERLAYS / "module-power-depth-v13.json"

# Owner review (overlays/maker-review-v1.json): this row predates the review rename.
REVIEWED = [{
    "slug": "tlm-audio-st-modular", "brand": "TLM Audio", "name": "ST MODULAR",
    "reason": "not a module: ST MODULAR is TLM's product-line prefix, and the page is the 84 HP LANGER ARM expansion",
    "evidence_url": "https://www.tlm-audio.com/product-page/st-modular-langer-arm-1u-3u-expansion",
}]


def planned_catalog() -> dict:
    """Catalog rows the loader would hold without this script's outputs."""
    import population as P

    for path in (RETIREMENTS, ADDITIONS, POWER):
        path.unlink(missing_ok=True)
    catalog: dict = {}
    P._catalog_state = lambda conn: catalog
    P._module_state = lambda conn: {}
    P._manufacturer_state = lambda conn: set()
    P.build_plan(None)
    return catalog


def main() -> int:
    crawl = json.loads((CATALOG / "hermes-research" / CRAWL).read_text())
    shared = B.shared_homepage_skips(crawl["brands"])
    catalog = planned_catalog()
    pages: dict[tuple[str, str], dict] = {}
    for b in crawl["brands"]:
        if b["brand"] in shared:
            for m in b.get("modules") or []:
                pages.setdefault((m["brand"], B.norm(m["brand"], B.clean_name(m["brand"], m["name"]))), m)

    # Rows an earlier crawl added: their own maker URL is the evidence when v2 has no page.
    added_urls = {
        (r["brand"], r["name"]): r.get("manufacturer_url")
        for path in sorted(OVERLAYS.glob("catalog-additions-v*.json"))
        for r in json.loads(path.read_text()).get("rows") or []
    }

    owner_keys: dict[str, set[str]] = {}
    for row in catalog.values():
        owner_keys.setdefault(row["brand"], set()).add(B.norm(row["brand"], row["name"]))

    retirements, readd = [], {}
    for slug in sorted(catalog):
        row = catalog[slug]
        owner = shared.get(row["brand"])
        if owner is None:
            continue
        clean = B.clean_name(owner, row["name"])
        key = B.norm(owner, clean)
        page = pages.get((row["brand"], B.norm(row["brand"], row["name"]))) or {}
        entry = {
            "slug": slug, "brand": row["brand"], "name": row["name"],
            "reason": f"filed under the wrong brand: the crawl gave {row['brand']} {owner}'s homepage",
            "owner": owner,
            "evidence_url": page.get("source_url") or added_urls.get((row["brand"], row["name"])),
        }
        if key in owner_keys.get(owner, set()):
            entry["kept_as"] = "existing row under owner"
        else:
            entry["kept_as"] = "re-added under owner (catalog-additions-v5)"
            if page and key not in readd:
                readd[key] = {**page, "brand": owner, "name": clean}
        retirements.append(entry)
    retirements += REVIEWED

    additions, entries = [], []
    for key in sorted(readd):
        m = readd[key]
        additions.append({
            "brand": m["brand"], "name": m["name"], "hp": m["hp"], "category": B.category(m.get("tags") or [], m["name"]),
            "manufacturer_url": m["source_url"], "image_url": m.get("image_url"), "is_available": "available",
            "source": "ManufacturerCrawl", "source_reference": m["source_url"], "tags": m.get("tags") or [],
            "access_basis": "official_publication",
            "content_sha256": m["content_sha256"], "fetch_method": m["fetch_method"],
        })
        entries.append({
            "brand": m["brand"], "name": m["name"],
            "power_12v_ma": m.get("power_12v_ma"), "power_neg12v_ma": m.get("power_neg12v_ma"),
            "power_5v_ma": m.get("power_5v_ma"), "depth_mm": m.get("depth_mm"),
            "source_url": m["source_url"], "sources": {k: v for k, v in (m.get("sources") or {}).items() if k != "hp"},
            "provenance": "OBSERVED", "status": "found", "extracted_by": m.get("extracted_by"),
            "verification_status": "verified", "verification_source_url": m["source_url"],
        })

    meta = {
        "generated_from": f"hermes-research/{CRAWL} via scripts/build_reattribution.py",
        "decided": "2026-10-28 (owner: retire every misattributed row and re-add the modules only they held)",
    }
    RETIREMENTS.write_text(json.dumps({
        "dataset_version": "catalog-retirements-v1", **meta,
        "policy": "tombstone, never delete: module_catalog.tombstoned_at + reason, modules.status='tombstoned'",
        "shared_homepages": dict(sorted(shared.items())),
        "count": len(retirements), "rows": retirements,
    }, indent=1, ensure_ascii=False) + "\n")
    policy = "maker's own pages only; values regex-parsed or verbatim; insert-if-absent / fill-null"
    ADDITIONS.write_text(json.dumps({
        "dataset_version": "catalog-additions-v5", **meta, "policy": policy,
        "count": len(additions), "rows": additions,
    }, indent=1, ensure_ascii=False) + "\n")
    POWER.write_text(json.dumps({
        "dataset_version": "module-power-depth-overlay-v13", **meta, "policy": policy,
        "count": len(entries), "entries": entries,
    }, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"retired": len(retirements), "readded": len(additions), "shared_homepages": len(shared)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
