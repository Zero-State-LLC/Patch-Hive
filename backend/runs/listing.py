"""Shared run listing with export bridge enrichment. Read-only (spec 001 FR-020)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from runs.bridge import recorded_run_bridge
from runs.models import Run
from runs.schemas import RunListResponse, RunResponse


def build_run_response(db: Session, run: Run) -> RunResponse:
    bridge = recorded_run_bridge(db, run)
    return RunResponse(
        id=int(run.id),  # type: ignore[arg-type]
        rack_id=int(run.rack_id),  # type: ignore[arg-type]
        status=str(run.status),
        created_at=run.created_at,  # type: ignore[arg-type]
        rig_revision_id=bridge.rig_revision_id,
        source_run_id=bridge.source_run_id,
        artifact_manifest_hash=bridge.artifact_manifest_hash,
        export_bridge_ready=bridge.export_bridge_ready,
    )


def list_runs_for_rack(db: Session, rack_id: int) -> RunListResponse:
    runs = (
        db.query(Run)
        .filter(Run.rack_id == rack_id)
        .order_by(Run.created_at.desc())
        .all()
    )
    payload = [build_run_response(db, run) for run in runs]
    return RunListResponse(total=len(payload), runs=payload)
