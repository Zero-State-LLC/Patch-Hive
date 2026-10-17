#!/usr/bin/env python3
"""CI guard: no ModularGrid data or fetch code in the repo (Danny 2026-10-17).

Fails when a tracked file
  * is a removed ModularGrid extract (by path),
  * is a data file (json/txt/csv/sql/yaml/zip/md under data/, backend/data/, fixtures/)
    that contains a modulargrid.net URL or a ModularGrid page title,
  * is Python code that builds or requests a modulargrid.net URL.
Docs may mention ModularGrid by name; the policy text itself is allowed.
History is not rewritten; this only guards HEAD going forward.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOVED = {
    "data/synth-catalog/phase2-major-br.md",
    "data/synth-catalog/brand-index-modulargrid.txt",
    "data/synth-catalog/overlays/catalog-new-brand-candidates-v1.json",
    "data/synth-catalog/receipts/population-upsert.sql",
    "backend/integrations/modulargrid_data.py",
    "patchhive-replit.zip",
} | {f"data/synth-catalog/overlays/module-power-depth-v{n}.json" for n in range(1, 6)}
DATA_DIRS = ("data/", "backend/data/", "fixtures/")
DATA_EXT = {".json", ".txt", ".csv", ".sql", ".yaml", ".yml", ".md", ".jsonl", ".tsv"}
URL = re.compile(r"modulargrid\.net", re.I)
TITLE = re.compile(r"Eurorack Module on ModularGrid", re.I)
# Python files allowed to name the host: the deny lists and this guard.
CODE_ALLOW = {
    "scripts/check_no_modulargrid.py",
    "data/synth-catalog/catalog_scrape.py",
    "backend/tests/test_no_modulargrid.py",
}
CODE_URL = re.compile(r"""["'](?:https?://)?(?:www\.)?modulargrid\.net/""", re.I)


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
    return [p for p in out.stdout.decode().split("\0") if p]


def violations(paths: list[str]) -> list[str]:
    bad = []
    for rel in paths:
        if rel in REMOVED:
            bad.append(f"{rel}: removed ModularGrid extract is back")
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        if rel.endswith(".zip") and rel.startswith(DATA_DIRS):
            bad.append(f"{rel}: archive in a data directory")
            continue
        if rel.startswith(DATA_DIRS) and path.suffix.lower() in DATA_EXT:
            text = path.read_text(encoding="utf-8", errors="replace")
            if URL.search(text) or TITLE.search(text):
                bad.append(f"{rel}: contains ModularGrid URLs or page titles")
        elif path.suffix == ".py" and rel not in CODE_ALLOW:
            text = path.read_text(encoding="utf-8", errors="replace")
            if CODE_URL.search(text):
                bad.append(f"{rel}: builds a modulargrid.net URL")
    return bad


def main() -> int:
    bad = violations(tracked())
    for line in bad:
        print(f"no-modulargrid: {line}")
    if bad:
        print(f"no-modulargrid: {len(bad)} violation(s). ModularGrid is never fetched or stored.")
        return 1
    print("no-modulargrid: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
