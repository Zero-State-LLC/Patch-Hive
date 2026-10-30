"""Routes for account dashboard data."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from community.auth import require_auth
from community.models import User
from core import get_db, settings

from .models import CreditLedgerEntry, ExportRecord, Referral
from .schemas import (
    CreditsSummaryResponse,
    ExportRecordResponse,
    ReferralRecordResponse,
    ReferralSummaryResponse,
)
from .services import build_referral_link, ensure_referral_code, mask_user_id

router = APIRouter()


@router.get("/credits", response_model=CreditsSummaryResponse)
def get_credits(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Get current credit balance and recent ledger entries."""
    balance = (
        db.query(func.coalesce(func.sum(CreditLedgerEntry.amount), 0))
        .filter(CreditLedgerEntry.user_id == current_user.id)
        .scalar()
    )
    entries = (
        db.query(CreditLedgerEntry)
        .filter(CreditLedgerEntry.user_id == current_user.id)
        .order_by(desc(CreditLedgerEntry.created_at))
        .limit(20)
        .all()
    )
    return CreditsSummaryResponse(balance=balance, entries=entries)


@router.get("/exports", response_model=list[ExportRecordResponse])
def get_exports(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Get recent exports for the current user."""
    exports = (
        db.query(ExportRecord)
        .filter(ExportRecord.user_id == current_user.id)
        .order_by(desc(ExportRecord.created_at))
        .limit(20)
        .all()
    )
    return exports


@router.get("/referrals", response_model=ReferralSummaryResponse)
def get_referrals(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Get referral summary for the current user."""
    if not settings.enable_referrals:
        raise HTTPException(status_code=404, detail="Referrals are not enabled")
    referral_code = ensure_referral_code(db, current_user)
    referrals = (
        db.query(Referral)
        .filter(Referral.referrer_user_id == current_user.id)
        .order_by(desc(Referral.created_at))
        .limit(10)
        .all()
    )

    pending_count = (
        db.query(func.count(Referral.id))
        .filter(Referral.referrer_user_id == current_user.id, Referral.status == "pending")
        .scalar()
    )
    earned_count = (
        db.query(func.count(Referral.id))
        .filter(Referral.referrer_user_id == current_user.id, Referral.status == "earned")
        .scalar()
    )

    recent_referrals = [
        ReferralRecordResponse(
            referred_user_id=mask_user_id(referral.referred_user_id),
            status=referral.status,
            rewarded_at=referral.rewarded_at,
        )
        for referral in referrals
    ]

    referral_link = build_referral_link(settings.frontend_base_url, referral_code)

    return ReferralSummaryResponse(
        referral_code=referral_code,
        referral_link=referral_link,
        pending_count=pending_count,
        earned_count=earned_count,
        recent_referrals=recent_referrals,
    )
