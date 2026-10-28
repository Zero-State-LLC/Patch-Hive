"""
FastAPI routes for Patch management and generation.
"""

from dataclasses import asdict
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from community.auth import get_current_user, require_auth
from community.models import User
from core import get_db, settings
from racks.access import owned_patch, owned_rack, readable_patch, readable_patches
from runs.bridge import ensure_legacy_run_export_bridge
from runs.models import Run

from .engine import PatchEngineConfig, generate_patches_with_ir
from .models import Patch
from .schemas import (
    GeneratePatchesRequest,
    GeneratePatchesResponse,
    PatchCreate,
    PatchListResponse,
    PatchResponse,
    PatchUpdate,
)

router = APIRouter()

# What an owner may change on a generated patch: a display label and visibility.
GENERATED_PATCH_EDITABLE = {"name_override", "is_public"}


@router.post("/", response_model=PatchResponse, status_code=201)
def create_patch(
    patch: PatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Create a hand-made patch on a rack the caller owns.

    A run's patches come only from generation; runs are append-only (spec 001
    FR-020), so a hand-made patch cannot join one, not even the caller's own.
    """
    owned_rack(db, patch.rack_id, current_user)
    if patch.run_id is not None:
        raise HTTPException(status_code=400, detail="RUN_IS_APPEND_ONLY")

    tags = patch.tags or _derive_tags(patch.connections)
    db_patch = Patch(
        rack_id=patch.rack_id,
        run_id=None,
        name=patch.name,
        suggested_name=patch.suggested_name,
        name_override=patch.name_override,
        category=patch.category,
        description=patch.description,
        connections=patch.connections,
        generation_seed=patch.generation_seed,
        generation_version=patch.generation_version,
        engine_config=patch.engine_config or {},
        waveform_params=patch.waveform_params or {},
        is_public=patch.is_public,
        tags=tags,
    )
    db.add(db_patch)
    db.commit()
    db.refresh(db_patch)
    return build_patch_response(db, db_patch)


@router.get("/", response_model=PatchListResponse)
def list_patches(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    rack_id: Optional[int] = None,
    run_id: Optional[int] = None,
    category: Optional[str] = None,
    is_public: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List the patches the caller may read, with optional filters."""
    query = readable_patches(db.query(Patch), current_user)

    # Apply filters
    if rack_id is not None:
        query = query.filter(Patch.rack_id == rack_id)
    if run_id is not None:
        query = query.filter(Patch.run_id == run_id)
    if category is not None:
        query = query.filter(Patch.category == category)
    if is_public is not None:
        query = query.filter(Patch.is_public == is_public)

    total = query.count()
    patches = query.offset(skip).limit(limit).all()

    patch_responses = [build_patch_response(db, p) for p in patches]

    return PatchListResponse(total=total, patches=patch_responses)


@router.get("/{patch_id}", response_model=PatchResponse)
def get_patch(
    patch_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Get a specific patch by ID."""
    patch = readable_patch(db, patch_id, current_user)

    return build_patch_response(db, patch)


@router.patch("/{patch_id}", response_model=PatchResponse)
def update_patch(
    patch_id: int,
    patch_update: PatchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Update a patch (rack owner only).

    A generated patch (one with a run) is append-only (spec 001 FR-020): its name and
    description are what the engine produced. The owner may still set a display
    label (``name_override``) and visibility; the label never replaces ``name``.
    """
    db_patch = owned_patch(db, patch_id, current_user)

    update_data = patch_update.model_dump(exclude_unset=True)
    generated = db_patch.run_id is not None
    if generated and set(update_data) - GENERATED_PATCH_EDITABLE:
        raise HTTPException(status_code=409, detail="GENERATED_PATCH_IS_APPEND_ONLY")
    for field, value in update_data.items():
        setattr(db_patch, field, value)

    if "name_override" in update_data and not generated:
        if patch_update.name_override:
            db_patch.name = patch_update.name_override
        else:
            db_patch.name = db_patch.suggested_name or db_patch.name

    db.commit()
    db.refresh(db_patch)

    return build_patch_response(db, db_patch)


@router.delete("/{patch_id}", status_code=204)
def delete_patch(
    patch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Delete a hand-made patch (rack owner only). Generated patches stay (FR-020)."""
    db_patch = owned_patch(db, patch_id, current_user)
    if db_patch.run_id is not None:
        raise HTTPException(status_code=409, detail="GENERATED_PATCH_IS_APPEND_ONLY")

    db.delete(db_patch)
    db.commit()
    return None


@router.post("/generate/{rack_id}", response_model=GeneratePatchesResponse)
def generate_patches(
    rack_id: int,
    request: GeneratePatchesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Generate patches for a rack the caller owns, using the patch engine."""
    rack = owned_rack(db, rack_id, current_user)

    # Build engine config
    config = PatchEngineConfig(
        max_patches=request.max_patches or settings.max_patches_per_generation,
        allow_feedback=request.allow_feedback,
        prefer_simple=request.prefer_simple,
    )

    seed = settings.default_generation_seed if request.seed is None else request.seed

    # Readiness first (spec 001 FR-022): a rack that cannot be computed gets a
    # NOT_COMPUTABLE answer and no run, generation record or library. The inventory
    # revision is kept: it is the evidence of what was checked.
    from canon.inventory_persist import persist_system_inventory_revision
    from patches.inventory_gate import evaluate_rack_inventory_gate

    gate_report, _ = evaluate_rack_inventory_gate(db, rack)
    if not gate_report.ready:
        persist_system_inventory_revision(db, gate_report.inventory, rack_id=int(rack.id))
        db.commit()
        return GeneratePatchesResponse(
            generated_count=0,
            patches=[],
            run_id=None,
            inventory_revision_id=gate_report.inventory.inventory_revision_id,
            inventory_gate_code=gate_report.code,
            generation_status="NOT_COMPUTABLE",
        )

    # Run lifecycle (FR-018): queued, then running, then succeeded or failed. Each
    # step is committed, so the record shows how far a run got.
    run = Run(rack_id=rack_id, status="queued")
    db.add(run)
    db.commit()
    db.refresh(run)
    # Matrix slice A: ensure canon FK targets + export bridge as soon as the run exists
    # (do not rely solely on GET /api/runs side-effect).
    bridge = ensure_legacy_run_export_bridge(
        db, run, generation_seed=seed, generator_version=settings.patch_engine_version
    )
    # F3 dual-write audit: generate must never mint legacy-* bridge ids when rack exists.
    if bridge.export_bridge_ready and (
        bridge.rig_revision_id.startswith("legacy-") or bridge.source_run_id.startswith("legacy-")
    ):
        raise HTTPException(
            status_code=500,
            detail="EXPORT_BRIDGE_LEGACY_ID_FORBIDDEN",
        )
    run.status = "running"
    db.commit()

    try:
        generation_ir, patch_graphs, provenance = generate_patches_with_ir(
            db, rack, seed=seed, config=config
        )
    except Exception:
        db.rollback()
        run.status = "failed"
        db.commit()
        raise

    # Save patches to database with full IR/provenance for deterministic replay.
    saved_patches = []
    ir_dict = generation_ir.to_dict()
    provenance_dict = provenance.to_dict()
    metrics = provenance_dict.get("metrics") or {}
    inventory_revision_id = metrics.get("inventory_revision_id")
    if not inventory_revision_id and isinstance(metrics.get("inventory_gate"), dict):
        inventory_revision_id = metrics["inventory_gate"].get("inventory_revision_id")
    inventory_gate_code = None
    if isinstance(metrics.get("inventory_gate"), dict):
        inventory_gate_code = metrics["inventory_gate"].get("code")
    generation_status = metrics.get("generation_status")
    for spec in patch_graphs:
        tags = _derive_tags([c.to_dict() for c in spec.connections])
        db_patch = Patch(
            rack_id=rack_id,
            run_id=run.id,
            name=spec.patch_name,
            category=spec.category,
            description=spec.description,
            connections=[c.to_dict() for c in spec.connections],
            generation_seed=spec.generation_seed,
            generation_version=settings.patch_engine_version,
            suggested_name=spec.patch_name,
            engine_config=config.__dict__,
            provenance=provenance_dict,
            generation_ir=ir_dict,
            generation_ir_hash=getattr(spec, "generation_ir_hash", None),
            is_public=False,
            tags=tags,
        )
        db.add(db_patch)
        saved_patches.append(db_patch)

    run.status = "succeeded"
    db.flush()
    # Path A (KD-20): dual-write sealed GeneratedPatchRecord for Design Engine spine
    from export.patchbook.design.dual_write import dual_write_generated_patches

    dual_write_generated_patches(db, bridge=bridge, patches=saved_patches)
    db.commit()

    # Build responses
    patch_responses = [build_patch_response(db, p) for p in saved_patches]

    return GeneratePatchesResponse(
        generated_count=len(patch_responses),
        patches=patch_responses,
        run_id=run.id,
        export_bridge_ready=bridge.export_bridge_ready,
        source_run_id=bridge.source_run_id,
        rig_revision_id=bridge.rig_revision_id,
        artifact_manifest_hash=bridge.artifact_manifest_hash,
        inventory_revision_id=inventory_revision_id,
        inventory_gate_code=inventory_gate_code,
        generation_status=generation_status,
    )


def build_patch_response(db: Session, patch: Patch) -> PatchResponse:
    """Build a complete patch response with vote count."""
    from community.models import Vote

    vote_count = db.query(Vote).filter(Vote.patch_id == patch.id).count()

    return PatchResponse(
        id=patch.id,
        rack_id=patch.rack_id,
        run_id=patch.run_id,
        name=patch.name,
        suggested_name=patch.suggested_name,
        name_override=patch.name_override,
        category=patch.category,
        description=patch.description,
        connections=patch.connections,
        generation_seed=patch.generation_seed,
        generation_version=patch.generation_version,
        engine_config=patch.engine_config,
        waveform_svg_path=patch.waveform_svg_path,
        waveform_params=patch.waveform_params,
        is_public=patch.is_public,
        tags=patch.tags or [],
        difficulty=_derive_difficulty(patch.connections),
        diagram_svg_url=f"/api/export/patches/{patch.id}/diagram.svg",
        created_at=patch.created_at,
        updated_at=patch.updated_at,
        vote_count=vote_count,
    )


def _derive_difficulty(connections: list[dict[str, Any]]) -> str:
    connection_count = len(connections)
    has_feedback = any(c.get("from_module_id") == c.get("to_module_id") for c in connections)
    if connection_count <= 2 and not has_feedback:
        return "Easy"
    if connection_count <= 4 and not has_feedback:
        return "Medium"
    return "Hard"


def _derive_tags(connections: list[dict[str, Any]]) -> list[str]:
    tags: list[str] = []
    if any(c.get("from_module_id") == c.get("to_module_id") for c in connections):
        tags.append("humor")
    return tags
