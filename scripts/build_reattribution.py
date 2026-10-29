#!/usr/bin/env python3
"""Retire catalog rows filed under the wrong brand, and re-add what only they held.

The v1 crawl sometimes gave one brand another maker's homepage ("Mental Noise" got
makenoisemusic.com), so the v2 crawl filed that maker's modules under both names.
`build_maker_overlays.misattributed_brands` names each such brand and its owner (None
when no brand owns the host: every brand there is retired).

Each run writes the next version (``--version N``), leaving out rows an earlier manifest
already retires, so applied manifests never change:
- overlays/catalog-retirements-vN.json: the rows to tombstone (never delete).
- catalog-additions and module-power-depth overlays (the next free numbers): modules that
  exist only under a misattributed brand, filed under their owner, from the owner's own
  pages, built the same way build_maker_overlays builds rows. A host with no owner (a
  retailer) re-adds nothing.

v1 (2026-10-28, #116) is frozen as applied: it used the name-only owner rule, before
"&" was read as "and", so rebuilding it now would differ. v2 adds the crawler's rule from
spec 003 T030: an adapter- or curated-resolved brand owns a host no name matches.

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
# Manifest version -> the catalog-additions and module-power-depth versions it writes.
OUTPUT_VERSIONS = {1: (5, 13), 2: (6, 14)}

# Owner review (overlays/maker-review-v1.json): this row predates the review rename (v1).
REVIEWED = [{
    "slug": "tlm-audio-st-modular", "brand": "TLM Audio", "name": "ST MODULAR",
    "reason": "not a module: ST MODULAR is TLM's product-line prefix, and the page is the 84 HP LANGER ARM expansion",
    "evidence_url": "https://www.tlm-audio.com/product-page/st-modular-langer-arm-1u-3u-expansion",
}]


def outputs(version: int) -> tuple[Path, Path, Path]:
    additions, power = OUTPUT_VERSIONS[version]
    return (
        OVERLAYS / f"catalog-retirements-v{version}.json",
        OVERLAYS / f"catalog-additions-v{additions}.json",
        OVERLAYS / f"module-power-depth-v{power}.json",
    )


def planned_catalog(version: int) -> dict:
    """Catalog rows the loader would hold without this version's outputs."""
    import population as P

    for path in outputs(version):
        path.unlink(missing_ok=True)
    catalog: dict = {}
    P._catalog_state = lambda conn: catalog
    P._module_state = lambda conn: {}
    P._manufacturer_state = lambda conn: set()
    P.build_plan(None)
    return catalog


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, default=max(OUTPUT_VERSIONS))
    ap.add_argument("--rebuild", action="store_true", help="rewrite a manifest that already exists")
    args = ap.parse_args(argv)
    version = args.version
    retirements_path, additions_path, power_path = outputs(version)
    if retirements_path.is_file() and not args.rebuild:
        print(f"{retirements_path.name} exists; an applied manifest never changes (use --rebuild only before it is loaded)", file=sys.stderr)
        return 2
    additions_version = OUTPUT_VERSIONS[version][0]

    crawl = json.loads((CATALOG / "hermes-research" / CRAWL).read_text())
    shared = B.shared_homepage_skips(crawl["brands"]) if version == 1 else B.misattributed_brands(crawl["brands"])
    already = {
        r["slug"]
        for n in range(1, version)
        if (path := OVERLAYS / f"catalog-retirements-v{n}.json").is_file()
        for r in json.loads(path.read_text())["rows"]
    }
    catalog = planned_catalog(version)
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
    hosts = {b["brand"]: b.get("homepage") for b in crawl["brands"]}
    for slug in sorted(catalog):
        row = catalog[slug]
        if row["brand"] not in shared or slug in already:
            continue
        owner = shared[row["brand"]]
        page = pages.get((row["brand"], B.norm(row["brand"], row["name"]))) or {}
        entry = {
            "slug": slug, "brand": row["brand"], "name": row["name"],
            "owner": owner,
            "evidence_url": page.get("source_url") or added_urls.get((row["brand"], row["name"])),
        }
        if owner is None:
            entry["reason"] = f"filed under the wrong brand: {hosts.get(row['brand'])} is not {row['brand']}'s site"
            entry["kept_as"] = "not re-added: no maker owns that host"
            retirements.append(entry)
            continue
        entry["reason"] = f"filed under the wrong brand: the crawl gave {row['brand']} {owner}'s homepage"
        clean = B.clean_name(owner, row["name"])
        key = B.norm(owner, clean)
        if key in owner_keys.get(owner, set()):
            entry["kept_as"] = "existing row under owner"
        elif not page:
            entry["kept_as"] = "not re-added: no page for it in the current crawl"
        else:
            entry["kept_as"] = f"re-added under owner (catalog-additions-v{additions_version})"
            readd.setdefault(key, {**page, "brand": owner, "name": clean})
        retirements.append(entry)
    if version == 1:
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
        "decided": (
            "2026-10-28 (owner: retire every misattributed row and re-add the modules only they held)"
            if version == 1
            else "2026-10-28 (owner: retire the misattributed brands spec 003 T030 found, the same way)"
        ),
    }
    retirements_path.write_text(json.dumps({
        "dataset_version": f"catalog-retirements-v{version}", **meta,
        "policy": "tombstone, never delete: module_catalog.tombstoned_at + reason, modules.status='tombstoned'",
        "shared_homepages": dict(sorted(shared.items())),
        "count": len(retirements), "rows": retirements,
    }, indent=1, ensure_ascii=False) + "\n")
    policy = "maker's own pages only; values regex-parsed or verbatim; insert-if-absent / fill-null"
    if not additions:
        print(json.dumps({"retired": len(retirements), "readded": 0, "shared_homepages": len(shared)}))
        return 0
    additions_path.write_text(json.dumps({
        "dataset_version": f"catalog-additions-v{additions_version}", **meta, "policy": policy,
        "count": len(additions), "rows": additions,
    }, indent=1, ensure_ascii=False) + "\n")
    power_path.write_text(json.dumps({
        "dataset_version": f"module-power-depth-overlay-v{OUTPUT_VERSIONS[version][1]}", **meta, "policy": policy,
        "count": len(entries), "entries": entries,
    }, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"retired": len(retirements), "readded": len(additions), "shared_homepages": len(shared)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
