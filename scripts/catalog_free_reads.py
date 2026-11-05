#!/usr/bin/env python3
"""Free maker reads for catalog rows the committed crawl can't settle (owner decisions 18, 41, 50, 54).

Plain GET only, through the shared router: robots.txt, the deny list, the per-host delay and
the cache. The paid cap is 0, and a site that refuses stays refused. It reads:

- the store feed of each maker with a feed adapter, for the store's own taxonomy;
- the maker page of every live row with no category;
- the named rows in NAMED, which hold a category or a width someone has questioned;
- NAMED_PAGES, for rows whose page the crawl never reached.

Writes page details to .cache/free-reads/pages.json (not committed: reviewers read them, and
only the short wording an overlay rests on goes in the repo) and every URL's outcome, with no
page text, to receipts/free-reads-<date>.json.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "synth-catalog"
sys.path.insert(0, str(CATALOG))
sys.path.insert(0, str(ROOT / "scripts"))

import build_category_overlay as O  # noqa: E402
import build_maker_overlays as B  # noqa: E402
import maker_adapters as A  # noqa: E402
from catalog_scrape import CatalogScraper  # noqa: E402

FEED_KINDS = {"shopify", "squarespace", "woocommerce"}
MUTABLE_DOCS = "https://pichenettes.github.io/mutable-instruments-documentation/modules/{}/"
# Rows that hold a value and aren't in the empty list. Where the crawl has no page, the URL is given.
MUTABLE_NAMED = {
    "Yarns": "yarns", "Rings": "rings", "Frames": "frames", "Edges": "edges", "Links": "links",
    "Grids": "grids", "Anushri (Eurorack)": "anushri", "anushri exp": "anushri",
    "Beads": "beads", "Blades": "blades", "Blinds": "blinds", "Branches": "branches", "Ears": "ears",
    "Elements": "elements", "Kinks": "kinks", "Peaks": "peaks", "Ripples_2020": "ripples_2020",
    "Shades_2020": "shades_2020", "Shades_Original": "shades", "Shelves": "shelves", "Streams": "streams",
    "Tides_2018": "tides_2018", "Veils_2020": "veils_2020", "Veils_Original": "veils", "Warps": "warps",
}
NAMED = [
    ("LZX Industries", "Cyclops"), ("LZX Industries", "Sensory Translator"),
    ("Afterlife Laboratories", "Castle Circuits #2"), ("Syntonie", "Animate"), ("Syntonie", "VU006"),
    ("Syntonie", "Cadrans"), ("Syntonie", "Matrice"), ("Syntonie", "Seuils"), ("Syntonie", "Solaire"),
    ("ALM Busy Circuits", "Akemie's Castle"), ("Eowave", "SOURCE MK3"), ("vpme.de", "UPWR"),
    ("ADDAC System", "ADDAC200PI"), ("ADDAC System", "ADDAC200S Size Matter (black)"),
    ("ADDAC System", "ADDAC501B Complex Random Expansion"), ("ADDAC System", "ADDAC001 VCC"),
    ("ADDAC System", "ADDAC003 VCC Manual Inputs"), ("ADDAC System", "ADDAC005 VCC Gate Outputs"),
    ("ADDAC System", "ADDAC101 .WAV Player"), ("ADDAC System", "ADDAC203 CV Mapping"),
    ("Befaco", "Mixer"), ("Befaco", "Dual Atenuverter"), ("Instruo", "dàil"), ("Cwejman", "D-LFO"),
    ("Doepfer", "A-101-4"), ("Intellijel", "μAtt"), ("Intellijel", "Quadra Expander"),
    ("Make Noise", "Mysteron"), ("Make Noise", "Strega"),
]
# Pages the crawl never reached, for widths and supply draws (decisions 15 and 30).
ADDAC = "https://www.addacsystem.com/en/products/modules/"
NAMED_PAGES = [
    ADDAC + "addac000-series/addac001", ADDAC + "addac000-series/addac003", ADDAC + "addac000-series/addac005",
    ADDAC + "addac100-series/addac101", ADDAC + "addac200-series/addac200pi", ADDAC + "addac200-series/addac200s",
    ADDAC + "addac200-series/addac203", ADDAC + "addac500-series/addac501b", "https://doepfer.de/a1014.htm",
    "https://www.makenoisemusic.com/modules/strega/", "https://www.makenoisemusic.com/modules/mysteron/",
    "https://www.cwejman.net/d-lfo.htm", "https://www.instruomodular.com/product/dail/",
    "https://aircraftdesigns.info/dc", "https://www.st-modular.de/modules/pow!", "https://www.st-modular.de/modules/usb",
    "https://wgdmodular.de/module/stv/", "http://www.hexinverter.net/mutant-chicken",
    "https://www.afterlifelaboratories.com/shop/p/zomplr8fkppggyayn1yz9zczuclakq",
]


class _Meta(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self.h1 = ""
        self._in: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            found = dict(attrs)
            key = (found.get("name") or found.get("property") or "").lower()
            if key and found.get("content") and key not in self.meta:
                self.meta[key] = found["content"]
        elif tag in ("title", "h1"):
            self._in = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == self._in:
            self._in = None

    def handle_data(self, data: str) -> None:
        if self._in == "title":
            self.title += data
        elif self._in == "h1" and len(self.h1) < 200:
            self.h1 += data


def page_details(markup: str) -> dict:
    parser = _Meta()
    try:
        parser.feed(markup)
    except (AssertionError, ValueError):
        pass
    body = re.sub(r"<(script|style|nav|header|footer)\b[\s\S]*?</\1\b[^>]*>", " ", markup or "", flags=re.I)
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body))).strip()
    squeeze = lambda value: re.sub(r"\s+", " ", value or "").strip()  # noqa: E731
    return {
        "title": squeeze(parser.title),
        "h1": squeeze(parser.h1),
        "description": squeeze(parser.meta.get("description") or parser.meta.get("og:description")),
        "text": text,
    }


def targets(catalog: dict, crawl: dict) -> list[dict]:
    pages = {}
    for brand in crawl["brands"]:
        for module in brand.get("modules") or []:
            pages.setdefault((module["brand"].lower(), B.norm(module["brand"], B.clean_name(module["brand"], module["name"]))), module)
    by_key = {(row["brand"].lower(), B.norm(row["brand"], row["name"])): (slug, row) for slug, row in catalog.items()}
    out: dict[str, dict] = {}

    def add(slug: str, row: dict, url: str | None, why: str) -> None:
        entry = out.setdefault(slug, {
            "slug": slug, "brand": row["brand"], "name": row["name"], "category": row.get("category"),
            "hp": row.get("hp"), "url": url, "why": [],
        })
        entry["url"] = entry["url"] or url
        entry["why"].append(why)

    for slug, row in catalog.items():
        if row.get("tombstoned") or row.get("category"):
            continue
        page = pages.get((row["brand"].lower(), B.norm(row["brand"], row["name"])))
        add(slug, row, (page or {}).get("source_url"), "empty_category")
    for name, doc in MUTABLE_NAMED.items():
        found = by_key.get(("mutable instruments", B.norm("Mutable Instruments", name)))
        if found:
            add(found[0], found[1], MUTABLE_DOCS.format(doc), "named_mutable")
    for brand, name in NAMED:
        found = by_key.get((brand.lower(), B.norm(brand, name)))
        if found:
            page = pages.get((brand.lower(), B.norm(brand, name)))
            add(found[0], found[1], (page or {}).get("source_url"), "named")
    return sorted(out.values(), key=lambda t: (t["brand"], t["name"]))


def read_feeds(scraper: CatalogScraper, sources: dict, brands: set[str]) -> dict[tuple[str, str], dict]:
    """The store's own product type, categories and tags, by brand and normalized name."""
    out: dict[tuple[str, str], dict] = {}
    for brand, cfg in sorted(sources["adapters"].items()):
        if brand not in brands or cfg["kind"] not in FEED_KINDS:
            continue
        candidates = A.enumerate_products(scraper, cfg)
        print(f"feed {brand}: {len(candidates)} products", flush=True)
        for cand in candidates:
            if cand.name:
                out.setdefault((brand.lower(), B.norm(brand, B.clean_name(brand, cand.name))), {
                    "url": cand.url, "store_tags": cand.store_tags, "feed_name": cand.name, "feed_text": cand.text,
                })
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="date for the receipt's name, YYYY-MM-DD")
    args = ap.parse_args(argv)
    sources = json.loads((CATALOG / "maker-sources.json").read_text(encoding="utf-8"))
    crawl = json.loads((CATALOG / "hermes-research" / "maker-crawl-v2.json").read_text(encoding="utf-8"))
    catalog, _modules = O.planned_catalog(None)
    work = targets(catalog, crawl)
    scraper = CatalogScraper.for_repo(max_paid_fetches=0)
    feeds = read_feeds(scraper, sources, {t["brand"] for t in work})
    outcomes: Counter[str] = Counter()
    for index, target in enumerate(work, 1):
        feed = feeds.get((target["brand"].lower(), B.norm(target["brand"], target["name"])))
        if feed:
            target.update(store_tags=feed["store_tags"], feed_name=feed["feed_name"], feed_url=feed["url"], feed_text=feed["feed_text"])
            target["url"] = target["url"] or feed["url"]
        if not target["url"]:
            target["outcome"] = "no_url"
            outcomes["no_url"] += 1
            continue
        result = scraper.fetch(target["url"], allow_paid=False)
        receipt = result.receipt
        target.update(
            ok=result.ok, status=receipt.get("status"), method=receipt.get("method"),
            note=receipt.get("note"), sha256=receipt.get("sha256"), timestamp=receipt.get("timestamp"),
        )
        target["outcome"] = "read" if result.ok else (receipt.get("note") or receipt.get("method") or "failed")
        outcomes[target["outcome"]] += 1
        if result.ok and result.text:
            target.update(page_details(result.text))
        if index % 50 == 0:
            print(f"{index}/{len(work)} {dict(outcomes)}", flush=True)
    named_pages = []
    for url in NAMED_PAGES:
        result = scraper.fetch(url, allow_paid=False)
        receipt = result.receipt
        named_pages.append({
            "url": url, "outcome": "read" if result.ok else (receipt.get("note") or receipt.get("method")),
            "status": receipt.get("status"), "note": receipt.get("note"), "sha256": receipt.get("sha256"),
        })
    assert scraper.paid_attempts == 0, "a free read reached a paid backend"
    private = CATALOG / ".cache" / "free-reads" / "pages.json"
    private.parent.mkdir(parents=True, exist_ok=True)
    private.write_text(json.dumps(work, indent=0, ensure_ascii=False), encoding="utf-8")
    receipt_rows = [
        {key: target.get(key) for key in ("slug", "url", "outcome", "status", "method", "note", "sha256", "timestamp")}
        for target in work
    ]
    (CATALOG / "receipts" / f"free-reads-{args.date}.json").write_text(json.dumps({
        "paid_attempts": scraper.paid_attempts, "rows": len(work), "outcomes": dict(outcomes),
        "feed_products": len(feeds), "reads": receipt_rows, "named_pages": named_pages,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(outcomes)), "feeds", len(feeds), "paid", scraper.paid_attempts, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
