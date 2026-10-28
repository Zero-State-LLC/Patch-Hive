"""Pydantic schemas for run APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from patches.schemas import PatchResponse


class RunResponse(BaseModel):
    """Legacy run row plus server-authored export bridge fields for /api/canon."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rack_id: int
    status: str
    created_at: datetime | None = None
    # Canon export bridge (OBSERVED server authority — do not re-derive on clients).
    rig_revision_id: str = Field(..., min_length=1, max_length=64)
    source_run_id: str = Field(..., min_length=1, max_length=64)
    artifact_manifest_hash: str = Field(..., min_length=64, max_length=64)
    export_bridge_ready: bool = False
    # Port resolution and validation report (spec 001 FR-016/FR-019).
    validation: dict | None = None


class RunListResponse(BaseModel):
    total: int
    runs: list[RunResponse]


class RunPatchesResponse(BaseModel):
    total: int
    patches: list[PatchResponse]
