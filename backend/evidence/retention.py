"""Retention enforcement for image evidence assets."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from canon.models import ImageAssetRecord
from core.storage import StorageError, get_file_store


def expire_image_assets(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    """Soft-delete assets past retention_expires_at; purge orphan storage files.

    A record is soft-deleted only once its bytes are gone (or still shared by a live
    record). If durable deletion fails, the record keeps ``deleted_at`` unset so the next
    run retries it; access is already refused because its retention has expired.

    Returns counts for observability receipts.
    """
    instant = now or datetime.now(timezone.utc)
    expired = (
        db.query(ImageAssetRecord)
        .filter(
            ImageAssetRecord.deleted_at.is_(None),
            ImageAssetRecord.retention_expires_at <= instant,
        )
        .all()
    )
    soft_deleted = 0
    purged_files = 0
    purge_deferred = 0
    for record in expired:
        path = Path(str(record.storage_path))
        live_siblings = (
            db.query(ImageAssetRecord)
            .filter(
                ImageAssetRecord.content_sha256 == record.content_sha256,
                ImageAssetRecord.deleted_at.is_(None),
                ImageAssetRecord.id != record.id,
            )
            .count()
        )
        if live_siblings == 0:
            try:
                if get_file_store().delete(path):
                    purged_files += 1
            except StorageError:
                purge_deferred += 1
                continue
        record.deleted_at = instant
        soft_deleted += 1
    if soft_deleted:
        db.flush()
    return {
        "soft_deleted": soft_deleted,
        "purged_files": purged_files,
        "purge_deferred": purge_deferred,
    }
