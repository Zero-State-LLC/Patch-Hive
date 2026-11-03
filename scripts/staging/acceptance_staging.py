#!/usr/bin/env python3
"""Run backend/tests/acceptance against a throwaway database on Neon staging.

Used by .github/workflows/acceptance-staging.yml. The acceptance conftest truncates
every public table, so the suite never runs against the deployed ``patchhive``
database: this script makes a throwaway target, migrates it to head, runs the suite,
removes the target, and writes a counts-only receipt.

  --isolation database     CREATE DATABASE patchhive_acceptance_<run>_<attempt> on the
                           staging branch; DROP DATABASE ... WITH (FORCE) at the end.
  --isolation neon-branch  child branch acceptance-<run>-<attempt> of the staging branch
                           (Neon API, needs NEON_API_KEY) with a throwaway database on it;
                           the branch is deleted at the end.

It runs as three workflow steps, so the workflow can mask the throwaway connection
string (scripts/staging/mask_db_url.sh) before anything uses it. This script never
prints any part of a connection string:

  provision  create the target; write its URL to --target-file (mode 0600, on the runner)
  suite      migrate the target to head and run the suite
  cleanup    remove the target and the file, finish the receipt (idempotent; the
             workflow runs it whatever happened, so a cancelled run leaves nothing)

Environment:
  STAGING_SOURCE_URL   staging connection string (required; never printed)
  GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT   name the throwaway target (digits)
  NEON_API_KEY, NEON_PROJECT_ID, NEON_PARENT_BRANCH   neon-branch only

Usage (repo root):
  acceptance_staging.py provision --isolation database --target-file T --receipt-out R
  acceptance_staging.py suite --target-file T --receipt-out R
  acceptance_staging.py cleanup --isolation database --target-file T --receipt-out R
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.ops.restore_drill import (  # noqa: E402
    DrillError,
    alembic_head,
    current_revision,
    server_major,
    summary_markdown,
)
from core.ops.throwaway_db import (  # noqa: E402
    NeonBranches,
    TargetRefused,
    ThrowawayError,
    create_database,
    drop_database,
    refuse_real_database,
    throwaway_branch_name,
    throwaway_database_name,
    with_database,
)

ISOLATIONS = ("database", "neon-branch")
DEFAULT_NEON_PROJECT = "polished-night-86976142"
DEFAULT_PARENT_BRANCH = "staging"
# Env vars the suite must not see: the conftest falls back to STAGING_DATABASE_URL.
_HIDDEN_FROM_SUITE = (
    "STAGING_SOURCE_URL",
    "STAGING_DATABASE_URL",
    "DATABASE_URL",
    "NEON_API_KEY",
)


@dataclass(frozen=True)
class Names:
    database: str
    branch: str


def _names(env: dict[str, str]) -> Names:
    run_id = env.get("GITHUB_RUN_ID", "").strip()
    attempt = env.get("GITHUB_RUN_ATTEMPT", "").strip()
    return Names(throwaway_database_name(run_id, attempt), throwaway_branch_name(run_id, attempt))


def _source_url(env: dict[str, str]) -> str:
    source = env.get("STAGING_SOURCE_URL", "").strip()
    if not source:
        raise TargetRefused(
            "STAGING_SOURCE_URL (the PATCHHIVE_DATABASE_URL_STAGING secret) is not set"
        )
    return source


def _neon(env: dict[str, str]) -> NeonBranches:
    return NeonBranches(
        env.get("NEON_API_KEY", "").strip(),
        env.get("NEON_PROJECT_ID", "").strip() or DEFAULT_NEON_PROJECT,
    )


def provision(isolation: str, env: dict[str, str]) -> str:
    """Create the throwaway target and return its URL."""
    source = _source_url(env)
    names = _names(env)
    if isolation == "database":
        target = with_database(source, names.database)
        refuse_real_database(target)
        create_database(source, names.database)
        return target
    neon = _neon(env)
    owner = make_url(source).username or ""
    if not owner:
        raise TargetRefused(
            "the staging connection string names no role to own the throwaway database"
        )
    branch_id = neon.create_branch(
        names.branch, env.get("NEON_PARENT_BRANCH", "").strip() or DEFAULT_PARENT_BRANCH
    )
    neon.create_database(branch_id, names.database, owner)
    target = neon.connection_uri(branch_id, names.database, owner)
    refuse_real_database(target)
    return target


def teardown(isolation: str, env: dict[str, str]) -> str:
    """Remove the throwaway target if it exists. Returns what was done."""
    names = _names(env)
    if isolation == "database":
        drop_database(_source_url(env), names.database)
        return "dropped"
    return "branch deleted" if _neon(env).delete_branch(names.branch) else "no branch to delete"


def _suite_env(target: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in _HIDDEN_FROM_SUITE}
    env.update(
        ACCEPTANCE_DATABASE_URL=target,
        PYTHONPATH=str(BACKEND),
        TEST_MODE="true",
        STRIPE_TEST_MODE="true",
        ALLOW_PRODUCTION_PAYMENTS="false",
    )
    return env


def junit_counts(path: Path) -> dict[str, float | int]:
    """passed/failed/errors/skipped/total from a pytest JUnit XML file."""
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    totals = {"total": 0, "failed": 0, "errors": 0, "skipped": 0}
    duration = 0.0
    for suite in suites:
        totals["total"] += int(suite.get("tests", 0))
        totals["failed"] += int(suite.get("failures", 0))
        totals["errors"] += int(suite.get("errors", 0))
        totals["skipped"] += int(suite.get("skipped", 0))
        duration += float(suite.get("time", 0.0))
    passed = totals["total"] - totals["failed"] - totals["errors"] - totals["skipped"]
    return {**totals, "passed": passed, "duration_seconds": round(duration, 1)}


def suite_passed(receipt: dict[str, Any]) -> bool:
    tests = receipt.get("tests") or {}
    return (
        bool((receipt.get("alembic") or {}).get("at_head"))
        and tests.get("pytest_exit_code") == 0
        and bool(tests.get("total"))
        and not tests.get("failed")
        and not tests.get("errors")
    )


def _describe(exc: Exception) -> str:
    # httpx messages carry the request URL; the class name is enough.
    if isinstance(exc, httpx.HTTPError):
        return f"Neon API request failed ({exc.__class__.__name__})"
    return str(exc)


def _new_receipt(isolation: str) -> dict[str, Any]:
    return {
        "kind": "acceptance-staging",
        "isolation": isolation,
        "source_sha": os.environ.get("GITHUB_SHA", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "alembic": {"head": alembic_head()},
        "result": "fail",
    }


def _read_receipt(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fail(receipt: dict[str, Any], message: str) -> None:
    print(f"::error::{message}", flush=True)
    # Keep the first error: later steps only report the consequence of it.
    receipt.setdefault("error", message)


def provision_step(isolation: str, target_file: Path, receipt_out: Path) -> int:
    receipt = _new_receipt(isolation)
    code = 1
    try:
        target = provision(isolation, dict(os.environ))
        target_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(target_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(target)
        receipt["throwaway"] = "created"
        code = 0
    except (TargetRefused, ThrowawayError, httpx.HTTPError) as exc:
        _fail(receipt, _describe(exc))
    _write_receipt(receipt_out, receipt)
    return code


def suite_step(target_file: Path, receipt_out: Path) -> int:
    receipt = _read_receipt(receipt_out) or _new_receipt("unknown")
    junit = receipt_out.parent / "acceptance-junit.xml"
    head = alembic_head()
    try:
        target = target_file.read_text(encoding="utf-8").strip()
        refuse_real_database(target)
        receipt["server_major"] = server_major(target)
        migrate = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND,
            env={**_suite_env(target), "DATABASE_URL": target},
            check=False,
        )
        current = current_revision(target)
        receipt["alembic"] = {"head": head, "current": current, "at_head": current == head}
        if migrate.returncode != 0 or current != head:
            _fail(receipt, "the throwaway database did not migrate to head")
        else:
            suite = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/acceptance",
                    "-q",
                    "--tb=short",
                    "-p",
                    "no:cacheprovider",
                    f"--junitxml={junit}",
                ],
                cwd=BACKEND,
                env=_suite_env(target),
                check=False,
            )
            counts = junit_counts(junit) if junit.is_file() else {"total": 0}
            receipt["tests"] = {**counts, "pytest_exit_code": suite.returncode}
    except OSError:
        _fail(receipt, "no throwaway target was provisioned")
    except (TargetRefused, DrillError) as exc:
        _fail(receipt, str(exc))
    _write_receipt(receipt_out, receipt)
    return 0 if suite_passed(receipt) else 1


def cleanup_step(isolation: str, target_file: Path, receipt_out: Path) -> int:
    receipt = _read_receipt(receipt_out) or _new_receipt(isolation)
    try:
        receipt["teardown"] = {"status": teardown(isolation, dict(os.environ))}
    except (TargetRefused, ThrowawayError, httpx.HTTPError) as exc:
        print(f"::error::teardown: {_describe(exc)}", flush=True)
        receipt["teardown"] = {"status": "failed", "error": _describe(exc)}
    target_file.unlink(missing_ok=True)
    teardown_ok = receipt["teardown"]["status"] != "failed"
    receipt["result"] = "pass" if suite_passed(receipt) and teardown_ok else "fail"
    _write_receipt(receipt_out, receipt)
    _summary(summary_markdown(f"Acceptance on Neon staging ({isolation})", receipt))
    return 0 if teardown_ok else 1


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
    provision_cmd = commands.add_parser("provision", help="create the throwaway target")
    suite_cmd = commands.add_parser("suite", help="migrate the target to head, run the suite")
    cleanup_cmd = commands.add_parser("cleanup", help="remove the target, finish the receipt")
    for command in (provision_cmd, cleanup_cmd):
        command.add_argument("--isolation", choices=ISOLATIONS, required=True)
    for command in (provision_cmd, suite_cmd, cleanup_cmd):
        command.add_argument("--target-file", type=Path, required=True)
        command.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "provision":
        return provision_step(args.isolation, args.target_file, args.receipt_out)
    if args.command == "suite":
        return suite_step(args.target_file, args.receipt_out)
    return cleanup_step(args.isolation, args.target_file, args.receipt_out)


if __name__ == "__main__":
    raise SystemExit(main())
