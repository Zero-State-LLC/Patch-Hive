#!/usr/bin/env python3
"""Batch 7b: fetch the ModularGrid module pages discovered for new brands (batch7 discovery) via the
shared scrape-router and parse HP / power / depth. Output rows are candidates for the catalog; nothing
is admitted. Fields that are not on the page stay null (never invent)."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HR = ROOT / "data/synth-catalog/hermes-research"
sys.path.insert(0, str(ROOT / "scripts"))
import catalog_batch7_router as b7  # noqa: E402
import enrich_module_power_depth_mg as mg  # noqa: E402


def title(html: str) -> str | None:
    m = re.search(r"<title>\s*([^<]+?)\s*</title>", html or "", re.I)
    return re.sub(r"\s*[-|–]\s*ModularGrid.*$", "", m.group(1)).strip() if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=float, default=200)
    a = ap.parse_args()
    disc = json.loads((HR / "batch7-results.json").read_text())["discovery"]
    rows = []
    for d in disc:
        for url in d.get("candidate_urls", []):
            html = b7.routed_fetch(url, a.cap)
            if not html:
                rows.append({"brand": d["brand"], "source_url": url, "status": "fetch_failed"}); continue
            f = mg.extract_power_depth(html)
            t = title(html)
            ok = any(f[k] is not None for k in ("hp", "power_12v_ma", "depth_mm"))
            rows.append({"brand": d["brand"], "page_title": t, "source_url": url,
                         "hp": f["hp"], "power_12v_ma": f["power_12v_ma"], "power_neg12v_ma": f["power_neg12v_ma"],
                         "power_5v_ma": f["power_5v_ma"], "depth_mm": f["depth_mm"],
                         "status": "found" if ok else "no_fields",
                         "provenance": "OBSERVED" if ok else None,
                         "notes": "source_class=modulargrid;method=scrape-router;batch7b;brand_match_unverified"})
    s = {"pages": len(rows), "found": sum(r["status"] == "found" for r in rows),
         "credits_total_run": round(b7.LEDGER["credits"], 2), "by_backend": b7.LEDGER["by_backend"]}
    (HR / "batch7b-new-brand-modules.json").write_text(json.dumps({"batch": "batch7b", "summary": s, "rows": rows}, indent=2) + "\n")
    prev = json.loads((ROOT / "data/synth-catalog/receipts/batch7-router-receipts.json").read_text())
    (ROOT / "data/synth-catalog/receipts/batch7-router-receipts.json").write_text(json.dumps(prev + b7.LEDGER["receipts"], indent=2) + "\n")
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
