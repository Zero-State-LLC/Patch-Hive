#!/usr/bin/env python3
"""Fail unless a populator dry-run receipt shows the seed loaded cleanly from these exact bytes."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def problems(receipt: dict, seed: bytes) -> list[str]:
    found = []
    if receipt.get("status") != "success":
        found.append(f"status is {receipt.get('status')!r}")
    if receipt.get("rejected") != 0:
        found.append(f"{receipt.get('rejected')} records rejected")
    if not receipt.get("input_records"):
        found.append("no input records")
    if receipt.get("input_sha256") != hashlib.sha256(seed).hexdigest():
        found.append("receipt doesn't match the seed file")
    return found


def main() -> int:
    receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    found = problems(receipt, Path(sys.argv[2]).read_bytes())
    for problem in found:
        print(f"case catalog dry run: {problem}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
