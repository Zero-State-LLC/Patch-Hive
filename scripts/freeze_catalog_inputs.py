#!/usr/bin/env python3
"""Record the SHA-256 of each catalog input in ``applied-inputs.sha256`` (spec 003 FR-018).

Adds new files only. An entry never changes: to change an input, write a new version of the file.
``backend/tests/unit/test_003_applied_inputs.py`` fails when a listed file differs or an input is
missing from the list.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

from population import input_file_hashes  # noqa: E402

FROZEN = ROOT / "data" / "synth-catalog" / "applied-inputs.sha256"


def read_frozen(path: Path = FROZEN) -> dict[str, str]:
    """Hash then path on each line, the format ``sha256sum -c`` reads."""
    if not path.is_file():
        return {}
    rows = (line.split("  ", 1) for line in path.read_text(encoding="utf-8").splitlines() if line)
    return {name: digest for digest, name in rows}


def main() -> int:
    frozen = read_frozen()
    current = input_file_hashes()
    changed = sorted(path for path, digest in frozen.items() if current.get(path) != digest)
    if changed:
        raise SystemExit("refusing to record changed or missing inputs: " + ", ".join(changed))
    added = sorted(current.keys() - frozen.keys())
    files = {**frozen, **{path: current[path] for path in added}}
    FROZEN.write_text("".join(f"{files[path]}  {path}\n" for path in sorted(files)), encoding="utf-8")
    print(f"added {len(added)}, {len(files)} recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
