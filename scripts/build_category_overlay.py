#!/usr/bin/env python3
"""Fill missing module_catalog categories from the maker crawl's own tags.

Writes overlays/module-catalog-category-vN.json: one entry per catalog row the loader
would hold with no category, when that row's crawled page gives a category.

- First the rules the overlay builder already uses (build_maker_overlays.category) over
  the crawl tags and the module name, then the source URL's path words.
- Then TAG_CATEGORY: whole-tag matches only, never the name or free text. A row whose
  tags point to more than one category is left empty (unknown stays null).
- Tags are the page's own (`tags`) plus, for feed-adapter rows, the store's product type,
  categories and tags (`store_tags`).
- A row with a HELD_TAGS tag, or from a brand most of whose crawled modules are tagged
  video, takes HELD_CATEGORY: VIDEO or SYSTEM (owner decisions 5 and 14, 2026-11-04).
- OWNER_TAG_CATEGORY (rectifier, crossfader, fan) settles a row even when another tag
  points elsewhere, and noise_rule settles rows tagged noise and another category
  (owner decisions 17, 14 and 6).

Built from the committed crawl (hermes-research/maker-crawl-v2.json); no fetches. The
loader fills nulls only, so a category already stored is never changed.

--list-ambiguous prints the rows still left empty because their tags point to more than
one category, after every committed overlay (v2 holds the hand-reviewed ones). An overlay
with a reviewed_by field is hand-made and never overwritten.
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
    # 003 T031 offline pass (2026-11-03). Every row each of these classifies is checked in
    # docs/evidence/CATALOG_T031_OFFLINE_PASS_2026-11-03.md.
    ("FX", r"phaser|phase shifter|frequency shifter|pitch shifter|saturator|clipper|drive|dry/wet|clouds"),
    ("VCO", r"synthesizer|speech|drone|plucked string|cowbell|percussion|kick|chiptune|plaits|braids"),
    ("ENV", r"trapezoid|integrator|glide|dual decay"),
    ("SEQ", r"pattern|groovebox|manual gate|cv controller|rhythmic|shift register"),
    ("MIX", r"panning|pan|summing|aux send"),
    ("UTIL", r"inverter|adder|splitter|adapter|router|matrix|vu meter|meter|oscilloscope|visualizer|"
             r"display|headphones|headphone amp|monitoring|microphone|preamp|line-in|indicator|dac|tester|"
             r"voltage scaler"),
]
_TAG_PATTERNS = [(cat, re.compile(rf"^(?:{pat})$")) for cat, pat in TAG_CATEGORY]
# Whole tags that took a row out of the rules above, and the category the owner gave each
# group on 2026-11-04 (decision 5: VIDEO; decision 14: SYSTEM, not retired).
HELD_TAGS = {"video": "video", "power": "power", "power supply": "power", "supply": "power", "psu": "power"}
HELD_CATEGORY = {"video": "VIDEO", "power": "SYSTEM"}
# Owner conventions, 2026-11-04: these win over any other tag on the row, so Rides in the
# Storm CLI (clipper, rectifier, matrix) is UTIL. Decision 17: rectifiers are UTIL and
# crossfaders MIX. Decision 14: a fan is rack infrastructure.
OWNER_TAG_CATEGORY = {"rectifier": "UTIL", "crossfader": "MIX", "fan": "SYSTEM"}
# Decision 6, option A of docs/evidence/CATALOG_TWO_CATEGORY_ROWS_2026-11-03.md.
NOISE_NAME = re.compile(r"\bnoise\b", re.I)
MODULATION_NAME = re.compile(r"\b(random|s&h|chaos)\b", re.I)
NOISE_MODULATION_TAGS = {"random", "chaos", "cv", "pattern", "generator"}
FORMAT_TAGS = {"1u", "eurorack"}


def held(tags: list[str], brand: str, video_brands: set[str]) -> str | None:
    if brand in video_brands:
        return "video"
    return next((HELD_TAGS[t.strip().lower()] for t in tags if t.strip().lower() in HELD_TAGS), None)


def video_brands(crawl: dict) -> set[str]:
    """Brands most of whose crawled modules are tagged video, so a video maker's row whose
    own tags do not say video is held too."""
    out = set()
    for brand in crawl["brands"]:
        mods = brand.get("modules") or []
        video = sum(1 for m in mods if "video" in {t.strip().lower() for t in m.get("tags") or []})
        if mods and video * 2 > len(mods):
            out.add(brand["brand"])
    return out


def tag_categories(tags: list[str]) -> set[str]:
    return {cat for cat, pat in _TAG_PATTERNS for tag in tags if pat.match(tag.strip().lower())}


def noise_rule(tags: list[str], name: str) -> tuple[str, str] | None:
    """Noise versus random, for a row whose tags point to more than one category.

    A1: the name names one function. A2: tagged noise and random only, as v1 filed them.
    A3: noise among modulation tags only. A4: noise next to another function stays empty
    here, for the maker page.
    """
    lowered = {tag.strip().lower() for tag in tags}
    if "noise" not in lowered:
        return None
    names_noise, names_modulation = bool(NOISE_NAME.search(name)), bool(MODULATION_NAME.search(name))
    if names_noise != names_modulation:
        return ("VCO", "noise_rule_a1") if names_noise else ("LFO", "noise_rule_a1")
    others = lowered - {"noise"} - FORMAT_TAGS
    if others == {"random"}:
        return "VCO", "noise_rule_a2"
    if others and others <= NOISE_MODULATION_TAGS:
        return "LFO", "noise_rule_a3"
    return None


def url_words(url: str) -> str:
    path = url.split("//", 1)[-1].split("/", 1)[-1] if url else ""
    return " ".join(w for w in re.split(r"[/_\-.?=&]+", path) if w)


def classify(tags: list[str], name: str, url: str) -> tuple[str, str] | None:
    """(category, basis) or None."""
    if cat := B.category(tags, name):
        return cat, "crawl_tags_or_name"
    if url and (cat := B.category([url_words(url)], "")):
        return cat, "source_url_path"
    owner = {OWNER_TAG_CATEGORY[t] for t in (tag.strip().lower() for tag in tags) if t in OWNER_TAG_CATEGORY}
    if len(owner) == 1:
        return owner.pop(), "owner_tag"
    cats = tag_categories(tags)
    if len(cats) == 1:
        return cats.pop(), "crawl_tag"
    return noise_rule(tags, name) if cats else None


def planned_catalog(output: Path | None) -> tuple[dict, dict]:
    """Catalog and module rows the loader would hold without this overlay (with every
    committed overlay when output is None)."""
    import population as P

    if output is not None:
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
    ap.add_argument("--list-ambiguous", action="store_true", help="print the ambiguous rows; write nothing")
    args = ap.parse_args(argv)
    output = CATALOG / "overlays" / f"module-catalog-category-v{args.version}.json"
    if not args.list_ambiguous and output.is_file() and json.loads(output.read_text()).get("reviewed_by"):
        raise SystemExit(f"{output.name} is hand-reviewed; pass a new --version")
    crawl = json.loads((CATALOG / "hermes-research" / args.crawl).read_text())
    catalog, modules = planned_catalog(None if args.list_ambiguous else output)

    crawled: dict[tuple[str, str], dict] = {}
    for brand in crawl["brands"]:
        for m in brand.get("modules") or []:
            key = (m["brand"].lower(), B.norm(m["brand"], B.clean_name(m["brand"], m["name"])))
            crawled.setdefault(key, m)
    module_tags = {(b.lower(), B.norm(b, n)): row.get("tags") or [] for (b, n), row in modules.items()}
    videos = video_brands(crawl)

    entries = []
    stats = {"catalog_rows": len(catalog), "missing_category": 0, "no_crawl_page": 0, "held_video": 0,
             "held_power": 0, "ambiguous": 0, "unclassified": 0}
    for slug in sorted(catalog):
        row = catalog[slug]
        if row.get("category") or row.get("tombstoned"):  # a retired row needs no category
            continue
        stats["missing_category"] += 1
        key = (row["brand"].lower(), B.norm(row["brand"], row["name"]))
        page = crawled.get(key)
        if page is None:
            stats["no_crawl_page"] += 1
            continue
        tags = list(page.get("tags") or []) + list(page.get("store_tags") or []) + list(module_tags.get(key) or [])
        url = page.get("source_url") or ""
        if reason := held(tags, row["brand"], videos):
            stats[f"held_{reason}"] += 1
            entries.append({
                "slug": slug, "brand": row["brand"], "name": row["name"], "category": HELD_CATEGORY[reason],
                "basis": f"owner_{reason}", "tags": tags, "source_url": url,
                "content_sha256": page.get("content_sha256"),
            })
            continue
        result = classify(tags, row["name"], url)
        if result is None:
            ambiguous = len(tag_categories(tags)) > 1
            stats["ambiguous" if ambiguous else "unclassified"] += 1
            if ambiguous and args.list_ambiguous:
                print(json.dumps({
                    "slug": slug, "brand": row["brand"], "name": row["name"], "live": not row.get("tombstoned"),
                    "categories": sorted(tag_categories(tags)), "tags": tags, "source_url": url,
                }, ensure_ascii=False))
            continue
        category, basis = result
        entries.append({
            "slug": slug, "brand": row["brand"], "name": row["name"], "category": category,
            "basis": basis, "tags": tags, "source_url": url, "content_sha256": page.get("content_sha256"),
        })
    stats["entries"] = len(entries)
    if args.list_ambiguous:
        print(json.dumps(stats))
        return 0
    output.write_text(json.dumps({
        "dataset_version": f"module-catalog-category-v{args.version}",
        "generated_from": f"hermes-research/{args.crawl}",
        "decided": "2026-11-04: owner decisions 5, 6, 14 and 17 (docs/evidence/OWNER_DECISIONS_2026-11-04.md, #278)",
        "policy": "maker's own page tags and store taxonomy (whole-tag match), name and URL path; fill-null only; "
                  "ambiguous rows left empty; video rows VIDEO and power rows SYSTEM; no ModularGrid",
        "count": len(entries),
        "entries": entries,
    }, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
