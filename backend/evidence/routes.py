"""Multi-image evidence upload, listing, and retention-aware deletion."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from canon.models import (
    ClassificationEvidenceRecord,
    ImageAssetRecord,
    SystemInventoryRevisionRecord,
)
from core import get_db, settings
from core.storage import StorageError, get_file_store
from evidence.images import (
    SignatureImageScanner,
    UnsafeImageError,
    assess_local_image_quality,
    prepare_image_evidence,
)
from evidence.cloud_provider import select_vision_provider
from evidence.vision_provider import (
    VisionProviderContext,
    collect_evidence_packet,
)
from community.auth import require_auth
from community.models import User
from racks.access import owned_private_rack, private_rack

router = APIRouter()

DEFAULT_RETENTION_DAYS = 30
MAX_FILES_PER_REQUEST = 12


class ImageAssetResponse(BaseModel):
    id: str
    rack_id: int
    content_sha256: str
    media_type: str
    width: int
    height: int
    byte_length: int
    retention_days: int
    retention_expires_at: datetime
    consent_provider_processing: bool
    deleted_at: datetime | None = None
    created_at: datetime
    quality_accepted: bool | None = None
    evidence_status: str | None = None


class ImageAssetListResponse(BaseModel):
    total: int
    assets: list[ImageAssetResponse]


class MultiImageUploadResponse(BaseModel):
    uploaded: list[ImageAssetResponse]
    rejected: list[dict[str, str]] = Field(default_factory=list)


def _evidence_root() -> Path:
    root = Path(settings.export_dir) / "evidence"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _asset_response(
    record: ImageAssetRecord,
    *,
    quality_accepted: bool | None = None,
    evidence_status: str | None = None,
) -> ImageAssetResponse:
    return ImageAssetResponse(
        id=str(record.id),
        rack_id=int(record.rack_id),
        content_sha256=str(record.content_sha256),
        media_type=str(record.media_type),
        width=int(record.width),
        height=int(record.height),
        byte_length=int(record.byte_length),
        retention_days=int(record.retention_days),
        retention_expires_at=record.retention_expires_at,
        consent_provider_processing=bool(record.consent_provider_processing),
        deleted_at=record.deleted_at,
        created_at=record.created_at,
        quality_accepted=quality_accepted,
        evidence_status=evidence_status,
    )


@router.post(
    "/racks/{rack_id}/evidence/images",
    response_model=MultiImageUploadResponse,
    status_code=201,
)
@router.post(
    "/canon/rigs/{rack_id}/evidence/images",
    response_model=MultiImageUploadResponse,
    status_code=201,
    name="upload_canon_rig_evidence_images",
)
async def upload_rack_evidence_images(
    rack_id: int,
    files: list[UploadFile] = File(...),
    retention_days: int = Form(DEFAULT_RETENTION_DAYS),
    consent_provider_processing: bool = Form(False),
    run_vision_mock: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> MultiImageUploadResponse:
    """Upload one or more images as untrusted evidence for a rack.

    Images are re-encoded and metadata-stripped. Provider processing consent is
    recorded; live cloud providers are not invoked — mock evidence only.
    """
    rack = owned_private_rack(db, rack_id, current_user)
    if not files:
        raise HTTPException(status_code=400, detail="NO_FILES")
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=400, detail="TOO_MANY_FILES")
    if retention_days < 1 or retention_days > 365:
        raise HTTPException(status_code=400, detail="RETENTION_DAYS_INVALID")

    uploaded: list[ImageAssetResponse] = []
    rejected: list[dict[str, str]] = []
    scanner = SignatureImageScanner()
    # Default mock; cloud only if explicitly preferred via env + consent (still fail-closed live).
    prefer_cloud = os.getenv("VISION_PREFER_CLOUD", "").lower() in {"1", "true", "yes"}
    provider = select_vision_provider(
        consent_provider_processing=consent_provider_processing,
        prefer_cloud=prefer_cloud,
        allow_live_calls=False,
    )
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=retention_days)
    user_id = int(rack.user_id)  # type: ignore[arg-type]

    for upload in files:
        filename = upload.filename or "upload"
        try:
            raw = await upload.read()
            prepared = prepare_image_evidence(
                raw,
                declared_media_type=upload.content_type,
                scanner=scanner,
            )
            quality = assess_local_image_quality(prepared)
            if not quality.accepted:
                rejected.append(
                    {
                        "filename": filename,
                        "reason": quality.reasons[0] if quality.reasons else "QUALITY_REJECTED",
                    }
                )
                continue

            asset_id = f"img-{uuid.uuid4().hex[:20]}"
            storage_name = f"{prepared.sha256}.jpg"
            storage_path = _evidence_root() / storage_name
            if not storage_path.exists():
                storage_path.write_bytes(prepared.content)
            # Never record a path whose bytes are not durable.
            try:
                get_file_store().persist(storage_path)
            except StorageError as exc:
                rejected.append({"filename": filename, "reason": exc.code})
                continue

            record = ImageAssetRecord(
                id=asset_id,
                rack_id=rack_id,
                user_id=user_id,
                content_sha256=prepared.sha256,
                media_type=prepared.media_type,
                width=prepared.width,
                height=prepared.height,
                byte_length=len(prepared.content),
                storage_path=str(storage_path),
                retention_days=retention_days,
                retention_expires_at=expires,
                consent_provider_processing=consent_provider_processing,
                created_at=now,
            )
            db.add(record)
            db.flush()

            evidence_status = None
            if run_vision_mock:
                packet = collect_evidence_packet(
                    provider,
                    VisionProviderContext(
                        image_asset_id=asset_id,
                        image_bytes=prepared.content,
                        request_id=f"req-{asset_id}",
                    ),
                )
                evidence_status = str(packet.get("status"))
                db.add(
                    ClassificationEvidenceRecord(
                        id=f"ev-{uuid.uuid4().hex[:20]}",
                        image_asset_id=asset_id,
                        inventory_revision_id=None,
                        evidence_packet=packet,
                        provider=provider.provider_name,
                        pipeline_version=str(
                            packet.get("pipeline_version") or "vision-evidence.v1"
                        ),
                        status=evidence_status or "INFERRED",
                        created_at=now,
                    )
                )
                db.flush()

            uploaded.append(
                _asset_response(
                    record,
                    quality_accepted=True,
                    evidence_status=evidence_status,
                )
            )
        except UnsafeImageError as exc:
            rejected.append({"filename": filename, "reason": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive
            rejected.append({"filename": filename, "reason": f"UPLOAD_FAILED:{type(exc).__name__}"})

    db.commit()
    return MultiImageUploadResponse(uploaded=uploaded, rejected=rejected)


@router.get("/racks/{rack_id}/evidence/images", response_model=ImageAssetListResponse)
@router.get(
    "/canon/rigs/{rack_id}/evidence/images",
    response_model=ImageAssetListResponse,
    name="list_canon_rig_evidence_images",
)
def list_rack_evidence_images(
    rack_id: int,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> ImageAssetListResponse:
    private_rack(db, rack_id, current_user)
    query = db.query(ImageAssetRecord).filter(ImageAssetRecord.rack_id == rack_id)
    if not include_deleted:
        query = query.filter(ImageAssetRecord.deleted_at.is_(None))
    rows = query.order_by(ImageAssetRecord.created_at.desc()).all()
    return ImageAssetListResponse(
        total=len(rows),
        assets=[_asset_response(row) for row in rows],
    )


@router.delete("/racks/{rack_id}/evidence/images/{asset_id}", status_code=200)
@router.delete(
    "/canon/rigs/{rack_id}/evidence/images/{asset_id}",
    status_code=200,
    name="delete_canon_rig_evidence_image",
)
def delete_rack_evidence_image(
    rack_id: int,
    asset_id: str,
    purge_bytes: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> dict[str, str]:
    """Soft-delete image evidence. Optionally purge storage bytes.

    Classification evidence and inventory lineage remain for audit when
    ``purge_bytes`` is false; storage files are removed when true and no other
    non-deleted asset shares the same content hash.
    """
    owned_private_rack(db, rack_id, current_user)
    record = (
        db.query(ImageAssetRecord)
        .filter(ImageAssetRecord.id == asset_id, ImageAssetRecord.rack_id == rack_id)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Image asset not found")
    if record.deleted_at is None:
        record.deleted_at = datetime.now(timezone.utc)
        db.flush()

    if purge_bytes:
        path = Path(str(record.storage_path))
        siblings = (
            db.query(ImageAssetRecord)
            .filter(
                ImageAssetRecord.content_sha256 == record.content_sha256,
                ImageAssetRecord.deleted_at.is_(None),
            )
            .count()
        )
        if siblings == 0:
            try:
                get_file_store().delete(path)
            except StorageError as exc:
                # Keep the soft-delete (access is revoked) and tell the caller the bytes
                # are not gone yet; calling again retries the purge.
                db.commit()
                raise HTTPException(status_code=503, detail=exc.code) from exc

    db.commit()
    return {"status": "deleted", "asset_id": asset_id}


class CandidateResponse(BaseModel):
    candidate_id: str
    entity_type: str
    manufacturer: str | None = None
    model: str | None = None
    confidence: float
    confidence_method: str
    alternative_candidates: list[str] = Field(default_factory=list)
    classification_status: str
    evidence_id: str
    image_asset_id: str | None = None
    gallery_revision_id: str | None = None
    gallery_module_id: str | None = None
    decision_advisory: dict | None = None


class CandidateListResponse(BaseModel):
    total: int
    candidates: list[CandidateResponse]


class ConfirmationDecisionIn(BaseModel):
    candidate_id: str
    status: str = Field(description="confirm | reject | defer | replace | manual_add")
    module_revision_id: str | None = None
    replacement_candidate_id: str | None = None
    notes: str | None = None


class ConfirmationBatchRequest(BaseModel):
    decisions: list[ConfirmationDecisionIn]
    confirmed_by: str | None = "user"


class ConfirmationBatchResponse(BaseModel):
    inventory_revision_id: str
    inventory_canonical_hash: str | None
    confirmed_count: int
    unresolved_candidate_ids: list[str]
    ready_for_generation: bool


def _load_candidates_for_rack(db: Session, rack_id: int) -> list[dict]:
    """Flatten device candidates from append-only evidence packets (newest first)."""
    from canon.visual_contracts import ClassificationCandidate

    rows = (
        db.query(ClassificationEvidenceRecord)
        .join(
            ImageAssetRecord,
            ImageAssetRecord.id == ClassificationEvidenceRecord.image_asset_id,
        )
        .filter(
            ImageAssetRecord.rack_id == rack_id,
            ImageAssetRecord.deleted_at.is_(None),
        )
        .order_by(ClassificationEvidenceRecord.created_at.desc())
        .all()
    )
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        packet = row.evidence_packet or {}
        devices = packet.get("devices") or []
        for raw in devices:
            try:
                candidate = ClassificationCandidate.model_validate(raw)
            except Exception:
                continue
            if candidate.candidate_id in seen:
                continue
            seen.add(candidate.candidate_id)
            out.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "entity_type": candidate.entity_type,
                    "manufacturer": candidate.manufacturer,
                    "model": candidate.model,
                    "confidence": candidate.confidence,
                    "confidence_method": candidate.confidence_method,
                    "alternative_candidates": list(candidate.alternative_candidates),
                    "classification_status": candidate.classification_status.value,
                    "evidence_id": candidate.evidence_id,
                    "image_asset_id": str(row.image_asset_id),
                    "gallery_revision_id": candidate.gallery_revision_id,
                    "gallery_module_id": candidate.gallery_module_id,
                    "_raw": raw,
                }
            )
    # Rank by confidence descending for review UX
    out.sort(key=lambda item: (-float(item["confidence"]), item["candidate_id"]))
    return out


@router.get("/racks/{rack_id}/evidence/candidates", response_model=CandidateListResponse)
@router.get(
    "/canon/rigs/{rack_id}/evidence/candidates",
    response_model=CandidateListResponse,
    name="list_canon_rig_evidence_candidates",
)
def list_rack_evidence_candidates(
    rack_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> CandidateListResponse:
    """Ranked classification candidates for human confirmation (untrusted)."""
    private_rack(db, rack_id, current_user)
    items = _load_candidates_for_rack(db, rack_id)
    # Decision Intelligence is deliberately read-only here. We project the newest
    # retained receipt for a candidate when one exists; no provider call occurs on GET,
    # and this projection cannot confirm or mutate inventory.
    from intelligence.models import DecisionReceiptRecord

    # Bind advisories to the exact evidence packet as well as candidate identity.
    # Candidate IDs can recur across racks/images; candidate-only lookup can leak a
    # valid advisory from unrelated evidence into this rack's review surface.
    candidate_ids = [item["candidate_id"] for item in items]
    evidence_hashes = {str(item["evidence_id"]) for item in items}
    receipts_by_binding: dict[tuple[str, str], DecisionReceiptRecord] = {}
    if candidate_ids and evidence_hashes:
        receipt_rows = (
            db.query(DecisionReceiptRecord)
            .filter(
                DecisionReceiptRecord.purpose == "module_identity",
                DecisionReceiptRecord.provider_status == "succeeded",
                DecisionReceiptRecord.selected_choice.in_(candidate_ids),
                DecisionReceiptRecord.evidence_hash.in_(evidence_hashes),
            )
            .order_by(DecisionReceiptRecord.created_at.desc())
            .all()
        )
        for receipt in receipt_rows:
            if receipt.selected_choice:
                key = (receipt.selected_choice, receipt.evidence_hash)
                if key not in receipts_by_binding:
                    receipts_by_binding[key] = receipt

    candidates = []
    for item in items:
        receipt = receipts_by_binding.get((item["candidate_id"], str(item["evidence_id"])))
        advisory = None
        if receipt is not None:
            advisory = {
                "disposition": receipt.disposition.lower(),
                "provider": receipt.provider,
                "confidence": receipt.confidence,
                "reason_codes": list(receipt.reason_codes or []),
            }
        payload = {k: v for k, v in item.items() if k != "_raw"}
        payload["decision_advisory"] = advisory
        candidates.append(CandidateResponse(**payload))
    return CandidateListResponse(total=len(candidates), candidates=candidates)


class ReconciliationResponse(BaseModel):
    image_asset_ids: list[str]
    image_count: int
    fused_entities: list[dict]
    unmatched_candidate_ids: list[str]
    conflict_count: int
    status: str
    note: str


@router.get(
    "/racks/{rack_id}/evidence/reconcile",
    response_model=ReconciliationResponse,
)
@router.get(
    "/canon/rigs/{rack_id}/evidence/reconcile",
    response_model=ReconciliationResponse,
    name="reconcile_canon_rig_evidence",
)
def reconcile_rack_evidence(
    rack_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> ReconciliationResponse:
    """Multi-photo fusion of untrusted candidates for one rack.

    Does not confirm inventory. Conflicts remain explicit for user resolution.
    """
    from evidence.reconciliation import reconcile_candidate_observations

    private_rack(db, rack_id, current_user)
    items = _load_candidates_for_rack(db, rack_id)
    report = reconcile_candidate_observations(items)
    return ReconciliationResponse(**report.to_dict())


class InventoryRevisionSummary(BaseModel):
    inventory_revision_id: str
    system_id: str
    rack_id: int | None
    confirmed_count: int
    unresolved_count: int
    ready_for_generation: bool
    canonical_hash: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None


class InventoryRevisionListResponse(BaseModel):
    total: int
    latest: InventoryRevisionSummary | None = None
    revisions: list[InventoryRevisionSummary]


@router.get(
    "/racks/{rack_id}/evidence/inventory",
    response_model=InventoryRevisionListResponse,
)
@router.get(
    "/canon/rigs/{rack_id}/evidence/inventory",
    response_model=InventoryRevisionListResponse,
    name="list_canon_rig_evidence_inventory",
)
def list_rack_inventory_revisions(
    rack_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> InventoryRevisionListResponse:
    """List sealed inventory revisions for a rack (newest first). Read-only."""
    from canon.inventory import inventory_ready_for_generation
    from canon.inventory_persist import load_system_inventory_revision

    private_rack(db, rack_id, current_user)

    rows = (
        db.query(SystemInventoryRevisionRecord)
        .filter(SystemInventoryRevisionRecord.rack_id == rack_id)
        .order_by(SystemInventoryRevisionRecord.created_at.desc())
        .limit(20)
        .all()
    )
    summaries: list[InventoryRevisionSummary] = []
    for row in rows:
        inventory = load_system_inventory_revision(db, row.id)
        confirmed = len(inventory.items) if inventory is not None else len(row.items or [])
        unresolved = (
            len(inventory.unresolved_candidate_ids)
            if inventory is not None
            else len(row.unresolved_candidate_ids or [])
        )
        ready = (
            inventory_ready_for_generation(inventory) if inventory is not None else confirmed > 0
        )
        summaries.append(
            InventoryRevisionSummary(
                inventory_revision_id=row.id,
                system_id=row.system_id,
                rack_id=row.rack_id,
                confirmed_count=confirmed,
                unresolved_count=unresolved,
                ready_for_generation=ready,
                canonical_hash=row.canonical_hash,
                created_by=row.created_by,
                created_at=row.created_at,
            )
        )
    return InventoryRevisionListResponse(
        total=len(summaries),
        latest=summaries[0] if summaries else None,
        revisions=summaries,
    )


@router.post(
    "/racks/{rack_id}/evidence/confirmations",
    response_model=ConfirmationBatchResponse,
    status_code=201,
)
@router.post(
    "/canon/rigs/{rack_id}/evidence/confirmations",
    response_model=ConfirmationBatchResponse,
    status_code=201,
    name="confirm_canon_rig_evidence_candidates",
)
def confirm_rack_evidence_candidates(
    rack_id: int,
    body: ConfirmationBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> ConfirmationBatchResponse:
    """Apply human confirmation decisions and mint an immutable inventory revision.

    Provider output remains evidence only. Confirmed modules require an explicit
    ``module_revision_id`` (gallery revision) on confirm/manual_add.
    """
    from canon.inventory import (
        InventoryBuildError,
        build_system_inventory_revision,
        inventory_ready_for_generation,
    )
    from canon.inventory_persist import persist_system_inventory_revision
    from canon.visual_contracts import (
        ClassificationCandidate,
        ConfirmationDecision,
        ResolutionStatus,
    )

    owned_private_rack(db, rack_id, current_user)
    if not body.decisions:
        raise HTTPException(status_code=400, detail="NO_DECISIONS")

    loaded = _load_candidates_for_rack(db, rack_id)
    by_id = {item["candidate_id"]: item for item in loaded}
    now = datetime.now(timezone.utc)
    candidates: list[ClassificationCandidate] = []
    decisions: list[ConfirmationDecision] = []

    for decision_in in body.decisions:
        raw_item = by_id.get(decision_in.candidate_id)
        if raw_item is None:
            raise HTTPException(
                status_code=400,
                detail=f"UNKNOWN_CANDIDATE:{decision_in.candidate_id}",
            )
        candidate = ClassificationCandidate.model_validate(raw_item["_raw"])
        if decision_in.status == "confirm":
            revision_id = decision_in.module_revision_id or candidate.gallery_revision_id
            if not revision_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"MODULE_REVISION_REQUIRED:{decision_in.candidate_id}",
                )
            candidate = candidate.model_copy(update={"gallery_revision_id": revision_id})
            resolved = ResolutionStatus.USER_CONFIRMED
        elif decision_in.status == "reject":
            resolved = ResolutionStatus.REJECTED
        elif decision_in.status == "defer":
            resolved = ResolutionStatus.UNKNOWN
        elif decision_in.status == "replace":
            resolved = ResolutionStatus.USER_CONFIRMED
        elif decision_in.status == "manual_add":
            if not decision_in.module_revision_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"MODULE_REVISION_REQUIRED:{decision_in.candidate_id}",
                )
            resolved = ResolutionStatus.USER_CONFIRMED
        else:
            raise HTTPException(status_code=400, detail=f"INVALID_STATUS:{decision_in.status}")

        candidates.append(candidate)
        decisions.append(
            ConfirmationDecision(
                confirmation_id=f"conf-{uuid.uuid4().hex[:16]}",
                candidate_id=decision_in.candidate_id,
                status=decision_in.status,  # type: ignore[arg-type]
                resolved_status=resolved,
                confirmed_by=body.confirmed_by,
                confirmed_at=now,
                replacement_candidate_id=decision_in.replacement_candidate_id,
                manual_module_revision_id=(
                    decision_in.module_revision_id if decision_in.status == "manual_add" else None
                ),
                notes=decision_in.notes,
            )
        )

    # Include undecided candidates so they remain unresolved
    decided_ids = {d.candidate_id for d in decisions}
    for item in loaded:
        if item["candidate_id"] not in decided_ids:
            candidates.append(ClassificationCandidate.model_validate(item["_raw"]))

    try:
        inventory = build_system_inventory_revision(
            system_id=f"rack-{rack_id}",
            candidates=candidates,
            decisions=decisions,
            created_at=now,
            created_by=body.confirmed_by,
        )
    except InventoryBuildError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    persist_system_inventory_revision(db, inventory, rack_id=rack_id)
    # ClassificationEvidenceRecord is append-only; inventory linkage is via
    # SystemInventoryRevisionRecord + candidate source_candidate_ids, not mutation.
    db.commit()
    return ConfirmationBatchResponse(
        inventory_revision_id=inventory.inventory_revision_id,
        inventory_canonical_hash=inventory.canonical_hash,
        confirmed_count=len(inventory.items),
        unresolved_candidate_ids=list(inventory.unresolved_candidate_ids),
        ready_for_generation=inventory_ready_for_generation(inventory),
    )


class DecisionResolutionRequest(BaseModel):
    evidence_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=128)


class DecisionResolutionResponse(BaseModel):
    evidence_id: str
    selected_choice: str | None
    disposition: str
    provider: str
    confidence: float | None
    canonical_authority: bool = False


def _configured_decision_provider(*, image_loader: Callable[..., Any] | None = None):
    """Construct only an explicitly configured production provider."""
    if settings.decision_provider == "jev":
        from intelligence.jev_provider import JevDecisionProvider

        if not settings.typesafe_api_key:
            raise RuntimeError("JEV_API_KEY_NOT_CONFIGURED")
        return JevDecisionProvider(
            api_key=settings.typesafe_api_key,
            base_url=settings.jev_base_url,
            model=settings.jev_model,
        )
    if settings.decision_provider == "clef":
        from intelligence.clef_provider import ClefDecisionProvider

        # Fail-closed: with enable_clef_provider off the adapter is inert and every
        # call returns CLEF_DISABLED without a network call.
        return ClefDecisionProvider(
            enabled=settings.enable_clef_provider,
            account_id=settings.cloudflare_account_id,
            api_token=settings.cloudflare_ai_api_token,
            model=settings.clef_model,
            base_url=settings.clef_base_url,
            timeout_seconds=settings.clef_timeout_seconds,
            image_loader=image_loader,
        )
    raise RuntimeError("DECISION_PROVIDER_NOT_CONFIGURED")


_GUARDED_FAILURE_STATUS = {
    "CLEF_DISABLED": 409,
    "CLEF_INVALID_REQUEST": 422,
    "PACKET_SCHEMA_INVALID": 502,
}


def _guarded_failure_status(code: str) -> int:
    if code in _GUARDED_FAILURE_STATUS:
        return _GUARDED_FAILURE_STATUS[code]
    return 504 if "TIMEOUT" in code or "TIMED_OUT" in code else 502


@router.post(
    "/racks/{rack_id}/evidence/decision-resolution",
    response_model=DecisionResolutionResponse,
)
def resolve_rack_evidence_decision(
    rack_id: int,
    body: DecisionResolutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> DecisionResolutionResponse:
    """Produce and retain one non-canonical identity advisory."""
    from intelligence.evidence_resolution import (
        DecisionIntelligenceDisabled,
        EvidenceResolutionError,
        resolve_module_identity,
    )
    from intelligence.policy import DecisionPolicy, PolicyThresholds
    from intelligence.jev_provider import JevProviderError

    owned_private_rack(db, rack_id, current_user)

    evidence = db.get(ClassificationEvidenceRecord, body.evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    asset = db.get(ImageAssetRecord, evidence.image_asset_id)
    if asset is None or int(asset.rack_id) != rack_id or asset.deleted_at is not None:
        raise HTTPException(status_code=400, detail="EVIDENCE_NOT_BOUND_TO_RACK")

    if not settings.enable_decision_intelligence:
        raise HTTPException(status_code=409, detail="DECISION_INTELLIGENCE_DISABLED")

    if settings.decision_provider == "clef":
        return _resolve_with_guarded_flow(db, body)

    try:
        provider = _configured_decision_provider()
        thresholds = PolicyThresholds(
            policy_version="decision-policy-v1",
            auto_propose_at=settings.decision_auto_propose_at,
            user_review_at=settings.decision_user_review_at,
            probability_margin=settings.decision_probability_margin,
        )
        proposal = resolve_module_identity(
            db,
            evidence_id=body.evidence_id,
            provider=provider,
            policy=DecisionPolicy(thresholds),
            enabled=True,
            idempotency_key=body.idempotency_key,
        )
    except DecisionIntelligenceDisabled as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except JevProviderError as exc:
        status_code = 504 if str(exc) == "JEV_TIMEOUT" else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except (EvidenceResolutionError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.commit()
    return DecisionResolutionResponse(
        evidence_id=body.evidence_id,
        selected_choice=proposal.packet.selected_choice,
        disposition=proposal.policy.disposition.value,
        provider=proposal.packet.provider,
        confidence=proposal.packet.confidence,
        canonical_authority=False,
    )


def _resolve_with_guarded_flow(
    db: Session, body: DecisionResolutionRequest
) -> DecisionResolutionResponse:
    """Spec 006 path: Clef behind the T010 resolution machine and Spec 005 policy.

    Disposition stays owned by DecisionPolicy; the response is advisory only and
    canonical inventory is never touched. Provider failures fail closed (REJECT)
    and persist no receipt.
    """
    from intelligence.clef_resolution import resolve_module_identity_guarded
    from intelligence.evidence_resolution import (
        DecisionIntelligenceDisabled,
        EvidenceResolutionError,
    )
    from intelligence.policy import DecisionPolicy, PolicyThresholds

    # Retention- and consent-aware loader for the image asset bound to this evidence.
    # It is lazy and only constructed when the Clef flag is on; a disabled adapter never
    # invokes it, so the flag-off path performs no image load and no network call.
    image_loader = None
    if settings.enable_clef_provider:
        from intelligence.evidence_images import BoundEvidenceImageLoader

        image_loader = BoundEvidenceImageLoader(
            db, evidence_id=body.evidence_id, storage_root=_evidence_root()
        )

    try:
        provider = _configured_decision_provider(image_loader=image_loader)
        thresholds = PolicyThresholds(
            policy_version=settings.decision_policy_version,
            auto_propose_at=settings.decision_auto_propose_at,
            user_review_at=settings.decision_user_review_at,
            probability_margin=settings.decision_probability_margin,
        )
        resolution = resolve_module_identity_guarded(
            db,
            evidence_id=body.evidence_id,
            provider=provider,
            policy=DecisionPolicy(thresholds),
            enabled=True,
            idempotency_key=body.idempotency_key,
            expected_policy_version=settings.decision_policy_version,
        )
    except DecisionIntelligenceDisabled as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (EvidenceResolutionError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if resolution.proposal is None:
        code = resolution.error_code or "PROVIDER_ERROR"
        raise HTTPException(status_code=_guarded_failure_status(code), detail=code)

    db.commit()
    proposal = resolution.proposal
    return DecisionResolutionResponse(
        evidence_id=body.evidence_id,
        selected_choice=proposal.packet.selected_choice,
        disposition=proposal.policy.disposition.value,
        provider=proposal.packet.provider,
        confidence=proposal.packet.confidence,
        canonical_authority=False,
    )
