"""
FastAPI routes for admin console operations.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from admin.dependencies import require_admin_mutate, require_admin_read
from admin.models import PendingFunction
from admin.schemas import (
    AdminActionReason,
    AdminAvatarUpdate,
    AdminCacheInvalidate,
    AdminCreditsGrant,
    AdminExportResponse,
    AdminFunctionApprove,
    AdminGalleryRevision,
    AdminGalleryRevisionList,
    AdminLeaderboardEntry,
    AdminModuleCreate,
    AdminModuleImport,
    AdminModuleMerge,
    AdminModuleStatusUpdate,
    AdminPendingFunctionList,
    AdminRoleUpdate,
    AdminRunList,
    AdminRunResponse,
    AdminUserList,
    AdminUserResponse,
)
from admin.utils import log_admin_action
from canon.models import CanonicalCreditLedgerEntryRecord
from community.models import User
from core import get_db
from gallery.models import GalleryRevision
from modules.models import Module
from monetization.models import CreditsLedger, Export
from runs.models import Run

router = APIRouter()

KNOWN_PORT_TYPES = {
    "audio_in",
    "audio_out",
    "cv_in",
    "cv_out",
    "gate_in",
    "gate_out",
    "clock_in",
    "clock_out",
}


def _canonical_revision_id(payload: dict) -> str:
    payload_text = str(sorted(payload.items()))
    return f"rev.{abs(hash(payload_text)) % 10**12}"


def _record_pending_functions(db: Session, module: Module) -> int:
    created = 0
    for port in module.io_ports:
        port_type = port.get("type") if isinstance(port, dict) else None
        if not port_type or port_type in KNOWN_PORT_TYPES:
            continue
        pending = PendingFunction(
            module_id=module.id,
            function_name=port_type,
            status="pending",
        )
        db.add(pending)
        created += 1
    return created


@router.get("/ops/runtime-flags")
def runtime_flags(current_user: User = Depends(require_admin_read)) -> dict:
    """Effective Design Engine and payment flags of THIS server (read-only).

    Spec 008 review: the staging walkthrough must verify the target server's
    effective configuration, not a local overlay file, before it runs or seals a
    receipt. Returns booleans plus the environment name only; no secrets, keys,
    or URLs, and it changes nothing.
    """
    from core.config import settings
    from core.ops.f5_cutover import runtime_flags_payload

    _ = current_user
    return runtime_flags_payload(settings)


@router.get("/users", response_model=AdminUserList)
def list_users(
    query: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_read),
):
    q = db.query(User)
    if query:
        like = f"%{query}%"
        q = q.filter(
            func.lower(User.username).like(like.lower())
            | func.lower(User.email).like(like.lower())
            | func.lower(User.display_name).like(like.lower())
        )
    users = q.order_by(User.created_at.desc()).all()
    return AdminUserList(total=len(users), users=users)


@router.patch("/users/{user_id}/role", response_model=AdminUserResponse)
def update_user_role(
    user_id: int,
    payload: AdminRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    previous = user.role
    # Ops may manage roles, but only an Admin may grant Admin or take it away.
    if "Admin" in (previous, payload.role) and current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Only an Admin can grant or remove Admin")
    user.role = payload.role
    if previous != payload.role:
        # A role change takes effect at once: the user's existing tokens stop working.
        from community.sessions import revoke_user

        revoke_user(db, user)
    log_admin_action(
        db,
        actor=current_user,
        action_type="user.role.update",
        target_type="user",
        target_id=str(user_id),
        delta_json={"from": previous, "to": payload.role},
        reason=payload.reason,
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/avatar", response_model=AdminUserResponse)
def update_user_avatar(
    user_id: int,
    payload: AdminAvatarUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    previous = user.avatar_url
    user.avatar_url = payload.avatar_url
    log_admin_action(
        db,
        actor=current_user,
        action_type="user.avatar.update",
        target_type="user",
        target_id=str(user_id),
        delta_json={"from": previous, "to": payload.avatar_url},
        reason=payload.reason,
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/credits/grant", status_code=201)
def grant_user_credits(
    user_id: int,
    payload: AdminCreditsGrant,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    """Grant credits to both the legacy and canonical ledgers.

    Dual-write keeps historical admin/referral paths working while MVP
    debit/balance surfaces read the canonical ledger only.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    entry = CreditsLedger(
        user_id=user.id,
        change_type="Grant",
        credits_delta=payload.credits,
        notes=payload.reason,
    )
    db.add(entry)

    # Stable, unique canonical grant id (append-only; retries must use a new reason/amount pair).
    grant_key = f"admin-grant:{user.id}:{payload.credits}:{payload.reason}:{current_user.id}"
    grant_id = f"grant-{sha256(grant_key.encode('utf-8')).hexdigest()[:24]}"
    idempotency_key = f"admin-grant:{grant_id}"
    existing_canon = db.get(CanonicalCreditLedgerEntryRecord, grant_id)
    if existing_canon is None:
        db.add(
            CanonicalCreditLedgerEntryRecord(
                id=grant_id,
                user_id=user.id,
                delta=int(payload.credits),
                entry_type="grant",
                idempotency_key=idempotency_key,
                export_id=None,
                created_at=datetime.now(timezone.utc),
            )
        )

    log_admin_action(
        db,
        actor=current_user,
        action_type="credits.grant",
        target_type="user",
        target_id=str(user_id),
        delta_json={
            "credits_delta": payload.credits,
            "canonical_ledger_entry_id": grant_id,
        },
        reason=payload.reason,
    )
    db.commit()
    return {"status": "granted", "canonical_ledger_entry_id": grant_id}


@router.post("/modules", status_code=201)
def create_module(
    payload: AdminModuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    module = Module(
        brand=payload.brand,
        name=payload.name,
        hp=payload.hp,
        module_type=payload.module_type,
        power_12v_ma=payload.power_12v_ma,
        power_neg12v_ma=payload.power_neg12v_ma,
        power_5v_ma=payload.power_5v_ma,
        io_ports=[port.model_dump() for port in payload.io_ports],
        tags=payload.tags,
        description=payload.description,
        manufacturer_url=payload.manufacturer_url,
        source=payload.source,
        source_reference=payload.source_reference,
        status="active",
    )
    db.add(module)
    db.flush()
    pending_count = _record_pending_functions(db, module)
    log_admin_action(
        db,
        actor=current_user,
        action_type="module.create",
        target_type="module",
        target_id=None,
        delta_json={"brand": payload.brand, "name": payload.name},
        reason="manual_add",
    )
    db.commit()
    db.refresh(module)
    return module


@router.post("/modules/import", status_code=201)
def import_modules(
    payload: AdminModuleImport,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    created = 0
    pending_created = 0
    for module_payload in payload.modules:
        module = Module(
            brand=module_payload.brand,
            name=module_payload.name,
            hp=module_payload.hp,
            module_type=module_payload.module_type,
            power_12v_ma=module_payload.power_12v_ma,
            power_neg12v_ma=module_payload.power_neg12v_ma,
            power_5v_ma=module_payload.power_5v_ma,
            io_ports=[port.model_dump() for port in module_payload.io_ports],
            tags=module_payload.tags,
            description=module_payload.description,
            manufacturer_url=module_payload.manufacturer_url,
            source=module_payload.source,
            source_reference=module_payload.source_reference,
            status="active",
        )
        db.add(module)
        db.flush()
        created += 1
        pending_created += _record_pending_functions(db, module)
    log_admin_action(
        db,
        actor=current_user,
        action_type="module.import",
        target_type="module",
        target_id=None,
        delta_json={"count": created, "pending_functions": pending_created},
        reason=payload.reason,
    )
    db.commit()
    return {"created": created}


@router.patch("/modules/{module_id}/status")
def update_module_status(
    module_id: int,
    payload: AdminModuleStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    previous = module.status
    module.status = payload.status
    if payload.status == "deprecated":
        module.deprecated_at = datetime.utcnow()
    if payload.status == "tombstoned":
        module.tombstoned_at = datetime.utcnow()
    log_admin_action(
        db,
        actor=current_user,
        action_type="module.status.update",
        target_type="module",
        target_id=str(module_id),
        delta_json={"from": previous, "to": payload.status},
        reason=payload.reason,
    )
    db.commit()
    return {"status": "updated"}


@router.patch("/modules/{module_id}/merge")
def merge_module(
    module_id: int,
    payload: AdminModuleMerge,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    module = db.query(Module).filter(Module.id == module_id).first()
    replacement = db.query(Module).filter(Module.id == payload.replacement_module_id).first()
    if not module or not replacement:
        raise HTTPException(status_code=404, detail="Module not found")
    module.replacement_module_id = payload.replacement_module_id
    module.status = "deprecated"
    module.deprecated_at = datetime.utcnow()
    log_admin_action(
        db,
        actor=current_user,
        action_type="module.merge",
        target_type="module",
        target_id=str(module_id),
        delta_json={"replacement_module_id": payload.replacement_module_id},
        reason=payload.reason,
    )
    db.commit()
    return {"status": "merged"}


@router.get("/gallery/revisions", response_model=AdminGalleryRevisionList)
def list_gallery_revisions(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_read),
):
    q = db.query(GalleryRevision)
    if status:
        q = q.filter(GalleryRevision.status == status)
    revisions = q.order_by(GalleryRevision.created_at.desc()).all()
    return AdminGalleryRevisionList(total=len(revisions), revisions=revisions)


def _append_gallery_revision(
    db: Session,
    *,
    revision: GalleryRevision,
    new_status: str,
) -> GalleryRevision:
    new_revision = GalleryRevision(
        module_key=revision.module_key,
        revision_id=_canonical_revision_id(revision.payload),
        status=new_status,
        payload=revision.payload,
    )
    db.add(new_revision)
    return new_revision


@router.post("/gallery/revisions/{revision_id}/approve", status_code=201)
def approve_revision(
    revision_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    revision = db.query(GalleryRevision).filter(GalleryRevision.id == revision_id).first()
    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")
    new_revision = _append_gallery_revision(db, revision=revision, new_status="Approved")
    log_admin_action(
        db,
        actor=current_user,
        action_type="gallery.revision.approve",
        target_type="gallery_revision",
        target_id=str(revision_id),
        delta_json={"new_revision_id": new_revision.id},
        reason="approve",
    )
    db.commit()
    return {"status": "approved"}


@router.post("/gallery/revisions/{revision_id}/confirm", status_code=201)
def confirm_revision(
    revision_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    revision = db.query(GalleryRevision).filter(GalleryRevision.id == revision_id).first()
    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")
    new_revision = _append_gallery_revision(db, revision=revision, new_status="Confirmed")
    log_admin_action(
        db,
        actor=current_user,
        action_type="gallery.revision.confirm",
        target_type="gallery_revision",
        target_id=str(revision_id),
        delta_json={"new_revision_id": new_revision.id},
        reason="confirm",
    )
    db.commit()
    return {"status": "confirmed"}


@router.get("/runs", response_model=AdminRunList)
def list_runs(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_read),
):
    q = db.query(Run)
    if status:
        q = q.filter(Run.status == status)
    runs = q.order_by(Run.created_at.desc()).all()
    return AdminRunList(total=len(runs), runs=runs)


@router.post("/runs/{rig_id}/rerun", response_model=AdminRunResponse, status_code=201)
def rerun_rig(
    rig_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    """Re-run generation for a rig through the normal path: readiness gate first, and a
    run that ends terminal (spec 001 FR-018/FR-022). Nothing is left queued."""
    from patches.routes import run_generation
    from patches.schemas import GeneratePatchesRequest
    from racks.models import Rack

    rack = db.query(Rack).filter(Rack.id == rig_id, Rack.deleted_at.is_(None)).first()
    if rack is None:
        raise HTTPException(status_code=404, detail="Rig not found")
    result = run_generation(db, rack, GeneratePatchesRequest())
    if result.run_id is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "RIG_NOT_COMPUTABLE", "inventory_gate_code": result.inventory_gate_code},
        )
    run = db.get(Run, result.run_id)
    log_admin_action(
        db,
        actor=current_user,
        action_type="run.rerun",
        target_type="run",
        target_id=str(run.id),
        delta_json={"rack_id": rig_id, "status": run.status},
        reason="rerun",
    )
    db.commit()
    db.refresh(run)
    return run


@router.post("/exports/{export_id}/unlock", status_code=201)
def unlock_export(
    export_id: int,
    payload: AdminActionReason,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    export = db.query(Export).filter(Export.id == export_id).first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    export.status = "unlocked"
    log_admin_action(
        db,
        actor=current_user,
        action_type="export.unlock",
        target_type="export",
        target_id=str(export_id),
        delta_json={"status": "unlocked"},
        reason=payload.reason,
    )
    db.commit()
    return {"status": "unlocked"}


@router.post("/exports/{export_id}/revoke", status_code=201)
def revoke_export(
    export_id: int,
    payload: AdminActionReason,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    export = db.query(Export).filter(Export.id == export_id).first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    export.status = "revoked"
    log_admin_action(
        db,
        actor=current_user,
        action_type="export.revoke",
        target_type="export",
        target_id=str(export_id),
        delta_json={"status": "revoked"},
        reason=payload.reason,
    )
    db.commit()
    return {"status": "revoked"}


@router.post("/cache/invalidate", status_code=201)
def invalidate_cache(
    payload: AdminCacheInvalidate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    log_admin_action(
        db,
        actor=current_user,
        action_type="cache.invalidate",
        target_type="cache",
        target_id=str(payload.run_id) if payload.run_id else None,
        delta_json={"export_type": payload.export_type},
        reason=payload.reason,
    )
    db.commit()
    return {"status": "invalidated"}


@router.get("/leaderboards/modules/popular", response_model=list[AdminLeaderboardEntry])
def popular_modules(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_read),
):
    from racks.models import RackModule

    rows = (
        db.query(Module.name, func.count(RackModule.id))
        .join(RackModule, RackModule.module_id == Module.id)
        .group_by(Module.name)
        .order_by(func.count(RackModule.id).desc())
        .limit(20)
        .all()
    )
    return [AdminLeaderboardEntry(label=row[0], count=row[1]) for row in rows]


@router.get("/leaderboards/modules/trending", response_model=list[AdminLeaderboardEntry])
def trending_modules(
    window_days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_read),
):
    from racks.models import Rack, RackModule

    since = datetime.utcnow() - timedelta(days=window_days)
    rows = (
        db.query(Module.name, func.count(RackModule.id))
        .join(RackModule, RackModule.module_id == Module.id)
        .join(Rack, Rack.id == RackModule.rack_id)
        .filter(Rack.created_at >= since)
        .group_by(Module.name)
        .order_by(func.count(RackModule.id).desc())
        .limit(20)
        .all()
    )
    return [AdminLeaderboardEntry(label=row[0], count=row[1]) for row in rows]


@router.get("/leaderboards/categories/exported", response_model=list[AdminLeaderboardEntry])
def exported_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_read),
):
    from patches.models import Patch

    rows = (
        db.query(Patch.category, func.count(Export.id))
        .join(Export, Export.patch_id == Patch.id)
        .group_by(Patch.category)
        .order_by(func.count(Export.id).desc())
        .limit(20)
        .all()
    )
    return [AdminLeaderboardEntry(label=row[0], count=row[1]) for row in rows]


@router.get("/functions/pending", response_model=AdminPendingFunctionList)
def list_pending_functions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_read),
):
    pending = db.query(PendingFunction).filter(PendingFunction.status == "pending").all()
    return AdminPendingFunctionList(total=len(pending), items=pending)


@router.post("/functions/{pending_id}/approve", status_code=201)
def approve_pending_function(
    pending_id: int,
    payload: AdminFunctionApprove,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
):
    pending = db.query(PendingFunction).filter(PendingFunction.id == pending_id).first()
    if not pending:
        raise HTTPException(status_code=404, detail="Pending function not found")
    pending.status = "approved"
    pending.canonical_function = payload.canonical_function
    pending.resolved_at = datetime.utcnow()
    log_admin_action(
        db,
        actor=current_user,
        action_type="function.approve",
        target_type="pending_function",
        target_id=str(pending_id),
        delta_json={
            "function_name": pending.function_name,
            "canonical_function": payload.canonical_function,
        },
        reason=payload.reason,
    )
    db.commit()
    return {"status": "approved"}
