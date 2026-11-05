"""Secure image validation and normalization before provider detection."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import Protocol

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_DIMENSION = 10_000
MAX_PIXELS = 40_000_000
NORMALIZED_MAX_DIMENSION = 4096
ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class UnsafeImageError(ValueError):
    """Stable, user-safe evidence rejection."""


class ImageScanner(Protocol):
    def scan(self, content: bytes) -> None:
        """Raise UnsafeImageError when content is unsafe."""


class SignatureImageScanner:
    """Local scanner adapter; production can replace it with an AV service."""

    def scan(self, content: bytes) -> None:
        prefix = content[:1024].lstrip().lower()
        if prefix.startswith((b"<svg", b"<?xml", b"<html", b"<!doctype")):
            raise UnsafeImageError("IMAGE_SCAN_REJECTED")


@dataclass(frozen=True)
class PreparedImageEvidence:
    content: bytes
    media_type: str
    width: int
    height: int
    sha256: str


@dataclass(frozen=True)
class LocalImageQualityAssessment:
    """Local, non-provider quality gates for secure intake.

    This does not claim ML blur/glare scores. Those remain provider-side and
    optional. Local gates fail closed on structural problems only.
    """

    accepted: bool
    reasons: tuple[str, ...]
    width: int
    height: int
    content_sha256: str


def prepare_image_evidence(
    content: bytes,
    *,
    declared_media_type: str | None,
    scanner: ImageScanner,
) -> PreparedImageEvidence:
    """Validate signature/dimensions, orient, re-encode, and strip metadata."""

    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise UnsafeImageError("IMAGE_SIZE_INVALID")
    scanner.scan(content)
    try:
        with Image.open(io.BytesIO(content)) as probe:
            image_format = probe.format
            width, height = probe.size
            if image_format not in ALLOWED_FORMATS:
                raise UnsafeImageError("IMAGE_FORMAT_UNSUPPORTED")
            actual_media_type = ALLOWED_FORMATS[image_format]
            if declared_media_type and declared_media_type.casefold() != actual_media_type:
                raise UnsafeImageError("IMAGE_MIME_MISMATCH")
            if width < 1 or height < 1 or width > MAX_DIMENSION or height > MAX_DIMENSION:
                raise UnsafeImageError("IMAGE_DIMENSIONS_INVALID")
            if width * height > MAX_PIXELS:
                raise UnsafeImageError("IMAGE_PIXEL_LIMIT_EXCEEDED")
            probe.verify()

        with Image.open(io.BytesIO(content)) as source:
            normalized = ImageOps.exif_transpose(source)
            normalized.thumbnail((NORMALIZED_MAX_DIMENSION, NORMALIZED_MAX_DIMENSION))
            normalized = normalized.convert("RGB")
            # A JPEG comment would otherwise be written back out.
            normalized.info.clear()
            output = io.BytesIO()
            normalized.save(output, format="JPEG", quality=90, optimize=True, progressive=False)
            cleaned = output.getvalue()
            normalized_width, normalized_height = normalized.size
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise UnsafeImageError("IMAGE_DECODE_FAILED") from exc

    scanner.scan(cleaned)
    return PreparedImageEvidence(
        content=cleaned,
        media_type="image/jpeg",
        width=normalized_width,
        height=normalized_height,
        sha256=hashlib.sha256(cleaned).hexdigest(),
    )


def assess_local_image_quality(
    prepared: PreparedImageEvidence,
    *,
    min_dimension: int = 64,
    min_bytes: int = 128,
) -> LocalImageQualityAssessment:
    """Structural quality check after re-encoding.

    Provider-side blur/glare/occlusion scores remain separate evidence fields.
    """

    reasons: list[str] = []
    if prepared.width < min_dimension or prepared.height < min_dimension:
        reasons.append("IMAGE_DIMENSIONS_TOO_SMALL")
    if len(prepared.content) < min_bytes:
        reasons.append("IMAGE_BYTES_TOO_SMALL")
    return LocalImageQualityAssessment(
        accepted=not reasons,
        reasons=tuple(reasons),
        width=prepared.width,
        height=prepared.height,
        content_sha256=prepared.sha256,
    )
