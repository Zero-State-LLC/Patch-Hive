"""
Pydantic schemas for publishing endpoints.
"""

from datetime import datetime
from typing import Literal, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from core.config import settings


def _cover_url(value: Optional[str]) -> Optional[str]:
    """An https image on an allowed host, or nothing (spec 002 T041). Anything else could be a
    tracking pixel, a downgrade to http, or a script URL in a careless client."""
    if value is None or not value.strip():
        return None
    parts = urlsplit(value.strip())
    host = (parts.hostname or "").lower()
    allowed = any(host == h or host.endswith(f".{h}") for h in settings.publication_cover_hosts)
    if parts.scheme != "https" or not allowed or parts.username or parts.password:
        raise ValueError("cover_image_url must be an https address on an allowed host")
    return value.strip()


class ExportCreate(BaseModel):
    """Create an export from a patch or rack."""

    source_type: Literal["patch", "rack"]
    source_id: int


class ExportResponse(BaseModel):
    """Export response schema."""

    id: int
    export_type: str
    license: str
    run_id: str
    generated_at: datetime
    patch_count: Optional[int]
    manifest_hash: str
    artifact_urls: dict

    class Config:
        from_attributes = True


class PublicationCreate(BaseModel):
    """Create publication request."""

    export_id: int
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    visibility: Literal["unlisted", "public"] = "unlisted"
    allow_download: bool
    allow_remix: bool
    cover_image_url: Optional[str] = None

    @field_validator("cover_image_url")
    @classmethod
    def _check_cover(cls, value: Optional[str]) -> Optional[str]:
        return _cover_url(value)


class PublicationUpdate(BaseModel):
    """Update publication request."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    visibility: Optional[Literal["unlisted", "public"]] = None
    allow_download: Optional[bool] = None
    allow_remix: Optional[bool] = None
    cover_image_url: Optional[str] = None

    @field_validator("cover_image_url")
    @classmethod
    def _check_cover(cls, value: Optional[str]) -> Optional[str]:
        return _cover_url(value)
    status: Optional[Literal["published", "hidden"]] = None


class PublicationOwnerResponse(BaseModel):
    """Publication response for owners."""

    id: int
    export_id: int
    slug: str
    visibility: str
    status: str
    allow_download: bool
    allow_remix: bool
    title: str
    description: Optional[str]
    cover_image_url: Optional[str]
    published_at: Optional[datetime]
    updated_at: datetime

    class Config:
        from_attributes = True


class PublicationListResponse(BaseModel):
    """List response for owner's publications."""

    publications: list[PublicationOwnerResponse]


class PublicationPublicResponse(BaseModel):
    """Public publication response."""

    title: str
    description: Optional[str]
    cover_image_url: Optional[str]
    export_type: str
    license: str
    provenance: dict
    publisher_display: str
    avatar_url: Optional[str]
    allow_download: bool
    download_urls: Optional[dict]


class PublicationCard(BaseModel):
    """Gallery card schema."""

    slug: str
    title: str
    description: Optional[str]
    cover_image_url: Optional[str]
    export_type: str
    published_at: Optional[datetime]


class GalleryResponse(BaseModel):
    """Gallery response schema."""

    publications: list[PublicationCard]
    next_cursor: Optional[str]


class ReportCreate(BaseModel):
    """Create report request."""

    reason: str = Field(..., min_length=3, max_length=200)
    details: Optional[str] = Field(default=None, max_length=2000)


class AdminModerationRequest(BaseModel):
    """Admin moderation request."""

    reason: str = Field(..., min_length=3, max_length=500)
