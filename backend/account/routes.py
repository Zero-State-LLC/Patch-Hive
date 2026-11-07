"""Routes for account dashboard data."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import desc
from sqlalchemy.orm import Session

from community import login_guard, sessions
from community.auth import require_auth
from community.models import User
from core import get_db, settings
from core.security import burn_password_check, verify_and_update_password
from monetization.referrals import get_referral_summary

from .deletion import anonymize_user, purge_user_images
from .models import ExportRecord
from .schemas import (
    AccountDeleteRequest,
    ExportRecordResponse,
    ReferralRecordResponse,
    ReferralSummaryResponse,
)
from .services import build_referral_link, ensure_referral_code, mask_user_id

router = APIRouter()


@router.delete("", status_code=204)
def delete_account(
    body: AccountDeleteRequest,
    http_request: Request,
    response: Response,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Delete the signed-in account (spec 004 OQ-12): re-confirm the password, then
    anonymize the user and remove their personal content in one transaction. Ledger,
    export and referral rows are kept. See ``account/deletion.py``."""
    if not login_guard.allow_attempt(login_guard.client_address(http_request)):
        raise HTTPException(status_code=429, detail="Too many attempts; try again shortly")
    wrong = HTTPException(status_code=403, detail="PASSWORD_INCORRECT")
    if login_guard.is_locked(current_user):
        burn_password_check(body.password)
        raise wrong
    valid, _ = verify_and_update_password(body.password, current_user.password_hash)
    if not valid:
        login_guard.record_failure(db, current_user)
        db.commit()
        raise wrong
    user_id = current_user.id
    anonymize_user(db, current_user)
    db.commit()
    purge_user_images(db, user_id)
    sessions.clear_cookie(response)
    response.status_code = 204
    return response


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
    """The referral summary for the current user (spec 004 FR-031), from the append-only
    ``referrals`` rows and the canonical reward grants that Machine A writes."""
    if not settings.enable_referrals:
        raise HTTPException(status_code=404, detail="Referrals are not enabled")
    referral_code = ensure_referral_code(db, current_user)
    summary = get_referral_summary(db, user=current_user)
    pending = summary["pending_referrals"]
    rewarded = summary["rewarded_referrals"]
    newest_first = sorted(
        [*pending, *rewarded], key=lambda referral: (referral.created_at, referral.id), reverse=True
    )
    return ReferralSummaryResponse(
        referral_code=referral_code,
        referral_link=build_referral_link(settings.frontend_base_url, referral_code),
        pending_count=len(pending),
        rewarded_count=len(rewarded),
        earned_credits=summary["earned_credits"],
        recent_referrals=[
            ReferralRecordResponse(
                referred_user_id=mask_user_id(referral.referred_user_id),
                status=referral.status,
                rewarded_at=referral.rewarded_at,
            )
            for referral in newest_first[:10]
        ],
    )
