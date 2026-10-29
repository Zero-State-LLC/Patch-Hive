"""
FastAPI routes for monetization events.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from community.auth import require_auth
from community.models import User
from core import get_db, settings
from monetization.referrals import record_purchase
from monetization.schemas import PurchaseCreate

router = APIRouter()


@router.post("/purchases", status_code=201)
def create_purchase(
    purchase: PurchaseCreate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Record a paid purchase event for referral eligibility."""
    if not settings.enable_legacy_referrals:
        raise HTTPException(status_code=404, detail="Referrals are not enabled")
    record_purchase(
        db,
        user=current_user,
        credits_delta=purchase.credits_delta,
        notes=purchase.notes,
    )
    db.commit()
    return {"status": "recorded"}

