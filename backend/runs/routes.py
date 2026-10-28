"""FastAPI routes for patch generation runs."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from community.auth import get_current_user
from community.models import User
from core import get_db
from racks.access import readable_rack
from patches.models import Patch
from patches.routes import build_patch_response
from runs.listing import build_run_response, list_runs_for_rack
from runs.models import Run

from .schemas import RunListResponse, RunPatchesResponse, RunResponse

router = APIRouter()


@router.get("/", response_model=RunListResponse)
def list_runs(
    rack_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    readable_rack(db, rack_id, current_user)
    payload = list_runs_for_rack(db, rack_id)
    db.commit()
    return payload


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    readable_rack(db, run.rack_id, current_user, label="Run")
    response = build_run_response(db, run)
    db.commit()
    return response


@router.get("/{run_id}/patches", response_model=RunPatchesResponse)
def get_run_patches(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    readable_rack(db, run.rack_id, current_user, label="Run")
    patches = db.query(Patch).filter(Patch.run_id == run_id).all()
    return RunPatchesResponse(
        total=len(patches), patches=[build_patch_response(db, p) for p in patches]
    )
