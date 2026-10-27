#!/usr/bin/env python3
"""GitHub Actions catalog load. Never prints the database URL.

Environment:
  DATABASE_URL          connection string (required, not logged)
  PATCHHIVE_DB_ENV      staging or prod, stored in the receipt instead of the URL
  PATCHHIVE_LOAD_MODE   dry-run (default) or apply
  GITHUB_STEP_SUMMARY   optional path for the job summary
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

from population import (  # noqa: E402
    assert_at_head,
    dump_affected_tables,
    populate,
    table_counts,
)

ARTIFACTS = ROOT / "load-artifacts"


def _summary(before: dict[str, int], after: dict[str, int] | None, mode: str, env_name: str) -> str:
    lines = [
        f"## Catalog load ({env_name}, {mode})",
        "",
        "| table | before | after | delta |",
        "|---|---:|---:|---:|",
    ]
    for table, prior in before.items():
        later = prior if after is None else after.get(table, prior)
        lines.append(f"| {table} | {prior} | {later} | {later - prior} |")
    if after is None:
        lines.append("")
        lines.append("After counts were not recorded because the load stopped early.")
    return "\n".join(lines) + "\n"


def _write_summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not path:
        print(text)
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    env_name = os.environ.get("PATCHHIVE_DB_ENV", "").strip()
    mode = os.environ.get("PATCHHIVE_LOAD_MODE", "dry-run").strip() or "dry-run"
    if env_name not in {"staging", "prod"}:
        raise SystemExit("PATCHHIVE_DB_ENV must be staging or prod")
    if mode not in {"dry-run", "apply"}:
        raise SystemExit("PATCHHIVE_LOAD_MODE must be dry-run or apply")
    allow = "--allow-nonlocal" in sys.argv
    if not allow:
        raise SystemExit("refusing a remote load without --allow-nonlocal")

    head = assert_at_head(database_url)
    before = table_counts(database_url)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "counts-before.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
    after: dict[str, int] | None = None
    try:
        if mode == "apply":
            dump_affected_tables(database_url, ARTIFACTS / "pre-apply.dump")
        receipt = populate(
            database_url,
            apply=mode == "apply",
            allow_nonlocal=True,
            receipt_path=ARTIFACTS / "receipt.json",
            sql_path=ARTIFACTS / "population-upsert.sql",
        )
        receipt["alembic_head"] = head
        (ARTIFACTS / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        after = table_counts(database_url)
        (ARTIFACTS / "counts-after.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"mode": receipt["mode"], "database": receipt["database"], "inserts": receipt["inserts"]}, indent=2))
        return 0
    finally:
        _write_summary(_summary(before, after, mode, env_name))


if __name__ == "__main__":
    raise SystemExit(main())
