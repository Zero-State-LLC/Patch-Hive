#!/usr/bin/env python3
"""Filter a fetch batch into rows that may back an overlay and targets to retry (spec 003).

Reads a ``*-results.json`` from ``hermes_hp_enrich_firecrawl.py``. Writes ``*-results.filtered.json``
(rows with a complete provenance packet and a known access basis, FR-014, FR-015, plus any rows that
disagree, marked CONFLICTED, FR-016) and a residual targets file for what stayed unresolved, in the
format ``--targets`` reads (FR-017). It touches no database, and it never overwrites a file (FR-018).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FILTER_ID = "official_only_hp_1_42"
PACKET = (
    "hp",
    "source_url",
    "provenance",
    "source_authority",
    "admission_status",
    "rights_status",
    "access_basis",
)
ALLOWED_ACCESS_BASIS = frozenset({"official_publication"})
HP_BAND = (1, 42)  # FR-007
UNRESOLVED = frozenset({"not_found", "refused"})


def _exclusion(row: dict[str, Any]) -> str | None:
    missing = [field for field in PACKET if row.get(field) in (None, "")]
    if missing:
        return f"missing:{','.join(missing)}"
    if row["access_basis"] not in ALLOWED_ACCESS_BASIS:
        return f"access_basis:{row['access_basis']}"
    if not HP_BAND[0] <= row["hp"] <= HP_BAND[1]:
        return f"hp_out_of_band:{row['hp']}"
    return None


def filter_results(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """The filtered file and the residual targets file for one batch."""
    rows = list(payload.get("results") or [])
    passed: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    residual: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") in UNRESOLVED:
            residual.append({key: row.get(key) for key in ("brand", "name", "slug")})
            continue
        reason = _exclusion(row)
        if reason:
            excluded.append({"slug": row.get("slug"), "reason": reason})
        else:
            passed.append(row)

    values: dict[str, set[Any]] = {}
    for row in passed:
        values.setdefault(row["slug"], set()).add(row["hp"])
    disputed = {slug for slug, seen in values.items() if len(seen) > 1}
    conflicted = [{**row, "epistemic_status": "CONFLICTED"} for row in passed if row["slug"] in disputed]
    results = [row for row in passed if row["slug"] not in disputed]

    filtered = {
        "batch": payload.get("batch"),
        "generated_by": "filter_fetch_results",
        "filter": FILTER_ID,
        "results": results,
        "conflicted": conflicted,
        "excluded": excluded,
        "summary": {
            "rows": len(rows),
            "passed": len(results),
            "conflicted": len(conflicted),
            "excluded": len(excluded),
            "residual": len(residual),
        },
    }
    return filtered, {"batch": payload.get("batch"), "targets": residual}


def _write_new(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--filtered-out", type=Path, default=None)
    parser.add_argument("--residual-out", type=Path, default=None)
    args = parser.parse_args(argv)

    stem = args.results.with_suffix("")
    filtered_path = args.filtered_out or stem.with_name(f"{stem.name}.filtered.json")
    residual_path = args.residual_out or stem.with_name(f"{stem.name}.residual.json")
    for path in (filtered_path, residual_path):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}: write a new version (FR-018)")

    filtered, residual = filter_results(json.loads(args.results.read_text(encoding="utf-8")))
    print(json.dumps(filtered["summary"], indent=2))
    if residual["targets"]:
        _write_new(residual_path, residual)
    if not filtered["results"] and not filtered["conflicted"]:
        print("no row passed the filter, so no filtered file was written")
        for item in filtered["excluded"]:
            print(f"  {item['slug']}: {item['reason']}")
        return 2
    _write_new(filtered_path, filtered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
