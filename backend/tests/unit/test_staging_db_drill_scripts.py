"""scripts/staging/acceptance_staging.py and restore_drill.py: fail closed, counts-only receipts."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.ops.throwaway_db import TargetRefused

ROOT = Path(__file__).resolve().parents[3]
SOURCE = "postgresql://owner:s3cret-pw@ep-cool-name-123.us-west-2.aws.neon.tech/patchhive?sslmode=require"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"staging_{name}", ROOT / "scripts" / "staging" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"staging_{name}"] = module
    spec.loader.exec_module(module)
    return module


acceptance = _load("acceptance_staging")
drill = _load("restore_drill")

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" errors="0" failures="1" skipped="2" tests="40" time="93.5"/></testsuites>
"""


@pytest.fixture()
def github_env(monkeypatch, tmp_path):
    for key, value in {
        "GITHUB_RUN_ID": "77",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "a" * 40,
        "STAGING_SOURCE_URL": SOURCE,
        "STAGING_DATABASE_URL": SOURCE,
        "DATABASE_URL": SOURCE,
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("NEON_API_KEY", raising=False)
    return tmp_path


def test_junit_counts(tmp_path) -> None:
    path = tmp_path / "junit.xml"
    path.write_text(JUNIT, encoding="utf-8")
    assert acceptance.junit_counts(path) == {
        "total": 40, "failed": 1, "errors": 0, "skipped": 2, "passed": 37, "duration_seconds": 93.5
    }


def test_database_isolation_targets_a_throwaway_on_the_staging_server(github_env, monkeypatch) -> None:
    created: list[tuple[str, str]] = []
    monkeypatch.setattr(acceptance, "create_database", lambda admin, name: created.append((admin, name)))

    target = acceptance.provision("database", dict(os.environ))

    assert created == [(SOURCE, "patchhive_acceptance_77_1")]
    assert target == SOURCE.replace("/patchhive?", "/patchhive_acceptance_77_1?")


def test_provision_refuses_without_the_staging_secret(github_env, monkeypatch) -> None:
    monkeypatch.delenv("STAGING_SOURCE_URL")
    with pytest.raises(TargetRefused, match="PATCHHIVE_DATABASE_URL_STAGING"):
        acceptance.provision("database", dict(os.environ))


def test_neon_branch_isolation_refuses_without_the_key(github_env) -> None:
    with pytest.raises(TargetRefused, match="NEON_API_KEY"):
        acceptance.provision("neon-branch", dict(os.environ))


def test_the_suite_never_sees_the_staging_or_neon_secrets(github_env, monkeypatch) -> None:
    monkeypatch.setenv("NEON_API_KEY", "neon-key")
    env = acceptance._suite_env("postgresql://u:p@h/patchhive_acceptance_77_1")
    for hidden in ("STAGING_SOURCE_URL", "STAGING_DATABASE_URL", "DATABASE_URL", "NEON_API_KEY"):
        assert hidden not in env
    assert env["ACCEPTANCE_DATABASE_URL"].endswith("/patchhive_acceptance_77_1")
    assert env["STRIPE_TEST_MODE"] == "true" and env["ALLOW_PRODUCTION_PAYMENTS"] == "false"


def _fake_suite(monkeypatch, *, pytest_code: int = 0, current: str | None = None):
    calls: list[list[str]] = []
    target = "postgresql://owner:s3cret-pw@ep-cool-name-123.neon.tech/patchhive_acceptance_77_1"
    head = acceptance.alembic_head()
    monkeypatch.setattr(acceptance, "provision", lambda isolation, env: target)
    monkeypatch.setattr(acceptance, "teardown", lambda isolation, env: "dropped")
    monkeypatch.setattr(acceptance, "server_major", lambda url: 15)
    monkeypatch.setattr(acceptance, "current_revision", lambda url: head if current is None else current)

    def fake_run(command, cwd, env, check):
        calls.append(command)
        if "pytest" in command:
            # pytest resolves a relative --junitxml against its own working directory
            junit = next(arg for arg in command if arg.startswith("--junitxml="))
            Path(cwd, junit.split("=", 1)[1]).write_text(JUNIT.replace('failures="1"', f'failures="{pytest_code}"'))
        return subprocess.CompletedProcess(command, pytest_code if "pytest" in command else 0)

    monkeypatch.setattr(acceptance.subprocess, "run", fake_run)
    return calls


def _three_steps(directory: Path, isolation: str = "database") -> tuple[int, int, int]:
    target = directory / "runner-temp" / "acceptance-target"
    receipt = directory / "out" / "receipt.json"
    return (
        acceptance.provision_step(isolation, target, receipt),
        acceptance.suite_step(target, receipt),
        acceptance.cleanup_step(isolation, target, receipt),
    )


def test_provision_suite_cleanup_pass_and_leave_no_secret_behind(github_env, monkeypatch, capsys) -> None:
    calls = _fake_suite(monkeypatch)
    target_file = github_env / "runner-temp" / "acceptance-target"

    assert acceptance.provision_step("database", target_file, github_env / "out" / "receipt.json") == 0
    assert oct(target_file.stat().st_mode & 0o777) == "0o600"
    assert acceptance.suite_step(target_file, github_env / "out" / "receipt.json") == 0
    assert acceptance.cleanup_step("database", target_file, github_env / "out" / "receipt.json") == 0

    assert [c[2:4] for c in calls] == [["alembic", "upgrade"], ["pytest", "tests/acceptance"]]
    assert not target_file.exists()
    receipt_path = github_env / "out" / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["result"] == "pass" and receipt["teardown"] == {"status": "dropped"}
    assert receipt["throwaway"] == "created" and receipt["server_major"] == 15
    assert receipt["tests"]["passed"] == 38 and receipt["alembic"]["at_head"] is True
    rendered = receipt_path.read_text() + (github_env / "summary.md").read_text() + capsys.readouterr().out
    for secret in ("s3cret-pw", "ep-cool-name-123", "owner"):
        assert secret not in rendered


def test_the_workflows_relative_receipt_path_still_finds_the_junit_report(github_env, monkeypatch) -> None:
    # The workflow passes acceptance-artifacts/receipt.json from the repo root, and pytest runs in backend/.
    _fake_suite(monkeypatch)
    backend = github_env / "backend"
    backend.mkdir()
    monkeypatch.setattr(acceptance, "BACKEND", backend)
    monkeypatch.chdir(github_env)
    target = github_env / "runner-temp" / "acceptance-target"
    receipt = Path("acceptance-artifacts") / "receipt.json"

    assert acceptance.provision_step("database", target, receipt) == 0
    assert acceptance.suite_step(target, receipt) == 0
    assert json.loads(receipt.read_text())["tests"]["total"] == 40


def test_a_failing_suite_fails_the_suite_step_and_the_receipt(github_env, monkeypatch) -> None:
    _fake_suite(monkeypatch, pytest_code=1)
    assert _three_steps(github_env) == (0, 1, 0)
    assert json.loads((github_env / "out" / "receipt.json").read_text())["result"] == "fail"


def test_the_suite_is_skipped_when_migration_does_not_reach_head(github_env, monkeypatch) -> None:
    calls = _fake_suite(monkeypatch, current="older")
    assert _three_steps(github_env) == (0, 1, 0)
    assert [c[2] for c in calls] == ["alembic"]
    receipt = json.loads((github_env / "out" / "receipt.json").read_text())
    assert receipt["alembic"]["at_head"] is False and receipt["result"] == "fail"


def test_a_refused_target_still_tears_down_and_writes_a_receipt(github_env, monkeypatch) -> None:
    torn: list[str] = []

    def refuse(isolation, env):
        raise TargetRefused("refusing database 'patchhive'")

    monkeypatch.setattr(acceptance, "provision", refuse)
    monkeypatch.setattr(acceptance, "teardown", lambda isolation, env: torn.append(isolation) or "dropped")

    assert _three_steps(github_env) == (1, 1, 0)
    assert torn == ["database"]
    receipt = json.loads((github_env / "out" / "receipt.json").read_text())
    assert receipt["result"] == "fail" and "patchhive" in receipt["error"]


def test_the_suite_step_refuses_a_target_file_naming_patchhive(github_env, monkeypatch) -> None:
    calls = _fake_suite(monkeypatch)
    target_file = github_env / "acceptance-target"
    target_file.write_text(SOURCE)
    assert acceptance.suite_step(target_file, github_env / "receipt.json") == 1
    assert calls == []


def test_teardown_failure_fails_cleanup(github_env, monkeypatch) -> None:
    def broken(isolation, env):
        raise acceptance.ThrowawayError("DROP DATABASE failed (OperationalError, SQLSTATE None)")

    _fake_suite(monkeypatch)
    monkeypatch.setattr(acceptance, "teardown", broken)
    assert _three_steps(github_env) == (0, 0, 1)
    receipt = json.loads((github_env / "out" / "receipt.json").read_text())
    assert receipt["teardown"]["status"] == "failed" and receipt["result"] == "fail"


# restore_drill.py ------------------------------------------------------------------------


def _drill_dir(tmp_path: Path, *, reconcile_status: str | None = "ok", at_head: bool = True) -> Path:
    directory = tmp_path / "drill"
    directory.mkdir()
    counts = {"server_major": 15, "tables": {"users": 3, "canonical_credit_ledger": 7}}
    (directory / "source-before.json").write_text(json.dumps(counts))
    (directory / "source-after.json").write_text(json.dumps(counts))
    (directory / "dump.json").write_text(json.dumps({"format": "custom", "bytes": 10, "sha256": "f" * 64}))
    (directory / "head.json").write_text(json.dumps({"head": "h", "current": "h" if at_head else "g", "at_head": at_head}))
    if reconcile_status:
        (directory / "reconcile.json").write_text(json.dumps({"status": reconcile_status, "mismatch_count": 0}))
    return directory


@pytest.fixture()
def restored(monkeypatch):
    monkeypatch.setenv("RESTORED_DATABASE_URL", "postgresql://postgres:restore-drill@127.0.0.1:55432/patchhive_restore")
    monkeypatch.setattr(drill, "public_table_counts", lambda url: {"users": 3, "canonical_credit_ledger": 7})


def test_drill_receipt_passes_when_every_check_passed(tmp_path, restored, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    directory = _drill_dir(tmp_path)
    out = directory / "receipt.json"

    assert drill.receipt(directory, "staging", "RESTORED_DATABASE_URL", out) == 0

    receipt = json.loads(out.read_text())
    assert receipt["result"] == "pass" and receipt["problems"] == []
    assert receipt["counts"]["ok"] and receipt["counts"]["conclusive"]
    assert "127.0.0.1" not in out.read_text() and "postgres:" not in out.read_text()


@pytest.mark.parametrize(
    ("kwargs", "problem"),
    [
        ({"reconcile_status": None}, "ledger reconcile did not run"),
        ({"reconcile_status": "mismatch"}, "ledger reconcile on the restored copy did not pass"),
        ({"at_head": False}, "restored copy is not at alembic head"),
    ],
)
def test_drill_receipt_fails_on_any_failed_or_missing_check(tmp_path, restored, monkeypatch, kwargs, problem) -> None:
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    directory = _drill_dir(tmp_path, **kwargs)
    out = directory / "receipt.json"
    assert drill.receipt(directory, "prod", "RESTORED_DATABASE_URL", out) == 1
    receipt = json.loads(out.read_text())
    assert receipt["result"] == "fail" and problem in receipt["problems"]


def test_drill_receipt_fails_when_rows_were_lost(tmp_path, restored, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setattr(drill, "public_table_counts", lambda url: {"users": 3, "canonical_credit_ledger": 6})
    directory = _drill_dir(tmp_path)
    assert drill.receipt(directory, "staging", "RESTORED_DATABASE_URL", directory / "receipt.json") == 1


def test_drill_receipt_fails_without_a_dump(tmp_path, restored, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    directory = _drill_dir(tmp_path)
    (directory / "dump.json").unlink()
    assert drill.receipt(directory, "staging", "RESTORED_DATABASE_URL", directory / "receipt.json") == 1


def test_drill_requires_its_url_variable(monkeypatch) -> None:
    monkeypatch.delenv("SOURCE_DATABASE_URL", raising=False)
    with pytest.raises(drill.DrillError, match="SOURCE_DATABASE_URL is not set"):
        drill._url("SOURCE_DATABASE_URL")


# mask_db_url.sh --------------------------------------------------------------------------


def _mask(url: str) -> list[str]:
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts" / "staging" / "mask_db_url.sh"), "DB_URL"],
        env={"PATH": os.environ["PATH"], "DB_URL": url},
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.splitlines()


def test_mask_script_masks_url_password_and_host() -> None:
    url = "postgresql+psycopg2://owner:s3cret-pw@ep-cool-name-123.us-west-2.aws.neon.tech:5432/patchhive?sslmode=require"
    assert _mask(url) == [
        f"::add-mask::{url}",
        "::add-mask::" + url.replace("postgresql+psycopg2://", "postgresql://"),
        "::add-mask::s3cret-pw",
        "::add-mask::ep-cool-name-123.us-west-2.aws.neon.tech",
    ]


def test_mask_script_handles_an_at_sign_in_the_password_and_no_port() -> None:
    lines = _mask("postgresql://owner:p%40ss@word@db.example.com/patchhive")
    assert "::add-mask::p%40ss@word" in lines and "::add-mask::db.example.com" in lines
    assert all(line.startswith("::add-mask::") for line in lines)


def test_mask_script_prints_nothing_for_an_empty_variable() -> None:
    assert _mask("") == []


def test_python_drill_scripts_never_print_mask_commands() -> None:
    for name in ("acceptance_staging.py", "restore_drill.py"):
        assert "add-mask" not in (ROOT / "scripts" / "staging" / name).read_text(encoding="utf-8")
