"""Multi-image evidence upload, listing, and retention-aware deletion."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from canon.models import (
    ClassificationEvidenceRecord,
    EvidenceDecisionRecord,
    ImageAssetRecord,
    PhotoReadingRecord,
    PhotoSightingRecord,
    SystemInventoryRevisionRecord,
)
from canon.visual_contracts import SystemInventoryRevision
from core import generate_rig_suggested_name, get_db, hash_string_to_seed, settings
from core.storage import StorageError, get_file_store
from evidence.images import (
    SignatureImageScanner,
    UnsafeImageError,
    assess_local_image_quality,
    prepare_image_evidence,
)
from evidence.cloud_provider import select_vision_provider
from evidence.reading_confirm import ConfirmRefused, ReadingConfirmRequest, confirm_readings
from evidence.readings import (
    REPLACEABLE_STATUSES,
    RETRYABLE_STATUSES,
    move_readings,
    photo_reading_closed_reason,
    read_photo,
)
from evidence.vision_provider import (
    VisionProviderContext,
    bind_packet_to_evidence,
    collect_evidence_packet,
)
from community.auth import require_auth
from community.models import User
from intelligence.evidence_images import ImageAccessDecision, image_access_decision
from racks.access import owned_private_rack, private_rack
from modules.models import Module
from racks.models import Rack

router = APIRouter()

DEFAULT_RETENTION_DAYS = 30
# Spec 001 OQ-10 (provisional): a requested retention is capped at 90 days.
MAX_RETENTION_DAYS = 90
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


class PhotoReadingCapability(BaseModel):
    available: bool
    # Why not, as a reason code, when it isn't.
    reason: str | None = None


class RigPhotoStartResponse(BaseModel):
    rig_id: int
    photo_id: str
    reading_id: str


class SightingResponse(BaseModel):
    sighting_id: str
    box: dict[str, float]
    kind: str
    row_index: int
    start_hp: int
    hp: int
    candidates: list[dict[str, Any]]
    disposition: str


class PhotoReadingResponse(BaseModel):
    reading_id: str
    photo_id: str
    status: str
    reason_code: str | None = None
    provider: str
    provider_version: str | None = None
    photo_sha256: str
    policy_version: str
    first_row: int
    last_row: int
    created_at: datetime
    completed_at: datetime | None = None
    sightings: list[SightingResponse]


class PhotoReadingListResponse(BaseModel):
    readings: list[PhotoReadingResponse]


def _evidence_root() -> Path:
    root = Path(settings.export_dir) / "evidence"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _store_image_asset(
    db: Session,
    prepared: Any,
    *,
    rack_id: int,
    user_id: int,
    retention_days: int,
    consent_provider_processing: bool,
    now: datetime,
) -> ImageAssetRecord:
    """Make a prepared image's bytes durable, then record them as the rack's evidence.

    Raises ``StorageError`` before recording anything when the bytes can't be kept.
    """
    storage_path = _evidence_root() / f"{prepared.sha256}.jpg"
    if not storage_path.exists():
        storage_path.write_bytes(prepared.content)
    # Never record a path whose bytes are not durable.
    get_file_store().persist(storage_path)
    record = ImageAssetRecord(
        id=f"img-{uuid.uuid4().hex[:20]}",
        rack_id=rack_id,
        user_id=user_id,
        content_sha256=prepared.sha256,
        media_type=prepared.media_type,
        width=prepared.width,
        height=prepared.height,
        byte_length=len(prepared.content),
        storage_path=str(storage_path),
        retention_days=retention_days,
        retention_expires_at=now + timedelta(days=retention_days),
        consent_provider_processing=consent_provider_processing,
        created_at=now,
    )
    db.add(record)
    db.flush()
    return record


def _photo_rows(rows: str) -> tuple[int, int]:
    """The rows a photo covers, first and last: "0", or "0-1" for rows 0 to 1."""
    match = re.fullmatch(r"(\d+)(?:-(\d+))?", rows.strip())
    if not match:
        raise HTTPException(status_code=400, detail="ROWS_INVALID")
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if end < start:
        raise HTTPException(status_code=400, detail="ROWS_INVALID")
    return start, end


# A photo in one of these is no longer stored, so nothing can read it again.
PHOTO_GONE = frozenset(
    {
        ImageAccessDecision.ASSET_MISSING,
        ImageAccessDecision.ASSET_DELETED,
        ImageAccessDecision.RETENTION_EXPIRED,
    }
)


def _photo_bytes(asset: ImageAssetRecord) -> bytes | None:
    """A stored photo's bytes, or None once it has expired or been deleted. Bytes that aren't
    the stored photo, or that went while it was read, are as good as gone. A store that can't
    answer is a 503."""
    if image_access_decision(asset, now=datetime.now(timezone.utc)) in PHOTO_GONE:
        return None
    path = Path(str(asset.storage_path))
    try:
        stored = get_file_store().ensure_local(path)
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=exc.code) from None
    try:
        image = path.read_bytes() if stored else None
    except FileNotFoundError:
        return None
    if image is None or hashlib.sha256(image).hexdigest() != str(asset.content_sha256):
        return None
    return image


def _stored_photo(db: Session, reading: PhotoReadingRecord) -> tuple[ImageAssetRecord, bytes]:
    """A Reading's stored photo and its bytes, refused with ``PHOTO_EXPIRED`` once it is gone:
    a Reading never outlives its photo."""
    asset = db.get(ImageAssetRecord, reading.image_asset_id)
    if asset is None or (image := _photo_bytes(asset)) is None:
        raise HTTPException(status_code=409, detail="PHOTO_EXPIRED")
    return asset, image


def _supersede(db: Session, reading_id: str, *, statuses: tuple[str, ...]) -> bool:
    return move_readings(db, [reading_id], from_statuses=statuses, to="superseded") == 1


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
    recorded; live cloud providers are not invoked. Mock evidence never runs in production:
    there the photo is stored and nothing is read.
    """
    rack = owned_private_rack(db, rack_id, current_user)
    if not files:
        raise HTTPException(status_code=400, detail="NO_FILES")
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=400, detail="TOO_MANY_FILES")
    if retention_days < 1 or retention_days > MAX_RETENTION_DAYS:
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

            try:
                record = _store_image_asset(
                    db,
                    prepared,
                    rack_id=rack_id,
                    user_id=user_id,
                    retention_days=retention_days,
                    consent_provider_processing=consent_provider_processing,
                    now=now,
                )
            except StorageError as exc:
                rejected.append({"filename": filename, "reason": exc.code})
                continue
            asset_id = str(record.id)

            evidence_status = None
            # The mock derives what it "sees" from the photo's hash, so production never runs it:
            # there a Module nobody saw would be offered (decision 63). Staging keeps it for its
            # checks on test cards (006 T060b).
            if run_vision_mock and settings.environment.strip().lower() != "production":
                packet = collect_evidence_packet(
                    provider,
                    VisionProviderContext(
                        image_asset_id=asset_id,
                        image_bytes=prepared.content,
                        request_id=f"req-{asset_id}",
                    ),
                )
                evidence_status = str(packet.get("status"))
                # The stored record id is the one authoritative evidence id: the
                # candidates endpoint shows it and decision resolution binds to it.
                evidence_id = f"ev-{uuid.uuid4().hex[:20]}"
                packet = bind_packet_to_evidence(packet, evidence_id)
                db.add(
                    ClassificationEvidenceRecord(
                        id=evidence_id,
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


@router.get("/evidence/photo-reading", response_model=PhotoReadingCapability)
def photo_reading_capability() -> PhotoReadingCapability:
    """Whether this host reads Rig photos, and why not when it doesn't (spec 009). Read-only,
    and open to anyone, so the Photo screen can offer manual entry instead."""
    reason = photo_reading_closed_reason()
    return PhotoReadingCapability(available=reason is None, reason=reason)


@router.post("/evidence/rig-photos", response_model=RigPhotoStartResponse, status_code=201)
async def start_rig_from_photo(
    file: UploadFile = File(...),
    rows: str = Form("0"),
    rig_id: int | None = Form(None),
    replaces_reading_id: str | None = Form(None),
    retention_days: int = Form(DEFAULT_RETENTION_DAYS),
    consent_provider_processing: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> RigPhotoStartResponse:
    """Start a Rig from a photo of it, or add a photo to the owner's Rig (spec 009).

    With no ``rig_id`` this creates the Rig, with no Case, and stores the photo as its
    evidence in one request. The photo is re-encoded, metadata-stripped, private, and
    expires like every evidence image. ``rows`` names the rows it covers. The photo is read
    at once, and ``reading_id`` names its Reading, ``read`` or ``failed``. A host that reads
    no photos refuses before storing anything. A provider that sends the photo away reads it
    only when ``consent_provider_processing`` says the owner agreed.

    A Retake names the Rig's current Reading it replaces in ``replaces_reading_id``, and that
    Reading becomes ``superseded``. A photo that names none is another photo of the Rig.
    """
    if photo_reading_closed_reason():
        raise HTTPException(status_code=409, detail="PHOTO_READING_UNAVAILABLE")
    covered = _photo_rows(rows)
    if retention_days < 1 or retention_days > MAX_RETENTION_DAYS:
        raise HTTPException(status_code=400, detail="RETENTION_DAYS_INVALID")
    if replaces_reading_id is not None and rig_id is None:
        raise HTTPException(status_code=400, detail="RETAKE_NEEDS_RIG")
    rack = owned_private_rack(db, rig_id, current_user, label="Rig") if rig_id is not None else None
    if replaces_reading_id is not None:
        replaced = (
            db.query(PhotoReadingRecord)
            .filter(
                PhotoReadingRecord.id == replaces_reading_id,
                PhotoReadingRecord.rack_id == rig_id,
            )
            .first()
        )
        if replaced is None:
            raise HTTPException(status_code=404, detail="READING_NOT_FOUND")
        if replaced.status not in REPLACEABLE_STATUSES:
            raise HTTPException(status_code=409, detail="READING_NOT_REPLACEABLE")

    raw = await file.read()
    try:
        prepared = prepare_image_evidence(
            raw,
            declared_media_type=file.content_type,
            scanner=SignatureImageScanner(),
        )
    except UnsafeImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    quality = assess_local_image_quality(prepared)
    if not quality.accepted:
        reason = quality.reasons[0] if quality.reasons else "QUALITY_REJECTED"
        raise HTTPException(status_code=400, detail=reason)

    if rack is None:
        name = generate_rig_suggested_name([])
        owner_id = int(current_user.id)  # type: ignore[arg-type]
        rack = Rack(
            user_id=owner_id,
            case_id=None,
            name=name,
            name_suggested=name,
            tags=[],
            is_public=False,
            generation_seed=hash_string_to_seed(f"rack-{owner_id}-photo-{prepared.sha256}"),
        )
        db.add(rack)
        db.flush()
    if replaces_reading_id is not None and not _supersede(
        db, replaces_reading_id, statuses=REPLACEABLE_STATUSES
    ):
        raise HTTPException(status_code=409, detail="READING_NOT_REPLACEABLE")
    try:
        # The photo is the Rig owner's evidence, as on the existing upload.
        record = _store_image_asset(
            db,
            prepared,
            rack_id=int(rack.id),  # type: ignore[arg-type]
            user_id=int(rack.user_id),  # type: ignore[arg-type]
            retention_days=retention_days,
            consent_provider_processing=consent_provider_processing,
            now=datetime.now(timezone.utc),
        )
    except StorageError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=exc.code) from None
    reading = read_photo(
        db,
        asset=record,
        photo_sha256=hashlib.sha256(raw).hexdigest(),
        image=prepared.content,
        rows=covered,
    )
    db.commit()
    return RigPhotoStartResponse(
        rig_id=int(rack.id),  # type: ignore[arg-type]
        photo_id=str(record.id),
        reading_id=str(reading.id),
    )


def _named_candidate(candidate: dict[str, Any], modules: dict[int, Module]) -> dict[str, Any]:
    """A candidate with its Module's maker, name and width, so the Reading screen can offer it."""
    module = modules.get(int(candidate["module_id"]))
    return {
        **candidate,
        "brand": module.brand if module else None,
        "name": module.name if module else None,
        "hp": module.hp if module else None,
    }


@router.get("/racks/{rack_id}/evidence/readings", response_model=PhotoReadingListResponse)
def list_rack_photo_readings(
    rack_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> PhotoReadingListResponse:
    """The Rig's Readings, oldest first, each with its Sightings by row and HP (spec 009)."""
    private_rack(db, rack_id, current_user, label="Rig")
    readings = (
        db.query(PhotoReadingRecord)
        .filter(PhotoReadingRecord.rack_id == rack_id)
        .order_by(PhotoReadingRecord.created_at.asc(), PhotoReadingRecord.id.asc())
        .all()
    )
    sightings: dict[str, list[PhotoSightingRecord]] = {r.id: [] for r in readings}  # type: ignore[misc]
    if readings:
        for sighting in (
            db.query(PhotoSightingRecord)
            .filter(PhotoSightingRecord.reading_id.in_(list(sightings)))
            .order_by(
                PhotoSightingRecord.row_index.asc(),
                PhotoSightingRecord.start_hp.asc(),
                PhotoSightingRecord.position.asc(),
            )
        ):
            sightings[str(sighting.reading_id)].append(sighting)
    named = {
        int(c["module_id"]) for found in sightings.values() for s in found for c in s.candidates
    }
    modules = {int(m.id): m for m in db.query(Module).filter(Module.id.in_(named))} if named else {}
    return PhotoReadingListResponse(
        readings=[
            PhotoReadingResponse(
                reading_id=str(r.id),
                photo_id=str(r.image_asset_id),
                status=str(r.status),
                reason_code=r.reason_code,
                provider=str(r.provider),
                provider_version=r.provider_version,
                photo_sha256=str(r.photo_sha256),
                policy_version=str(r.policy_version),
                first_row=int(r.first_row),  # type: ignore[arg-type]
                last_row=int(r.last_row),  # type: ignore[arg-type]
                created_at=r.created_at,
                completed_at=r.completed_at,
                sightings=[
                    SightingResponse(
                        sighting_id=str(s.id),
                        box=dict(s.box),
                        kind=str(s.kind),
                        row_index=int(s.row_index),  # type: ignore[arg-type]
                        start_hp=int(s.start_hp),  # type: ignore[arg-type]
                        hp=int(s.hp),  # type: ignore[arg-type]
                        candidates=[_named_candidate(c, modules) for c in s.candidates],
                        disposition=str(s.disposition),
                    )
                    for s in sightings[str(r.id)]
                ],
            )
            for r in readings
        ]
    )


@router.post(
    "/racks/{rack_id}/evidence/readings/{reading_id}/retry",
    response_model=RigPhotoStartResponse,
    status_code=201,
)
def retry_rack_photo_reading(
    rack_id: int,
    reading_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> RigPhotoStartResponse:
    """Read a ``failed`` Reading's stored photo again as a new Reading, and supersede the
    failed one (spec 009). Once the photo has expired or been deleted, the owner retakes."""
    owned_private_rack(db, rack_id, current_user, label="Rig")
    reading = (
        db.query(PhotoReadingRecord)
        .filter(PhotoReadingRecord.id == reading_id, PhotoReadingRecord.rack_id == rack_id)
        .first()
    )
    if reading is None:
        raise HTTPException(status_code=404, detail="READING_NOT_FOUND")
    if photo_reading_closed_reason():
        raise HTTPException(status_code=409, detail="PHOTO_READING_UNAVAILABLE")
    if reading.status not in RETRYABLE_STATUSES:
        raise HTTPException(status_code=409, detail="READING_NOT_FAILED")
    asset, image = _stored_photo(db, reading)
    if not _supersede(db, reading_id, statuses=RETRYABLE_STATUSES):
        raise HTTPException(status_code=409, detail="READING_NOT_FAILED")
    fresh = read_photo(
        db,
        asset=asset,
        photo_sha256=str(reading.photo_sha256),
        image=image,
        rows=(int(reading.first_row), int(reading.last_row)),
    )
    db.commit()
    return RigPhotoStartResponse(
        rig_id=rack_id, photo_id=str(reading.image_asset_id), reading_id=str(fresh.id)
    )


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


@router.get("/racks/{rack_id}/evidence/images/{asset_id}/content")
def rack_evidence_image_content(
    rack_id: int,
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> Response:
    """The owner's photo, for the Reading screen (spec 009): private, and never cached. Gone
    once it has expired or been deleted."""
    owned_private_rack(db, rack_id, current_user, label="Rig")
    record = (
        db.query(ImageAssetRecord)
        .filter(ImageAssetRecord.id == asset_id, ImageAssetRecord.rack_id == rack_id)
        .first()
    )
    image = _photo_bytes(record) if record is not None else None
    if record is None or image is None:
        raise HTTPException(status_code=404, detail="PHOTO_NOT_FOUND")
    return Response(
        content=image,
        media_type=str(record.media_type),
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> dict[str, str]:
    """Delete an evidence image the caller owns: soft-delete the row and remove its bytes.

    Owner only; anyone who cannot see the rack gets 404 (spec 001 OQ-10, provisional).
    The bytes are removed unless another live asset shares the same content hash, as in
    ``evidence.retention.expire_image_assets``. Classification evidence, decision
    receipts and inventory revisions stay as append-only history: they keep reading, but
    the deleted image is no longer served, listed as a candidate source, or accepted for
    a new decision (``image_access_decision`` returns ASSET_DELETED).
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
    # The newest decision on this candidate, if any: confirm, reject, defer, replace, manual_add.
    last_decision: str | None = None


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
    # Who confirmed is the signed-in user, never a client-supplied name (spec 005 FR-006).


class ModuleToPlaceOut(BaseModel):
    """A confirmed photo module not on the rack yet. Place it with ``PATCH /api/racks/{id}``."""

    instance_id: str
    module_revision_id: str
    manufacturer: str | None = None
    model: str | None = None
    # None when no single catalog row matches; nothing invents one.
    module_id: int | None = None


class ConfirmationBatchResponse(BaseModel):
    inventory_revision_id: str
    inventory_canonical_hash: str | None
    confirmed_count: int
    unresolved_candidate_ids: list[str]
    # Generation's own gate answer for this Rig (#283).
    ready_for_generation: bool
    modules_to_place: list[ModuleToPlaceOut]


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
    # Receipts carry a hash of the retained packet and image (R5). Receipts written
    # before that change carry the raw evidence id, so both forms bind.
    hash_by_evidence_id: dict[str, str] = {}
    if evidence_hashes:
        from canon.models import ClassificationEvidenceRecord, ImageAssetRecord
        from intelligence.evidence_resolution import retained_evidence_hash

        rows = (
            db.query(ClassificationEvidenceRecord, ImageAssetRecord.content_sha256)
            .join(
                ImageAssetRecord, ImageAssetRecord.id == ClassificationEvidenceRecord.image_asset_id
            )
            .filter(ClassificationEvidenceRecord.id.in_(evidence_hashes))
            .all()
        )
        for record, image_sha in rows:
            hash_by_evidence_id[record.id] = retained_evidence_hash(
                record.evidence_packet or {}, image_sha
            )
    evidence_hashes |= set(hash_by_evidence_id.values())
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

    latest_decisions = _latest_decisions(db, rack_id)
    candidates = []
    for item in items:
        evidence_id = str(item["evidence_id"])
        receipt = receipts_by_binding.get(
            (item["candidate_id"], hash_by_evidence_id.get(evidence_id, evidence_id))
        ) or receipts_by_binding.get((item["candidate_id"], evidence_id))
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
        latest = latest_decisions.get(item["candidate_id"])
        payload["last_decision"] = latest.status if latest else None
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
    # Generation reads the Rig's placements, not a revision, so every summary carries the
    # gate's one answer for the Rig as it is now (#283).
    ready_for_generation: bool
    canonical_hash: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None


class InventoryRevisionListResponse(BaseModel):
    total: int
    latest: InventoryRevisionSummary | None = None
    revisions: list[InventoryRevisionSummary]
    # From the newest photo confirmation, which ``latest`` may not be: generation also
    # seals revisions, from placements.
    modules_to_place: list[ModuleToPlaceOut]


def _modules_to_place(
    db: Session, rack: Rack, inventory: SystemInventoryRevision
) -> list[ModuleToPlaceOut]:
    from patches.inventory_gate import modules_still_to_place

    return [
        ModuleToPlaceOut(**asdict(entry)) for entry in modules_still_to_place(db, rack, inventory)
    ]


def _latest_decisions(db: Session, rack_id: int) -> dict[str, EvidenceDecisionRecord]:
    """The newest recorded decision for each candidate on this rack."""
    rows = (
        db.query(EvidenceDecisionRecord)
        .filter(EvidenceDecisionRecord.rack_id == rack_id)
        .order_by(EvidenceDecisionRecord.decided_at.asc(), EvidenceDecisionRecord.id.asc())
    )
    return {row.candidate_id: row for row in rows}


def _record_decisions(
    db: Session,
    rack_id: int,
    requested: list[ConfirmationDecisionIn],
    decisions: list,
    inventory_revision_id: str,
) -> None:
    """Keep every decision, a reject included, and name the one a changed decision reverses
    (spec 001 D8). A reject still leaves the candidate listed and canon unchanged."""
    latest = _latest_decisions(db, rack_id)
    for asked, decision in zip(requested, decisions, strict=True):
        earlier = latest.get(decision.candidate_id)
        db.add(
            EvidenceDecisionRecord(
                id=decision.confirmation_id,
                rack_id=rack_id,
                candidate_id=decision.candidate_id,
                status=decision.status,
                module_revision_id=asked.module_revision_id,
                replacement_candidate_id=decision.replacement_candidate_id,
                inventory_revision_id=inventory_revision_id,
                reverses_decision_id=(
                    earlier.id if earlier and earlier.status != decision.status else None
                ),
                decided_by=decision.confirmed_by,
                decided_at=decision.confirmed_at,
            )
        )
    db.flush()


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
    from canon.inventory_persist import load_system_inventory_revision
    from patches.inventory_gate import evaluate_rack_inventory_gate, latest_confirmation_revision

    rack = private_rack(db, rack_id, current_user)
    gate_report, _ = evaluate_rack_inventory_gate(db, rack)
    confirmation = latest_confirmation_revision(db, rack)

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
        summaries.append(
            InventoryRevisionSummary(
                inventory_revision_id=row.id,
                system_id=row.system_id,
                rack_id=row.rack_id,
                confirmed_count=confirmed,
                unresolved_count=unresolved,
                ready_for_generation=gate_report.ready,
                canonical_hash=row.canonical_hash,
                created_by=row.created_by,
                created_at=row.created_at,
            )
        )
    return InventoryRevisionListResponse(
        total=len(summaries),
        latest=summaries[0] if summaries else None,
        revisions=summaries,
        modules_to_place=_modules_to_place(db, rack, confirmation) if confirmation else [],
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
    confirmed_by = f"user:{current_user.id}"
    from canon.inventory import InventoryBuildError, build_system_inventory_revision
    from canon.inventory_persist import persist_system_inventory_revision
    from canon.visual_contracts import (
        ClassificationCandidate,
        ConfirmationDecision,
        ResolutionStatus,
    )
    from patches.inventory_gate import evaluate_rack_inventory_gate

    rack = owned_private_rack(db, rack_id, current_user)
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
                confirmed_by=confirmed_by,
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
            created_by=confirmed_by,
        )
    except InventoryBuildError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    persist_system_inventory_revision(db, inventory, rack_id=rack_id)
    _record_decisions(db, rack_id, body.decisions, decisions, inventory.inventory_revision_id)
    # ClassificationEvidenceRecord is append-only; inventory linkage is via
    # SystemInventoryRevisionRecord + candidate source_candidate_ids, not mutation.
    db.commit()
    # A candidate has no position, so confirming it adds no placement; generation reads
    # placements (#283). Confirming a Reading does place its Modules (decision 59).
    gate_report, _ = evaluate_rack_inventory_gate(db, rack)
    return ConfirmationBatchResponse(
        inventory_revision_id=inventory.inventory_revision_id,
        inventory_canonical_hash=inventory.canonical_hash,
        confirmed_count=len(inventory.items),
        unresolved_candidate_ids=list(inventory.unresolved_candidate_ids),
        ready_for_generation=gate_report.ready,
        modules_to_place=_modules_to_place(db, rack, inventory),
    )


class ReadingConfirmResponse(BaseModel):
    rig_revision_id: str
    inventory_revision_id: str
    ready_for_generation: bool
    placements: list[dict[str, int]]
    modules_to_place: list[ModuleToPlaceOut]
    # Advisories on the layout, such as POWER_UNSPECIFIED when no Case states a budget.
    warnings: list[dict[str, Any]] = Field(default_factory=list)


@router.post(
    "/racks/{rack_id}/evidence/readings/confirm",
    response_model=ReadingConfirmResponse,
    status_code=201,
)
def confirm_rack_photo_readings(
    rack_id: int,
    body: ReadingConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
) -> ReadingConfirmResponse:
    """Confirm the Rig's current Readings as its layout (spec 009).

    The owner's final list becomes the Rig's placements, in one new Rig revision, and
    readiness counts those positions. A refusal answers ``{"code", "modules"}`` and writes
    nothing.
    """
    from patches.inventory_gate import evaluate_rack_inventory_gate

    rack = owned_private_rack(db, rack_id, current_user, label="Rig")
    try:
        result = confirm_readings(db, rack, body, confirmed_by=f"user:{current_user.id}")
    except ConfirmRefused as refused:
        db.rollback()  # a refusal writes nothing, even after the Readings were claimed
        raise HTTPException(status_code=refused.status_code, detail=refused.detail) from None
    db.commit()
    gate_report, _ = evaluate_rack_inventory_gate(db, rack)
    return ReadingConfirmResponse(
        rig_revision_id=result.rig_revision_id,
        inventory_revision_id=result.inventory.inventory_revision_id,
        ready_for_generation=gate_report.ready,
        placements=result.placements,
        modules_to_place=_modules_to_place(db, rack, result.inventory),
        warnings=[w.model_dump() for w in result.warnings],
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
    if settings.decision_provider == "nvidia":
        from intelligence.nvidia_provider import NvidiaVisionProvider

        # Fail-closed like Clef: with enable_nvidia_provider off every call returns
        # NVIDIA_DISABLED without a network call.
        if settings.enable_nvidia_provider and not settings.nvidia_api_key:
            raise RuntimeError("NVIDIA_API_KEY_NOT_CONFIGURED")
        return NvidiaVisionProvider(
            enabled=settings.enable_nvidia_provider,
            api_key=settings.nvidia_api_key,
            model=settings.nvidia_model,
            base_url=settings.nvidia_base_url,
            timeout_seconds=settings.nvidia_timeout_seconds,
            image_loader=image_loader,
        )
    raise RuntimeError("DECISION_PROVIDER_NOT_CONFIGURED")


_GUARDED_FAILURE_STATUS = {
    "CLEF_DISABLED": 409,
    "CLEF_INVALID_REQUEST": 422,
    "NVIDIA_DISABLED": 409,
    "NVIDIA_INVALID_REQUEST": 422,
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
    """Produce and retain one non-canonical identity advisory.

    Every provider runs behind the resolution machine and the configured policy version
    (spec 005 FR-010, research R2); there is no unguarded path.
    """
    owned_private_rack(db, rack_id, current_user)

    evidence = db.get(ClassificationEvidenceRecord, body.evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    asset = db.get(ImageAssetRecord, evidence.image_asset_id)
    if asset is None or int(asset.rack_id) != rack_id or asset.deleted_at is not None:
        raise HTTPException(status_code=400, detail="EVIDENCE_NOT_BOUND_TO_RACK")

    if not settings.enable_decision_intelligence:
        raise HTTPException(status_code=409, detail="DECISION_INTELLIGENCE_DISABLED")
    # Defence in depth for the startup gate (spec 005 T080, research R1).
    from intelligence.enablement_gate import enablement_gate_failures

    gate_failures = enablement_gate_failures(settings)
    if gate_failures:
        raise HTTPException(
            status_code=409,
            detail={"code": "ENABLEMENT_RECEIPT_REQUIRED", "failures": list(gate_failures)},
        )

    return _resolve_with_guarded_flow(db, body)


def _resolve_with_guarded_flow(
    db: Session, body: DecisionResolutionRequest
) -> DecisionResolutionResponse:
    """Any provider behind the T010 resolution machine and Spec 005 policy.

    Disposition stays owned by DecisionPolicy; the response is advisory only and
    canonical inventory is never touched. A provider failure or an unreadable packet
    ends UNRESOLVED (or ESCALATE with a review route), returns an error code and
    persists no receipt.
    """
    from intelligence.clef_resolution import resolve_module_identity_guarded
    from intelligence.evidence_resolution import (
        DecisionIntelligenceDisabled,
        EvidenceResolutionError,
    )
    from intelligence.persistence import IdempotencyConflict
    from intelligence.policy import DecisionPolicy, PolicyThresholds

    # Retention- and consent-aware loader for the image asset bound to this evidence.
    # It is lazy and only constructed when a vision provider's flag is on (Clef or
    # NVIDIA); a disabled adapter never invokes it, so the flag-off path performs no
    # image load and no network call.
    image_loader = None
    if settings.enable_clef_provider or settings.enable_nvidia_provider:
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
            routing_targets=(
                frozenset({settings.decision_routing_target})
                if settings.decision_routing_target
                else frozenset()
            ),
        )
    except DecisionIntelligenceDisabled as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (EvidenceResolutionError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    replayed = resolution.replayed_outcome
    if replayed is not None:
        # Same key, same evidence: answer from the stored outcome, no provider call.
        # The disposition is the one bound to this key, not the shared receipt's.
        stored = replayed.receipt
        return DecisionResolutionResponse(
            evidence_id=body.evidence_id,
            selected_choice=stored.selected_choice,
            disposition=replayed.disposition,
            provider=stored.provider,
            confidence=stored.confidence,
            canonical_authority=False,
        )

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
