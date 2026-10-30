"""Retention enforcement for image evidence assets."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from canon.models import ImageAssetRecord
from core.storage import StorageError, get_file_store


def expire_image_assets(
    db: Session, *, now: datetime | None = None, dry_run: bool = False
) -> dict[str, int]:
    """Soft-delete assets past retention_expires_at; purge orphan storage files.

    A record is soft-deleted only once its bytes are gone (or still shared by a live
    record). If durable deletion fails, the record keeps ``deleted_at`` unset so the next
    run retries it; access is already refused because its retention has expired.

    With ``dry_run=True`` nothing is deleted or written: the same decisions are made and
    counted (``soft_deleted`` and ``purged_files`` are what a real run would do, assuming
    storage deletes succeed), and ``purge_deferred`` is always 0.

    Only ``image_assets`` rows (mutable) and their storage objects are touched; no
    append-only table is written.

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
    # Sessions here run with autoflush off, so rows retired earlier in this loop are not
    # yet visible to the sibling query; track them so shared bytes are purged exactly once.
    retired_this_run: set[str] = set()
    to_purge: list[tuple[ImageAssetRecord, Path]] = []
    for record in expired:
        live_siblings = (
            db.query(ImageAssetRecord)
            .filter(
                ImageAssetRecord.content_sha256 == record.content_sha256,
                ImageAssetRecord.deleted_at.is_(None),
                ImageAssetRecord.id != record.id,
                ImageAssetRecord.id.notin_(retired_this_run),
            )
            .count()
        )
        retired_this_run.add(str(record.id))
        if live_siblings == 0:
            to_purge.append((record, Path(str(record.storage_path))))
        if not dry_run:
            record.deleted_at = instant

    soft_deleted = len(expired)
    purged_files = 0
    purge_deferred = 0
    if dry_run:
        return {
            "soft_deleted": soft_deleted,
            "purged_files": len(to_purge),
            "purge_deferred": 0,
        }

    # Persist the retirement first: if the flush fails, no stored bytes have been touched.
    if expired:
        db.flush()
    for record, path in to_purge:
        try:
            if get_file_store().delete(path):
                purged_files += 1
        except StorageError:
            # Bytes remain, so un-retire the row; the next run retries it.
            record.deleted_at = None
            purge_deferred += 1
            soft_deleted -= 1
    if purge_deferred:
        db.flush()
    return {
        "soft_deleted": soft_deleted,
        "purged_files": purged_files,
        "purge_deferred": purge_deferred,
    }
