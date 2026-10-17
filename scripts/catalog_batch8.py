#!/usr/bin/env python3
"""Batch 8 brand verification and power/depth search.

Free HTTP unless --max-paid-fetches is greater than zero. Keys are read from
FIRECRAWL_API_KEY and CONTEXT_DEV_API_KEY at run time and are never printed.

Paid run on a machine that already has those keys:

  python scripts/catalog_batch8.py --max-paid-fetches 200
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

from batch8 import (  # noqa: E402
    CATALOG,
    load_catalog_slugs,
    search_power_depth,
    unresolved_power_targets,
    verify_candidate,
)
from catalog_scrape import RECEIPT_KEYS, CatalogScraper  # noqa: E402


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-paid-fetches", type=int, default=0)
    parser.add_argument("--fetch-cap", type=int, default=6)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)

    scraper = CatalogScraper.for_repo(max_paid_fetches=args.max_paid_fetches, min_interval_s=1.0)
    brand_path = CATALOG / "hermes-research" / "batch8-brand-verification.json"
    power_path = CATALOG / "hermes-research" / "batch8-power-depth.json"
    receipt_path = CATALOG / "receipts" / "batch8-router-receipts.json"
    summary_path = CATALOG / "receipts" / "batch8-summary.json"

    candidates = json.loads((CATALOG / "overlays" / "catalog-new-brand-candidates-v1.json").read_text())
    known = load_catalog_slugs()
    done: dict[str, dict] = {}
    if args.resume and brand_path.is_file():
        prev = json.loads(brand_path.read_text(encoding="utf-8"))
        for row in prev.get("rows") or []:
            if row.get("source_url"):
                done[row["source_url"]] = row

    rows = []
    for index, candidate in enumerate(candidates.get("rows") or [], start=1):
        source = candidate.get("source_url")
        if source in done:
            rows.append(done[source])
            continue
        rows.append(verify_candidate(scraper, candidate, known))
        if index % 10 == 0:
            _write(brand_path, {"batch": "batch8", "complete": False, "rows": rows})
            print(f"brands {index}/{len(candidates['rows'])}", flush=True)
    _write(brand_path, {"batch": "batch8", "complete": True, "rows": rows})

    power_done: dict[int, dict] = {}
    if args.resume and power_path.is_file():
        prev = json.loads(power_path.read_text(encoding="utf-8"))
        for row in prev.get("rows") or []:
            if row.get("module_id") is not None:
                power_done[row["module_id"]] = row
    power_rows = []
    targets = unresolved_power_targets()
    for target in targets:
        mid = target.get("module_id")
        if mid in power_done:
            power_rows.append(power_done[mid])
            continue
        power_rows.append(search_power_depth(scraper, target, fetch_cap=args.fetch_cap))
        _write(power_path, {"batch": "batch8", "complete": False, "rows": power_rows})
        print(f"power {target.get('brand')} / {target.get('name')} -> {power_rows[-1]['status']}", flush=True)
    _write(power_path, {"batch": "batch8", "complete": True, "rows": power_rows})

    public_receipts = [
        {key: item.get(key) for key in RECEIPT_KEYS} | {"credits": item.get("credits", 0), "note": item.get("note")}
        for item in scraper.receipts
    ]
    if args.resume and receipt_path.is_file():
        previous = json.loads(receipt_path.read_text(encoding="utf-8"))
        if isinstance(previous, list):
            public_receipts = previous + public_receipts
    _write(receipt_path, public_receipts)

    found = [row for row in power_rows if row.get("status") == "found"]
    if found:
        overlay = {
            "dataset_version": "module-power-depth-overlay-v7",
            "policy": "batch8 search; fill-null only; OBSERVED values with source_url; unresolved rows omitted",
            "count": len(found),
            "entries": [
                {
                    "module_id": row.get("module_id"),
                    "brand": row["brand"],
                    "name": row["name"],
                    "source_url": next(iter((row.get("sources") or {}).values()), None),
                    "sources": row.get("sources"),
                    "power_12v_ma": row.get("power_12v_ma"),
                    "power_neg12v_ma": row.get("power_neg12v_ma"),
                    "power_5v_ma": row.get("power_5v_ma"),
                    "depth_mm": row.get("depth_mm"),
                    "provenance": "OBSERVED",
                    "status": "found",
                }
                for row in found
            ],
        }
        _write(CATALOG / "overlays" / "module-power-depth-v7.json", overlay)

    summary = {
        "mode": "free-only" if args.max_paid_fetches == 0 else "paid",
        "max_paid_fetches": args.max_paid_fetches,
        "paid_attempts": scraper.paid_attempts,
        "brands": {
            "candidates": len(rows),
            "verified": sum(row["verification_status"] == "verified" for row in rows),
            "corrected": sum(row["verification_status"] == "corrected" for row in rows),
            "flagged": sum(row["verification_status"] == "flagged" for row in rows),
            "duplicates": sum(row["catalog_match"] == "duplicate" for row in rows),
        },
        "power_depth": {
            "targets": len(power_rows),
            "found": len(found),
            "unresolved": len(power_rows) - len(found),
        },
        "paid_command": "python scripts/catalog_batch8.py --max-paid-fetches 200",
    }
    _write(summary_path, summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
