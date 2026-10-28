#!/usr/bin/env python3
"""Fill missing module_catalog categories from the maker crawl's own tags.

Writes overlays/module-catalog-category-vN.json: one entry per catalog row the loader
would hold with no category, when that row's crawled page gives a category.

- First the rules the overlay builder already uses (build_maker_overlays.category) over
  the crawl tags and the module name, then the source URL's path words.
- Then TAG_CATEGORY: whole-tag matches only, never the name or free text. A row whose
  tags point to more than one category is left empty (unknown stays null).

Built from the committed crawl (hermes-research/maker-crawl-v2.json); no fetches. The
loader fills nulls only, so a category already stored is never changed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "synth-catalog"
sys.path.insert(0, str(CATALOG))
sys.path.insert(0, str(ROOT / "scripts"))

import build_maker_overlays as B  # noqa: E402

# Whole tags, as the maker's page lists them, mapped onto the existing categories.
TAG_CATEGORY = [
    ("VCA", r"low ?pass gate|lpg|vactrol|vactrol lpg"),
    ("VCO", r"noise|noise source|white noise|pink noise"),
    ("LFO", r"random|chaos|chaotic|s&h|sample (and|&) hold"),
    ("FX", r"eq|equali[sz]er|compressor|waveshaper|wavefolder|ring ?mod(ulator)?|bitcrusher|saturation|overdrive"),
    ("UTIL", r"attenuverters?|expander|mute|converter|passive|precision adder|comparator|di|transformer|level"),
    ("SEQ", r"controller|touch|keyboard|arpeggiator"),
]
_TAG_PATTERNS = [(cat, re.compile(rf"^(?:{pat})$")) for cat, pat in TAG_CATEGORY]


def tag_categories(tags: list[str]) -> set[str]:
    return {cat for cat, pat in _TAG_PATTERNS for tag in tags if pat.match(tag.strip().lower())}


def url_words(url: str) -> str:
    path = url.split("//", 1)[-1].split("/", 1)[-1] if url else ""
    return " ".join(w for w in re.split(r"[/_\-.?=&]+", path) if w)


def classify(tags: list[str], name: str, url: str) -> tuple[str, str] | None:
    """(category, basis) or None."""
    if cat := B.category(tags, name):
        return cat, "crawl_tags_or_name"
    if url and (cat := B.category([url_words(url)], "")):
        return cat, "source_url_path"
    cats = tag_categories(tags)
    if len(cats) == 1:
        return cats.pop(), "crawl_tag"
    return None


def planned_catalog(output: Path) -> tuple[dict, dict]:
    """Catalog and module rows the loader would hold without this overlay."""
    import population as P

    output.unlink(missing_ok=True)
    catalog: dict = {}
    modules: dict = {}
    P._catalog_state = lambda conn: catalog
    P._module_state = lambda conn: modules
    P._manufacturer_state = lambda conn: set()
    P.build_plan(None)
    return catalog, modules


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crawl", default="maker-crawl-v2.json", help="file under hermes-research/")
    ap.add_argument("--version", type=int, default=1)
    args = ap.parse_args(argv)
    output = CATALOG / "overlays" / f"module-catalog-category-v{args.version}.json"
    crawl = json.loads((CATALOG / "hermes-research" / args.crawl).read_text())
    catalog, modules = planned_catalog(output)

    crawled: dict[tuple[str, str], dict] = {}
    for brand in crawl["brands"]:
        for m in brand.get("modules") or []:
            key = (m["brand"].lower(), B.norm(m["brand"], B.clean_name(m["brand"], m["name"])))
            crawled.setdefault(key, m)
    module_tags = {(b.lower(), B.norm(b, n)): row.get("tags") or [] for (b, n), row in modules.items()}

    entries = []
    stats = {"catalog_rows": len(catalog), "missing_category": 0, "no_crawl_page": 0, "ambiguous": 0, "unclassified": 0}
    for slug in sorted(catalog):
        row = catalog[slug]
        if row.get("category"):
            continue
        stats["missing_category"] += 1
        key = (row["brand"].lower(), B.norm(row["brand"], row["name"]))
        page = crawled.get(key)
        if page is None:
            stats["no_crawl_page"] += 1
            continue
        tags = list(page.get("tags") or []) + list(module_tags.get(key) or [])
        url = page.get("source_url") or ""
        result = classify(tags, row["name"], url)
        if result is None:
            stats["ambiguous" if len(tag_categories(tags)) > 1 else "unclassified"] += 1
            continue
        category, basis = result
        entries.append({
            "slug": slug, "brand": row["brand"], "name": row["name"], "category": category,
            "basis": basis, "tags": tags, "source_url": url, "content_sha256": page.get("content_sha256"),
        })
    stats["entries"] = len(entries)
    output.write_text(json.dumps({
        "dataset_version": f"module-catalog-category-v{args.version}",
        "generated_from": f"hermes-research/{args.crawl}",
        "policy": "maker's own page tags (whole-tag match), name and URL path; fill-null only; ambiguous rows left empty; no ModularGrid",
        "count": len(entries),
        "entries": entries,
    }, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
