"""Schemas for catalog-backed rack compatibility calculations."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

CompatibilityStatus = Literal["verified", "incomplete", "conflict"]


class CompatibilityModuleIn(BaseModel):
    """One module placement evaluated against a catalog case revision.

    Prefer ``module_id`` to load registry specs. Inline fields override missing
    registry values without inventing unspecified case rails or depths.
    """

    module_id: Optional[int] = None
    name: Optional[str] = None
    row_index: int = Field(0, ge=0)
    start_hp: int = Field(0, ge=0)
    hp: Optional[int] = Field(None, gt=0)
    depth_mm: Optional[float] = Field(None, ge=0)
    format_family: Optional[str] = Field(
        None, description="Module format; defaults to eurorack when omitted"
    )
    power_12v_ma: Optional[int] = Field(None, ge=0)
    power_neg12v_ma: Optional[int] = Field(None, ge=0)
    power_5v_ma: Optional[int] = Field(None, ge=0)
    requires_close_patched_lid: Optional[bool] = None


class CompatibilityRequest(BaseModel):
    revision_key: Optional[str] = Field(
        None, description="Defaults to primary catalog revision when omitted"
    )
    modules: list[CompatibilityModuleIn] = Field(default_factory=list)
    # Soft planning flag: operator intends to close the lid with patch cables attached.
    plan_close_lid: bool = False


class CheckResult(BaseModel):
    status: CompatibilityStatus
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class RowCapacityResult(BaseModel):
    row_index: int
    format_family: str
    capacity_unit: Optional[str] = None
    capacity_value: Optional[float] = None
    used_value: Optional[float] = None
    remaining_value: Optional[float] = None
    status: CompatibilityStatus
    message: str


class PowerRailResult(BaseModel):
    rail: str
    case_capacity_ma: Optional[int] = None
    # Sum of the known draws only. With unknown draws this is a lower bound.
    module_draw_ma: int
    # With unknown draws this is an upper bound.
    headroom_ma: Optional[int] = None
    unknown_draw_count: int = 0
    unknown_modules: list[str] = Field(default_factory=list)
    status: CompatibilityStatus
    message: str


class CompatibilityResponse(BaseModel):
    case_slug: str
    manufacturer: str
    model: str
    format_family: str
    revision_key: str
    overall_status: CompatibilityStatus
    format_check: CheckResult
    physical_fit: CheckResult
    remaining_capacity: list[RowCapacityResult]
    power_headroom: list[PowerRailResult]
    connector_availability: CheckResult
    pos5_compatibility: CheckResult
    lid_close: CheckResult
    warnings: list[CheckResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
