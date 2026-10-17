#!/usr/bin/env python3
"""Catalog batch 7: power/depth residuals + HP residual + new-brand discovery.

Uses the in-repo catalog scraper (free HTTP first, then context.dev, then Firecrawl).
Paid calls stay off unless ``--max-paid-fetches`` is greater than zero. The legacy
``--power-cap`` and ``--search-cap`` values are credit skip thresholds only; they do
not raise the paid-fetch budget. Never invents values.

  python scripts/catalog_batch7_router.py --max-paid-fetches 0 --brands 40
"""
from __future__ import annotations
import argparse, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SC = ROOT / "data/synth-catalog"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))
import enrich_module_power_depth_mg as mg  # noqa: E402
from catalog_scrape import CatalogScraper  # noqa: E402

SCRAPER: CatalogScraper | None = None
PAID_CAP = 0
LEDGER = {"credits": 0.0, "calls": 0, "by_backend": {}, "receipts": []}


def _scraper() -> CatalogScraper:
    global SCRAPER
    if SCRAPER is None:
        SCRAPER = CatalogScraper.for_repo(max_paid_fetches=PAID_CAP)
    return SCRAPER


def routed_fetch(url: str, cap: float = 0) -> str | None:
    """Fetch one URL. ``cap`` is retained for batch 7b callers and is not a paid budget."""
    del cap
    scraper = _scraper()
    result = scraper.fetch(url)
    credits = float(result.receipt.get("credits") or 0)
    method = result.receipt.get("method") or "none"
    LEDGER["credits"] += credits
    LEDGER["calls"] += 1
    LEDGER["by_backend"][method] = LEDGER["by_backend"].get(method, 0) + 1
    LEDGER["receipts"].append(
        {key: result.receipt.get(key) for key in ("url", "method", "status", "sha256", "timestamp")}
    )
    return result.text if result.ok else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--power-cap", type=float, default=250)
    ap.add_argument("--search-cap", type=float, default=60)
    ap.add_argument("--max-paid-fetches", type=int, default=0)
    ap.add_argument("--brands", type=int, default=40)
    ap.add_argument("--urls-per-target", type=int, default=4)
    a = ap.parse_args()
    global PAID_CAP, SCRAPER
    PAID_CAP = max(0, int(a.max_paid_fetches))
    SCRAPER = CatalogScraper.for_repo(max_paid_fetches=PAID_CAP)
    hr = SC / "hermes-research"

    # 1) targets
    pd = json.loads((hr / "power-depth-residual-3-results.json").read_text())["still_null"]
    hp = json.loads((hr / "hp-enrichment-batch6-final-results.json").read_text())["still_null"]
    non_euro = [t for t in hp if re.search(r"pedal|desktop|non-eurorack", t["reason"], re.I)]
    hp_retry = [{"brand": "Doepfer", "name": "A-101-5", "slug": t["slug"]} for t in hp if t not in non_euro]
    seed = json.loads((SC / "seed-phase2-v1.json").read_text())
    have = {m["brand"] for m in seed["catalog_modules"]} | {m.get("brand") for m in seed["full_spec_modules"]}
    new_brands = [b for b in seed["brands"] if b not in have][: a.brands]
    targets = {"batch": "batch7", "power_depth": pd, "hp_retry": hp_retry,
               "hp_excluded_non_eurorack": non_euro, "new_brand_discovery": new_brands}
    (hr / "batch7-targets.json").write_text(json.dumps(targets, indent=2) + "\n")

    # 2) power/depth + hp via router
    mg.fetch = lambda url, timeout=25: routed_fetch(url)
    orig = mg.candidate_urls
    mg.candidate_urls = lambda *x, **k: orig(*x, **k)[: a.urls_per_target]
    results = [mg.process_one(t, 0) for t in pd + hp_retry]
    power_credits = LEDGER["credits"]

    # 3) new-brand discovery (search, candidate URLs only; INFERRED, never admitted)
    disc = []
    for b in new_brands:
        if LEDGER["credits"] - power_credits >= a.search_cap:
            disc.append({"brand": b, "status": "skipped_cap"}); continue
        scraper = _scraper()
        res = scraper.search(f"{b} eurorack module modulargrid", limit=10)
        LEDGER["credits"] += sum(float(item.get("credits") or 0) for item in res.receipts)
        urls = sorted(set(re.findall(r"https?://modulargrid\.net/e/[A-Za-z0-9%\-_.]+", "\n".join(res.urls))))
        disc.append({"brand": b, "status": "ok" if res.ok else "failed", "candidate_urls": urls[:25], "provenance": "INFERRED"})
        time.sleep(0.2)

    now = datetime.now(timezone.utc).isoformat()
    found = [r for r in results if r.get("status") == "found"]
    out = {"batch": "batch7", "captured_at": now, "results": results, "discovery": disc,
           "summary": {"targets": len(results), "found": len(found), "still_null": len(results) - len(found),
                       "brands_searched": sum(d["status"] == "ok" for d in disc),
                       "credits": round(LEDGER["credits"], 2), "credits_power": round(power_credits, 2),
                       "calls": LEDGER["calls"], "by_backend": LEDGER["by_backend"]}}
    (hr / "batch7-results.json").write_text(json.dumps(out, indent=2) + "\n")
    (SC / "receipts/batch7-router-receipts.json").write_text(json.dumps(LEDGER["receipts"], indent=2) + "\n")
    print(json.dumps(out["summary"], indent=2))


if __name__ == "__main__":
    main()
