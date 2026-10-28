"""
FastAPI routes for Case management.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from admin.dependencies import require_admin_mutate
from admin.utils import log_admin_action
from community.models import User
from core import get_db

from .models import Case
from .schemas import CaseCreate, CaseListResponse, CaseResponse, CaseUpdate

router = APIRouter()


def _defaults_from_payload(case: CaseCreate) -> dict:
    """Derive format_family / capacity_unit / powered when omitted."""
    meta = case.meta if isinstance(case.meta, dict) else {}
    family = case.format_family or meta.get("format_family") or "Eurorack"
    unit = case.capacity_unit or meta.get("capacity_unit") or "hp"
    if case.powered is not None:
        powered = case.powered
    elif "powered" in meta:
        powered = bool(meta.get("powered"))
    else:
        name_l = (case.name or "").lower()
        powered = "no power" not in name_l and "unpowered" not in name_l
    return {
        "format_family": str(family)[:64],
        "capacity_unit": str(unit)[:64],
        "powered": powered,
    }


# Cases are shared reference data that racks point at: writes are admin-only and audited.
@router.post("/", response_model=CaseResponse, status_code=201)
def create_case(
    case: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    """Create a new case."""
    if len(case.hp_per_row) != case.rows:
        raise HTTPException(
            status_code=400, detail=f"hp_per_row length must match rows ({case.rows})"
        )

    if sum(case.hp_per_row) != case.total_hp:
        raise HTTPException(
            status_code=400,
            detail=f"total_hp ({case.total_hp}) must match sum of hp_per_row ({sum(case.hp_per_row)})",
        )

    derived = _defaults_from_payload(case)
    db_case = Case(
        brand=case.brand,
        name=case.name,
        total_hp=case.total_hp,
        rows=case.rows,
        hp_per_row=case.hp_per_row,
        format_family=derived["format_family"],
        capacity_unit=derived["capacity_unit"],
        powered=derived["powered"],
        power_12v_ma=case.power_12v_ma,
        power_neg12v_ma=case.power_neg12v_ma,
        power_5v_ma=case.power_5v_ma,
        description=case.description,
        manufacturer_url=case.manufacturer_url,
        meta=case.meta,
        source=case.source,
        source_reference=case.source_reference,
    )
    db.add(db_case)
    db.flush()
    log_admin_action(
        db,
        actor=current_user,
        action_type="case.create",
        target_type="case",
        target_id=str(db_case.id),
        delta_json=jsonable_encoder(case.model_dump()),
    )
    db.commit()
    db.refresh(db_case)
    return db_case


@router.get("/", response_model=CaseListResponse)
def list_cases(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    brand: Optional[str] = None,
    min_hp: Optional[int] = None,
    max_hp: Optional[int] = None,
    q: Optional[str] = Query(None, description="Search brand or name"),
    format_family: Optional[str] = Query(
        None,
        description="Filter by format_family (e.g. Eurorack). Null/legacy treated as Eurorack.",
    ),
    powered: Optional[bool] = Query(None, description="Filter by powered flag"),
    min_rows: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    """List cases with SQL filters on first-class format columns."""
    query = db.query(Case)

    if brand:
        query = query.filter(Case.brand.ilike(f"%{brand}%"))
    if min_hp is not None:
        query = query.filter(Case.total_hp >= min_hp)
    if max_hp is not None:
        query = query.filter(Case.total_hp <= max_hp)
    if min_rows is not None:
        query = query.filter(Case.rows >= min_rows)
    if q:
        like = f"%{q}%"
        query = query.filter((Case.brand.ilike(like)) | (Case.name.ilike(like)))

    if format_family:
        # Legacy rows with null format_family count as Eurorack for placement defaults.
        if format_family.lower() == "eurorack":
            query = query.filter(
                (Case.format_family.is_(None))
                | (Case.format_family == "")
                | (Case.format_family.ilike("eurorack"))
            )
        else:
            query = query.filter(Case.format_family.ilike(format_family))

    if powered is not None:
        query = query.filter(Case.powered.is_(bool(powered)))

    total = query.count()
    cases = (
        query.order_by(Case.brand.asc(), Case.name.asc()).offset(skip).limit(limit).all()
    )

    return CaseListResponse(total=total, cases=cases)


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: int, db: Session = Depends(get_db)):
    """Get a specific case by ID."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: int,
    case_update: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    """Update a case."""
    db_case = db.query(Case).filter(Case.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="Case not found")

    update_data = case_update.model_dump(exclude_unset=True)
    before = {field: getattr(db_case, field) for field in update_data}
    for field, value in update_data.items():
        setattr(db_case, field, value)

    log_admin_action(
        db,
        actor=current_user,
        action_type="case.update",
        target_type="case",
        target_id=str(case_id),
        delta_json=jsonable_encoder({"before": before, "after": update_data}),
    )
    db.commit()
    db.refresh(db_case)
    return db_case


@router.delete("/{case_id}", status_code=204)
def delete_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    """Delete a case."""
    db_case = db.query(Case).filter(Case.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="Case not found")

    log_admin_action(
        db,
        actor=current_user,
        action_type="case.delete",
        target_type="case",
        target_id=str(case_id),
        delta_json=jsonable_encoder({"brand": db_case.brand, "name": db_case.name}),
    )
    db.delete(db_case)
    db.commit()
    return None
