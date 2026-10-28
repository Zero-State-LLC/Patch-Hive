"""Startup migrations are opt-in: a cold start must never migrate unless RUN_MIGRATIONS opts in."""

from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
ROOT = BACKEND.parent
ENTRYPOINT = BACKEND / "docker-entrypoint.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def _run_entrypoint(tmp_path: Path, run_migrations: str | None, *, database_url: str | None = None):
    """Run the real entrypoint with a stub `python` that records its arguments."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "python.log"
    stub = bin_dir / "python"
    stub.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{log}"\nexit 0\n', encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}", "HOME": str(tmp_path)}
    if run_migrations is not None:
        env["RUN_MIGRATIONS"] = run_migrations
    if database_url is not None:
        env["DATABASE_URL"] = database_url
    result = subprocess.run(
        ["bash", str(ENTRYPOINT), "true"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, calls


def _migrated(calls: list[str]) -> bool:
    return any("alembic upgrade head" in call for call in calls)


def test_unset_does_not_migrate(tmp_path: Path) -> None:
    result, calls = _run_entrypoint(tmp_path, None)
    assert result.returncode == 0, result.stderr
    assert not _migrated(calls)
    assert "Startup migrations disabled" in result.stdout


@pytest.mark.parametrize("value", ["false", "", "0", "TRUE", "yes", " true"])
def test_non_opt_in_values_do_not_migrate(tmp_path: Path, value: str) -> None:
    result, calls = _run_entrypoint(tmp_path, value)
    assert result.returncode == 0, result.stderr
    assert not _migrated(calls)


@pytest.mark.parametrize("value", ["true", "1"])
def test_opt_in_migrates(tmp_path: Path, value: str) -> None:
    result, calls = _run_entrypoint(tmp_path, value)
    assert result.returncode == 0, result.stderr
    assert _migrated(calls)
    assert "Migrations applied." in result.stdout


def test_disabled_runs_read_only_check_and_never_migrates(tmp_path: Path) -> None:
    # sqlite skips the DB wait; the stub records the schema check instead of running it.
    result, calls = _run_entrypoint(tmp_path, "false", database_url="sqlite:///unused.db")
    assert result.returncode == 0, result.stderr
    assert not _migrated(calls)
    assert any("check_schema_head.py" in call for call in calls)


def _load_schema_check():
    spec = importlib.util.spec_from_file_location(
        "check_schema_head", BACKEND / "scripts" / "check_schema_head.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_schema_check_warns_when_behind_and_is_silent_at_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check = _load_schema_check()
    heads = check.code_heads()
    assert len(heads) == 1
    monkeypatch.setattr(check, "database_revisions", lambda _url: set())
    message = check.check("sqlite://")
    assert message is not None and "db-migrate" in message
    monkeypatch.setattr(check, "database_revisions", lambda _url: set(heads))
    assert check.check("sqlite://") is None
    assert check.check(None) is None


def test_schema_check_never_fails_startup(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    check = _load_schema_check()

    def boom(_url: str) -> set[str]:
        raise RuntimeError("postgresql://user:secret@host/db")

    monkeypatch.setattr(check, "database_revisions", boom)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@host/db")
    assert check.main() == 0
    captured = capsys.readouterr()
    assert "secret" not in captured.out + captured.err


def test_schema_check_reads_empty_sqlite_as_behind(tmp_path: Path) -> None:
    check = _load_schema_check()
    url = f"sqlite:///{tmp_path / 'empty.db'}"
    assert check.database_revisions(url) == set()
    assert check.check(url) is not None


def test_cloudflare_workers_do_not_opt_in() -> None:
    wrangler = (ROOT / "edge" / "api" / "wrangler.jsonc").read_text(encoding="utf-8")
    assert '"RUN_MIGRATIONS"' not in wrangler
    worker = (ROOT / "edge" / "api" / "src" / "index.ts").read_text(encoding="utf-8")
    assert 'RUN_MIGRATIONS: "true"' not in worker
    assert "RUN_MIGRATIONS: runMigrations(env.RUN_MIGRATIONS)" in worker
    assert 'value === "true" || value === "1" ? "true" : "false"' in worker


def test_images_do_not_default_migrations_on() -> None:
    for dockerfile in (BACKEND / "Dockerfile", ROOT / "Dockerfile.backend"):
        assert "ENV RUN_MIGRATIONS" not in dockerfile.read_text(encoding="utf-8"), dockerfile
    assert 'RUN_MIGRATIONS="${RUN_MIGRATIONS:-false}"' in ENTRYPOINT.read_text(encoding="utf-8")
