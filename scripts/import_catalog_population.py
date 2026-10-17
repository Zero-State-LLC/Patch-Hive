#!/usr/bin/env python3
"""Populate an empty catalog database. Dry-run unless --apply is set.

Reads DATABASE_URL from the environment or --database-url. The URL is never printed.
Remote databases are refused unless --allow-nonlocal is set. Staging and production
loads belong in .github/workflows/db-load.yml.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

from population import populate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write rows. Omit this flag for a dry run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force a dry run even if --apply is also present.",
    )
    parser.add_argument("--allow-nonlocal", action="store_true")
    parser.add_argument(
        "--receipt",
        type=Path,
        default=ROOT / "data" / "synth-catalog" / "receipts" / "population.dry-run.json",
    )
    parser.add_argument(
        "--sql-out",
        type=Path,
        default=ROOT / "data" / "synth-catalog" / "receipts" / "population-upsert.sql",
    )
    parser.add_argument("--verification", type=Path, default=None)
    args = parser.parse_args(argv)
    apply = bool(args.apply) and not args.dry_run
    receipt = populate(
        args.database_url,
        apply=apply,
        allow_nonlocal=args.allow_nonlocal,
        receipt_path=args.receipt,
        sql_path=args.sql_out,
        verification_path=args.verification,
    )
    print(json.dumps({k: receipt[k] for k in ("mode", "database", "inserts", "updates", "unmatched")}, indent=2))
    print(f"conflicts={len(receipt['conflicts'])} receipt={args.receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
