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

Environment:
  STAGING_SOURCE_URL   staging connection string (required; never printed)
  GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT   name the throwaway target (digits)
  NEON_API_KEY, NEON_PROJECT_ID, NEON_PARENT_BRANCH   neon-branch only

Usage (repo root):
  python scripts/staging/acceptance_staging.py run --isolation database --receipt-out receipt.json
  python scripts/staging/acceptance_staging.py cleanup --isolation database

``cleanup`` is idempotent; the workflow runs it after ``run`` whatever happened, so a
cancelled run does not leave a database or branch behind.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path

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
    secret_parts,
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


def _mask(url: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for part in secret_parts(url):
            print(f"::add-mask::{part}", flush=True)


def _neon(env: dict[str, str]) -> NeonBranches:
    return NeonBranches(
        env.get("NEON_API_KEY", "").strip(),
        env.get("NEON_PROJECT_ID", "").strip() or DEFAULT_NEON_PROJECT,
    )


def provision(isolation: str, env: dict[str, str]) -> str:
    """Create the throwaway target and return its URL (masked, never printed)."""
    source = _source_url(env)
    _mask(source)
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
    _mask(target)
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


def run(isolation: str, receipt_out: Path) -> int:
    env = dict(os.environ)
    head = alembic_head()
    receipt: dict[str, object] = {
        "kind": "acceptance-staging",
        "isolation": isolation,
        "source_sha": env.get("GITHUB_SHA", ""),
        "run_id": env.get("GITHUB_RUN_ID", ""),
        "run_attempt": env.get("GITHUB_RUN_ATTEMPT", ""),
        "alembic": {"head": head},
        "result": "fail",
    }
    junit = receipt_out.parent / "acceptance-junit.xml"
    receipt_out.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    tests_ok = False
    try:
        target = provision(isolation, env)
        receipt["throwaway"] = "created"
        receipt["server_major"] = server_major(target)
        migrate = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND,
            env={**_suite_env(target), "DATABASE_URL": target},
            check=False,
        )
        current = current_revision(target)
        receipt["alembic"] = {
            "head": head,
            "current": current,
            "at_head": current == head,
        }
        if migrate.returncode != 0 or current != head:
            print("::error::the throwaway database did not migrate to head", flush=True)
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
            tests_ok = (
                suite.returncode == 0
                and bool(counts.get("total"))
                and not counts.get("failed")
                and not counts.get("errors")
            )
    except (TargetRefused, ThrowawayError, DrillError) as exc:
        print(f"::error::{exc}", flush=True)
        receipt["error"] = str(exc)
    except httpx.HTTPError as exc:
        print(f"::error::Neon API request failed ({exc.__class__.__name__})", flush=True)
        receipt["error"] = f"Neon API request failed ({exc.__class__.__name__})"
    finally:
        try:
            receipt["teardown"] = {"status": teardown(isolation, env)}
        except (TargetRefused, ThrowawayError, httpx.HTTPError) as exc:
            print(f"::error::teardown: {_describe(exc)}", flush=True)
            receipt["teardown"] = {"status": "failed", "error": _describe(exc)}
        receipt["wall_seconds"] = round(time.monotonic() - started, 1)
        teardown_ok = receipt["teardown"]["status"] != "failed"  # type: ignore[index]
        receipt["result"] = "pass" if tests_ok and teardown_ok else "fail"
        receipt_out.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _summary(summary_markdown(f"Acceptance on Neon staging ({isolation})", receipt))
    return 0 if receipt["result"] == "pass" else 1


def cleanup(isolation: str) -> int:
    try:
        print(json.dumps({"teardown": teardown(isolation, dict(os.environ))}))
    except (TargetRefused, ThrowawayError, httpx.HTTPError) as exc:
        print(f"::error::teardown: {_describe(exc)}", flush=True)
        return 1
    return 0


def _describe(exc: Exception) -> str:
    # httpx messages carry the request URL; the class name is enough.
    return (
        f"Neon API request failed ({exc.__class__.__name__})"
        if isinstance(exc, httpx.HTTPError)
        else str(exc)
    )


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
    run_cmd = commands.add_parser(
        "run", help="provision, migrate, run the suite, tear down, write the receipt"
    )
    run_cmd.add_argument("--isolation", choices=ISOLATIONS, required=True)
    run_cmd.add_argument("--receipt-out", type=Path, required=True)
    cleanup_cmd = commands.add_parser(
        "cleanup", help="remove this run's throwaway target if it still exists"
    )
    cleanup_cmd.add_argument("--isolation", choices=ISOLATIONS, required=True)
    args = parser.parse_args(argv)
    if args.command == "run":
        return run(args.isolation, args.receipt_out)
    return cleanup(args.isolation)


if __name__ == "__main__":
    raise SystemExit(main())
