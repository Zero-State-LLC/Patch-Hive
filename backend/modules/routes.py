"""
FastAPI routes for Module management.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from admin.dependencies import require_admin_mutate
from admin.utils import log_admin_action
from community.models import User
from core import get_db

from .models import Module, PowerConfig
from .schemas import (
    ModuleCreate,
    ModuleListResponse,
    ModuleResponse,
    ModuleUpdate,
    PowerConfigResponse,
)

router = APIRouter()


# Writes change the shared catalog every user's racks read, so they are admin-only and audited.
@router.post("/", response_model=ModuleResponse, status_code=201)
def create_module(
    module: ModuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    """Create a new module."""
    db_module = Module(
        brand=module.brand,
        name=module.name,
        hp=module.hp,
        depth_mm=module.depth_mm,
        module_type=module.module_type,
        power_12v_ma=module.power_12v_ma,
        power_neg12v_ma=module.power_neg12v_ma,
        power_5v_ma=module.power_5v_ma,
        io_ports=[port.model_dump() for port in module.io_ports],
        tags=module.tags,
        description=module.description,
        manufacturer_url=module.manufacturer_url,
        status=module.status or "active",
        replacement_module_id=module.replacement_module_id,
        deprecated_at=module.deprecated_at,
        tombstoned_at=module.tombstoned_at,
        source=module.source,
        source_reference=module.source_reference,
    )
    db.add(db_module)
    db.flush()
    log_admin_action(
        db,
        actor=current_user,
        action_type="module.create",
        target_type="module",
        target_id=str(db_module.id),
        delta_json=jsonable_encoder(module.model_dump()),
    )
    db.commit()
    db.refresh(db_module)
    return db_module


@router.get("/", response_model=ModuleListResponse)
def list_modules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    brand: Optional[str] = None,
    module_type: Optional[str] = None,
    hp_min: Optional[int] = None,
    hp_max: Optional[int] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List modules with optional filters."""
    query = db.query(Module).filter(Module.status != "tombstoned")

    # Apply filters
    if brand:
        query = query.filter(Module.brand.ilike(f"%{brand}%"))
    if module_type:
        query = query.filter(Module.module_type == module_type)
    if hp_min is not None:
        query = query.filter(Module.hp >= hp_min)
    if hp_max is not None:
        query = query.filter(Module.hp <= hp_max)
    if tag:
        query = query.filter(Module.tags.contains([tag]))

    total = query.count()
    modules = query.offset(skip).limit(limit).all()

    return ModuleListResponse(total=total, modules=modules)


@router.get("/{module_id}", response_model=ModuleResponse)
def get_module(module_id: int, db: Session = Depends(get_db)):
    """Get a specific module by ID."""
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


@router.get("/{module_id}/power-configs", response_model=list[PowerConfigResponse])
def list_power_configs(module_id: int, db: Session = Depends(get_db)):
    """The module's jumper settings, each with its own draws (spec 003 D8).

    Empty for a module whose draw does not depend on a jumper, or whose settings the
    maker page does not state clearly enough to load.
    """
    if db.query(Module.id).filter(Module.id == module_id).first() is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return (
        db.query(PowerConfig)
        .filter(PowerConfig.module_id == module_id)
        .order_by(PowerConfig.id)
        .all()
    )


@router.patch("/{module_id}", response_model=ModuleResponse)
def update_module(
    module_id: int,
    module_update: ModuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    """Update a module."""
    db_module = db.query(Module).filter(Module.id == module_id).first()
    if not db_module:
        raise HTTPException(status_code=404, detail="Module not found")

    # Update fields if provided
    update_data = module_update.model_dump(exclude_unset=True)
    if "io_ports" in update_data and update_data["io_ports"] is not None:
        update_data["io_ports"] = [port.model_dump() for port in module_update.io_ports]

    before = {field: getattr(db_module, field) for field in update_data}
    for field, value in update_data.items():
        setattr(db_module, field, value)

    log_admin_action(
        db,
        actor=current_user,
        action_type="module.update",
        target_type="module",
        target_id=str(module_id),
        delta_json=jsonable_encoder({"before": before, "after": update_data}),
    )
    db.commit()
    db.refresh(db_module)
    return db_module


@router.delete("/{module_id}", status_code=204)
def delete_module(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    """Tombstone a module (no hard delete)."""
    db_module = db.query(Module).filter(Module.id == module_id).first()
    if not db_module:
        raise HTTPException(status_code=404, detail="Module not found")

    db_module.status = "tombstoned"
    db_module.tombstoned_at = datetime.utcnow()
    log_admin_action(
        db,
        actor=current_user,
        action_type="module.tombstone",
        target_type="module",
        target_id=str(module_id),
    )
    db.commit()
    return None
