"""
FastAPI routes for export functionality (PDF, SVG).
"""

from typing import Optional
import os
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from community.auth import get_current_user, require_auth
from community.models import User
from core import get_db, settings
from core.storage import StorageError, get_file_store
from monetization.credits import get_credits_balance
from monetization.models import CreditsLedger, Export
from patches.models import Patch
from racks.access import readable_patch, readable_rack
from racks.models import Rack
from runs.models import Run

from .pdf import generate_patch_pdf, generate_rack_pdf
from .visualization import generate_patch_diagram_svg, generate_rack_layout_svg
from .patchbook.build import build_patchbook_pdf_bytes_from_payload
from .patchbook.models import PatchBookExportRequest, PATCHBOOK_TEMPLATE_VERSION, PatchBookTier

router = APIRouter()


@router.get("/patches/{patch_id}/pdf")
def export_patch_pdf(
    patch_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Export a patch as PDF."""
    patch = readable_patch(db, patch_id, current_user)

    try:
        pdf_path = generate_patch_pdf(db, patch)
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"patch_{patch.id}_{patch.name.replace(' ', '_')}.pdf",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.get("/racks/{rack_id}/pdf")
def export_rack_pdf(
    rack_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Export a rack as PDF."""
    rack = readable_rack(db, rack_id, current_user)

    try:
        pdf_path = generate_rack_pdf(db, rack)
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"rack_{rack.id}_{rack.name.replace(' ', '_')}.pdf",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.get("/racks/{rack_id}/layout.svg")
def export_rack_layout_svg(
    rack_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Export rack layout as SVG."""
    rack = readable_rack(db, rack_id, current_user)

    try:
        svg = generate_rack_layout_svg(db, rack)
        return Response(content=svg, media_type="image/svg+xml")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SVG generation failed: {str(e)}")


@router.get("/patches/{patch_id}/diagram.svg")
def export_patch_diagram_svg(
    patch_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Export patch diagram as SVG."""
    patch = readable_patch(db, patch_id, current_user)

    rack = db.query(Rack).filter(Rack.id == patch.rack_id).first()
    if not rack:
        raise HTTPException(status_code=404, detail="Rack not found")

    try:
        svg = generate_patch_diagram_svg(db, rack, patch.connections)
        return Response(content=svg, media_type="image/svg+xml")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SVG generation failed: {str(e)}")


@router.post("/runs/{run_id}/patchbook")
def export_patchbook_pdf(
    run_id: int,
    force_fail: bool = Query(False),
    tier: PatchBookTier = Query(PatchBookTier.CORE),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Export a patch book PDF for a run (legacy credit-gated path).

    **Deprecated for MVP debit.** Prefer ``POST /api/canon/exports`` which
    debits the canonical ledger. This route remains transitional for PDF
    artifact generation and older clients. Set
    ``ENABLE_LEGACY_PATCHBOOK_DEBIT=false`` to reject new debits (410).
    """
    if not settings.enable_legacy_patchbook_debit:
        raise HTTPException(
            status_code=410,
            detail=(
                "LEGACY_PATCHBOOK_DEBIT_DISABLED — use POST /api/canon/exports "
                "for credit-gated exports"
            ),
        )

    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    readable_rack(db, run.rack_id, current_user, label="Run")

    cached = (
        db.query(Export)
        .filter(
            Export.run_id == run_id, Export.export_type == "patchbook", Export.status == "completed"
        )
        .first()
    )
    if cached:
        return {
            "export_id": cached.id,
            "status": cached.status,
            "artifact_path": (cached.provenance or {}).get("artifact_path"),
            "content_hash": cached.manifest_hash,
            "template_version": PATCHBOOK_TEMPLATE_VERSION,
            "cached": True,
            "deprecated": True,
            "prefer": "POST /api/canon/exports",
        }

    balance = get_credits_balance(db, current_user.id)
    if balance < settings.patchbook_export_cost:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    # Accept either the reloaded Settings flag or the process env used by acceptance.
    # Route modules may hold a pre-reload Settings instance while tests set TEST_MODE later.
    test_mode_enabled = settings.test_mode or os.environ.get("TEST_MODE", "").lower() in {
        "1",
        "true",
        "yes",
    }
    if force_fail and test_mode_enabled:
        raise HTTPException(status_code=500, detail="Forced export failure")

    rack = db.query(Rack).filter(Rack.id == run.rack_id).first()
    if not rack:
        raise HTTPException(status_code=404, detail="Rack not found")

    patches = (
        db.query(Patch)
        .filter(Patch.run_id == run.id)
        .order_by(Patch.id.asc())
        .all()
    )
    if not patches:
        raise HTTPException(status_code=404, detail="No patches available for run")

    payload = PatchBookExportRequest(
        rack_id=rack.id, patch_ids=[patch.id for patch in patches], tier=tier
    )
    try:
        pdf_bytes, content_hash = build_patchbook_pdf_bytes_from_payload(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    export_dir = Path(settings.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    pdf_path = export_dir / f"patchbook_run_{run.id}_{timestamp}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    # Persist before recording the export or spending credits on it.
    try:
        get_file_store().persist(pdf_path)
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=exc.code) from exc
    digest = sha256(pdf_bytes).hexdigest()

    export = Export(
        user_id=current_user.id,
        rack_id=rack.id,
        run_id=run.id,
        export_type="patchbook",
        status="completed",
        credits_spent=settings.patchbook_export_cost,
        manifest_hash=content_hash,
        provenance={
            "artifact_path": str(pdf_path),
            "content_hash": content_hash,
            "template_version": PATCHBOOK_TEMPLATE_VERSION,
            "file_hash": digest,
            "deprecated_path": True,
        },
    )
    db.add(export)
    db.commit()
    db.refresh(export)

    ledger = CreditsLedger(
        user_id=current_user.id,
        change_type="Spend",
        credits_delta=-settings.patchbook_export_cost,
        notes="Patch book export (legacy path)",
        export_id=export.id,
    )
    db.add(ledger)
    db.commit()

    return {
        "export_id": export.id,
        "status": export.status,
        "artifact_path": str(pdf_path),
        "content_hash": content_hash,
        "template_version": PATCHBOOK_TEMPLATE_VERSION,
        "cached": False,
        "deprecated": True,
        "prefer": "POST /api/canon/exports",
    }


@router.post("/patchbook")
def export_patchbook_document(
    payload: PatchBookExportRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Export PatchBook PDF bytes for a rack/patch selection."""
    if not settings.enable_legacy_patchbook_export:
        raise HTTPException(
            status_code=410,
            detail="LEGACY_PATCHBOOK_EXPORT_DISABLED: the Design Engine is the patch book path",
        )
    if not payload.rack_id and not payload.patch_ids:
        raise HTTPException(status_code=400, detail="rack_id or patch_ids required")

    rack = None
    patches_query = db.query(Patch)
    if payload.patch_ids:
        patches_query = patches_query.filter(Patch.id.in_(payload.patch_ids))
        patches = patches_query.all()
        if not patches:
            raise HTTPException(status_code=404, detail="Patches not found")
        rack_id = payload.rack_id or patches[0].rack_id
        rack = db.query(Rack).filter(Rack.id == rack_id).first()
    else:
        rack = db.query(Rack).filter(Rack.id == payload.rack_id).first()
        patches = db.query(Patch).filter(Patch.rack_id == payload.rack_id).all()

    if not rack:
        raise HTTPException(status_code=404, detail="Rack not found")
    readable_rack(db, rack.id, current_user)
    # Readability first: an inaccessible patch stays a 404, never named in a 400.
    for patch in patches:
        readable_patch(db, patch.id, current_user)
    # A book compiles against one rig: a patch from another rig would silently lose the
    # modules that rig lacks (spec 002 FR-013/FR-014).
    foreign = sorted(p.id for p in patches if p.rack_id != rack.id)
    if foreign:
        raise HTTPException(
            status_code=400,
            detail={"code": "PATCH_BOOK_REFERENCE_UNRESOLVED", "patch_ids": foreign},
        )
    if not patches:
        raise HTTPException(status_code=404, detail="No patches available for rack")

    try:
        pdf_bytes, content_hash = build_patchbook_pdf_bytes_from_payload(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "X-PatchBook-Template-Version": PATCHBOOK_TEMPLATE_VERSION,
            "X-PatchBook-Content-Hash": content_hash,
        },
    )
