"""Account deletion by anonymization (spec 004 OQ-12, EC-8; decided ``A_anonymize_keep``).

The ``users`` row is kept and stripped of personal data, because the append-only
canonical ledger, canonical exports and generation runs reference it with
``ON DELETE RESTRICT`` and referral rows are append-only too. Nothing financial is
updated or deleted. In one transaction (the caller commits):

- every session and access token of the user is revoked;
- personal content is removed where nothing append-only depends on it: comments,
  votes, patch overlays and annotations, and style recipes are deleted; racks are
  soft-deleted (their runs and canonical history are append-only) with their free
  text cleared; publications are set ``removed`` with their text cleared; the user is
  detached from publication reports they filed;
- evidence images are expired now, so ``expire_image_assets`` purges their bytes;
- the user's personal fields are replaced (email, username, display name, avatar,
  bio, password hash, referral code) and ``deleted_at`` is set;
- one ``admin_audit_log`` row records the deletion with counts only, no personal data.

Retention periods for what is kept are for a lawyer to confirm.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy import inspect, update
from sqlalchemy.orm import Session

from admin.models import AdminAuditLog
from canon.models import (
    CanonicalExportRecord,
    ImageAssetRecord,
    PatchUserOverlayRecord,
    UserPatchAnnotationRecord,
    UserStyleRecipeRecord,
)
from community import sessions
from community.models import Comment, User, Vote
from evidence.retention import expire_image_assets
from publishing.models import Publication, PublicationReport
from racks.models import Rack

logger = logging.getLogger(__name__)

# A value no password hash scheme parses, so no password ever verifies against it.
UNUSABLE_PASSWORD_HASH = "!account-deleted"
DELETED_RACK_NAME = "Deleted rack"
REMOVED_PUBLICATION_TITLE = "Removed"
AUDIT_ACTION = "account_deleted"


def anonymize_user(db: Session, user: User, *, now: datetime | None = None) -> dict[str, int]:
    """Anonymize ``user`` and remove their personal content. Returns per-table counts.

    Flushes but does not commit; the caller commits once so it all lands together.
    """
    instant = now or datetime.now(timezone.utc)
    naive = instant.replace(tzinfo=None)
    user_id = user.id
    counts: dict[str, int] = {}

    sessions.revoke_user(db, user)

    counts["comments_deleted"] = (
        db.query(Comment).filter(Comment.user_id == user_id).delete(synchronize_session=False)
    )
    counts["votes_deleted"] = (
        db.query(Vote).filter(Vote.user_id == user_id).delete(synchronize_session=False)
    )
    counts["patch_overlays_deleted"] = (
        db.query(PatchUserOverlayRecord)
        .filter(PatchUserOverlayRecord.user_id == user_id)
        .delete(synchronize_session=False)
    )
    counts["patch_annotations_deleted"] = (
        db.query(UserPatchAnnotationRecord)
        .filter(UserPatchAnnotationRecord.user_id == user_id)
        .delete(synchronize_session=False)
    )
    # The export keeps its sealed recipe snapshot; only the pointer to the library row
    # goes, as the foreign key's ON DELETE SET NULL would do.
    recipe_ids = [
        row.id
        for row in db.query(UserStyleRecipeRecord.id).filter(
            UserStyleRecipeRecord.user_id == user_id
        )
    ]
    if recipe_ids:
        db.execute(
            update(CanonicalExportRecord)
            .where(CanonicalExportRecord.style_recipe_id.in_(recipe_ids))
            .values(style_recipe_id=None)
        )
    counts["style_recipes_deleted"] = (
        db.query(UserStyleRecipeRecord)
        .filter(UserStyleRecipeRecord.user_id == user_id)
        .delete(synchronize_session=False)
    )

    racks = db.query(Rack).filter(Rack.user_id == user_id).all()
    for rack in racks:
        if rack.deleted_at is None:
            rack.deleted_at = naive
        rack.name = DELETED_RACK_NAME
        rack.description = None
        rack.tags = []
        rack.is_public = False
    counts["racks_soft_deleted"] = len(racks)

    counts["images_expired"] = (
        db.query(ImageAssetRecord)
        .filter(ImageAssetRecord.user_id == user_id, ImageAssetRecord.deleted_at.is_(None))
        .update(
            {ImageAssetRecord.retention_expires_at: instant}, synchronize_session=False
        )
    )

    # Legacy publishing has no Alembic migration, so migrated databases lack its tables.
    publications = []
    counts["reports_detached"] = 0
    if inspect(db.connection()).has_table(Publication.__tablename__):
        publications = (
            db.query(Publication).filter(Publication.publisher_user_id == user_id).all()
        )
        counts["reports_detached"] = (
            db.query(PublicationReport)
            .filter(PublicationReport.reporter_user_id == user_id)
            .update({PublicationReport.reporter_user_id: None}, synchronize_session=False)
        )
    for publication in publications:
        publication.status = "removed"
        publication.removed_reason = "ACCOUNT_DELETED"
        publication.title = REMOVED_PUBLICATION_TITLE
        publication.description = None
        publication.cover_image_url = None
        publication.allow_download = False
    counts["publications_removed"] = len(publications)

    token = secrets.token_hex(12)
    user.username = f"deleted-{token}"
    user.email = f"deleted-{token}@deleted.invalid"
    user.password_hash = UNUSABLE_PASSWORD_HASH
    user.display_name = None
    user.avatar_url = None
    user.allow_public_avatar = False
    user.bio = None
    user.referral_code = secrets.token_hex(16)
    user.role = "User"
    user.failed_login_count = 0
    user.locked_until = None
    user.deleted_at = naive

    db.add(
        AdminAuditLog(
            actor_user_id=user_id,
            actor_role="User",
            action_type=AUDIT_ACTION,
            target_type="user",
            target_id=str(user_id),
            delta_json=counts,
            reason="user_request",
            created_at=naive,
        )
    )
    db.flush()
    return counts


def purge_user_images(
    db: Session, user_id: int, *, now: datetime | None = None
) -> dict[str, int] | None:
    """Purge the stored bytes of the user's expired images after the deletion commits.

    Storage is not transactional, so this runs after the anonymization commit. A failed
    purge leaves the asset expired but not soft-deleted; ``python -m evidence.expire
    --apply`` retries it. Returns the expiry counts, or None when the run failed.
    """
    try:
        counts = expire_image_assets(db, now=now, user_id=user_id)
        db.commit()
        return counts
    except Exception:
        db.rollback()
        logger.exception("account deletion: image purge deferred")
        return None
