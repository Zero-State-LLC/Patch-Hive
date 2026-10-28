"""Read API for the normalized modular case catalog.

Mounted under ``/api/cases`` alongside the legacy Case CRUD routes. Static
``/catalog`` paths must be registered before ``/{case_id}`` integer routes.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from cases import catalog_service
from cases.compatibility import evaluate_catalog_compatibility
from cases.compatibility_schemas import CompatibilityRequest, CompatibilityResponse
from cases.materialize import materialize_catalog_batch, materialize_legacy_case
from cases.schemas import CaseResponse
from cases.catalog_schemas import (
    CaseCatalogDetail,
    CaseCatalogListItem,
    CaseCatalogListResponse,
    CaseCatalogStatsResponse,
    CaseFeatureOut,
    CasePowerSystemOut,
    CasePriceOut,
    CaseRevisionDetailOut,
    CaseRevisionListResponse,
    CaseRevisionSummaryOut,
    CaseRowOut,
    CaseSourceOut,
    CaseSourcePolicyOut,
    FormatCount,
    FormatListResponse,
    ManufacturerCount,
    ManufacturerListResponse,
)
from cases.models import CaseCatalog, CaseRevision
from admin.dependencies import require_admin_mutate
from admin.utils import log_admin_action
from community.models import User
from core.database import get_db

router = APIRouter(tags=["case-catalog"])


def _revision_summary(revision: CaseRevision) -> CaseRevisionSummaryOut:
    return CaseRevisionSummaryOut.model_validate(revision)


def _revision_detail(revision: CaseRevision) -> CaseRevisionDetailOut:
    return CaseRevisionDetailOut(
        revision_key=revision.revision_key,
        revision_label=revision.revision_label,
        row_count=revision.row_count,
        capacity_value=revision.capacity_value,
        capacity_unit=revision.capacity_unit,
        usable_capacity_value=revision.usable_capacity_value,
        depth_min_mm=revision.depth_min_mm,
        depth_max_mm=revision.depth_max_mm,
        depth_notes=revision.depth_notes,
        width_mm=revision.width_mm,
        height_mm=revision.height_mm,
        depth_mm=revision.depth_mm,
        weight_kg=revision.weight_kg,
        materials=revision.materials,
        mounting_type=revision.mounting_type,
        portable=revision.portable,
        removable_lid=revision.removable_lid,
        close_patched_lid=revision.close_patched_lid,
        integrated_stand=revision.integrated_stand,
        rack_mountable=revision.rack_mountable,
        notes=revision.notes,
        confidence=revision.confidence,
        rows=[CaseRowOut.model_validate(row) for row in sorted(revision.rows, key=lambda r: r.row_index)],
        power_systems=[CasePowerSystemOut.model_validate(p) for p in revision.power_systems],
        features=[CaseFeatureOut.model_validate(f) for f in revision.features],
    )


def _list_item(case: CaseCatalog) -> CaseCatalogListItem:
    primary = catalog_service.pick_primary_revision(list(case.revisions or []))
    return CaseCatalogListItem(
        slug=case.slug,
        manufacturer=case.manufacturer,
        model=case.model,
        format_family=case.format_family,
        production_status=case.production_status,
        powered=case.powered,
        official_url=case.official_url,
        image_url=case.image_url,
        primary_revision=_revision_summary(primary) if primary else None,
    )


@router.get("/catalog", response_model=CaseCatalogListResponse)
def list_case_catalog(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    manufacturer: Optional[str] = Query(None, description="Substring match on manufacturer"),
    format_family: Optional[str] = Query(None, description="Exact format_family enum"),
    production_status: Optional[str] = Query(None),
    powered: Optional[bool] = Query(None),
    q: Optional[str] = Query(None, description="Search manufacturer, model, or slug"),
    capacity_unit: Optional[str] = Query(None),
    min_capacity: Optional[float] = Query(None, ge=0),
    max_capacity: Optional[float] = Query(None, ge=0),
    min_rows: Optional[int] = Query(None, ge=0),
    max_rows: Optional[int] = Query(None, ge=0),
    min_depth_mm: Optional[float] = Query(None, ge=0),
    min_pos12_ma: Optional[int] = Query(None, ge=0),
    min_neg12_ma: Optional[int] = Query(None, ge=0),
    min_pos5_ma: Optional[int] = Query(None, ge=0),
    portable: Optional[bool] = Query(None),
    removable_lid: Optional[bool] = Query(None),
    integrated_stand: Optional[bool] = Query(None),
    feature_key: Optional[str] = Query(None, description="Require revision feature_key"),
    db: Session = Depends(get_db),
):
    """List normalized catalog cases with format-safe filters."""
    query = catalog_service.list_catalog_query(
        db,
        manufacturer=manufacturer,
        format_family=format_family,
        production_status=production_status,
        powered=powered,
        q=q,
        capacity_unit=capacity_unit,
        min_capacity=min_capacity,
        max_capacity=max_capacity,
        min_rows=min_rows,
        max_rows=max_rows,
        min_depth_mm=min_depth_mm,
        min_pos12_ma=min_pos12_ma,
        min_neg12_ma=min_neg12_ma,
        min_pos5_ma=min_pos5_ma,
        portable=portable,
        removable_lid=removable_lid,
        integrated_stand=integrated_stand,
        feature_key=feature_key,
    )
    total = query.count()
    cases = (
        query.options(selectinload(CaseCatalog.revisions))
        .order_by(CaseCatalog.manufacturer.asc(), CaseCatalog.model.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return CaseCatalogListResponse(
        total=total,
        skip=skip,
        limit=limit,
        cases=[_list_item(case) for case in cases],
    )


@router.get("/catalog/manufacturers", response_model=ManufacturerListResponse)
def list_catalog_manufacturers(db: Session = Depends(get_db)):
    rows = catalog_service.manufacturer_counts(db)
    manufacturers = [ManufacturerCount(name=name, case_count=count) for name, count in rows]
    return ManufacturerListResponse(total=len(manufacturers), manufacturers=manufacturers)


@router.get("/catalog/formats", response_model=FormatListResponse)
def list_catalog_formats(db: Session = Depends(get_db)):
    rows = catalog_service.format_counts(db)
    formats = [FormatCount(format_family=family, case_count=count) for family, count in rows]
    return FormatListResponse(total=len(formats), formats=formats)


@router.get("/catalog/stats", response_model=CaseCatalogStatsResponse)
def get_catalog_stats(db: Session = Depends(get_db)):
    return CaseCatalogStatsResponse(**catalog_service.catalog_stats(db))


@router.post(
    "/catalog/materialize-batch",
    response_model=dict,
    summary="Materialize many catalog cases into legacy rows",
)
def materialize_catalog_batch_route(
    format_family: Optional[str] = Query(
        "eurorack",
        description="Catalog format_family filter; eurorack includes intellijel_1u identity",
    ),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    """Bulk bridge for Rack Builder. Idempotent per catalog slug. Admin only."""
    log_admin_action(
        db,
        actor=current_user,
        action_type="case_catalog.materialize_batch",
        target_type="case_catalog",
        delta_json={"format_family": format_family, "limit": limit},
    )
    db.commit()
    return materialize_catalog_batch(db, format_family=format_family, limit=limit)


@router.get("/catalog/{slug}", response_model=CaseCatalogDetail)
def get_catalog_case(slug: str, db: Session = Depends(get_db)):
    case = catalog_service.get_case_by_slug(db, slug)
    if case is None:
        raise HTTPException(status_code=404, detail="Catalog case not found")

    policy_map = catalog_service.policy_by_source_ids(db, [s.id for s in case.sources if s.id])
    sources: list[CaseSourceOut] = []
    for source in case.sources:
        packet = policy_map.get(source.id)
        sources.append(
            CaseSourceOut(
                source_type=source.source_type,
                title=source.title,
                url=source.url,
                field_path=source.field_path,
                published_value=source.published_value,
                normalized_value=source.normalized_value,
                discrepancy_note=source.discrepancy_note,
                confidence=source.confidence,
                captured_at=source.captured_at,
                policy=CaseSourcePolicyOut.model_validate(packet) if packet else None,
            )
        )

    revisions = sorted(case.revisions, key=lambda r: r.id or 0)
    return CaseCatalogDetail(
        slug=case.slug,
        manufacturer=case.manufacturer,
        model=case.model,
        format_family=case.format_family,
        production_status=case.production_status,
        powered=case.powered,
        official_url=case.official_url,
        image_url=case.image_url,
        created_at=case.created_at,
        updated_at=case.updated_at,
        revisions=[_revision_detail(r) for r in revisions],
        prices=[CasePriceOut.model_validate(p) for p in case.prices],
        sources=sources,
    )


@router.get("/catalog/{slug}/revisions", response_model=CaseRevisionListResponse)
def list_catalog_revisions(slug: str, db: Session = Depends(get_db)):
    case = catalog_service.get_case_by_slug(db, slug)
    if case is None:
        raise HTTPException(status_code=404, detail="Catalog case not found")
    revisions = sorted(case.revisions, key=lambda r: r.id or 0)
    return CaseRevisionListResponse(
        slug=case.slug,
        manufacturer=case.manufacturer,
        model=case.model,
        revisions=[_revision_detail(r) for r in revisions],
    )


@router.post(
    "/catalog/{slug}/compatibility",
    response_model=CompatibilityResponse,
    summary="Evaluate module placements against a catalog case revision",
)
def evaluate_case_compatibility(
    slug: str,
    body: CompatibilityRequest,
    db: Session = Depends(get_db),
):
    """Physical fit, remaining capacity, rail headroom, connectors, +5V, and lid checks.

    Each check reports ``verified``, ``incomplete``, or ``conflict``. Missing
    case or module specs never invent capacity.
    """
    try:
        return evaluate_catalog_compatibility(db, slug, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/catalog/{slug}/materialize",
    response_model=dict,
    summary="Create or refresh a legacy Case row for Rack Builder placement",
)
def materialize_catalog_case(
    slug: str,
    revision_key: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Bridge catalog → legacy ``cases`` table (racks still use ``case_id``).

    Idempotent for the same manufacturer/model + ``meta.catalog_slug``.
    """
    try:
        legacy, created = materialize_legacy_case(db, slug, revision_key=revision_key)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        # Fail-closed: refuse inventing HP / wiping layout when catalog is incomplete.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "created": created,
        "catalog_slug": slug,
        "case": CaseResponse.model_validate(legacy),
    }
