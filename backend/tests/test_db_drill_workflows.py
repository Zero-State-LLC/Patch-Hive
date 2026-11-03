"""Acceptance and restore-drill workflows stay manual, fail closed and upload counts only."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _load(name: str) -> tuple[str, dict]:
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    return text, yaml.safe_load(text)


def _triggers(workflow: dict) -> dict:
    # PyYAML reads the bare key `on` as True.
    return workflow.get("on") or workflow.get(True)


def test_ci_runs_the_acceptance_suite_on_its_own_database() -> None:
    _text, ci = _load("ci.yml")
    job = ci["jobs"]["acceptance"]
    url = job["env"]["ACCEPTANCE_DATABASE_URL"]
    assert url.endswith("/patchhive_acceptance")
    assert job["services"]["postgres"]["env"]["POSTGRES_DB"] == "patchhive_acceptance"
    runs = [step.get("run", "") for step in job["steps"]]
    assert "python -m pytest tests/acceptance -q" in runs
    # The unit/api job still leaves acceptance to its own job.
    assert "--ignore=tests/acceptance" in " ".join(s.get("run", "") for s in ci["jobs"]["backend"]["steps"])


def test_acceptance_staging_is_manual_staging_only_and_cleans_up() -> None:
    text, workflow = _load("acceptance-staging.yml")
    assert set(_triggers(workflow)) == {"workflow_dispatch"}
    isolation = _triggers(workflow)["workflow_dispatch"]["inputs"]["isolation"]
    assert isolation["default"] == "database" and isolation["options"] == ["database", "neon-branch"]
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["group"] == "neon-db-staging"
    job = workflow["jobs"]["acceptance"]
    assert job["environment"] == "staging"
    assert "PATCHHIVE_DATABASE_URL_PROD" not in text
    # The conftest falls back to STAGING_DATABASE_URL; the workflow must never set it.
    assert "STAGING_DATABASE_URL" not in text
    steps = {step.get("name"): step for step in job["steps"]}
    cleanup = steps["Remove the throwaway database or branch"]
    assert cleanup["if"] == "always()" and "acceptance_staging.py cleanup" in cleanup["run"]
    upload = steps["Keep the counts-only receipt"]
    assert upload["with"]["path"] == "acceptance-artifacts/receipt.json"
    assert "set -x" not in text and "echo " not in text


def test_restore_drill_gates_production_before_loading_secrets() -> None:
    text, workflow = _load("db-restore-drill.yml")
    inputs = _triggers(workflow)["workflow_dispatch"]["inputs"]
    assert set(_triggers(workflow)) == {"workflow_dispatch"}
    assert inputs["env"]["default"] == "staging" and inputs["env"]["options"] == ["staging", "prod"]
    assert inputs["confirm_production"]["default"] == ""
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["group"] == "neon-db-${{ inputs.env }}"
    gate = workflow["jobs"]["gate"]
    assert "environment" not in gate and "secrets." not in str(gate)
    assert '[ "$CONFIRM" != "dump production read-only" ]' in gate["steps"][0]["run"]
    drill = workflow["jobs"]["drill"]
    assert drill["needs"] == "gate"
    assert drill["environment"] == "${{ inputs.env == 'prod' && 'production' || 'staging' }}"
    assert "set -x" not in text and "echo " not in text


def test_restore_drill_never_uploads_the_dump_and_checks_head_and_ledger() -> None:
    _text, workflow = _load("db-restore-drill.yml")
    steps = workflow["jobs"]["drill"]["steps"]
    names = [step.get("name", "") for step in steps]
    runs = {step.get("name", ""): step.get("run", "") for step in steps}
    assert "--format=custom" in runs["pg_dump the source (the dump stays on this runner)"]
    assert "--exit-on-error" in runs["pg_restore into the runner's Postgres"]
    remove = next(step for step in steps if step.get("name") == "Remove the dump")
    assert remove["if"] == "always()" and remove["run"] == 'rm -f "$DRILL_DIR/source.dump"'
    upload_index = names.index("Upload counts-only receipt")
    assert names.index("Remove the dump") < upload_index
    upload = steps[upload_index]
    assert upload["with"]["path"] == "drill-artifacts/receipt.json"
    assert "restore_drill.py head" in runs["alembic current on the restored copy is head"]
    assert "python -m alembic current" in runs["alembic current on the restored copy is head"]
    assert "python -m canon.reconcile_all" in runs["Reconcile the ledger on the restored copy"]
    receipt = next(step for step in steps if step.get("name") == "Receipt")
    assert receipt["if"] == "always()"
    # Source secrets reach only the steps that read the source.
    with_source = [step["name"] for step in steps if "SOURCE_DATABASE_URL" in str(step.get("env", {}))]
    assert with_source == [
        "Source counts before the dump (read-only)",
        "pg_dump the source (the dump stays on this runner)",
        "Source counts after the dump (read-only)",
    ]
