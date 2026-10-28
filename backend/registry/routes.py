"""Read-only Product Database registry routes plus bounded admin curation."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from admin.dependencies import require_admin_mutate
from community.models import User
from core.database import get_db
from registry.models import Manufacturer

from . import services

router = APIRouter()


@router.get("/manufacturers")
def list_manufacturers(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return {
        "total": services.count_manufacturers(db=db),
        "items": services.list_manufacturers(limit=limit, offset=offset, db=db),
    }


@router.get("/manufacturers/{slug}")
def get_manufacturer(slug: str, db: Session = Depends(get_db)):
    detail = services.get_manufacturer_detail(slug, db=db)
    if detail:
        return detail
    snapshot_manufacturer = services.get_manufacturer(slug)
    if snapshot_manufacturer:
        return snapshot_manufacturer
    raise HTTPException(404, "Manufacturer not found")


@router.get("/search")
def search(
    q: str = Query("", description="Search term"),
    brand: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    return {"results": services.search_models(q=q, brand=brand, limit=limit, db=db)}


@router.get("/coverage")
def coverage(db: Session = Depends(get_db)):
    return services.get_coverage_report(db=db)


class ManufacturerCreate(BaseModel):
    slug: str
    canonical_name: str
    website: str | None = None
    aliases: list[str] = Field(default_factory=list)


@router.post("/admin/manufacturers", tags=["admin", "registry"])
def create_manufacturer(
    payload: ManufacturerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    if db.query(Manufacturer).filter_by(slug=payload.slug).first():
        raise HTTPException(400, "Slug already exists")
    manufacturer = Manufacturer(
        slug=payload.slug,
        canonical_name=payload.canonical_name,
        website=payload.website,
        aliases=payload.aliases,
        status="active",
        provenance={"source": "admin-curation"},
    )
    db.add(manufacturer)
    db.commit()
    db.refresh(manufacturer)
    return {"id": manufacturer.id, "slug": manufacturer.slug}


@router.get("/manufacturers/{slug}/models")
def models_for_manufacturer(
    slug: str,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    return {"models": services.list_models_for_manufacturer(slug, limit=limit, db=db)}
