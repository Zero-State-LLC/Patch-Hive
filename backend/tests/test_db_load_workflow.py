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
    # Apply names both hashes of the reviewed dry run (spec 003 FR-020, OQ-9).
    assert "PATCHHIVE_PLAN_HASH: ${{ inputs.plan_hash }}" in text
    assert "PATCHHIVE_INPUTS_HASH: ${{ inputs.inputs_hash }}" in text
    assert "set -x" not in text
    assert "echo " not in text
    permissions = text[text.index("\npermissions:"):text.index("\nconcurrency:")]
    assert "contents: read" in permissions
    assert "actions: write" not in text
    assert "neon-db-${{ inputs.env }}" in text
    migrate = (ROOT / ".github" / "workflows" / "db-migrate.yml").read_text(encoding="utf-8")
    assert "neon-db-${{ inputs.target }}" in migrate


def test_actions_summary_reports_the_module_type_sync() -> None:
    # Decision 51: the summary is what the owner reads before approving a production load.
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import catalog_actions_load as loader

    sync = {"synced": 55, "by_category": {"VIDEO": 24}, "left_alone_other_value": 3, "left_alone_not_loader_row": 1}
    receipt = {"plan_hash": "a", "inputs_hash": "b", "conflicts_total": 0, "run_id": "r", "module_type_sync": sync}
    summary = loader._summary({"modules": 1}, {"modules": 1}, "dry-run", "prod", receipt)
    assert "module_type set from the catalog category: 55 {'VIDEO': 24}" in summary
    assert "left alone: 3 with another value, 1 not loader rows" in summary
    assert "row_key" not in summary  # counts only: the repo and its artifacts are public


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
    receipt = {"plan_hash": "a" * 64, "inputs_hash": "b" * 64, "conflicts_total": 0, "run_id": "1"}
    dry = loader._summary({"modules": 1}, {"modules": 1}, "dry-run", "staging", receipt)
    assert f"plan_hash: `{'a' * 64}`" in dry
    assert f"inputs_hash: `{'b' * 64}`" in dry


def test_actions_apply_requires_both_reviewed_hashes(monkeypatch, tmp_path: Path) -> None:
    """The Actions loader asks populate to check plan_hash and inputs_hash on apply only."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import catalog_actions_load as loader

    seen: dict = {}

    def fake_populate(database_url, **kwargs):
        seen.update(kwargs)
        raise SystemExit("stop")

    monkeypatch.setattr(loader, "assert_at_head", lambda url: "head")
    monkeypatch.setattr(loader, "table_counts", lambda url: {"modules": 0})
    monkeypatch.setattr(loader, "dump_affected_tables", lambda url, path: None)
    monkeypatch.setattr(loader, "populate", fake_populate)
    monkeypatch.setattr(loader, "_write_summary", lambda text: None)
    monkeypatch.setattr(loader, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(sys, "argv", ["catalog_actions_load.py", "--allow-nonlocal"])
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example/x")
    monkeypatch.setenv("PATCHHIVE_DB_ENV", "staging")
    for mode, required in (("apply", True), ("dry-run", False)):
        seen.clear()
        monkeypatch.setenv("PATCHHIVE_LOAD_MODE", mode)
        monkeypatch.setenv("PATCHHIVE_PLAN_HASH", "a" * 64)
        monkeypatch.setenv("PATCHHIVE_INPUTS_HASH", " " + "b" * 64 + " ")
        try:
            loader.main()
        except SystemExit:
            pass
        assert seen["require_plan_hash"] is required and seen["require_inputs_hash"] is required
        assert seen["expected_plan_hash"] == "a" * 64 and seen["expected_inputs_hash"] == "b" * 64


def test_edge_secrets_revokes_new_token_when_write_fails() -> None:
    text = (ROOT / ".github" / "workflows" / "edge-secrets.yml").read_text(encoding="utf-8")
    assert "id: write" in text
    step = text[text.index("- name: Revoke the new R2 token after a failed write"):text.index("- name: Clean up")]
    assert "if: failure() && env.NEW_R2_TOKEN_ID != '' && steps.write.conclusion != 'success'" in step
    assert 'os.environ["NEW_R2_TOKEN_ID"]' in step
    assert 'method="DELETE"' in step
    assert "print(token" not in step
    # The older-token revoke must stay after the write, and the new-token revoke after both.
    assert text.index("id: write") < text.index("- name: Revoke older R2 tokens for this Worker") < text.index(
        "- name: Revoke the new R2 token after a failed write"
    )


def test_pin_pr_workflow_removed() -> None:
    assert not (ROOT / ".github" / "workflows" / "deploy-worker-pin-pr.yml").exists()


def test_prod_workflows_set_job_environment() -> None:
    """Prod runs of all three workflows must go through the `production` environment."""
    import yaml

    expected = {
        "db-migrate.yml": ("migrate", "inputs.target == 'prod'"),
        "db-load.yml": ("load", "inputs.env == 'prod'"),
        "edge-secrets.yml": ("secrets", "inputs.env == 'production'"),
    }
    for name, (job, condition) in expected.items():
        doc = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
        assert list(doc["jobs"]) == [job], name
        assert doc["jobs"][job]["environment"] == (
            "${{ " + condition + " && 'production' || 'staging' }}"
        ), name
