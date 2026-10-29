"""HTTP surface for the canonical export/download/webhook boundary.

These routes intentionally wrap pure domain functions in ``canon.exports`` and
``canon.downloads``. Legacy ``/api/export`` PatchBook routes remain for the
current product path; this router is the canonical contract entrypoint.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from canon.contracts import ExportRequest
from canon.downloads import DownloadTokenError, issue_download_token, verify_download_token
from canon.exports import (
    ExportBoundaryError,
    credit_balance,
    request_export,
    verify_stripe_webhook,
)
from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    CanonicalExportRecord,
    PatchUserOverlayRecord,
    RigRevisionRecord,
    StripeEventRecordModel,
    UserStyleRecipeRecord,
)
from community.auth import get_current_user, require_auth
from community.models import User
from core import get_db, settings
from runs.listing import list_runs_for_rack
from runs.schemas import RunListResponse

router = APIRouter()

ExportFormat = Literal["pdf", "svg", "json", "zip"]


class CanonicalExportCreate(BaseModel):
    source_run_id: str = Field(..., min_length=1, max_length=64)
    source_rig_revision_id: str = Field(..., min_length=1, max_length=64)
    artifact_manifest_hash: str = Field(..., min_length=64, max_length=64)
    formats: list[ExportFormat] = Field(default_factory=lambda: ["pdf", "json"])
    license: str = Field(default="personal", min_length=1, max_length=100)
    # Ignored: the server sets the price (KD-14, spec 004 FR-005). Kept so older
    # clients that still send it are not rejected.
    credit_cost: int | None = Field(default=None, ge=0)
    idempotency_key: str = Field(..., min_length=8, max_length=128)
    # Optional inline request recipe (no client tier). Prefer one of recipe sources.
    style_recipe: dict[str, Any] | None = None
    # Optional library recipe id — loads owner recipe when style_recipe omitted.
    style_recipe_id: str | None = Field(default=None, min_length=8, max_length=64)


class CanonicalExportResponse(BaseModel):
    export_id: str
    status: str
    credit_cost: int
    ledger_entry_id: str | None
    source_run_id: str
    source_rig_revision_id: str
    idempotency_key: str
    created_at: datetime
    composition_hash: str | None = None
    style_recipe_hash: str | None = None
    error_code: str | None = None
    pack_manifest_hash: str | None = None
    style_recipe_id: str | None = None


class StylePreviewRequest(BaseModel):
    source_run_id: str = Field(..., min_length=1, max_length=64)
    source_rig_revision_id: str = Field(..., min_length=1, max_length=64)
    artifact_manifest_hash: str = Field(..., min_length=64, max_length=64)
    style_recipe: dict[str, Any] | None = None
    style_recipe_id: str | None = Field(default=None, min_length=8, max_length=64)
    max_pages: int = Field(default=3, ge=1, le=5)


class StyleRecipeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    style_recipe: dict[str, Any]
    notes: str | None = Field(default=None, max_length=500)
    is_shared: bool = False


class StyleRecipeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    style_recipe: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=500)
    is_shared: bool | None = None


class StyleRecipeResponse(BaseModel):
    id: str
    name: str
    notes: str | None
    style_recipe: dict[str, Any]
    recipe_hash: str
    is_shared: bool = False
    created_at: datetime
    updated_at: datetime


class StylePreviewResponse(BaseModel):
    resolved_recipe: dict[str, Any]
    resolution_events: list[dict[str, Any]]
    style_recipe_hash: str
    library_content_hash: str
    load_path: str
    page_summaries: list[dict[str, Any]]
    composition_preview_hash: str | None = None


class DownloadTokenCreate(BaseModel):
    ttl_seconds: int = Field(default=300, ge=1, le=15 * 60)


class DownloadTokenResponse(BaseModel):
    export_id: str
    token: str
    ttl_seconds: int


class DownloadVerifyRequest(BaseModel):
    token: str
    user_id: int | None = None


class DownloadVerifyResponse(BaseModel):
    export_id: str
    user_id: str
    expires_at: int
    status: str


class CreditBalanceResponse(BaseModel):
    balance: int


class CreditLedgerEntryResponse(BaseModel):
    id: str
    delta: int
    entry_type: str
    export_id: str | None
    created_at: datetime


class CreditsSummaryResponse(BaseModel):
    """Account-dashboard shape: balance + recent canonical ledger rows."""

    balance: int
    entries: list[CreditLedgerEntryResponse]


class StripeWebhookResponse(BaseModel):
    stripe_event_id: str
    status: str
    event_type: str
    duplicate: bool


def _download_secret() -> str:
    from core.security import derived_key

    # Never the login-token key itself: a dedicated secret, or one derived for downloads.
    secret = (settings.download_token_secret or "").strip()
    if not secret:
        return derived_key("download-token")
    if len(secret.encode("utf-8")) < 32:
        # Deterministic pad for local/dev only; production policy rejects weak secrets.
        secret = (secret + ("0" * 32))[:32]
    return secret


def _export_response(record: CanonicalExportRecord) -> CanonicalExportResponse:
    return CanonicalExportResponse(
        export_id=record.id,
        status=record.status,
        credit_cost=record.credit_cost,
        ledger_entry_id=record.ledger_entry_id,
        source_run_id=record.source_run_id,
        source_rig_revision_id=record.source_rig_revision_id,
        idempotency_key=record.idempotency_key,
        created_at=record.created_at,
        composition_hash=getattr(record, "composition_hash", None),
        style_recipe_hash=getattr(record, "style_recipe_hash", None),
        error_code=getattr(record, "error_code", None),
        pack_manifest_hash=getattr(record, "pack_manifest_hash", None),
        style_recipe_id=getattr(record, "style_recipe_id", None),
    )


def _style_recipe_response(row: UserStyleRecipeRecord) -> StyleRecipeResponse:
    return StyleRecipeResponse(
        id=row.id,
        name=row.name,
        notes=row.notes,
        style_recipe=row.recipe_json if isinstance(row.recipe_json, dict) else {},
        recipe_hash=row.recipe_hash,
        is_shared=bool(getattr(row, "is_shared", False)),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


_ARTIFACT_FILES: dict[str, tuple[str, str]] = {
    # artifact key -> (relative path under pack, media type)
    "pdf": ("PatchBook.pdf", "application/pdf"),
    "companion": ("technical/companion.txt", "text/plain; charset=utf-8"),
    "manifest": ("manifest/patch-book.json", "application/json"),
}


def _require_download_grant(
    *,
    export: CanonicalExportRecord,
    user: User,
    token: str,
) -> None:
    try:
        verify_download_token(
            token,
            export_id=export.id,
            user_id=str(user.id),
            secret=_download_secret(),
        )
    except DownloadTokenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _load_request_recipe_payload(
    *,
    db: Session,
    user_id: int,
    style_recipe: dict[str, Any] | None,
    style_recipe_id: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return (recipe dict or None for default, library_id used)."""
    if style_recipe is not None and style_recipe_id:
        raise HTTPException(
            status_code=400,
            detail="STYLE_RECIPE_SOURCE_CONFLICT",
        )
    if style_recipe_id:
        from canon.style_recipes import get_user_recipe

        row = get_user_recipe(db, user_id, style_recipe_id)
        if row is None:
            raise HTTPException(status_code=404, detail="RECIPE_NOT_FOUND")
        payload = row.recipe_json if isinstance(row.recipe_json, dict) else None
        if not payload:
            raise HTTPException(status_code=400, detail="INVALID_STYLE_RECIPE")
        return payload, row.id
    return style_recipe, None


@router.get("/credits/balance", response_model=CreditBalanceResponse)
def get_canonical_credit_balance(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> CreditBalanceResponse:
    return CreditBalanceResponse(balance=credit_balance(db, current_user.id))


@router.get("/credits/summary", response_model=CreditsSummaryResponse)
def get_canonical_credits_summary(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    limit: int = 100,
) -> CreditsSummaryResponse:
    """Balance plus recent append-only ledger entries for the authenticated user."""

    capped = max(1, min(limit, 200))
    rows = db.scalars(
        select(CanonicalCreditLedgerEntryRecord)
        .where(CanonicalCreditLedgerEntryRecord.user_id == current_user.id)
        .order_by(CanonicalCreditLedgerEntryRecord.created_at.desc())
        .limit(capped)
    ).all()
    entries = [
        CreditLedgerEntryResponse(
            id=row.id,
            delta=int(row.delta),
            entry_type=str(row.entry_type),
            export_id=row.export_id,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return CreditsSummaryResponse(
        balance=credit_balance(db, current_user.id),
        entries=entries,
    )


@router.get("/runs", response_model=RunListResponse)
def list_canonical_runs(
    rig_id: int = Query(
        ...,
        ge=1,
        description="Legacy rack id (rig). Alias of GET /api/runs?rack_id= with same bridge DTO.",
    ),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> RunListResponse:
    """Matrix slice B: canon-prefixed run list for FE migration off /api/runs."""
    from racks.access import readable_rack

    readable_rack(db, rig_id, current_user, label="Rig")

    payload = list_runs_for_rack(db, rig_id)
    return payload


# --- F2: thin inventory rig read adapter (rack_id ≡ rig_id) -------------------


class CanonRigSummary(BaseModel):
    """Read-only inventory rig. ``rig_id`` is the stable external key (≡ rack.id)."""

    rig_id: int
    rack_id: int
    user_id: int
    case_id: int
    name: str | None = None
    name_suggested: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_public: bool = False
    module_count: int = 0
    created_at: datetime
    updated_at: datetime


class CanonRigListResponse(BaseModel):
    total: int
    rigs: list[CanonRigSummary]


class CanonRigDetail(CanonRigSummary):
    """Single-rig detail with placements (same inventory source as GET /api/racks/{id})."""

    generation_seed: int | None = None
    modules: list[dict[str, Any]] = Field(default_factory=list)
    case: dict[str, Any] | None = None
    vote_count: int = 0


def _canon_rig_summary_from_rack(db: Session, rack: Any) -> CanonRigSummary:
    from racks.models import RackModule

    module_count = db.query(RackModule).filter(RackModule.rack_id == rack.id).count()
    return CanonRigSummary(
        rig_id=int(rack.id),
        rack_id=int(rack.id),
        user_id=int(rack.user_id),
        case_id=int(rack.case_id),
        name=rack.name,
        name_suggested=rack.name_suggested,
        description=rack.description,
        tags=list(rack.tags or []),
        is_public=bool(rack.is_public),
        module_count=int(module_count),
        created_at=rack.created_at,
        updated_at=rack.updated_at,
    )


@router.get("/rigs", response_model=CanonRigListResponse)
def list_canon_rigs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_public: bool | None = None,
    user_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> CanonRigListResponse:
    """F2 thin read adapter: list inventory rigs over the racks table.

    Does not replace POST/PATCH ``/api/racks``; new clients should prefer this
    list path. ``rig_id`` and ``rack_id`` are always equal (MVP honesty).
    """
    from racks.access import readable_racks
    from racks.models import Rack

    query = readable_racks(db.query(Rack), current_user)
    if is_public is not None:
        query = query.filter(Rack.is_public == is_public)
    if user_id is not None:
        query = query.filter(Rack.user_id == user_id)

    total = query.count()
    racks = query.order_by(Rack.id.desc()).offset(skip).limit(limit).all()
    return CanonRigListResponse(
        total=total,
        rigs=[_canon_rig_summary_from_rack(db, rack) for rack in racks],
    )


@router.get("/rigs/{rig_id}", response_model=CanonRigDetail)
def get_canon_rig(
    rig_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> CanonRigDetail:
    """F2 thin read adapter: single inventory rig (≡ GET /api/racks/{rig_id})."""
    from racks.access import readable_rack
    from racks.routes import build_rack_response

    rack = readable_rack(db, rig_id, current_user, label="Rig")

    summary = _canon_rig_summary_from_rack(db, rack)
    full = build_rack_response(db, rack)
    modules = [
        m.model_dump() if hasattr(m, "model_dump") else dict(m) for m in (full.modules or [])
    ]
    return CanonRigDetail(
        **summary.model_dump(),
        generation_seed=full.generation_seed,
        modules=modules,
        case=full.case,
        vote_count=int(full.vote_count or 0),
    )


class RigRevisionSummary(BaseModel):
    rig_revision_id: str
    content_hash: str | None = None
    run_count: int = 0
    latest_run_id: int | None = None
    latest_run_at: datetime | None = None
    export_bridge_ready: bool = False


class RigRevisionListResponse(BaseModel):
    total: int
    revisions: list[RigRevisionSummary]


class PatchOverlayUpsert(BaseModel):
    notes: str | None = None
    favorite: bool | None = None
    tried: bool | None = None


class PatchOverlayResponse(BaseModel):
    id: str
    patch_ref: str
    notes: str | None
    favorite: bool
    tried: bool
    updated_at: datetime


def legacy_patch_ref(patch_id: int) -> str:
    return f"legacy-patch-{int(patch_id)}"


@router.get("/rigs/{rig_id}/revisions", response_model=RigRevisionListResponse)
def list_rig_revisions(
    rig_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> RigRevisionListResponse:
    """Distinct server-authored rig revision ids observed for this rig's runs.

    Grouping is derived from the export bridge (immutable revision per content).
    """
    from racks.access import readable_rack

    readable_rack(db, rig_id, current_user, label="Rig")

    payload = list_runs_for_rack(db, rig_id)
    by_rev: dict[str, RigRevisionSummary] = {}
    for run in payload.runs:
        rev_id = run.rig_revision_id
        existing = by_rev.get(rev_id)
        created = run.created_at
        if existing is None:
            content_hash = None
            record = db.get(RigRevisionRecord, rev_id)
            if record is not None:
                content_hash = str(record.canonical_hash)
            by_rev[rev_id] = RigRevisionSummary(
                rig_revision_id=rev_id,
                content_hash=content_hash,
                run_count=1,
                latest_run_id=run.id,
                latest_run_at=created,
                export_bridge_ready=bool(run.export_bridge_ready),
            )
        else:
            existing.run_count += 1
            if created and (existing.latest_run_at is None or created > existing.latest_run_at):
                existing.latest_run_id = run.id
                existing.latest_run_at = created
                existing.export_bridge_ready = bool(run.export_bridge_ready)

    revisions = sorted(
        by_rev.values(),
        key=lambda item: item.latest_run_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return RigRevisionListResponse(total=len(revisions), revisions=revisions)


@router.get("/overlays/{patch_ref}", response_model=PatchOverlayResponse)
def get_patch_overlay(
    patch_ref: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> PatchOverlayResponse:
    row = db.scalars(
        select(PatchUserOverlayRecord).where(
            PatchUserOverlayRecord.user_id == current_user.id,
            PatchUserOverlayRecord.patch_ref == patch_ref,
        )
    ).first()
    if row is None:
        # Empty overlay — not an error (personal state is optional).
        now = datetime.now(timezone.utc)
        return PatchOverlayResponse(
            id="",
            patch_ref=patch_ref,
            notes=None,
            favorite=False,
            tried=False,
            updated_at=now,
        )
    return PatchOverlayResponse(
        id=str(row.id),
        patch_ref=str(row.patch_ref),
        notes=row.notes,
        favorite=bool(row.favorite),
        tried=bool(row.tried),
        updated_at=row.updated_at,
    )


@router.put("/overlays/{patch_ref}", response_model=PatchOverlayResponse)
def upsert_patch_overlay(
    patch_ref: str,
    body: PatchOverlayUpsert,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> PatchOverlayResponse:
    """Create or update mutable personal overlay without mutating canonical patches."""

    if not patch_ref or len(patch_ref) > 64:
        raise HTTPException(status_code=400, detail="INVALID_PATCH_REF")
    row = db.scalars(
        select(PatchUserOverlayRecord).where(
            PatchUserOverlayRecord.user_id == current_user.id,
            PatchUserOverlayRecord.patch_ref == patch_ref,
        )
    ).first()
    now = datetime.now(timezone.utc)
    if row is None:
        import uuid

        row = PatchUserOverlayRecord(
            id=f"overlay-{uuid.uuid4().hex[:20]}",
            user_id=current_user.id,
            patch_ref=patch_ref,
            notes=body.notes,
            favorite=bool(body.favorite) if body.favorite is not None else False,
            tried=bool(body.tried) if body.tried is not None else False,
            updated_at=now,
        )
        db.add(row)
    else:
        if body.notes is not None:
            row.notes = body.notes
        if body.favorite is not None:
            row.favorite = body.favorite
        if body.tried is not None:
            row.tried = body.tried
        row.updated_at = now
    db.commit()
    db.refresh(row)
    return PatchOverlayResponse(
        id=str(row.id),
        patch_ref=str(row.patch_ref),
        notes=row.notes,
        favorite=bool(row.favorite),
        tried=bool(row.tried),
        updated_at=row.updated_at,
    )


@router.get("/exports", response_model=list[CanonicalExportResponse])
def list_canonical_exports(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    limit: int = 100,
) -> list[CanonicalExportResponse]:
    """Owner-scoped export history from the canonical ledger path."""

    capped = max(1, min(limit, 200))
    rows = db.scalars(
        select(CanonicalExportRecord)
        .where(CanonicalExportRecord.user_id == current_user.id)
        .order_by(CanonicalExportRecord.created_at.desc())
        .limit(capped)
    ).all()
    return [_export_response(row) for row in rows]


@router.get("/style-recipes", response_model=list[StyleRecipeResponse])
def list_style_recipes(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[StyleRecipeResponse]:
    from canon.style_recipes import list_user_recipes

    return [_style_recipe_response(r) for r in list_user_recipes(db, current_user.id)]


@router.post("/style-recipes", response_model=StyleRecipeResponse, status_code=201)
def create_style_recipe(
    body: StyleRecipeCreate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> StyleRecipeResponse:
    from canon.style_recipes import StyleRecipeLibraryError, create_user_recipe

    try:
        row = create_user_recipe(
            db,
            user_id=current_user.id,
            name=body.name,
            recipe_payload=body.style_recipe,
            notes=body.notes,
            is_shared=body.is_shared,
        )
        db.commit()
        db.refresh(row)
    except StyleRecipeLibraryError as exc:
        db.rollback()
        status = 409 if exc.code in {"RECIPE_NAME_CONFLICT", "RECIPE_LIBRARY_FULL"} else 400
        raise HTTPException(status_code=status, detail=exc.code) from exc
    return _style_recipe_response(row)


@router.get("/style-recipes/shared/{recipe_id}", response_model=StyleRecipeResponse)
def get_shared_style_recipe(
    recipe_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> StyleRecipeResponse:
    """Load a recipe marked is_shared by any user (authenticated read)."""
    _ = current_user
    row = db.get(UserStyleRecipeRecord, recipe_id)
    if row is None or not row.is_shared:
        raise HTTPException(status_code=404, detail="RECIPE_NOT_FOUND")
    return _style_recipe_response(row)


@router.get("/style-recipes/{recipe_id}", response_model=StyleRecipeResponse)
def get_style_recipe(
    recipe_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> StyleRecipeResponse:
    from canon.style_recipes import get_user_recipe

    row = get_user_recipe(db, current_user.id, recipe_id)
    if row is None:
        raise HTTPException(status_code=404, detail="RECIPE_NOT_FOUND")
    return _style_recipe_response(row)


@router.patch("/style-recipes/{recipe_id}", response_model=StyleRecipeResponse)
def update_style_recipe(
    recipe_id: str,
    body: StyleRecipeUpdate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> StyleRecipeResponse:
    from canon.style_recipes import StyleRecipeLibraryError, update_user_recipe

    try:
        row = update_user_recipe(
            db,
            user_id=current_user.id,
            recipe_id=recipe_id,
            name=body.name,
            recipe_payload=body.style_recipe,
            notes=body.notes,
            is_shared=body.is_shared,
        )
        db.commit()
        db.refresh(row)
    except StyleRecipeLibraryError as exc:
        db.rollback()
        if exc.code == "RECIPE_NOT_FOUND":
            raise HTTPException(status_code=404, detail=exc.code) from exc
        status = 409 if exc.code == "RECIPE_NAME_CONFLICT" else 400
        raise HTTPException(status_code=status, detail=exc.code) from exc
    return _style_recipe_response(row)


@router.delete("/style-recipes/{recipe_id}", status_code=204)
def delete_style_recipe(
    recipe_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> None:
    from canon.style_recipes import StyleRecipeLibraryError, delete_user_recipe

    try:
        delete_user_recipe(db, user_id=current_user.id, recipe_id=recipe_id)
        db.commit()
    except StyleRecipeLibraryError as exc:
        db.rollback()
        if exc.code == "RECIPE_NOT_FOUND":
            raise HTTPException(status_code=404, detail=exc.code) from exc
        raise HTTPException(status_code=400, detail=exc.code) from exc
    return None


@router.post("/exports/preview", response_model=StylePreviewResponse)
def preview_patchbook_style(
    body: StylePreviewRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> StylePreviewResponse:
    """Free preview: resolve recipe + load content spine; no debit (KD-15)."""
    from canon.entitlements import get_design_entitlements, tier_allows_family
    from export.patchbook.design.constraints import StyleResolveError, resolve_style_recipe
    from export.patchbook.design.content_spine import ContentSpineError, load_patch_compilations
    from export.patchbook.design.rate_limit import check_preview_rate_limit
    from export.patchbook.design.recipe import (
        RequestStyleRecipe,
        default_request_recipe,
        recipe_hash,
    )

    limit = check_preview_rate_limit(current_user.id)
    if not limit.allowed:
        raise HTTPException(
            status_code=429,
            detail="PREVIEW_RATE_LIMIT",
            headers={"Retry-After": str(int(limit.retry_after_seconds) + 1)},
        )

    entitlements = get_design_entitlements(current_user.id)
    recipe_payload, _lib_id = _load_request_recipe_payload(
        db=db,
        user_id=current_user.id,
        style_recipe=body.style_recipe,
        style_recipe_id=body.style_recipe_id,
    )
    try:
        if recipe_payload is not None:
            request_recipe = RequestStyleRecipe.model_validate(recipe_payload)
        else:
            request_recipe = default_request_recipe()
        resolved = resolve_style_recipe(
            request_recipe,
            resolved_tier=entitlements.tier,
            family_allowed=tier_allows_family(entitlements.tier, request_recipe.template_family),
            publication_enabled=entitlements.publication_enabled,
        )
    except StyleResolveError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"INVALID_STYLE_RECIPE:{exc}") from exc

    try:
        library = load_patch_compilations(
            db,
            source_run_id=body.source_run_id,
            source_rig_revision_id=body.source_rig_revision_id,
            artifact_manifest_hash=body.artifact_manifest_hash,
            require_sealed=bool(settings.require_sealed_generated_patches),
        )
    except ContentSpineError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from exc

    summaries: list[dict[str, Any]] = []
    for item in library.items[: body.max_pages]:
        plan = item.compilation.patch_plan
        graph = item.compilation.patch_graph
        summaries.append(
            {
                "position": item.position,
                "title": plan.title,
                "intent": plan.intent,
                "edge_count": len(graph.edges),
                "steps": [{"phase": s.phase, "instruction": s.instruction} for s in plan.steps[:8]],
                "warnings": [
                    {"code": i.code, "severity": i.severity, "message": i.message}
                    for i in item.compilation.validation_report.issues[:5]
                ],
            }
        )

    return StylePreviewResponse(
        resolved_recipe=resolved.model_dump(mode="json"),
        resolution_events=[e.model_dump(mode="json") for e in resolved.events],
        style_recipe_hash=recipe_hash(resolved),
        library_content_hash=library.library_content_hash,
        load_path=library.load_path,
        page_summaries=summaries,
        composition_preview_hash=None,
    )


@router.post("/exports", response_model=CanonicalExportResponse, status_code=201)
def create_canonical_export(
    body: CanonicalExportCreate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> CanonicalExportResponse:
    if not body.formats:
        raise HTTPException(status_code=400, detail="At least one export format is required")
    # Spec 004 FR-005: never take credits for an export nothing will fulfill. Inline
    # fulfillment is the only fulfiller (there is no queue worker), and it refunds every
    # failure it catches, so with either flag off the request is refused before any debit.
    if not (settings.enable_canon_export_fulfillment and settings.enable_inline_export_fulfillment):
        raise HTTPException(status_code=503, detail="EXPORT_FULFILLMENT_UNAVAILABLE")

    # KD-14 / spec 004 FR-005: the server sets the price; a client credit_cost is
    # never trusted, whatever the Design Engine flag says.
    cost = settings.patchbook_export_cost

    resolved_recipe = None
    request_recipe_dump = None
    library_recipe_id: str | None = None
    if settings.enable_patchbook_design_engine or settings.enable_canon_export_fulfillment:
        from canon.entitlements import get_design_entitlements, tier_allows_family
        from export.patchbook.design.constraints import StyleResolveError, resolve_style_recipe
        from export.patchbook.design.recipe import (
            RequestStyleRecipe,
            default_request_recipe,
            recipe_hash,
        )

        entitlements = get_design_entitlements(current_user.id)
        recipe_payload, library_recipe_id = _load_request_recipe_payload(
            db=db,
            user_id=current_user.id,
            style_recipe=body.style_recipe,
            style_recipe_id=body.style_recipe_id,
        )
        try:
            if recipe_payload is not None:
                request_recipe = RequestStyleRecipe.model_validate(recipe_payload)
            else:
                request_recipe = default_request_recipe()
            request_recipe_dump = request_recipe.model_dump(mode="json")
            resolved_recipe = resolve_style_recipe(
                request_recipe,
                resolved_tier=entitlements.tier,
                family_allowed=tier_allows_family(
                    entitlements.tier, request_recipe.template_family
                ),
                publication_enabled=entitlements.publication_enabled,
            )
        except StyleResolveError as exc:
            raise HTTPException(status_code=400, detail=exc.code) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"INVALID_STYLE_RECIPE:{exc}") from exc

    request_id = hashlib.sha256(
        f"{current_user.id}:{body.idempotency_key}".encode("utf-8")
    ).hexdigest()[:32]
    domain_request = ExportRequest(
        request_id=request_id,
        user_id=current_user.id,
        source_run_id=body.source_run_id,
        source_rig_revision_id=body.source_rig_revision_id,
        formats=tuple(body.formats),
        license=body.license,
        credit_cost=cost,
        idempotency_key=body.idempotency_key,
        requested_at=datetime.now(timezone.utc),
    )
    try:
        export = request_export(
            db,
            domain_request,
            artifact_manifest_hash=body.artifact_manifest_hash,
            export_version=settings.patch_engine_version,
        )
        if resolved_recipe is not None:
            from export.patchbook.design.recipe import DESIGN_ENGINE_VERSION, recipe_hash

            export.style_recipe_hash = recipe_hash(resolved_recipe)
            export.request_style_recipe_json = request_recipe_dump
            export.resolved_style_recipe_json = resolved_recipe.model_dump(mode="json")
            export.resolved_tier = resolved_recipe.resolved_tier
            export.design_engine_version = DESIGN_ENGINE_VERSION
            export.book_profile = resolved_recipe.constraints.book_profile.value
            if library_recipe_id:
                export.style_recipe_id = library_recipe_id
        db.commit()
        db.refresh(export)
    except ExportBoundaryError as exc:
        db.rollback()
        code = str(exc)
        if code == "INSUFFICIENT_CREDITS":
            raise HTTPException(status_code=402, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc
    except Exception:
        db.rollback()
        raise

    # KD-12 inline fulfill after debit commit (acceptance path)
    if settings.enable_canon_export_fulfillment and settings.enable_inline_export_fulfillment:
        from canon.fulfillment import fulfill_export

        try:
            fulfill_export(db, export.id)
            db.commit()
            db.refresh(export)
        except Exception:
            db.rollback()
            # leave queued/running for retry; do not 500 the debit response
            db.refresh(export)

    return _export_response(export)


@router.get("/exports/{export_id}", response_model=CanonicalExportResponse)
def get_canonical_export(
    export_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> CanonicalExportResponse:
    export = db.get(CanonicalExportRecord, export_id)
    if export is None or export.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Export not found")
    return _export_response(export)


@router.post(
    "/exports/{export_id}/download-token",
    response_model=DownloadTokenResponse,
)
def create_download_token(
    export_id: str,
    body: DownloadTokenCreate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> DownloadTokenResponse:
    export = db.get(CanonicalExportRecord, export_id)
    if export is None or export.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Export not found")
    # When fulfillment is enabled, only completed packs are downloadable (KD-12).
    if settings.enable_canon_export_fulfillment:
        allowed = {"succeeded"}
    else:
        allowed = {"queued", "running", "succeeded"}
    if export.status not in allowed:
        raise HTTPException(status_code=409, detail="Export is not downloadable")
    if settings.enable_canon_export_fulfillment and not getattr(export, "pack_manifest_hash", None):
        raise HTTPException(status_code=409, detail="Export pack not ready")

    try:
        token = issue_download_token(
            export_id=export.id,
            user_id=str(current_user.id),
            secret=_download_secret(),
            ttl_seconds=body.ttl_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DownloadTokenResponse(
        export_id=export.id,
        token=token,
        ttl_seconds=body.ttl_seconds,
    )


@router.post(
    "/exports/{export_id}/download",
    response_model=DownloadVerifyResponse,
)
def verify_download(
    export_id: str,
    body: DownloadVerifyRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> DownloadVerifyResponse:
    export = db.get(CanonicalExportRecord, export_id)
    if export is None or export.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Export not found")

    try:
        grant = verify_download_token(
            body.token,
            export_id=export.id,
            user_id=str(current_user.id),
            secret=_download_secret(),
        )
    except DownloadTokenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return DownloadVerifyResponse(
        export_id=grant.export_id,
        user_id=grant.user_id,
        expires_at=grant.expires_at,
        status=export.status,
    )


@router.get("/exports/{export_id}/artifacts/{artifact}")
def download_export_artifact(
    export_id: str,
    artifact: str,
    token: str = Query(..., min_length=16),
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Response:
    """Stream a Design Engine pack artifact after download-token verification.

    Artifacts: ``pdf`` | ``companion`` | ``manifest`` | ``zip``
    """
    export = db.get(CanonicalExportRecord, export_id)
    if export is None or export.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Export not found")
    if export.status != "succeeded" and settings.enable_canon_export_fulfillment:
        raise HTTPException(status_code=409, detail="Export pack not ready")

    _require_download_grant(export=export, user=current_user, token=token)

    from canon.fulfillment import pack_dir_for_export
    from core.storage import StorageError, get_file_store

    pack_dir = pack_dir_for_export(export.id)
    try:
        get_file_store().ensure_local_tree(pack_dir)
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=exc.code) from exc
    if not pack_dir.exists():
        # Fall back to artifact_uri if set
        uri = getattr(export, "artifact_uri", None)
        if uri:
            pack_dir = Path(uri)
    if not pack_dir.exists():
        raise HTTPException(status_code=404, detail="PACK_NOT_FOUND")

    if artifact == "zip":
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(pack_dir.rglob("*")):
                if path.is_file():
                    zf.write(path, arcname=str(path.relative_to(pack_dir)))
        data = buf.getvalue()
        return Response(
            content=data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="patchbook-{export.id}.zip"',
            },
        )

    if artifact not in _ARTIFACT_FILES:
        raise HTTPException(status_code=400, detail="UNKNOWN_ARTIFACT")
    rel, media = _ARTIFACT_FILES[artifact]
    file_path = pack_dir / rel
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="ARTIFACT_NOT_FOUND")
    filename = file_path.name
    return FileResponse(
        path=file_path,
        media_type=media,
        filename=filename,
        content_disposition_type="attachment",
    )


@router.post("/webhooks/stripe", response_model=StripeWebhookResponse)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> StripeWebhookResponse:
    """Replay-safe Stripe-style webhook intake (test-mode by default)."""

    if settings.environment.lower() == "production" and not settings.allow_production_payments:
        # Hard reject production payment intake while the kill switch is off.
        raise HTTPException(status_code=403, detail="PRODUCTION_PAYMENTS_DISABLED")

    secret = (settings.stripe_webhook_secret or "").strip()
    if not secret:
        # Only a local development stack may sign its own test webhooks; any hosted
        # environment, staging included, must use the Stripe-issued whsec_ secret.
        from core.security import derived_key, is_dev_environment

        if not is_dev_environment(settings.environment):
            raise HTTPException(status_code=503, detail="STRIPE_WEBHOOK_SECRET is not configured")
        secret = derived_key("stripe-webhook-dev")

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    payload = await request.body()
    try:
        provisional_id = ""
        try:
            provisional_id = str(json.loads(payload).get("id") or "")
        except (json.JSONDecodeError, TypeError, AttributeError):
            provisional_id = ""
        already_seen = bool(
            provisional_id and db.get(StripeEventRecordModel, provisional_id) is not None
        )
        record, event = verify_stripe_webhook(
            db,
            payload=payload,
            signature_header=stripe_signature,
            secret=secret,
            test_mode=settings.stripe_test_mode,
        )
        db.commit()
        db.refresh(record)
    except ExportBoundaryError as exc:
        db.rollback()
        code = str(exc)
        status = 400
        if code in {"LIVEMODE_EVENT_REJECTED", "WEBHOOK_REPLAY_CONFLICT"}:
            status = 409
        raise HTTPException(status_code=status, detail=code) from exc
    except Exception:
        db.rollback()
        raise

    return StripeWebhookResponse(
        stripe_event_id=record.stripe_event_id,
        status=record.status,
        event_type=str(event.get("type", record.event_type)),
        duplicate=already_seen,
    )


def validate_payment_startup_policy(app_settings: Any = settings) -> None:
    """Fail closed when production payment configuration is unsafe."""

    env = str(getattr(app_settings, "environment", "development")).lower()
    if env != "production":
        return

    allow = bool(getattr(app_settings, "allow_production_payments", False))
    test_mode = bool(getattr(app_settings, "stripe_test_mode", True))
    webhook_secret = str(getattr(app_settings, "stripe_webhook_secret", "") or "").strip()
    download_secret = str(
        getattr(app_settings, "download_token_secret", "")
        or getattr(app_settings, "secret_key", "")
    ).strip()

    if not allow:
        if not test_mode:
            raise RuntimeError(
                "Production requires STRIPE_TEST_MODE=true while ALLOW_PRODUCTION_PAYMENTS=false"
            )
        return

    # Production payments explicitly enabled: require reviewed secrets.
    if test_mode:
        raise RuntimeError(
            "ALLOW_PRODUCTION_PAYMENTS=true is incompatible with STRIPE_TEST_MODE=true"
        )
    if len(webhook_secret) < 16:
        raise RuntimeError("ALLOW_PRODUCTION_PAYMENTS requires a real STRIPE_WEBHOOK_SECRET")
    if len(download_secret.encode("utf-8")) < 32:
        raise RuntimeError(
            "ALLOW_PRODUCTION_PAYMENTS requires DOWNLOAD_TOKEN_SECRET or SECRET_KEY >= 32 bytes"
        )
