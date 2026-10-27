#!/usr/bin/env python3
"""Targeted pass for catalog rows that the population importer could not match.

Fetches manufacturer pages only (free HTTP first, then the paid router fallback
when --max-paid-fetches > 0). ModularGrid is never fetched: its terms prohibit
automated extraction and reuse. Writes raw parsed observations to
data/synth-catalog/hermes-research/unmatched-pass.json for human review; only
reviewed values go into an overlay.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "synth-catalog"
sys.path.insert(0, str(CATALOG))

from catalog_scrape import CatalogScraper  # noqa: E402

TARGETS: list[tuple[str, str, list[str]]] = [
    ("ALM Busy Circuits", "Akemie's Castle", ["https://busycircuits.com/alm028/"]),
    ("ALM Busy Circuits", "Pamela's NEW Workout", ["https://busycircuits.com/alm017/"]),
    ("Befaco", "Hexmix VCA", ["https://www.befaco.org/hexmix-vca/"]),
    ("Doepfer", "A-106-5", ["https://doepfer.de/a1065.htm"]),
    ("Doepfer", "A-110-1", ["https://doepfer.de/a1101.htm"]),
    ("Erica Synths", "Fusion VCO", ["https://www.ericasynths.lv/shop/eurorack-modules/by-series/fusion-series/fusion-vco/", "https://www.ericasynths.lv/shop/eurorack-modules/fusion-vco/"]),
    ("Intellijel", "Quadrax", ["https://intellijel.com/shop/eurorack/quadrax/"]),
    ("Intellijel", "Rubicon 2", ["https://intellijel.com/shop/eurorack/rubicon-2/"]),
    ("Joranalogue", "Filter 8", ["https://joranalogue.com/products/filter-8"]),
    ("Joranalogue", "Generate 3", ["https://joranalogue.com/products/generate-3"]),
    ("Make Noise", "Rene 2", ["https://www.makenoisemusic.com/modules/rene", "https://www.makenoisemusic.com/modules/rene-2"]),
    ("Mutable Instruments", "Braids", ["https://pichenettes.github.io/mutable-instruments-documentation/modules/braids/"]),
    ("Mutable Instruments", "Clouds", ["https://pichenettes.github.io/mutable-instruments-documentation/modules/clouds/"]),
    ("Mutable Instruments", "Marbles", ["https://pichenettes.github.io/mutable-instruments-documentation/modules/marbles/"]),
    ("Mutable Instruments", "Plaits", ["https://pichenettes.github.io/mutable-instruments-documentation/modules/plaits/"]),
    ("Mutable Instruments", "Rings", ["https://pichenettes.github.io/mutable-instruments-documentation/modules/rings/"]),
    ("Mutable Instruments", "Stages", ["https://pichenettes.github.io/mutable-instruments-documentation/modules/stages/"]),
    ("Noise Engineering", "Basimilus Iteritas Alter", ["https://noiseengineering.us/products/basimilus-iteritas-alter"]),
    ("Noise Engineering", "Desmodus Versio", ["https://noiseengineering.us/products/desmodus-versio"]),
    ("Qu-Bit Electronix", "Chord v2", ["https://www.qubitelectronix.com/shop/chord", "https://www.qubitelectronix.com/modules/chord"]),
    ("Qu-Bit Electronix", "Data Bender", ["https://www.qubitelectronix.com/shop/data-bender", "https://www.qubitelectronix.com/modules/data-bender"]),
    ("Xaoc Devices", "Batumi", ["http://xaocdevices.com/main/batumi/", "https://xaocdevices.com/main/batumi-ii/"]),
    ("Xaoc Devices", "Zadar", ["http://xaocdevices.com/main/zadar/"]),
]


def page_text(page: str) -> str:
    text = re.sub(r"<(script|style)\b[\s\S]*?</\1\b[^>]*>", " ", page or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text))


SNIPPET = re.compile(r".{0,70}(\bmA\b|[Dd]epth|\bHP\b|\bmm\b).{0,70}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-paid-fetches", type=int, default=0)
    parser.add_argument("--search-fallback", action="store_true")
    parser.add_argument("--only-missing", action="store_true", help="retry rows without a fetched page")
    args = parser.parse_args()
    target = CATALOG / "hermes-research" / "unmatched-pass.json"
    previous = {}
    if args.only_missing and target.is_file():
        previous = {(r["brand"], r["name"]): r for r in json.loads(target.read_text())["rows"]}
    scraper = CatalogScraper.for_repo(max_paid_fetches=args.max_paid_fetches)
    out = []
    for brand, name, urls in TARGETS:
        if previous.get((brand, name), {}).get("fetched"):
            out.append(previous[(brand, name)])
            continue
        row: dict = {"brand": brand, "name": name, "fetched": None, "snippets": []}
        tried = list(urls)
        if args.search_fallback:
            found = scraper.search(f"{brand} {name} eurorack module specifications mA depth", limit=5)
            tried += [u for u in found.urls if "modulargrid" not in u]
        for url in tried:
            if "modulargrid" in url:
                continue
            result = scraper.fetch(url)
            if result.ok and result.text:
                snippets = [m.group(0).strip() for m in SNIPPET.finditer(page_text(result.text))][:12]
                if snippets:
                    row.update(fetched=url, method=result.receipt.get("method"), snippets=snippets)
                    break
        print(f"{brand} / {name} -> {row['fetched'] or 'none'}", flush=True)
        out.append(row)
    target.write_text(json.dumps({"rows": out, "paid_attempts": scraper.paid_attempts}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
