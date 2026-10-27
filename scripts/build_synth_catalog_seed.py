#!/usr/bin/env python3
"""Rebuild data/synth-catalog/seed-phase2-v1.json from research packet sources.

Default source directory is the Abraxas skill references path, overridable via
--source-dir. Generated ``generated_at`` is pinned for deterministic seeds
unless --timestamp-now is set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "data" / "synth-catalog"
DEFAULT_SOURCE = Path.home() / "Documents" / "Abraxas-v2.0" / "skills" / "modular-synth-catalog-research" / "references"

CATEGORY_RULES = [
    (("oscillator", "vco", "sound source", "wavetable"), "VCO"),
    (("filter", "vcf"), "VCF"),
    (("vca",), "VCA"),
    (("envelope", "function generator"), "ENV"),
    (("lfo",), "LFO"),
    (("sequencer", "clock", "quantizer", "sample and hold"), "SEQ"),
    (
        (
            "effect",
            "distortion",
            "reverb",
            "delay",
            "waveshaper",
            "equalizer",
            "fuzz",
            "lo-fi",
        ),
        "FX",
    ),
    (("mixer", "mix", "panning"), "MIX"),
    (("sampl", "granular", ".wav", "wav player"), "SAMP"),
    (("midi",), "MIDI"),
]


def map_category(raw: str) -> str:
    r = (raw or "").lower()
    for keys, cat in CATEGORY_RULES:
        if any(k in r for k in keys):
            return cat
    return "UTIL"


def map_availability(status: str) -> str:
    s = re.sub(r"\*+", "", status or "").strip().lower()
    if "discontinu" in s:
        return "discontinued"
    if "upcoming" in s or "announce" in s:
        return "upcoming"
    return "available"


def parse_hp(raw: str):
    if not raw or raw.strip() in {"—", "-", "–", "N/A", "n/a"}:
        return None
    m = re.search(r"(\d+)", raw)
    return int(m.group(1)) if m else None


def parse_phase2(text: str) -> list[dict]:
    modules: list[dict] = []
    current_brand = None
    seen: set[tuple[str, str]] = set()
    for line in text.splitlines():
        m = re.match(r"\*\*Brand:\*\*\s*(.+)", line)
        if m:
            current_brand = m.group(1).strip()
            continue
        m2 = re.match(r"^## Brand \d+:\s*(.+?)(?:\s*\(|$)", line)
        if m2:
            current_brand = re.sub(r"\s+\(Complete\).*$", "", m2.group(1)).strip()
            continue
        if not current_brand or not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        name = re.sub(r"\*\*", "", cells[0]).strip()
        if not name or name.lower() in {"module", "metric", "total modules", "value"}:
            continue
        if name.lower().startswith("total "):
            continue
        key = (current_brand.lower(), name.lower())
        if key in seen:
            continue
        seen.add(key)
        modules.append(
            {
                "brand": current_brand,
                "name": name,
                "hp": parse_hp(cells[1]),
                "category": map_category(cells[2]),
                "category_raw": cells[2],
                "is_available": map_availability(cells[4] if len(cells) > 4 else ""),
                "description": (cells[5].strip() if len(cells) > 5 else "") or None,
                "source": "SynthCatalogResearch",
                "source_reference": "data/synth-catalog/seed-phase2-v1.json",
                "provenance": "OBSERVED",
                "research_phase": "phase2",
            }
        )
    modules.sort(key=lambda m: (m["brand"].lower(), m["name"].lower()))
    return modules


CURATED_FULL = [
    {
        "brand": "Noise Engineering",
        "name": "Basimilus Iteritas Alter",
        "hp": 10,
        "module_type": "VCO",
        "power_12v_ma": 70,
        "power_neg12v_ma": 10,
        "io_ports": [
            {"name": "Pitch", "type": "cv_in"},
            {"name": "Trig", "type": "gate_in"},
            {"name": "Out", "type": "audio_out"},
        ],
        "tags": ["drum", "percussion", "digital"],
        "description": "Digital drum voice",
        "manufacturer_url": "https://noiseengineering.us/",
        "source": "SynthCatalogResearch",
        "source_reference": "phase2-major-brands.md",
        "depth_mm": None,
    },
    {
        "brand": "Make Noise",
        "name": "Maths",
        "hp": 20,
        "module_type": "UTIL",
        "power_12v_ma": 60,
        "power_neg12v_ma": 50,
        "io_ports": [
            {"name": "CH1", "type": "cv_in"},
            {"name": "SUM", "type": "cv_out"},
        ],
        "tags": ["function generator"],
        "description": "Analog computer / function generator",
        "manufacturer_url": "https://www.makenoisemusic.com/",
        "source": "SynthCatalogResearch",
        "source_reference": "phase2-major-brands.md",
        "depth_mm": None,
    },
    {
        "brand": "Instruo",
        "name": "arbhar",
        "hp": 18,
        "module_type": "SAMP",
        "power_12v_ma": 120,
        "power_neg12v_ma": 15,
        "io_ports": [
            {"name": "In", "type": "audio_in"},
            {"name": "Out", "type": "audio_out"},
        ],
        "tags": ["granular"],
        "description": "Granular processor",
        "manufacturer_url": "https://www.instruomodular.com/",
        "source": "SynthCatalogResearch",
        "source_reference": "phase2-major-brands.md",
        "depth_mm": None,
    },
]

MAJOR_BRANDS = [
    "2hp",
    "4ms Company",
    "ALM Busy Circuits",
    "Acid Rain Technology",
    "ADDAC System",
    "Befaco",
    "Doepfer",
    "Bastl Instruments",
    "Cwejman",
    "Dreadbox",
    "Erica Synths",
    "Endorphin.es",
    "Expert Sleepers",
    "Intellijel",
    "Make Noise",
    "Mutable Instruments",
    "Behringer",
    "Noise Engineering",
    "Pittsburgh Modular",
    "Qu-Bit Electronix",
    "Rossum Electro-Music",
    "TipTop Audio",
    "Verbos Electronics",
    "WMD",
    "Winterbloom",
    "Xaoc Devices",
    "Zlob Modular",
    "ZVEX Modular",
    "Instruo",
]


def main(argv: list[str] | None = None) -> int:
    # Retired 2026-10-17: the ModularGrid-derived inputs (phase2-major-br.md,
    # brand-index-modulargrid.txt) are no longer in the repo. The committed seed is
    # the frozen output; do not regenerate it from ModularGrid material.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    src = args.source_dir
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    phase2_path = src / "phase2-major-br"
    if not phase2_path.is_file():
        # committed copy under data/synth-catalog
        alt = out / "phase2-major-br.md"
        if alt.is_file():
            phase2_path = alt
        else:
            print(f"error: phase2 source not found: {phase2_path}")
            return 1

    phase2 = phase2_path.read_text(encoding="utf-8")
    brand_index_path = src / "brand-index-modulargrid.txt"
    if not brand_index_path.is_file():
        brand_index_path = out / "brand-index-modulargrid.txt"
    brands_text = brand_index_path.read_text(encoding="utf-8")
    brands = sorted({b.strip() for b in brands_text.splitlines() if b.strip()}, key=str.lower)

    modules = parse_phase2(phase2)
    payload = {
        "fixture_version": "1.0",
        "name": "Synth Catalog Research — Phase 2 major-brand module catalog seed",
        "generated_at": "2026-07-21T00:00:00Z",
        "source_note": (
            "Derived from Abraxas modular-synth-catalog-research Phase 2 tables. "
            "HP and power left null when research did not record them; never invented. "
            "ModularGrid-derived (browser scrape of ModularGrid manufacturer pages); re-verify on maker pages."
        ),
        "abraxas_skill": "skills/modular-synth-catalog-research",
        "abraxas_pr": "https://github.com/scrimshawlife-ctrl/Abraxas-v2.0/pull/984",
        "content_hashes": {
            "phase2_major_br_sha256": hashlib.sha256(phase2.encode()).hexdigest(),
            "brand_index_sha256": hashlib.sha256(brands_text.encode()).hexdigest(),
        },
        "brand_count": len(brands),
        "catalog_module_count": len(modules),
        "full_spec_module_count": len(CURATED_FULL),
        "brands": brands,
        "major_brands": MAJOR_BRANDS,
        "catalog_modules": modules,
        "full_spec_modules": CURATED_FULL,
    }

    seed_path = out / "seed-phase2-v1.json"
    seed_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    sources = {
        "packet_version": "1.0",
        "source_id": "synth-catalog-research-phase2-v1",
        "access_basis": "browser_scrape_of_modulargrid_manufacturer_pages",
        "license_status": "ModularGrid-derived (browser scrape of ModularGrid manufacturer pages + manufacturer index); see DATA_SOURCES.md",
        "evidence_status": "MODULARGRID_UNVERIFIED",
        "review_state": "needs_reverify",
        "normalizer_version": "synth-catalog-v1",
        "notes": "Multi-source rotation research sealed via Abraxas PR #984; HP/power null when unknown.",
        "content_hashes": payload["content_hashes"],
    }
    sources_path = out / "seed-phase2-v1.sources.json"
    sources_path.write_text(json.dumps(sources, indent=2) + "\n")

    # Package under backend/ for Docker/Render images that only ship backend/
    backend_pack = REPO / "backend" / "data" / "synth-catalog"
    backend_pack.mkdir(parents=True, exist_ok=True)
    shutil.copy(seed_path, backend_pack / "seed-phase2-v1.json")
    shutil.copy(sources_path, backend_pack / "seed-phase2-v1.sources.json")

    # Refresh audit copies when building from Abraxas packet
    for name in (
        "PATCHHIVE_INTEGRATION.md",
        "master-catalog.md",
        "alternative-sources.md",
        "brand-index-modulargrid.txt",
    ):
        src_file = src / name
        if src_file.is_file():
            shutil.copy(src_file, out / name)
    if (src / "phase2-major-br").is_file():
        shutil.copy(src / "phase2-major-br", out / "phase2-major-br.md")

    print(
        json.dumps(
            {
                "status": "success",
                "seed_path": str(seed_path),
                "catalog_modules": len(modules),
                "brands": len(brands),
                "hp_known": sum(1 for m in modules if m.get("hp") is not None),
                "by_brand": Counter(m["brand"] for m in modules).most_common(10),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
