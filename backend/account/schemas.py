"""Pydantic schemas for account dashboard data."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreditLedgerEntryResponse(BaseModel):
    id: int
    entry_type: str
    amount: int
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CreditsSummaryResponse(BaseModel):
    balance: int
    entries: list[CreditLedgerEntryResponse]


class ExportRecordResponse(BaseModel):
    id: int
    export_type: str
    entity_id: int
    run_id: str
    unlocked: bool
    license_type: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReferralRecordResponse(BaseModel):
    referred_user_id: str
    status: str
    rewarded_at: Optional[datetime] = None


class ReferralSummaryResponse(BaseModel):
    referral_code: str
    referral_link: str
    pending_count: int
    earned_count: int
    recent_referrals: list[ReferralRecordResponse]


class LeaderboardEntryResponse(BaseModel):
    rank: int = Field(..., ge=1)
    module_name: str
    manufacturer: str
    count: int


class AccountDeleteRequest(BaseModel):
    """Deleting the account re-confirms the current password."""

    password: str = Field(..., max_length=128)
