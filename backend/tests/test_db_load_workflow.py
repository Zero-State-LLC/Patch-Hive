"""The manual load workflow must stay fail-closed and must not print the URL."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_db_load_workflow_contract() -> None:
    text = (ROOT / ".github" / "workflows" / "db-load.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in text
    assert "default: dry-run" in text
    assert "options: [dry-run, apply]" in text
    assert "PATCHHIVE_DATABASE_URL_STAGING" in text
    assert "PATCHHIVE_DATABASE_URL_PROD" in text
    assert "actions/upload-artifact@v4" in text
    # Public repo: raw dumps and row-level SQL must never be uploaded as artifacts.
    assert "catalog-load-pre-apply" not in text
    assert "rm -f load-artifacts/pre-apply.dump load-artifacts/population-upsert.sql" in text
    upload = text[text.index("actions/upload-artifact@v4"):]
    assert "pre-apply.dump" not in upload
    assert "population-upsert.sql" not in upload
    assert "test -s load-artifacts/pre-apply.dump" in text
    assert "catalog_actions_load.py --allow-nonlocal" in text
    assert "set -x" not in text
    assert "echo " not in text
    assert "neon-db-${{ inputs.env }}" in text
    migrate = (ROOT / ".github" / "workflows" / "db-migrate.yml").read_text(encoding="utf-8")
    assert "neon-db-${{ inputs.target }}" in migrate


def test_actions_summary_shape(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import catalog_actions_load as loader

    summary = loader._summary({"modules": 1, "manufacturers": 2}, {"modules": 4, "manufacturers": 2}, "dry-run", "staging")
    assert "| modules | 1 | 4 | 3 |" in summary
    assert "| manufacturers | 2 | 2 | 0 |" in summary
    assert "staging" in summary
    early = loader._summary({"modules": 0}, None, "apply", "prod")
    assert "stopped early" in early
