"""
Pydantic schemas for Rack API.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RackModuleSpec(BaseModel):
    """Specification for placing a module in a rack."""

    module_id: int
    row_index: int = Field(..., ge=0)
    start_hp: int = Field(..., ge=0)


class SuggestedPlacement(BaseModel):
    """Suggested placement for a module instance in a case layout."""

    instance_id: str
    row: int = Field(..., ge=0)
    x_hp: int = Field(..., ge=0)
    width_hp: int = Field(..., ge=0)


class RackModuleResponse(RackModuleSpec):
    """Response schema for a module in a rack."""

    id: int
    module: Optional[dict] = None  # Will contain module details

    class Config:
        from_attributes = True


class RackBase(BaseModel):
    """Base schema for rack data."""

    name: Optional[str] = None
    name_suggested: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    is_public: bool = False


class RackCreate(RackBase):
    """Schema for creating a new rack."""

    case_id: int
    modules: list[RackModuleSpec] = Field(default_factory=list)
    generation_seed: Optional[int] = None


class RackUpdate(BaseModel):
    """Schema for updating a rack."""

    name: Optional[str] = None
    name_suggested: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    is_public: Optional[bool] = None
    modules: Optional[list[RackModuleSpec]] = None


class RackValidationError(BaseModel):
    """Rack validation error / advisory details."""

    field: str
    message: str
    details: Optional[dict] = None


class RackResponse(RackBase):
    """Schema for rack response."""

    id: int
    user_id: int
    case_id: int
    generation_seed: Optional[int]
    created_at: datetime
    updated_at: datetime
    modules: list[RackModuleResponse] = []
    case: Optional[dict] = None  # Will contain case details
    vote_count: int = 0
    # Soft advisories from the last write, plus MODULE_TOMBSTONED on every read
    validation_warnings: list[RackValidationError] = Field(default_factory=list)

    class Config:
        from_attributes = True


class RackListResponse(BaseModel):
    """Schema for paginated rack list."""

    total: int
    racks: list[RackResponse]



