"""The API reports the package version from backend/pyproject.toml (one source of truth)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

from core import get_db
from core.version import PYPROJECT_PATH, UNKNOWN_VERSION, read_package_version
from main import app

_PYPROJECT_VERSION = tomllib.loads(PYPROJECT_PATH.read_text())["project"]["version"]


def test_read_package_version_matches_pyproject() -> None:
    assert read_package_version() == _PYPROJECT_VERSION
    assert _PYPROJECT_VERSION != "0.1.0"


def test_read_package_version_fails_soft(tmp_path: Path) -> None:
    assert read_package_version(tmp_path / "missing.toml") == UNKNOWN_VERSION
    bad = tmp_path / "pyproject.toml"
    bad.write_text("not [valid toml")
    assert read_package_version(bad) == UNKNOWN_VERSION
    bad.write_text("[tool.x]\na = 1\n")
    assert read_package_version(bad) == UNKNOWN_VERSION


def test_health_reports_package_version() -> None:
    body = TestClient(app).get("/health").json()
    assert body["version"] == _PYPROJECT_VERSION
    assert set(body) == {"status", "app", "version", "abx_core_version"}


def test_health_ready_reports_package_version(db_session) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        resp = TestClient(app).get("/health/ready")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == _PYPROJECT_VERSION
    assert set(body) == {"status", "app", "version", "abx_core_version", "database"}


def test_dockerfile_ships_pyproject_next_to_core() -> None:
    backend = PYPROJECT_PATH.parent
    ignored = (backend / ".dockerignore").read_text().split()
    assert "pyproject.toml" not in ignored
    assert "COPY . ." in (backend / "Dockerfile").read_text()
