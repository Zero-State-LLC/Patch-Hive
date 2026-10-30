"""
Pydantic schemas for Module API.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class IOPort(BaseModel):
    """I/O port specification."""

    name: str
    type: str  # "audio_in", "audio_out", "cv_in", "cv_out", "gate_in", "gate_out", "clock_in", "clock_out"


class ModuleBase(BaseModel):
    """Base schema for module data."""

    brand: str = Field(..., max_length=100)
    name: str = Field(..., max_length=200)
    hp: int = Field(..., gt=0, description="Width in HP units")
    module_type: str = Field(
        ..., max_length=50, description="VCO, VCF, VCA, ENV, LFO, SEQ, UTIL, MIX, FX, etc."
    )
    power_12v_ma: Optional[int] = Field(None, ge=0)
    power_neg12v_ma: Optional[int] = Field(None, ge=0)
    power_5v_ma: Optional[int] = Field(None, ge=0)
    depth_mm: Optional[float] = Field(
        None, ge=0, description="Module depth in mm; null = unspecified"
    )
    io_ports: list[IOPort] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    manufacturer_url: Optional[str] = None
    status: Optional[str] = "active"
    replacement_module_id: Optional[int] = None
    deprecated_at: Optional[datetime] = None
    tombstoned_at: Optional[datetime] = None


class ModuleCreate(ModuleBase):
    """Schema for creating a new module."""

    source: str = Field(..., max_length=50, description="Manual, CSV, ModularGrid, etc.")
    source_reference: Optional[str] = Field(None, max_length=500)


class ModuleUpdate(BaseModel):
    """Schema for updating a module."""

    brand: Optional[str] = Field(None, max_length=100)
    name: Optional[str] = Field(None, max_length=200)
    hp: Optional[int] = Field(None, gt=0)
    module_type: Optional[str] = Field(None, max_length=50)
    power_12v_ma: Optional[int] = Field(None, ge=0)
    power_neg12v_ma: Optional[int] = Field(None, ge=0)
    power_5v_ma: Optional[int] = Field(None, ge=0)
    depth_mm: Optional[float] = Field(None, ge=0)
    io_ports: Optional[list[IOPort]] = None
    tags: Optional[list[str]] = None
    description: Optional[str] = None
    manufacturer_url: Optional[str] = None
    status: Optional[str] = None
    replacement_module_id: Optional[int] = None
    deprecated_at: Optional[datetime] = None
    tombstoned_at: Optional[datetime] = None


class ModuleResponse(ModuleBase):
    """Schema for module response."""

    id: int
    source: str
    source_reference: Optional[str]
    imported_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PowerConfigResponse(BaseModel):
    """One jumper setting's draws, with the maker page that states them (spec 003 D8).

    A rail with no number on the page is null (unknown), never 0.
    """

    id: int
    module_id: int
    label: str
    kind: str
    is_recommended: bool
    power_12v_ma: Optional[int]
    power_neg12v_ma: Optional[int]
    power_5v_ma: Optional[int]
    unit_stated: bool
    source_url: str
    quote: str

    class Config:
        from_attributes = True


class ModuleListResponse(BaseModel):
    """Schema for paginated module list."""

    total: int
    modules: list[ModuleResponse]
