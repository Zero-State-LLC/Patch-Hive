"""
Referral program utilities and credit ledger helpers.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from hashlib import sha256
from typing import Optional

from sqlalchemy.orm import Session

from community.models import User
from monetization.models import CreditsLedger, Referral

REFERRAL_REWARD_CREDITS = 3


def generate_referral_code(db: Session, length: int = 10) -> str:
    """Generate a random, unique referral code.

    The code is public (it goes in share links), so it must not be derived from
    anything private such as the email address.
    """
    while True:
        code = secrets.token_urlsafe(length)[:length].upper()
        if db.query(User).filter(User.referral_code == code).first() is None:
            return code


def create_referral(db: Session, *, referrer: User, referred: User) -> Referral:
    """Create a referral entry for a new user."""
    if referrer.id == referred.id:
        raise ValueError("Referrer and referred user cannot be the same.")
    existing_reward = (
        db.query(Referral)
        .filter(
            Referral.referred_user_id == referred.id,
            Referral.status == "Rewarded",
        )
        .first()
    )
    if existing_reward:
        raise ValueError("Referral already rewarded for this user.")
    existing_referral = (
        db.query(Referral)
        .filter(
            Referral.referred_user_id == referred.id,
            Referral.status == "Pending",
        )
        .first()
    )
    if existing_referral:
        raise ValueError("Referral already recorded for this user.")
    referral = Referral(
        referrer_user_id=referrer.id,
        referred_user_id=referred.id,
        status="Pending",
    )
    db.add(referral)
    return referral


def record_purchase(
    db: Session,
    *,
    user: User,
    credits_delta: int = 0,
    notes: Optional[str] = None,
    payment_verified: bool = False,
) -> CreditsLedger:
    """
    Record a paid purchase event and apply referral rewards if eligible.

    The ledger entry uses change_type="Purchase" and is treated as the
    canonical marker for first-paid purchase eligibility. Only a purchase the payment
    provider verified (``payment_verified``) earns a spendable canonical reward; the
    user-callable legacy route never does.
    """
    purchase_entry = CreditsLedger(
        user_id=user.id,
        change_type="Purchase",
        credits_delta=credits_delta,
        notes=notes,
    )
    db.add(purchase_entry)
    db.flush()
    apply_referral_reward(
        db,
        referred_user_id=user.id,
        purchase_entry_id=purchase_entry.id,
        payment_verified=payment_verified,
    )
    return purchase_entry


def apply_referral_reward(
    db: Session,
    *,
    referred_user_id: int,
    purchase_entry_id: int,
    payment_verified: bool = False,
) -> Optional[CreditsLedger]:
    """Grant referral credits after the referred user's first paid purchase."""
    purchase_count = (
        db.query(CreditsLedger)
        .filter(CreditsLedger.user_id == referred_user_id, CreditsLedger.change_type == "Purchase")
        .count()
    )
    if purchase_count != 1:
        return None

    # Lock the pending referral so two concurrent first purchases cannot both reward
    # it; the partial unique index uq_referrals_one_reward is the backstop.
    referral_pending = (
        db.query(Referral)
        .filter(
            Referral.referred_user_id == referred_user_id,
            Referral.status == "Pending",
        )
        .with_for_update()
        .first()
    )
    if not referral_pending:
        return None
    if referral_pending.referrer_user_id == referred_user_id:
        return None

    rewarded_exists = (
        db.query(Referral)
        .filter(
            Referral.referred_user_id == referred_user_id,
            Referral.status == "Rewarded",
        )
        .first()
    )
    if rewarded_exists:
        return None

    reward_entry = CreditsLedger(
        user_id=referral_pending.referrer_user_id,
        change_type="Grant",
        credits_delta=REFERRAL_REWARD_CREDITS,
        notes=f"Referral reward: {referred_user_id}",
        referral_id=referral_pending.id,
    )
    rewarded_entry = Referral(
        referrer_user_id=referral_pending.referrer_user_id,
        referred_user_id=referred_user_id,
        status="Rewarded",
        first_purchase_id=purchase_entry_id,
        rewarded_at=datetime.utcnow(),
    )
    db.add(reward_entry)
    db.add(rewarded_entry)
    # Spending and the balance users see read the canonical ledger (spec 004 FR-009), so a
    # reward for a provider-verified purchase goes there too, once per referral. A
    # self-reported purchase (the legacy route) must never mint spendable credits.
    if not payment_verified:
        return reward_entry
    from canon.models import CanonicalCreditLedgerEntryRecord

    reward_key = f"referral-reward:{referral_pending.id}"
    reward_id = f"grant-{sha256(reward_key.encode('utf-8')).hexdigest()[:24]}"
    if db.get(CanonicalCreditLedgerEntryRecord, reward_id) is None:
        db.add(
            CanonicalCreditLedgerEntryRecord(
                id=reward_id,
                user_id=referral_pending.referrer_user_id,
                delta=REFERRAL_REWARD_CREDITS,
                entry_type="grant",
                idempotency_key=reward_key,
                export_id=None,
                created_at=datetime.now(timezone.utc),
            )
        )
    return reward_entry


def get_referral_summary(db: Session, *, user: User) -> dict:
    """Return referral status overview for a user."""
    referrals = (
        db.query(Referral)
        .filter(Referral.referrer_user_id == user.id)
        .order_by(Referral.created_at.desc())
        .all()
    )
    rewarded_ids = {
        referral.referred_user_id for referral in referrals if referral.status == "Rewarded"
    }
    pending_referrals = [
        referral
        for referral in referrals
        if referral.status == "Pending" and referral.referred_user_id not in rewarded_ids
    ]
    rewarded_referrals = [referral for referral in referrals if referral.status == "Rewarded"]
    earned_credits = (
        db.query(CreditsLedger)
        .filter(
            CreditsLedger.user_id == user.id,
            CreditsLedger.change_type == "Grant",
            CreditsLedger.referral_id.isnot(None),
        )
        .with_entities(CreditsLedger.credits_delta)
        .all()
    )
    earned_total = sum(entry.credits_delta for entry in earned_credits)
    return {
        "referral_code": user.referral_code,
        "referral_link": f"/signup?ref={user.referral_code}",
        "pending_referrals": pending_referrals,
        "rewarded_referrals": rewarded_referrals,
        "earned_credits": earned_total,
    }
