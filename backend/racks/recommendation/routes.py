"""Routes for rack layout recommendations."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from typing import Optional

from cases.models import Case
from community.auth import get_current_user
from community.models import User
from core import get_db
from modules.models import Module
from racks.access import readable_rack
from racks.models import RackModule

from .models import (
    ModuleSpec,
    RackRecommendationFromRackRequest,
    RackRecommendationRequest,
    RackRecommendationResponse,
)
from .recommend import recommend_layouts

router = APIRouter()


@router.post("/recommend-layout", response_model=RackRecommendationResponse)
def recommend_rack_layout(payload: RackRecommendationRequest) -> RackRecommendationResponse:
    return recommend_layouts(
        rack_hp=payload.rack_hp,
        modules=payload.modules,
        connections=payload.connection_frequencies,
    )


@router.post("/{rack_id}/recommend-layout", response_model=RackRecommendationResponse)
def recommend_rack_layout_for_rack(
    rack_id: int,
    payload: RackRecommendationFromRackRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> RackRecommendationResponse:
    rack = readable_rack(db, rack_id, current_user)

    case = db.query(Case).filter(Case.id == rack.case_id).first()
    rack_modules = db.query(RackModule).filter(RackModule.rack_id == rack.id).all()
    module_ids = [rm.module_id for rm in rack_modules]
    modules = db.query(Module).filter(Module.id.in_(module_ids)).all() if module_ids else []
    modules_by_id = {module.id: module for module in modules}

    module_specs = []
    for rack_module in rack_modules:
        module = modules_by_id.get(rack_module.module_id)
        if not module:
            continue
        role_tags = []
        if module.tags:
            role_tags.extend([tag for tag in module.tags if isinstance(tag, str)])
        if module.module_type:
            role_tags.append(module.module_type)
        module_specs.append(
            ModuleSpec(
                module_id=module.id,
                name=module.name,
                hp=module.hp,
                role_tags=role_tags,
            )
        )

    rack_hp = case.total_hp if case else sum(module.hp for module in modules)

    return recommend_layouts(
        rack_hp=rack_hp,
        modules=module_specs,
        connections=payload.connection_frequencies,
    )
