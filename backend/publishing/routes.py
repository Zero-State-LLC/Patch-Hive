"""
Publishing layer API routes.
"""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from admin.models import AdminAuditLog
from community.auth import get_current_user, require_admin, require_auth
from community.models import User
from core import Provenance, get_db, settings
from export.pdf import generate_patch_pdf, generate_rack_pdf
from export.visualization import generate_patch_diagram_svg, generate_rack_layout_svg
from patches.models import Patch
from racks.models import Rack

from .models import Export, Publication, PublicationReport
from .schemas import (
    AdminModerationRequest,
    ExportCreate,
    ExportResponse,
    GalleryResponse,
    PublicationCard,
    PublicationCreate,
    PublicationListResponse,
    PublicationOwnerResponse,
    PublicationPublicResponse,
    PublicationUpdate,
    ReportCreate,
)
from .utils import slugify_title, unique_slug

router = APIRouter()


ARTIFACT_TYPES = {"pdf", "svg", "zip"}


def _ensure_export_dir() -> None:
    os.makedirs(settings.export_dir, exist_ok=True)


def _write_svg(svg: str, filename: str) -> str:
    _ensure_export_dir()
    path = os.path.join(settings.export_dir, filename)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(svg)
    return path


def _zip_artifacts(paths: list[str], filename: str) -> str:
    _ensure_export_dir()
    zip_path = os.path.join(settings.export_dir, filename)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            if path and os.path.exists(path):
                archive.write(path, arcname=os.path.basename(path))
    return zip_path


def _build_manifest_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _create_export_from_patch(db: Session, patch: Patch, owner: User) -> Export:
    provenance = Provenance.create(entity_type="export", pipeline="export")
    provenance.mark_completed()

    pdf_path = generate_patch_pdf(db, patch)
    rack = db.query(Rack).filter(Rack.id == patch.rack_id).first()
    if not rack:
        raise HTTPException(status_code=404, detail="Rack not found")

    diagram_svg = generate_patch_diagram_svg(db, rack, patch.connections)
    diagram_path = _write_svg(
        diagram_svg, f"patch_{patch.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.svg"
    )

    zip_path = _zip_artifacts(
        [pdf_path, diagram_path],
        f"patch_{patch.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip",
    )

    artifact_urls = {
        "pdf": pdf_path,
        "svg": diagram_path,
        "zip": zip_path,
    }

    manifest_hash = _build_manifest_hash(
        {
            "export_type": "patch",
            "patch_id": patch.id,
            "run_id": provenance.run_id,
            "generated_at": provenance.completed_at,
            "artifact_urls": artifact_urls,
        }
    )

    export = Export(
        owner_user_id=owner.id,
        patch_id=patch.id,
        export_type="patch",
        license="CC BY-NC 4.0",
        run_id=provenance.run_id,
        generated_at=datetime.utcnow(),
        patch_count=1,
        manifest_hash=manifest_hash,
        artifact_urls=artifact_urls,
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


def _create_export_from_rack(db: Session, rack: Rack, owner: User) -> Export:
    provenance = Provenance.create(entity_type="export", pipeline="export")
    provenance.mark_completed()

    pdf_path = generate_rack_pdf(db, rack)
    layout_svg = generate_rack_layout_svg(db, rack)
    layout_path = _write_svg(
        layout_svg,
        f"rack_{rack.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.svg",
    )

    zip_path = _zip_artifacts(
        [pdf_path, layout_path],
        f"rack_{rack.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip",
    )

    artifact_urls = {
        "pdf": pdf_path,
        "svg": layout_path,
        "zip": zip_path,
    }

    manifest_hash = _build_manifest_hash(
        {
            "export_type": "rack",
            "rack_id": rack.id,
            "run_id": provenance.run_id,
            "generated_at": provenance.completed_at,
            "artifact_urls": artifact_urls,
        }
    )

    export = Export(
        owner_user_id=owner.id,
        rack_id=rack.id,
        export_type="rack",
        license="CC BY-NC 4.0",
        run_id=provenance.run_id,
        generated_at=datetime.utcnow(),
        patch_count=len(rack.patches),
        manifest_hash=manifest_hash,
        artifact_urls=artifact_urls,
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


@router.post("/me/exports", response_model=ExportResponse, status_code=201)
def create_export(
    payload: ExportCreate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Create an export for the current user."""
    if payload.source_type == "patch":
        patch = db.query(Patch).filter(Patch.id == payload.source_id).first()
        if not patch:
            raise HTTPException(status_code=404, detail="Patch not found")
        rack = db.query(Rack).filter(Rack.id == patch.rack_id).first()
        if rack is not None and rack.deleted_at is not None:
            # A deleted rack is gone, patches included (spec 001 OQ-02).
            raise HTTPException(status_code=404, detail="Patch not found")
        if not rack or rack.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Export ownership mismatch")
        return _create_export_from_patch(db, patch, current_user)

    rack = db.query(Rack).filter(Rack.id == payload.source_id).first()
    if not rack or rack.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Rack not found")
    if rack.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Export ownership mismatch")
    return _create_export_from_rack(db, rack, current_user)


@router.get("/me/exports", response_model=list[ExportResponse])
def list_exports(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """List exports for the current user."""
    exports = (
        db.query(Export)
        .filter(Export.owner_user_id == current_user.id)
        .order_by(desc(Export.created_at))
        .all()
    )
    return exports


@router.post("/me/publications", response_model=PublicationOwnerResponse, status_code=201)
def create_publication(
    payload: PublicationCreate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Create a publication for an export."""
    export = db.query(Export).filter(Export.id == payload.export_id).first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    if export.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Export ownership mismatch")

    existing = db.query(Publication).filter(Publication.export_id == export.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Export already published")

    slug = unique_slug(slugify_title(payload.title))
    publication = Publication(
        export_id=export.id,
        publisher_user_id=current_user.id,
        slug=slug,
        visibility=payload.visibility,
        # Spec 002 lifecycle: a new publication starts as a draft; the owner publishes it.
        status="draft",
        allow_download=payload.allow_download,
        allow_remix=payload.allow_remix,
        title=payload.title,
        description=payload.description,
        cover_image_url=payload.cover_image_url,
    )
    db.add(publication)
    db.commit()
    db.refresh(publication)
    return publication


@router.patch("/me/publications/{publication_id}", response_model=PublicationOwnerResponse)
def update_publication(
    publication_id: int,
    payload: PublicationUpdate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Update a publication owned by the current user."""
    publication = (
        db.query(Publication)
        .filter(Publication.id == publication_id, Publication.publisher_user_id == current_user.id)
        .first()
    )
    if not publication:
        raise HTTPException(status_code=404, detail="Publication not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "status" in update_data:
        status_value = update_data["status"]
        if status_value not in {"published", "hidden"}:
            raise HTTPException(status_code=400, detail="Invalid status transition")
        # An owner toggles only their own hide. A removed publication, or one an
        # admin hid (it carries a moderation audit), stays as moderation left it.
        if publication.status == "removed" or publication.moderation_audit_id is not None:
            raise HTTPException(status_code=409, detail="PUBLICATION_UNDER_MODERATION")
        if (publication.status, status_value) not in OWNER_TRANSITIONS:
            raise HTTPException(status_code=409, detail="INVALID_TRANSITION")
        publication.status = status_value
        if status_value == "published" and publication.published_at is None:
            publication.published_at = datetime.utcnow()
        update_data.pop("status")

    for field, value in update_data.items():
        setattr(publication, field, value)

    db.commit()
    db.refresh(publication)
    return publication


# Owner status changes allowed by the spec 002 publication lifecycle (from, to). Any
# other pair is rejected and changes nothing. Setting the current status again is a no-op.
OWNER_TRANSITIONS = {
    ("draft", "published"),
    ("published", "hidden"),
    ("hidden", "published"),
    ("published", "published"),
    ("hidden", "hidden"),
}


@router.get("/me/publications", response_model=PublicationListResponse)
def list_publications(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """List publications for current user."""
    publications = (
        db.query(Publication)
        .filter(Publication.publisher_user_id == current_user.id)
        .order_by(desc(Publication.updated_at))
        .all()
    )
    return PublicationListResponse(publications=publications)


@router.get("/p/{slug}", response_model=PublicationPublicResponse)
def get_publication(slug: str, db: Session = Depends(get_db)):
    """Get a public publication by slug."""
    publication = (
        db.query(Publication)
        .filter(Publication.slug == slug, Publication.status == "published")
        .first()
    )
    if not publication:
        raise HTTPException(status_code=404, detail="Publication not found")

    export = publication.export
    publisher = publication.publisher
    # Public profiles are outside the canonical MVP. Historical publications
    # therefore expose neither display names nor avatars.
    publisher_display = "PatchHive User"
    avatar_url = None

    download_urls = None
    if publication.allow_download:
        download_urls = {
            "pdf_url": f"/api/p/{publication.slug}/download/pdf",
            "svg_url": f"/api/p/{publication.slug}/download/svg",
            "zip_url": f"/api/p/{publication.slug}/download/zip",
        }

    return PublicationPublicResponse(
        title=publication.title,
        description=publication.description,
        cover_image_url=publication.cover_image_url,
        export_type=export.export_type,
        license=export.license,
        provenance={
            "run_id": export.run_id,
            "generated_at": export.generated_at.isoformat(),
            "patch_count": export.patch_count,
            "manifest_hash": export.manifest_hash,
        },
        publisher_display=publisher_display,
        avatar_url=avatar_url,
        allow_download=publication.allow_download,
        download_urls=download_urls,
    )


@router.get("/p/{slug}/download/{artifact_type}")
def download_publication_artifact(
    slug: str,
    artifact_type: str,
    db: Session = Depends(get_db),
):
    """Download publication artifact if allowed."""
    if artifact_type not in ARTIFACT_TYPES:
        raise HTTPException(status_code=404, detail="Artifact type not found")

    publication = (
        db.query(Publication)
        .filter(Publication.slug == slug, Publication.status == "published")
        .first()
    )
    if not publication:
        raise HTTPException(status_code=404, detail="Publication not found")

    if not publication.allow_download:
        raise HTTPException(status_code=403, detail="Downloads disabled")

    artifact_path = publication.export.artifact_urls.get(artifact_type)
    if not artifact_path or not os.path.exists(artifact_path):
        raise HTTPException(status_code=404, detail="Artifact not found")

    return FileResponse(artifact_path)


@router.get("/gallery/publications", response_model=GalleryResponse)
def list_gallery(
    limit: int = Query(20, ge=1, le=50),
    cursor: Optional[str] = None,
    export_type: Optional[str] = None,
    recent_days: Optional[int] = Query(None, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """List public publications for gallery."""
    query = (
        db.query(Publication)
        .filter(Publication.status == "published", Publication.visibility == "public")
        .order_by(desc(Publication.published_at))
    )

    if export_type:
        query = query.join(Export).filter(Export.export_type == export_type)

    if recent_days:
        since = datetime.utcnow() - timedelta(days=recent_days)
        query = query.filter(Publication.published_at >= since)

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor")
        query = query.filter(Publication.published_at < cursor_dt)

    publications = query.limit(limit).all()
    cards = [
        PublicationCard(
            slug=pub.slug,
            title=pub.title,
            description=pub.description,
            cover_image_url=pub.cover_image_url,
            export_type=pub.export.export_type,
            published_at=pub.published_at,
        )
        for pub in publications
    ]

    next_cursor = None
    if len(publications) == limit:
        last_pub = publications[-1]
        if last_pub.published_at:
            next_cursor = last_pub.published_at.isoformat()

    return GalleryResponse(publications=cards, next_cursor=next_cursor)


@router.post("/p/{slug}/report", status_code=201)
def report_publication(
    slug: str,
    payload: ReportCreate,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Report a publication."""
    publication = db.query(Publication).filter(Publication.slug == slug).first()
    # Only a published publication is publicly readable, so only it can be reported.
    if not publication or publication.status != "published":
        raise HTTPException(status_code=404, detail="Publication not found")

    report = PublicationReport(
        publication_id=publication.id,
        reporter_user_id=current_user.id if current_user else None,
        reason=payload.reason,
        details=payload.details,
    )
    db.add(report)
    db.commit()
    return {"status": "reported"}


def _audit_moderation(
    db: Session,
    actor: User,
    publication: Publication,
    action_type: str,
    reason: str,
    new_status: str,
) -> AdminAuditLog:
    before = {
        "status": publication.status,
        "visibility": publication.visibility,
        "allow_download": publication.allow_download,
        "allow_remix": publication.allow_remix,
    }
    after = {
        "status": new_status,
        "visibility": publication.visibility,
        "allow_download": publication.allow_download,
        "allow_remix": publication.allow_remix,
    }
    audit = AdminAuditLog(
        actor_user_id=actor.id,
        actor_role=actor.role,
        action_type=action_type,
        target_type="publication",
        target_id=publication.id,
        delta_json={"before": before, "after": after},
        reason=reason,
    )
    db.add(audit)
    db.flush()
    return audit


@router.post("/admin/publications/{publication_id}/hide", status_code=200)
def hide_publication(
    publication_id: int,
    payload: AdminModerationRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin hide a publication."""
    publication = db.query(Publication).filter(Publication.id == publication_id).first()
    if not publication:
        raise HTTPException(status_code=404, detail="Publication not found")
    if publication.status not in ("published",):
        raise HTTPException(status_code=409, detail="INVALID_TRANSITION")

    audit = _audit_moderation(
        db,
        current_user,
        publication,
        action_type="hide_publication",
        reason=payload.reason,
        new_status="hidden",
    )
    publication.status = "hidden"
    publication.moderation_audit_id = audit.id

    db.commit()
    return {"status": "hidden"}


@router.post("/admin/publications/{publication_id}/remove", status_code=200)
def remove_publication(
    publication_id: int,
    payload: AdminModerationRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin remove a publication."""
    publication = db.query(Publication).filter(Publication.id == publication_id).first()
    if not publication:
        raise HTTPException(status_code=404, detail="Publication not found")
    if publication.status not in ("published", "hidden"):
        raise HTTPException(status_code=409, detail="INVALID_TRANSITION")

    audit = _audit_moderation(
        db,
        current_user,
        publication,
        action_type="remove_publication",
        reason=payload.reason,
        new_status="removed",
    )
    publication.status = "removed"
    publication.removed_reason = payload.reason
    publication.moderation_audit_id = audit.id

    db.commit()
    return {"status": "removed"}
