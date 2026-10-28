"""
Pydantic schemas for admin APIs.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from modules.schemas import IOPort


class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdminUserList(BaseModel):
    total: int
    users: list[AdminUserResponse]


class AdminRoleUpdate(BaseModel):
    role: Literal["Admin", "Ops", "Support", "ReadOnly", "User"]
    reason: str


class AdminAvatarUpdate(BaseModel):
    avatar_url: Optional[str] = None
    reason: str


class AdminCreditsGrant(BaseModel):
    credits: int = Field(..., gt=0)
    reason: str


class AdminModuleCreate(BaseModel):
    brand: str
    name: str
    hp: int
    module_type: str
    power_12v_ma: Optional[int] = None
    power_neg12v_ma: Optional[int] = None
    power_5v_ma: Optional[int] = None
    io_ports: list[IOPort] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    manufacturer_url: Optional[str] = None
    source: str
    source_reference: Optional[str] = None


class AdminModuleImport(BaseModel):
    modules: list[AdminModuleCreate]
    reason: str


class AdminModuleStatusUpdate(BaseModel):
    status: str
    reason: str


class AdminModuleMerge(BaseModel):
    replacement_module_id: int
    reason: str


class AdminGalleryRevision(BaseModel):
    id: int
    module_key: str
    revision_id: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdminGalleryRevisionList(BaseModel):
    total: int
    revisions: list[AdminGalleryRevision]


class AdminRunResponse(BaseModel):
    id: int
    rack_id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdminRunList(BaseModel):
    total: int
    runs: list[AdminRunResponse]


class AdminExportResponse(BaseModel):
    id: int
    user_id: int
    export_type: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdminPendingFunction(BaseModel):
    id: int
    module_id: int
    function_name: str
    status: str
    canonical_function: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminPendingFunctionList(BaseModel):
    total: int
    items: list[AdminPendingFunction]


class AdminFunctionApprove(BaseModel):
    canonical_function: str
    reason: str


class AdminLeaderboardEntry(BaseModel):
    label: str
    count: int


class AdminCacheInvalidate(BaseModel):
    run_id: Optional[int] = None
    export_type: Optional[str] = None
    reason: str


class AdminActionReason(BaseModel):
    reason: str
