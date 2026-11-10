"""One-use invites to the closed beta (owner's call, 2026-11-10).

With ``enable_invite_only_signup`` on, sign-up needs an unused code. A missing, wrong or used
code gets one reply, so a guess learns nothing.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from hashlib import sha256
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from community.models import BetaInvite, User
from monetization.grants import write_credit_grant

INVITE_REQUIRED = "INVITE_REQUIRED"


def new_code() -> str:
    return secrets.token_urlsafe(16)


def code_hash(code: str) -> str:
    return sha256(code.strip().encode("utf-8")).hexdigest()


def require_unused(db: Session, code: Optional[str]) -> None:
    """Refuse before any other sign-up check, so sign-up tells an uninvited caller nothing."""
    unused = (
        code
        and db.query(BetaInvite.id)
        .filter(BetaInvite.code_hash == code_hash(code), BetaInvite.redeemed_by.is_(None))
        .first()
    )
    if not unused:
        raise HTTPException(status_code=403, detail=INVITE_REQUIRED)


def redeem(db: Session, code: str, user: User) -> None:
    """Claim the invite for this new account and grant its credits, in the caller's transaction.
    The claim is one conditional update, so two sign-ups with one code can't both win."""
    digest = code_hash(code)
    claimed = (
        db.query(BetaInvite)
        .filter(BetaInvite.code_hash == digest, BetaInvite.redeemed_by.is_(None))
        .update({"redeemed_by": user.id, "redeemed_at": datetime.utcnow()}, synchronize_session=False)
    )
    if claimed != 1:
        db.rollback()
        raise HTTPException(status_code=403, detail=INVITE_REQUIRED)
    invite = db.query(BetaInvite).filter(BetaInvite.code_hash == digest).one()
    write_credit_grant(
        db,
        user_id=user.id,
        credits=invite.credits,
        reason=f"beta-invite:{invite.id}",
        grant_key=f"beta-invite:{invite.id}",
        key_prefix="beta-invite",
    )
