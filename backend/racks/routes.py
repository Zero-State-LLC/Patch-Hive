"""
FastAPI routes for Rack management.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from cases.models import Case
from community.auth import get_current_user, require_auth
from community.models import User
from core import generate_rig_suggested_name, get_db, hash_string_to_seed
from modules.models import Module

from .access import owned_rack, readable_rack, readable_racks
from .catalog_compatibility import (
    dual_gate_catalog_errors_and_warnings,
    evaluate_rack_catalog_compatibility,
)
from .models import Rack, RackModule
from .schemas import RackCreate, RackListResponse, RackResponse, RackUpdate
from .validation import tombstone_note, tombstone_warning, validate_rack_configuration

router = APIRouter()


def _raise_if_invalid(errors: list, warnings: list) -> None:
    if errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Rack validation failed",
                "errors": [e.model_dump() for e in errors],
                "warnings": [w.model_dump() for w in warnings],
            },
        )


@router.post("/", response_model=RackResponse, status_code=201)
def create_rack(
    rack: RackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Create a new rack, owned by the signed-in user."""
    user_id = current_user.id

    # Validate rack configuration (legacy hard gate)
    is_valid, errors, warnings = validate_rack_configuration(db, rack.case_id, rack.modules)
    # Dual-gate: catalog conflicts hard-fail when case is materialized
    cat_errors, cat_warnings = dual_gate_catalog_errors_and_warnings(
        db, rack.case_id, rack.modules
    )
    errors = list(errors) + list(cat_errors)
    warnings = list(warnings) + list(cat_warnings)
    if not is_valid or cat_errors:
        _raise_if_invalid(errors, warnings)

    modules = []
    for module_spec in rack.modules:
        module = db.query(Module).filter(Module.id == module_spec.module_id).first()
        if module:
            modules.append(module)

    seed = rack.generation_seed or hash_string_to_seed(f"rack-{user_id}-{rack.case_id}")
    suggested_name = rack.name_suggested or generate_rig_suggested_name(modules)
    if not rack.name:
        rack.name = suggested_name

    # Create rack
    db_rack = Rack(
        user_id=user_id,
        case_id=rack.case_id,
        name=rack.name,
        name_suggested=suggested_name,
        description=rack.description,
        tags=rack.tags,
        is_public=rack.is_public,
        generation_seed=seed,
    )
    db.add(db_rack)
    db.flush()  # Get rack.id

    # Add modules
    for module_spec in rack.modules:
        db_rack_module = RackModule(
            rack_id=db_rack.id,
            module_id=module_spec.module_id,
            row_index=module_spec.row_index,
            start_hp=module_spec.start_hp,
        )
        db.add(db_rack_module)
        module = db.query(Module).filter(Module.id == module_spec.module_id).first()
        if module:
            modules.append(module)

    db.commit()
    db.refresh(db_rack)

    return build_rack_response(db, db_rack, validation_warnings=warnings)


@router.get("/", response_model=RackListResponse)
def list_racks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_public: Optional[bool] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List the racks the caller may read: their own and public ones."""
    query = readable_racks(db.query(Rack), current_user)

    # Apply filters
    if is_public is not None:
        query = query.filter(Rack.is_public == is_public)
    if user_id is not None:
        query = query.filter(Rack.user_id == user_id)

    total = query.count()
    racks = query.offset(skip).limit(limit).all()

    rack_responses = [build_rack_response(db, rack) for rack in racks]

    return RackListResponse(total=total, racks=rack_responses)


@router.get("/{rack_id}", response_model=RackResponse)
def get_rack(
    rack_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Get a specific rack by ID."""
    rack = readable_rack(db, rack_id, current_user)

    return build_rack_response(db, rack)


@router.get("/{rack_id}/compatibility")
def get_rack_catalog_compatibility(
    rack_id: int,
    plan_close_lid: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Evaluate catalog compatibility for the rack's placed modules.

    Requires the bound legacy case to have been materialized from the catalog
    (``meta.catalog_slug``). Returns ``bridge_status`` incomplete when unlinked.
    """
    rack = readable_rack(db, rack_id, current_user)
    return evaluate_rack_catalog_compatibility(db, rack, plan_close_lid=plan_close_lid)


@router.patch("/{rack_id}", response_model=RackResponse)
def update_rack(
    rack_id: int,
    rack_update: RackUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Update a rack (owner only)."""
    db_rack = owned_rack(db, rack_id, current_user)

    # Update basic fields
    update_data = rack_update.model_dump(exclude_unset=True, exclude={"modules", "name_suggested"})
    for field, value in update_data.items():
        setattr(db_rack, field, value)

    warnings: list = []
    # Update modules if provided
    if rack_update.modules is not None:
        is_valid, errors, warnings = validate_rack_configuration(
            db, db_rack.case_id, rack_update.modules
        )
        cat_errors, cat_warnings = dual_gate_catalog_errors_and_warnings(
            db, db_rack.case_id, rack_update.modules
        )
        errors = list(errors) + list(cat_errors)
        warnings = list(warnings) + list(cat_warnings)
        if not is_valid or cat_errors:
            _raise_if_invalid(errors, warnings)

        db.query(RackModule).filter(RackModule.rack_id == rack_id).delete()

        modules = []
        for module_spec in rack_update.modules:
            db_rack_module = RackModule(
                rack_id=db_rack.id,
                module_id=module_spec.module_id,
                row_index=module_spec.row_index,
                start_hp=module_spec.start_hp,
            )
            db.add(db_rack_module)
            module = db.query(Module).filter(Module.id == module_spec.module_id).first()
            if module:
                modules.append(module)

        if not db_rack.name_suggested:
            db_rack.name_suggested = generate_rig_suggested_name(modules)

    db.commit()
    db.refresh(db_rack)

    return build_rack_response(db, db_rack, validation_warnings=warnings)


@router.delete("/{rack_id}", status_code=204)
def delete_rack(
    rack_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Delete a rack (owner only).

    Soft delete (spec 001 OQ-02): the rack disappears from every list and read, and can
    no longer generate or export, but its runs, patches and canonical history stay.
    """
    db_rack = owned_rack(db, rack_id, current_user)

    db_rack.deleted_at = datetime.utcnow()
    db.commit()
    return None


def build_rack_response(
    db: Session,
    rack: Rack,
    validation_warnings: list | None = None,
) -> RackResponse:
    """Build a complete rack response with related data."""
    # Get case
    case = db.query(Case).filter(Case.id == rack.case_id).first()

    # Get modules with details
    rack_modules = db.query(RackModule).filter(RackModule.rack_id == rack.id).all()
    modules_response = []
    warnings = list(validation_warnings or [])
    for index, rm in enumerate(rack_modules):
        module = db.query(Module).filter(Module.id == rm.module_id).first()
        # A tombstoned module stays placed; every read says so (not only the last write).
        note = tombstone_note(db, module) if module else None
        if note:
            warnings.append(tombstone_warning(index, module, note))
        modules_response.append(
            {
                "id": rm.id,
                "module_id": rm.module_id,
                "row_index": rm.row_index,
                "start_hp": rm.start_hp,
                "module": (
                    {
                        "id": module.id,
                        "brand": module.brand,
                        "name": module.name,
                        "hp": module.hp,
                        "module_type": module.module_type,
                        "power_12v_ma": module.power_12v_ma,
                        "power_neg12v_ma": module.power_neg12v_ma,
                        "power_5v_ma": module.power_5v_ma,
                        "depth_mm": module.depth_mm,
                        "status": module.status,
                        "tombstone_reason": note["reason"] if note else None,
                        "alternatives": note["alternatives"] if note else [],
                    }
                    if module
                    else None
                ),
            }
        )

    # Count votes
    from community.models import Vote

    vote_count = db.query(Vote).filter(Vote.rack_id == rack.id).count()

    return RackResponse(
        id=rack.id,
        user_id=rack.user_id,
        case_id=rack.case_id,
        name=rack.name,
        name_suggested=rack.name_suggested,
        description=rack.description,
        tags=rack.tags,
        is_public=rack.is_public,
        generation_seed=rack.generation_seed,
        created_at=rack.created_at,
        updated_at=rack.updated_at,
        modules=modules_response,
        case=(
            {
                "id": case.id,
                "brand": case.brand,
                "name": case.name,
                "total_hp": case.total_hp,
                "rows": case.rows,
                "hp_per_row": case.hp_per_row,
                "format_family": case.format_family,
                "capacity_unit": case.capacity_unit,
                "powered": case.powered,
                "power_12v_ma": case.power_12v_ma,
                "power_neg12v_ma": case.power_neg12v_ma,
                "power_5v_ma": case.power_5v_ma,
                "meta": case.meta if isinstance(case.meta, dict) else {},
                "catalog_slug": (
                    (case.meta or {}).get("catalog_slug")
                    if isinstance(case.meta, dict)
                    else None
                ),
            }
            if case
            else None
        ),
        vote_count=vote_count,
        validation_warnings=warnings,
    )
