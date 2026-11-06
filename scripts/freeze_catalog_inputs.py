#!/usr/bin/env python3
"""Record the SHA-256 of each catalog input in ``applied-inputs.json`` (spec 003 FR-018).

Adds new files only. An entry never changes: to change an input, write a new version of the file.
``backend/tests/unit/test_003_applied_inputs.py`` fails when a listed file differs or an input is
missing from the list.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

from population import input_file_hashes  # noqa: E402

FROZEN = ROOT / "data" / "synth-catalog" / "applied-inputs.json"
MEANING = (
    "The SHA-256 of every catalog input the loader reads. An input is versioned and is never edited "
    "in place (FR-018): write a new version and add it with scripts/freeze_catalog_inputs.py."
)


def main() -> int:
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))["files"] if FROZEN.is_file() else {}
    current = input_file_hashes()
    changed = sorted(path for path, digest in frozen.items() if current.get(path) != digest)
    if changed:
        raise SystemExit("refusing to record changed or missing inputs: " + ", ".join(changed))
    added = sorted(current.keys() - frozen.keys())
    files = {**frozen, **{path: current[path] for path in added}}
    payload = {"meaning": MEANING, "files": dict(sorted(files.items()))}
    FROZEN.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"added {len(added)}, {len(files)} recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
