#!/usr/bin/env python3
"""Backup/restore drill steps for .github/workflows/db-restore-drill.yml.

The workflow runs pg_dump against the Neon staging (or, with a typed confirmation,
production) database. It restores the dump into a Postgres container on the runner,
then calls this script for the counts-only facts and the receipt. Every query against
the source is read-only. The dump never leaves the runner. Nothing here prints a URL,
host, user or row value; the workflow masks the URL's parts first
(scripts/staging/mask_db_url.sh).

Usage (repo root, PYTHONPATH=backend):
  restore_drill.py counts  --url-env SOURCE_DATABASE_URL --out drill/source-before.json [--github-output]
  restore_drill.py head    --url-env RESTORED_DATABASE_URL --out drill/head.json
  restore_drill.py receipt --dir drill --env staging --url-env RESTORED_DATABASE_URL --out drill/receipt.json

``head`` exits 1 unless the restored copy is at this checkout's alembic head.
``receipt`` exits 1 unless every check passed: dump made, restored copy at head, row
counts match the source (when the source did not change while it was dumped), and
``python -m canon.reconcile_all`` found no mismatch.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.ops.restore_drill import (  # noqa: E402
    DrillError,
    compare_counts,
    head_check,
    public_table_counts,
    server_major,
    summary_markdown,
)

ENVIRONMENTS = ("staging", "prod")


def _url(name: str) -> str:
    url = os.environ.get(name, "").strip()
    if not url:
        raise DrillError(f"{name} is not set")
    return url


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def counts(url_env: str, out: Path, github_output: bool) -> int:
    url = _url(url_env)
    facts = {"server_major": server_major(url), "tables": public_table_counts(url)}
    _write(out, facts)
    if github_output and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            handle.write(f"server_major={facts['server_major']}\n")
    print(json.dumps({"server_major": facts["server_major"], "tables": len(facts["tables"])}))
    return 0


def head(url_env: str, out: Path) -> int:
    result = head_check(_url(url_env))
    _write(out, result)
    print(json.dumps(result, sort_keys=True))
    if not result["at_head"]:
        print(
            f"::error::restored copy is at {result['current'] or 'no revision'}, not alembic head {result['head']}; "
            "migrate the source with db-migrate.yml on this ref, or dispatch the drill from the ref it was migrated from",
            flush=True,
        )
        return 1
    return 0


def receipt(directory: Path, env_name: str, url_env: str, out: Path) -> int:
    before = _load(directory / "source-before.json")
    after = _load(directory / "source-after.json")
    dump = _load(directory / "dump.json")
    alembic = _load(directory / "head.json")
    reconcile = _load(directory / "reconcile.json")
    problems: list[str] = []
    document: dict[str, Any] = {
        "kind": "restore-drill",
        "env": env_name,
        "source_sha": os.environ.get("GITHUB_SHA", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "server_major": (before or {}).get("server_major"),
        "dump": dump or {"status": "missing"},
        "alembic": alembic or {"status": "missing"},
    }
    if not dump:
        problems.append("no dump was recorded")
    if not alembic or not alembic.get("at_head"):
        problems.append("restored copy is not at alembic head")
    if before and after:
        try:
            restored = public_table_counts(_url(url_env))
        except DrillError as exc:
            restored = {}
            problems.append(str(exc))
        document["counts"] = compare_counts(before["tables"], after["tables"], restored)
        if not document["counts"]["ok"]:
            problems.append("restored row counts do not match the source")
    else:
        problems.append("source counts are missing")
    if reconcile:
        document["reconcile"] = reconcile
        if reconcile.get("status") != "ok":
            problems.append("ledger reconcile on the restored copy did not pass")
    else:
        document["reconcile"] = {"status": "missing"}
        problems.append("ledger reconcile did not run")
    document["problems"] = problems
    document["result"] = "fail" if problems else "pass"
    _write(out, document)
    _summary(summary_markdown(f"Backup/restore drill ({env_name})", document))
    for problem in problems:
        print(f"::error::{problem}", flush=True)
    return 1 if problems else 0


def _summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)
    else:
        print(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    counts_cmd = commands.add_parser(
        "counts", help="server major version and public table row counts"
    )
    counts_cmd.add_argument("--url-env", required=True)
    counts_cmd.add_argument("--out", type=Path, required=True)
    counts_cmd.add_argument(
        "--github-output",
        action="store_true",
        help="also write server_major to GITHUB_OUTPUT",
    )
    head_cmd = commands.add_parser(
        "head", help="check the restored copy is at this checkout's alembic head"
    )
    head_cmd.add_argument("--url-env", required=True)
    head_cmd.add_argument("--out", type=Path, required=True)
    receipt_cmd = commands.add_parser("receipt", help="assemble the counts-only receipt")
    receipt_cmd.add_argument("--dir", type=Path, required=True)
    receipt_cmd.add_argument("--env", choices=ENVIRONMENTS, required=True)
    receipt_cmd.add_argument("--url-env", required=True)
    receipt_cmd.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "counts":
            return counts(args.url_env, args.out, args.github_output)
        if args.command == "head":
            return head(args.url_env, args.out)
        return receipt(args.dir, args.env, args.url_env, args.out)
    except DrillError as exc:
        print(f"::error::{exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
