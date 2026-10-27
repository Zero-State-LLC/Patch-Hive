#!/usr/bin/env python3
"""Correction manifest for draws misread by the v2 maker crawl's rail parser.

`module-power-depth-v11.json` as first loaded (git `--before`, default the #67
merge) read some pages in the wrong rail order ("+12V 140mA -12V 115mA" gave
-12V = 140). The loader never overwrites a stored value, so the rebuilt v11
alone cannot repair a database that loaded the first one. This manifest lists
every field whose value changed, with the misread value. On load the field is
archived and cleared only while the database still holds exactly that value;
the rebuilt v11 then fills it from the maker's page in the same run. A database
that never loaded the first v11 (prod) holds other values and is left alone.

Usage: python scripts/build_rail_fix_manifest.py [--before 0ad98a6]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = "data/synth-catalog/overlays/module-power-depth-v11.json"
OUT = ROOT / "data" / "synth-catalog" / "provenance" / "maker-crawl-v2-rail-fix-v1.json"
FIELDS = ("power_12v_ma", "power_neg12v_ma", "power_5v_ma", "depth_mm")


def build(before: dict, after: dict, ref: str) -> dict:
    new = {(e["brand"], e["name"]): e for e in after.get("entries") or []}
    rows = []
    for old in before.get("entries") or []:
        cur = new.get((old["brand"], old["name"]), {})
        fields = [
            {
                "field": field,
                "source_tag": f"maker-crawl:module-power-depth-v11.json@{ref}",
                "maker_check": "rail_parse_fix",
                "action": "null",
                "only_if_value": old[field],
            }
            for field in FIELDS
            if old.get(field) is not None and old.get(field) != cur.get(field)
        ]
        if fields:
            rows.append({"table": "modules", "brand": old["brand"], "name": old["name"], "fields": fields})
    return {
        "batch": "maker-crawl-v2-rail-fix-v1",
        "created": "2026-10-27",
        "approved_by": "Danny 2026-10-27 (chat: approval granted for the conflict review and its fixes)",
        "flag_reverify": False,
        "policy": (
            "Values misread by the v2 crawl's rail parser. On load each listed field is copied into "
            "catalog_value_archive and set to NULL only while the database still holds only_if_value; "
            "the rebuilt module-power-depth-v11 then fills it from the maker's page. Rows are not "
            "flagged needs_reverify: the replacement value is maker-published. Nothing is deleted."
        ),
        "counts": {"rows": len(rows), "fields": sum(len(r["fields"]) for r in rows)},
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="0ad98a6", help="git ref whose v11 was loaded")
    args = ap.parse_args()
    before = json.loads(subprocess.check_output(["git", "show", f"{args.before}:{OVERLAY}"], cwd=ROOT))
    after = json.loads((ROOT / OVERLAY).read_text(encoding="utf-8"))
    manifest = build(before, after, args.before)
    OUT.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"]))


if __name__ == "__main__":
    main()
