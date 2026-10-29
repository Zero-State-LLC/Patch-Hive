#!/usr/bin/env python3
"""Turn a maker-crawl run into loader overlays.

Defaults rebuild the v1 overlays; T025 uses
`--crawl maker-crawl-v2.json --additions-version 3 --power-version 11`; T026 adds
`--additions-version 4 --power-version 12 --brands "4ms Company,Erica Synths,Pittsburgh Modular"`.

- catalog-additions-vN.json: modules not already in the catalog (insert-if-absent),
  tagged `access_basis = official_publication`.
- module-power-depth-vM.json: verified specs for crawled modules, keyed to the
  existing catalog name when one matches. The loader fills nulls only and flags
  rows whose stored values disagree.
Every value was parsed deterministically or found verbatim on the maker's page.
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

CATEGORY = [
    ("SAMP", r"sampl|looper"), ("SEQ", r"sequenc|clock|trigger|gate gen|euclid"), ("VCO", r"oscillat|vco|voice|drum|wavetable"),
    ("VCF", r"filter|vcf"), ("VCA", r"vca|amplifier"), ("ENV", r"envelope|adsr|function gen|slew"), ("LFO", r"\blfo\b|modulat"),
    ("MIX", r"mixer|mix\b|panner"), ("FX", r"reverb|delay|effect|distort|granular|chorus|fx"), ("MIDI", r"midi"),
    ("UTIL", r"attenuat|mult|buffer|utility|output|input|logic|switch|quantiz|offset|interface"),
]
# Fallback when CATEGORY finds nothing: maker names without tags ("Pico SEQ", "Mutant Clap").
# Applied second so it never changes a category the rules above assign.
NAME_CATEGORY = [
    ("SEQ", r"\bseq\b|controller|joystick|catalyst|\bqcd\b"), ("SAMP", r"recorder"),
    ("VCO", r"\bvcno\b|clap|hi-?hats?|snare|cymbal|bass ?line|\bkick\b|cowbell"), ("ENV", r"\bpeg\b"),
    ("LFO", r"qplfo|\brnd\b|random"),
    ("FX", r"(?<!motor )\bdrive\b|\bphaser\b|flang|\bdsp\b|resonat|replicator|fold"),
    ("UTIL", r"\bquant\b|expander|breakout"),
]


def norm(brand: str, name: str) -> str:
    n = name.lower()
    for token in [brand.lower(), "eurorack", "module", "modules", "synthesizer", "synth"]:
        n = n.replace(token, " ")
    return re.sub(r"[^a-z0-9]+", "", n)


HP_MIN, HP_MAX = 1, 42  # FR-007: HP outside 1..42 is discarded
# Products that share a maker's store with modules: pedals, upgrades, bare panels, power, MCUs.
NOT_MODULE_NAME = re.compile(
    r"(\bpedal\b|\bupgrade\b|(aluminum|alu|replacement|front|blank)\s+panel|\bpanel only\b|\bteensy\b|"
    r"power supply|\bpsu\b|\brow power\b|\(\d+(\.\d+)?\s*a\)|\bcase\b|\bskiff\b|\bcable|\bt-shirt|\bgift card)",
    re.I,
)


def clean_name(brand: str, name: str) -> str:
    """Maker store titles carry boilerplate: "Bastl CRUST Eurorack Module", "Eurorack: Coma Reactor 2"."""
    n = re.sub(r"^\s*new\s+", "", name, flags=re.I)
    n = re.sub(rf"^\s*{re.escape(brand)}\s*[:\-]?\s+", "", n, flags=re.I)
    first = brand.split()[0] if brand.split() else ""
    if len(first) >= 4 and first.lower() not in {"the", "audio", "music"}:  # "Bastl CRUST" under "Bastl Instruments"
        n = re.sub(rf"^\s*{re.escape(first)}\s+(?=\S)", "", n, flags=re.I)
    n = re.sub(r"^\s*eurorack\s*:\s*", "", n, flags=re.I)
    n = re.sub(r"\s+eurorack(\s+modules?)?\s*$|\s+modules?\s*$", "", n, flags=re.I)
    return re.sub(r"\s{2,}", " ", n).strip(" -:|") or name.strip()


def existing_index(outputs: tuple[str, ...]) -> dict[str, dict[str, tuple[str, str, bool]]]:
    """Catalog and module identities the loader would hold without this build's outputs.

    Keyed by lower-cased brand, so "Mutable instruments" (seed) finds "Mutable Instruments"
    (curated); values keep the stored spelling, which the overlays must reuse.
    """
    import population as P

    for stale in outputs:
        (CATALOG / "overlays" / stale).unlink(missing_ok=True)
    catalog: dict = {}
    modules: dict = {}
    P._catalog_state = lambda conn: catalog
    P._module_state = lambda conn: modules
    P._manufacturer_state = lambda conn: set()
    P.build_plan(None)
    idx: dict[str, dict[str, tuple[str, str, bool]]] = {}

    def add(brand: str, name: str, exists: bool = True) -> None:
        idx.setdefault(brand.lower(), {}).setdefault(norm(brand, name), (brand, name, exists))

    for row in catalog.values():
        add(row["brand"], row["name"])
    for (brand, name) in modules:
        add(brand, name)
    # HP overlays name rows they expect to find. A crawled module they describe is still added,
    # but under the overlay's spelling, so the overlay's identity check matches the new row.
    # The provenance manifests check identity the same way before archiving a row.
    named = [e for path in sorted((CATALOG / "overlays").glob("module-catalog-hp-v*.json")) for e in json.loads(path.read_text()).get("entries") or []]
    named += [r for path in sorted((CATALOG / "provenance").glob("*.json")) for r in json.loads(path.read_text()).get("rows") or []]
    for e in named:
        if e.get("brand") and e.get("name"):
            add(e["brand"], e["name"], exists=False)
    return idx


def shared_homepage_conflicts(brands: list[dict]) -> list[dict]:
    """Hosts claimed by more than one brand: [{host, brands, owner}], owner None if unclear.

    The v1 crawl once gave "Mental Noise" Make Noise's site, so 48 Make Noise modules were
    added under the wrong brand. When brands share a host, the one whose name is spelled in
    the host owns it; with no single such brand there is no owner.
    """
    from urllib.parse import urlsplit

    import unicodedata

    def compact(text: str) -> str:
        # "Jasmine & Olive Trees" is spelled jasmineandolivetrees; "Instruō" is instruo.
        plain = unicodedata.normalize("NFKD", text.replace("&", " and ")).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]", "", plain.lower())

    by_host: dict[str, set[str]] = {}
    for b in brands:
        host = urlsplit(b.get("homepage") or "").netloc.lower().removeprefix("www.")
        if host:
            by_host.setdefault(host, set()).add(b["brand"])
    conflicts = []
    for host in sorted(by_host):
        names = sorted(by_host[host])
        if len(names) < 2:
            continue
        owners = [n for n in names if compact(n) and compact(n) in compact(host)]
        conflicts.append({"host": host, "brands": names, "owner": owners[0] if len(owners) == 1 else None})
    return conflicts


TRUSTED_RESOLUTION = ("curated", "curated_confirmed")


def misattributed_brands(brands: list[dict]) -> dict[str, str | None]:
    """Every brand on a shared host that is not its owner: {brand: owner or None}.

    The owner is the brand named in the host; failing that, the one brand whose homepage
    came from a maker adapter or the curated list (``resolved_by``), as the crawler
    decides (spec 003 T030). With no owner, every brand on the host maps to None.
    """
    how = {b["brand"]: b.get("resolved_by") or "" for b in brands}
    out: dict[str, str | None] = {}
    for c in shared_homepage_conflicts(brands):
        owner = c["owner"]
        if owner is None:
            trusted = [n for n in c["brands"] if how.get(n, "").startswith("adapter:") or how.get(n) in TRUSTED_RESOLUTION]
            owner = trusted[0] if len(trusted) == 1 else None
        out.update({n: owner for n in c["brands"] if n != owner})
    return out


def shared_homepage_skips(brands: list[dict]) -> dict[str, str]:
    """Brands whose homepage belongs to another brand: {skipped brand: owner}.

    Only hosts with a single owner; with no owner, nothing is skipped here (the crawler
    refuses those hosts before crawling, so overlays never see them from a new run).
    """
    return {
        name: c["owner"]
        for c in shared_homepage_conflicts(brands)
        if c["owner"]
        for name in c["brands"]
        if name != c["owner"]
    }


def category(tags: list[str], name: str) -> str | None:
    hay = " ".join(tags).lower() + " " + name.lower()
    for cat, pat in CATEGORY:
        if re.search(pat, hay):
            return cat
    for cat, pat in NAME_CATEGORY:
        if re.search(pat, name.lower()):
            return cat
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crawl", default="maker-crawl-v1.json", help="file under hermes-research/")
    ap.add_argument("--additions-version", type=int, default=2)
    ap.add_argument("--power-version", type=int, default=9)
    ap.add_argument("--brands", default="", help="comma-separated: build only these brands (a partial crawl pass)")
    ap.add_argument("--skip-brands", default="", help="comma-separated: leave these brands out (built in a later version)")
    args = ap.parse_args(argv)
    only = {b.strip() for b in args.brands.split(",") if b.strip()}
    skip = {b.strip() for b in args.skip_brands.split(",") if b.strip()}
    additions_name = f"catalog-additions-v{args.additions_version}.json"
    power_name = f"module-power-depth-v{args.power_version}.json"
    crawl = json.loads((CATALOG / "hermes-research" / args.crawl).read_text())
    idx = existing_index((additions_name, power_name))
    additions, entries = [], []
    stats = {"crawled_modules": 0, "matched_existing": 0, "new": 0, "skipped_dupe_in_crawl": 0, "skipped_hp_range": 0, "skipped_not_module": 0, "skipped_shared_homepage": 0}
    shared = shared_homepage_skips(crawl["brands"])
    for b in crawl["brands"]:
        if (only and b["brand"] not in only) or b["brand"] in skip:
            continue
        if b["brand"] in shared:
            stats["skipped_shared_homepage"] += len(b.get("modules") or [])
            continue
        seen = set()
        for m in b.get("modules") or []:
            stats["crawled_modules"] += 1
            if not (HP_MIN <= (m.get("hp") or 0) <= HP_MAX):
                stats["skipped_hp_range"] += 1
                continue
            if NOT_MODULE_NAME.search(m["name"]):
                stats["skipped_not_module"] += 1
                continue
            m = {**m, "name": clean_name(m["brand"], m["name"])}
            key = norm(m["brand"], m["name"])
            if not key or key in seen:
                stats["skipped_dupe_in_crawl"] += 1
                continue
            seen.add(key)
            hit = idx.get(m["brand"].lower(), {}).get(key)
            if hit:
                m = {**m, "brand": hit[0], "name": hit[1]}
            existing = hit[1] if hit and hit[2] else None
            name = m["name"]
            if existing:
                stats["matched_existing"] += 1
            else:
                stats["new"] += 1
                additions.append({
                    "brand": m["brand"], "name": name, "hp": m["hp"], "category": category(m.get("tags") or [], name),
                    "manufacturer_url": m["source_url"], "image_url": m.get("image_url"), "is_available": "available",
                    "source": "ManufacturerCrawl", "source_reference": m["source_url"], "tags": m.get("tags") or [],
                    "access_basis": "official_publication",
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
    meta = {"generated_from": f"hermes-research/{args.crawl}" + (f" (brands: {', '.join(sorted(only))})" if only else ""), "policy": "maker's own pages only; values regex-parsed or verbatim; no ModularGrid; insert-if-absent / fill-null; disagreements are flagged by the loader"}
    (D / additions_name).write_text(json.dumps({"dataset_version": f"catalog-additions-v{args.additions_version}", **meta, "count": len(additions), "rows": additions}, indent=1) + "\n")
    (D / power_name).write_text(json.dumps({"dataset_version": f"module-power-depth-overlay-v{args.power_version}", **meta, "count": len(entries), "entries": entries}, indent=1) + "\n")
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
