"""
Referral program utilities and credit ledger helpers.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from hashlib import sha256
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from admin.models import AdminAuditLog
from community.models import User
from monetization.models import CreditsLedger, Referral

logger = logging.getLogger(__name__)

REFERRAL_REWARD_CREDITS = 3
REWARD_WITHHELD_ACTION = "referral_reward_withheld"
REFERRER_DELETED_REASON = "REFERRER_ACCOUNT_DELETED"


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
    provider verified (``payment_verified``) may be recorded (spec 004 FR-033): an
    unverified one raises before anything is written, so it can neither count as the
    first purchase nor trigger a referral reward.
    """
    if not payment_verified:
        raise ValueError("Only a provider-verified purchase can be recorded (spec 004 FR-033)")
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


def _referrer_is_deleted(db: Session, referrer_user_id: int) -> bool:
    """Whether the referrer's account is deleted, read under a shared row lock.

    Account deletion updates this row in its own transaction, so the two serialize: a
    reward that meets an uncommitted deletion waits and then reads the committed
    ``deleted_at``, and a deletion that meets an uncommitted reward waits for it. The lock
    is shared so that rewards to one referrer do not queue behind each other.
    """
    row = (
        db.query(User.deleted_at)
        .filter(User.id == referrer_user_id)
        .with_for_update(read=True)
        .one_or_none()
    )
    return row is None or row.deleted_at is not None


def _trace_withheld_reward(db: Session, *, referral_id: int, purchase_entry_id: int) -> None:
    """Leave one audit row per referral for a reward not paid. It holds no personal data.

    Runs under the ``Pending`` row lock, so concurrent first purchases leave one row. In a
    savepoint, so a failure here cannot cost the buyer their purchase.
    """
    target_id = str(referral_id)
    try:
        with db.begin_nested():
            already_traced = (
                db.query(AdminAuditLog.id)
                .filter(
                    AdminAuditLog.action_type == REWARD_WITHHELD_ACTION,
                    AdminAuditLog.target_type == "referral",
                    AdminAuditLog.target_id == target_id,
                )
                .first()
            )
            if already_traced is None:
                db.add(
                    AdminAuditLog(
                        actor_user_id=None,
                        actor_role="System",
                        action_type=REWARD_WITHHELD_ACTION,
                        target_type="referral",
                        target_id=target_id,
                        delta_json={
                            "credits_withheld": REFERRAL_REWARD_CREDITS,
                            "first_purchase_id": purchase_entry_id,
                        },
                        reason=REFERRER_DELETED_REASON,
                    )
                )
                db.flush()
    except SQLAlchemyError:
        logger.exception("referral %s: withheld-reward audit row not written", referral_id)


def apply_referral_reward(
    db: Session,
    *,
    referred_user_id: int,
    purchase_entry_id: int,
    payment_verified: bool = False,
) -> Optional[CreditsLedger]:
    """Grant referral credits after the referred user's first provider-verified purchase.

    An unverified purchase never rewards (spec 004 Machine A, FR-033). Nor does a referrer
    who has deleted their account (owner decision 44, 2026-11-04): the referral stays
    ``Pending``, no grant is written to either ledger, an audit row records why, and the
    buyer's purchase is not affected.
    """
    if not payment_verified:
        return None
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

    if _referrer_is_deleted(db, referral_pending.referrer_user_id):
        _trace_withheld_reward(
            db, referral_id=referral_pending.id, purchase_entry_id=purchase_entry_id
        )
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
    # Spending and the balance users see read the canonical ledger (spec 004 FR-009), so
    # the reward goes there too, once per referral.
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
    # Count only spendable credit: the canonical referral grants keyed by this user's own
    # referrals (spec 004 FR-009, FR-031, research R6). Legacy-ledger rewards for a
    # self-reported purchase are not spendable, so they are not earned credit.
    from canon.models import CanonicalCreditLedgerEntryRecord

    reward_keys = [f"referral-reward:{referral.id}" for referral in referrals]
    earned_total = 0
    if reward_keys:
        earned_total = int(
            db.query(func.coalesce(func.sum(CanonicalCreditLedgerEntryRecord.delta), 0))
            .filter(
                CanonicalCreditLedgerEntryRecord.user_id == user.id,
                CanonicalCreditLedgerEntryRecord.entry_type == "grant",
                CanonicalCreditLedgerEntryRecord.idempotency_key.in_(reward_keys),
            )
            .scalar()
            or 0
        )
    return {
        "referral_code": user.referral_code,
        "referral_link": f"/signup?ref={user.referral_code}",
        "pending_referrals": pending_referrals,
        "rewarded_referrals": rewarded_referrals,
        "earned_credits": earned_total,
    }
