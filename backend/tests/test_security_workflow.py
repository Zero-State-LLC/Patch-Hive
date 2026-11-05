"""CI must keep running what docs/SECURITY.md says it runs (#264)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_security_workflow_runs_every_claimed_check() -> None:
    text = _workflow("security.yml")
    for check in (
        "python -m pip_audit",
        "python -m bandit",
        "npm run audit",
        "cyclonedx-py environment",
        "npm sbom",
        "detect --source .",
    ):
        assert check in text
    assert "pull_request" in text
    # A check that can't fail claims nothing.
    assert "|| true" not in text
    assert "continue-on-error" not in text


def test_secret_scan_covers_history_redacts_and_pins_its_binary() -> None:
    text = _workflow("security.yml")
    assert "fetch-depth: 0" in text
    assert "--redact" in text
    assert "--config .gitleaks.toml" in text
    assert "sha256sum --check" in text
    # gitleaks-action needs a paid licence for organisations; the binary is MIT.
    assert "gitleaks/gitleaks-action" not in text


def test_ci_runs_backend_lint_types_and_import_guard() -> None:
    text = _workflow("ci.yml")
    lint = text[text.index("backend-lint:") :]
    for check in (
        "python -m ruff check",
        "python -m black --check",
        "python -m mypy",
        "check_no_canon_patchhive_imports.sh",
    ):
        assert check in lint
