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


def test_no_workflow_looks_up_a_secret_by_expression() -> None:
    # `secrets[...]` makes Actions hand every org and repo secret to the runner.
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        assert "secrets[" not in path.read_text(encoding="utf-8"), path.name


def test_a_missing_prod_secret_cannot_fall_through_to_staging() -> None:
    # `a && secret || other` would pick `other` when the secret is empty, so each branch tests
    # the target and the expression ends empty, which the job then refuses.
    for name, target in (
        ("db-load.yml", "inputs.env == 'prod'"),
        ("db-migrate.yml", "inputs.target == 'prod'"),
        ("db-restore-drill.yml", "inputs.env == 'prod'"),
        ("edge-secrets.yml", "inputs.env == 'production'"),
    ):
        text = _workflow(name)
        other = target.replace("==", "!=")
        assert (
            f"{target} && secrets.PATCHHIVE_DATABASE_URL_PROD"
            f" || {other} && secrets.PATCHHIVE_DATABASE_URL_STAGING || ''"
        ) in text, name
