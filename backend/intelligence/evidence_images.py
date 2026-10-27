"""Provider-neutral, lazy loader for image evidence bound to a classification record.

This module is the single sanctioned bridge between stored image assets and decision
providers (for example vision-ranking adapters). It is deliberately narrow:

* Provider-neutral: it returns raw bytes plus a content type and makes no claim about
  detections, quality scores, or model behavior.
* Lazy: constructing ``BoundEvidenceImageLoader`` touches neither the database nor the
  filesystem, so a disabled provider that never invokes the loader performs no I/O.
* Consent-aware: it reuses the existing consent gate exactly as
  ``evidence/cloud_provider.py`` does. Provider processing requires
  ``ImageAssetRecord.consent_provider_processing`` to be True. No second consent model
  is introduced here.
* Retention-aware: it reuses the existing retention predicate from
  ``evidence/retention.py``. An asset is unavailable when ``deleted_at`` is set or when
  ``retention_expires_at <= now``. Naive datetimes read back from SQLite are treated as
  UTC when compared.
* Fail-closed: every rejection raises ``ImageLoadError`` carrying only a stable code
  string. Paths, ids, OS error text, and bytes never appear in the message or in any
  exception chain.

Never-raw-bytes-in-packets is the caller's responsibility: a provider must hash or
summarize the bytes it consumes and must not persist them into decision packets.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from canon.models import ClassificationEvidenceRecord, ImageAssetRecord
from intelligence.contracts import DecisionRequest

__all__ = [
    "ALLOWED_MEDIA_TYPES",
    "BoundEvidenceImageLoader",
    "EvidenceImage",
    "ImageAccessDecision",
    "ImageLoadError",
    "image_access_decision",
]

ALLOWED_MEDIA_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})

DEFAULT_MAX_BYTES = 4 * 1024 * 1024

_MODULE_IDENTITY_PREFIX = "module-identity:"


class ImageLoadError(RuntimeError):
    """Stable, path-free, byte-free image loading failure.

    The exception message is exactly the stable code string, so callers may branch on
    ``str(exc)`` without ever exposing storage paths, asset ids, or OS error text.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ImageAccessDecision(str, Enum):
    """Outcome of evaluating consent and retention for one bound image asset."""

    CLEARED = "CLEARED"
    ASSET_MISSING = "ASSET_MISSING"
    ASSET_DELETED = "ASSET_DELETED"
    RETENTION_EXPIRED = "RETENTION_EXPIRED"
    CONSENT_NOT_GRANTED = "CONSENT_NOT_GRANTED"


@dataclass(frozen=True)
class EvidenceImage:
    """One loadable image payload for a decision provider."""

    content_type: str
    data: bytes = field(repr=False)


def _as_utc(instant: datetime) -> datetime:
    """Normalize a datetime to aware UTC, treating naive values as UTC."""
    if instant.tzinfo is None:
        return instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc)


def image_access_decision(
    asset: ImageAssetRecord | None,
    *,
    now: datetime,
) -> ImageAccessDecision:
    """Pure consent/retention evaluation, mirroring existing evidence semantics.

    Ordering is fixed: missing, then deleted, then expired, then consent, then cleared.
    """
    if asset is None:
        return ImageAccessDecision.ASSET_MISSING
    if asset.deleted_at is not None:
        return ImageAccessDecision.ASSET_DELETED
    if _as_utc(asset.retention_expires_at) <= _as_utc(now):
        return ImageAccessDecision.RETENTION_EXPIRED
    if not asset.consent_provider_processing:
        return ImageAccessDecision.CONSENT_NOT_GRANTED
    return ImageAccessDecision.CLEARED


class BoundEvidenceImageLoader:
    """Callable that loads the image asset bound to one classification record.

    Construction is side-effect free. The database session and filesystem are touched
    only inside ``__call__``, and only after the request binding and access decision
    have been validated.
    """

    def __init__(
        self,
        db: Session,
        *,
        evidence_id: str,
        storage_root: Path,
        clock: Callable[[], datetime] | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self._db = db
        self._evidence_id = evidence_id
        self._storage_root = Path(storage_root)
        self._clock = clock if clock is not None else _default_clock
        self._max_bytes = max_bytes
        self._last_decision: ImageAccessDecision | None = None
        self._load_count = 0
        self._calls = 0

    @property
    def last_decision(self) -> ImageAccessDecision | None:
        """Most recent access decision, or None when the loader was never called."""
        return self._last_decision

    @property
    def load_count(self) -> int:
        """Number of successful file reads performed by this loader."""
        return self._load_count

    @property
    def calls(self) -> int:
        """Number of invocations of this loader, including rejected ones."""
        return self._calls

    def __call__(self, request: DecisionRequest) -> tuple[EvidenceImage, ...]:
        """Return at most one image, or an empty tuple for a graceful text-only degrade."""
        self._calls += 1
        expected_request_id = f"{_MODULE_IDENTITY_PREFIX}{self._evidence_id}"
        if request.request_id != expected_request_id:
            raise ImageLoadError("IMAGE_REQUEST_MISMATCH")

        evidence = self._db.get(ClassificationEvidenceRecord, self._evidence_id)
        if evidence is None:
            raise ImageLoadError("IMAGE_EVIDENCE_MISSING")

        asset = self._db.get(ImageAssetRecord, evidence.image_asset_id)
        decision = image_access_decision(asset, now=self._clock())
        self._last_decision = decision
        if decision is not ImageAccessDecision.CLEARED:
            return ()
        if asset is None:
            return ()

        media_type = str(asset.media_type)
        if media_type not in ALLOWED_MEDIA_TYPES:
            raise ImageLoadError("IMAGE_MEDIA_TYPE_UNSUPPORTED")

        root = self._storage_root.resolve()
        try:
            resolved = Path(str(asset.storage_path)).resolve()
        except OSError:
            raise ImageLoadError("IMAGE_OUTSIDE_STORAGE_ROOT") from None
        if not resolved.is_relative_to(root):
            raise ImageLoadError("IMAGE_OUTSIDE_STORAGE_ROOT")

        try:
            size = resolved.stat().st_size
        except FileNotFoundError:
            raise ImageLoadError("IMAGE_FILE_MISSING") from None
        except OSError:
            raise ImageLoadError("IMAGE_READ_FAILED") from None
        if size > self._max_bytes:
            raise ImageLoadError("IMAGE_TOO_LARGE")

        try:
            data = resolved.read_bytes()
        except FileNotFoundError:
            raise ImageLoadError("IMAGE_FILE_MISSING") from None
        except OSError:
            raise ImageLoadError("IMAGE_READ_FAILED") from None

        if hashlib.sha256(data).hexdigest() != str(asset.content_sha256):
            raise ImageLoadError("IMAGE_INTEGRITY_MISMATCH")

        self._load_count += 1
        return (EvidenceImage(content_type=media_type, data=data),)


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)
