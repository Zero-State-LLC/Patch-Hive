"""
Module Catalog API endpoints - browse/search/filter modules.

Fast, lightweight catalog of all available modules.
Full specs fetched on-demand when user adds to rack.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from admin.dependencies import require_admin_mutate
from admin.utils import log_admin_action
from community.models import User
from core.database import get_db
from modules.catalog import ModuleCatalog
from modules.models import Module

router = APIRouter()

# Rows the loader's retirement manifest tombstoned are hidden from browse, search,
# counts and materialization; a lookup by slug still answers.
LIVE = ModuleCatalog.tombstoned_at.is_(None)


@router.get("/catalog")
def browse_module_catalog(
    db: Session = Depends(get_db),
    # Search
    search: Optional[str] = Query(None, description="Search in brand/name"),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    category: Optional[str] = Query(None, description="Filter by category (VCO, VCF, etc.)"),
    # Size filters
    hp_min: Optional[int] = Query(None, description="Minimum HP width"),
    hp_max: Optional[int] = Query(None, description="Maximum HP width"),
    hp_known: Optional[bool] = Query(
        None, description="If true, only rows with HP; if false, only null HP"
    ),
    # Status
    is_available: Optional[str] = Query(None, description="available, discontinued, upcoming"),
    # Provenance
    source: Optional[str] = Query(
        None, description="Filter by catalog admit source (e.g. SynthCatalogResearch)"
    ),
    # Pagination
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    # Sorting
    sort_by: str = Query("brand", pattern="^(brand|name|hp|category|created_at|source)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
):
    """
    Browse module catalog with search, filters, and sorting.

    This is a lightweight endpoint for browsing thousands of modules.
    Returns basic info only. Fetch full specs separately when needed.

    Examples:
        - /catalog?search=maths
        - /catalog?brand=Mutable+Instruments&category=VCO
        - /catalog?hp_min=8&hp_max=16
        - /catalog?hp_known=true
        - /catalog?sort_by=hp&sort_order=asc
    """
    query = db.query(ModuleCatalog)

    # Apply filters
    filters = [LIVE]

    if search:
        search_term = f"%{search}%"
        filters.append(
            or_(ModuleCatalog.brand.ilike(search_term), ModuleCatalog.name.ilike(search_term))
        )

    if brand:
        filters.append(ModuleCatalog.brand == brand)

    if category:
        filters.append(ModuleCatalog.category == category)

    if hp_min is not None:
        filters.append(ModuleCatalog.hp >= hp_min)

    if hp_max is not None:
        filters.append(ModuleCatalog.hp <= hp_max)

    if hp_known is True:
        filters.append(ModuleCatalog.hp.isnot(None))
    elif hp_known is False:
        filters.append(ModuleCatalog.hp.is_(None))

    if is_available:
        filters.append(ModuleCatalog.is_available == is_available)

    if source:
        filters.append(ModuleCatalog.source == source)

    if filters:
        query = query.filter(and_(*filters))

    # Count total matches
    total = query.count()

    # Apply sorting
    sort_column = getattr(ModuleCatalog, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    modules = query.offset(skip).limit(limit).all()

    return {"total": total, "skip": skip, "limit": limit, "modules": [m.to_dict() for m in modules]}


@router.get("/catalog/brands")
def list_catalog_brands(db: Session = Depends(get_db)):
    """Get list of all brands in catalog with module counts."""
    from sqlalchemy import func

    brands = (
        db.query(ModuleCatalog.brand, func.count(ModuleCatalog.id).label("count"))
        .filter(LIVE)
        .group_by(ModuleCatalog.brand)
        .order_by(ModuleCatalog.brand)
        .all()
    )

    return {
        "total": len(brands),
        "brands": [{"name": brand, "module_count": count} for brand, count in brands],
    }


@router.get("/catalog/categories")
def list_catalog_categories(db: Session = Depends(get_db)):
    """Get list of all categories with module counts."""
    from sqlalchemy import func

    categories = (
        db.query(ModuleCatalog.category, func.count(ModuleCatalog.id).label("count"))
        .filter(LIVE)
        .group_by(ModuleCatalog.category)
        .order_by(func.count(ModuleCatalog.id).desc())
        .all()
    )

    return {
        "total": len(categories),
        "categories": [{"name": cat, "module_count": count} for cat, count in categories if cat],
    }


@router.get("/catalog/stats")
def get_catalog_stats(db: Session = Depends(get_db)):
    """Get catalog statistics including HP coverage for research seeds."""
    from sqlalchemy import func

    total_modules = db.query(func.count(ModuleCatalog.id)).filter(LIVE).scalar() or 0
    total_brands = db.query(func.count(func.distinct(ModuleCatalog.brand))).filter(LIVE).scalar() or 0
    total_categories = (
        db.query(func.count(func.distinct(ModuleCatalog.category))).filter(LIVE).scalar() or 0
    )

    # HP distribution (among known only)
    avg_hp = db.query(func.avg(ModuleCatalog.hp)).filter(LIVE).scalar()
    min_hp = db.query(func.min(ModuleCatalog.hp)).filter(LIVE).scalar()
    max_hp = db.query(func.max(ModuleCatalog.hp)).filter(LIVE).scalar()
    hp_known = (
        db.query(func.count(ModuleCatalog.id))
        .filter(LIVE, ModuleCatalog.hp.isnot(None))
        .scalar()
        or 0
    )
    hp_unknown = total_modules - hp_known

    # Availability
    available_count = (
        db.query(func.count(ModuleCatalog.id))
        .filter(LIVE, ModuleCatalog.is_available == "available")
        .scalar()
        or 0
    )

    coverage = round(100.0 * hp_known / total_modules, 1) if total_modules else 0.0

    source_rows = (
        db.query(ModuleCatalog.source, func.count(ModuleCatalog.id).label("count"))
        .filter(LIVE)
        .group_by(ModuleCatalog.source)
        .order_by(func.count(ModuleCatalog.id).desc())
        .all()
    )
    by_source = {
        (src or "unknown"): count for src, count in source_rows
    }

    return {
        "total_modules": total_modules,
        "total_brands": total_brands,
        "total_categories": total_categories,
        "hp_stats": {
            "average": round(float(avg_hp or 0), 1),
            "min": min_hp,
            "max": max_hp,
            "known": hp_known,
            "unknown": hp_unknown,
            "coverage_pct": coverage,
        },
        "by_source": by_source,
        "availability": {
            "available": available_count,
            "discontinued": max(total_modules - available_count, 0),
        },
    }


def materialize_catalog_entry(db: Session, slug: str) -> Dict[str, Any]:
    """
    Ensure a full ``modules`` row exists for a catalog slug.

    Requires catalog HP (fail-closed). Does not invent power/depth/I/O.
    Idempotent: returns existing Module when brand+name already present.
    """
    entry = db.query(ModuleCatalog).filter(ModuleCatalog.slug == slug).first()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Module '{slug}' not found in catalog")
    if entry.tombstoned_at is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "CATALOG_ROW_TOMBSTONED", "reason": entry.tombstone_reason},
        )

    existing = (
        db.query(Module)
        .filter(Module.brand == entry.brand, Module.name == entry.name)
        .order_by(Module.id.asc())
        .first()
    )
    if existing:
        return {
            "status": "exists",
            "catalog_slug": slug,
            "module_id": existing.id,
            "module": {
                "id": existing.id,
                "brand": existing.brand,
                "name": existing.name,
                "hp": existing.hp,
                "module_type": existing.module_type,
                "source": existing.source,
                "power_12v_ma": getattr(existing, "power_12v_ma", None),
                "power_neg12v_ma": getattr(existing, "power_neg12v_ma", None),
                "io_ports": getattr(existing, "io_ports", []),
                "tags": getattr(existing, "tags", []),
                "description": getattr(existing, "description", None),
                "registry_manufacturer_slug": getattr(existing, "registry_manufacturer_slug", None),
                "registry_device_slug": getattr(existing, "registry_device_slug", None),
            },
        }

    if entry.hp is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Catalog entry '{slug}' has unknown HP. "
                "Cannot materialize a placeable module without manufacturer-confirmed width."
            ),
        )

    module = Module(
        brand=entry.brand,
        name=entry.name,
        hp=int(entry.hp),
        module_type=entry.category or "UTIL",
        power_12v_ma=None,
        power_neg12v_ma=None,
        power_5v_ma=None,
        depth_mm=None,
        io_ports=[],
        tags=[],
        description=None,
        manufacturer_url=entry.manufacturer_url,
        registry_manufacturer_slug=entry.registry_manufacturer_slug,
        registry_device_slug=entry.registry_device_slug,
        source="ModuleCatalog",
        source_reference=(
            f"module_catalog:{slug}"
            + (f":source={entry.source}" if entry.source else "")
        ),
    )
    db.add(module)
    db.commit()
    db.refresh(module)

    return {
        "status": "created",
        "catalog_slug": slug,
        "module_id": module.id,
        "module": {
            "id": module.id,
            "brand": module.brand,
            "name": module.name,
            "hp": module.hp,
            "module_type": module.module_type,
            "source": module.source,
            "registry_manufacturer_slug": module.registry_manufacturer_slug,
            "registry_device_slug": module.registry_device_slug,
        },
    }


def materialize_catalog_batch(
    db: Session,
    *,
    brand: Optional[str] = None,
    hp_known_only: bool = True,
    limit: int = 500,
) -> Dict[str, Any]:
    """Materialize many catalog rows into full ``modules`` (idempotent).

    Default: only HP-known rows (placeable). Does not invent power/depth/I/O.
    Continues on per-row failures so one bad slug cannot abort the batch.
    """
    query = db.query(ModuleCatalog).filter(LIVE).order_by(
        ModuleCatalog.brand.asc(), ModuleCatalog.name.asc()
    )
    if brand:
        query = query.filter(ModuleCatalog.brand == brand)
    if hp_known_only:
        query = query.filter(ModuleCatalog.hp.isnot(None))
    entries = query.limit(limit).all()

    created = 0
    exists = 0
    failed: list[dict[str, str]] = []
    samples: list[dict[str, Any]] = []

    for entry in entries:
        try:
            result = materialize_catalog_entry(db, entry.slug)
            status = result.get("status")
            if status == "created":
                created += 1
            elif status == "exists":
                exists += 1
            if len(samples) < 30:
                samples.append(
                    {
                        "catalog_slug": entry.slug,
                        "status": status,
                        "module_id": result.get("module_id"),
                        "hp": entry.hp,
                    }
                )
        except HTTPException as exc:
            failed.append(
                {
                    "catalog_slug": entry.slug,
                    "error": str(exc.detail),
                    "status_code": str(exc.status_code),
                }
            )
        except Exception as exc:  # noqa: BLE001 — batch continues
            failed.append({"catalog_slug": entry.slug, "error": str(exc)})

    return {
        "status": "success" if not failed else "partial",
        "scanned": len(entries),
        "created": created,
        "exists": exists,
        "failed": len(failed),
        "failed_samples": failed[:20],
        "samples": samples,
        "filters": {
            "brand": brand,
            "hp_known_only": hp_known_only,
            "limit": limit,
        },
    }


@router.post("/catalog/materialize-batch")
def materialize_module_catalog_batch(
    brand: Optional[str] = Query(None, description="Optional brand filter"),
    hp_known_only: bool = Query(
        True, description="If true (default), only rows with known HP"
    ),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
) -> Dict[str, Any]:
    """Bulk materialize catalog rows into placeable ``modules`` (idempotent). Admin only."""
    log_admin_action(
        db,
        actor=current_user,
        action_type="module_catalog.materialize_batch",
        target_type="module_catalog",
        delta_json={"brand": brand, "hp_known_only": hp_known_only, "limit": limit},
    )
    db.commit()
    return materialize_catalog_batch(
        db, brand=brand, hp_known_only=hp_known_only, limit=limit
    )


@router.post("/catalog/{slug}/materialize")
def materialize_module_from_catalog(slug: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Materialize a lightweight catalog row into a full ``modules`` record for rack placement.

    Fails with 422 when HP is unknown (never invents width).
    """
    return materialize_catalog_entry(db, slug)


@router.get("/catalog/{slug}")
def get_catalog_module(slug: str, db: Session = Depends(get_db)):
    """
    Get catalog entry for specific module.

    Returns lightweight catalog info. Use /modules/{id} for full specs.
    """
    module = db.query(ModuleCatalog).filter(ModuleCatalog.slug == slug).first()

    if not module:
        raise HTTPException(status_code=404, detail=f"Module '{slug}' not found in catalog")

    return module.to_dict()
