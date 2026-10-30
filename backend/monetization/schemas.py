"""
Pydantic schemas for monetization APIs.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReferralDetail(BaseModel):
    """Referral detail entry."""

    id: int
    referred_user_id: int
    status: str
    first_purchase_id: Optional[int]
    rewarded_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ReferralSummary(BaseModel):
    """Referral overview for the current user."""

    referral_code: str
    referral_link: str
    earned_credits: int
    pending_referrals: list[ReferralDetail]
    rewarded_referrals: list[ReferralDetail]
