"""Spec 004 T010: Machine A (Referral) transitions table encoded as tests.

Source: specs/004-commerce/spec.md, "## Stateful behavior", "### Machine A: Referral".
Machine B (one-time credit purchase) and Machine C (subscription) are not encoded: their
handlers are still ``_machine_not_built`` in canon/webhook_events.py (T046, T049 open).
Purchases here are provider-verified (``payment_verified=True``); an unverified one is
refused before anything is written (illegal row, FR-033).
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from canon.models import CanonicalCreditLedgerEntryRecord
from community.models import User
from monetization.models import CreditsLedger, Referral
from monetization.referrals import REFERRAL_REWARD_CREDITS, create_referral, record_purchase

NONE, PENDING, REWARDED = "NONE", "Pending", "Rewarded"


def _user(db: Session, name: str) -> User:
    user = User(
        username=name,
        email=f"{name}@example.com",
        password_hash="hashed",
        referral_code=f"code-{name}",
        role="User",
        display_name=name,
    )
    db.add(user)
    db.commit()
    return user


def _state(db: Session, referred: User) -> str:
    """Effective state per spec: Rewarded row wins, then Pending row, else NONE."""
    statuses = {
        r.status for r in db.query(Referral).filter(Referral.referred_user_id == referred.id)
    }
    if REWARDED in statuses:
        return REWARDED
    return PENDING if PENDING in statuses else NONE


def _grants(db: Session) -> int:
    return db.query(CreditsLedger).filter(CreditsLedger.change_type == "Grant").count()


def _canonical_grants(db: Session) -> list[CanonicalCreditLedgerEntryRecord]:
    return db.query(CanonicalCreditLedgerEntryRecord).filter_by(entry_type="grant").all()


def _snapshot(db: Session) -> tuple[int, int]:
    return db.query(Referral).count(), db.query(CreditsLedger).count()


@pytest.fixture
def pair(db_session: Session) -> tuple[User, User]:
    return _user(db_session, "referrer"), _user(db_session, "referred")


def _in_state(db: Session, state: str, referrer: User, referred: User) -> None:
    if state in (PENDING, REWARDED):
        create_referral(db, referrer=referrer, referred=referred)
        db.commit()
    if state == REWARDED:
        record_purchase(db, user=referred, credits_delta=5, payment_verified=True)
        db.commit()
    assert _state(db, referred) == state


# (from, event, error text, to): signup_with_code rejected, state unchanged.
SIGNUP_REJECTED = [
    (PENDING, "signup_with_code", "Referral already recorded", PENDING),
    (REWARDED, "signup_with_code", "Referral already rewarded", REWARDED),
]


def test_none_signup_with_code_becomes_pending(db_session: Session, pair):
    referrer, referred = pair
    assert _state(db_session, referred) == NONE
    create_referral(db_session, referrer=referrer, referred=referred)
    db_session.commit()
    assert _state(db_session, referred) == PENDING
    row = db_session.query(Referral).one()
    assert (row.referrer_user_id, row.status) == (referrer.id, PENDING)
    assert _grants(db_session) == 0


def test_none_self_referral_rejected_without_rows(db_session: Session, pair):
    _, referred = pair
    before = _snapshot(db_session)
    with pytest.raises(ValueError):
        create_referral(db_session, referrer=referred, referred=referred)
    assert _snapshot(db_session) == before
    assert _state(db_session, referred) == NONE


@pytest.mark.parametrize(("start", "event", "message", "end"), SIGNUP_REJECTED)
def test_signup_rejected_when_already_pending_or_rewarded(
    db_session: Session, pair, start, event, message, end
):
    referrer, referred = pair
    _in_state(db_session, start, referrer, referred)
    before = _snapshot(db_session)
    with pytest.raises(ValueError, match=message):
        create_referral(db_session, referrer=referrer, referred=referred)
    assert _snapshot(db_session) == before
    assert _state(db_session, referred) == end


def test_pending_first_purchase_rewards_once_atomically(db_session: Session, pair):
    referrer, referred = pair
    _in_state(db_session, PENDING, referrer, referred)
    pending = db_session.query(Referral).one()

    purchase = record_purchase(db_session, user=referred, credits_delta=5, payment_verified=True)
    db_session.commit()

    assert _state(db_session, referred) == REWARDED
    grant = db_session.query(CreditsLedger).filter_by(change_type="Grant").one()
    assert grant.user_id == referrer.id
    assert grant.credits_delta == REFERRAL_REWARD_CREDITS == 3
    assert grant.notes == f"Referral reward: {referred.id}"
    assert grant.referral_id == pending.id
    rewarded = db_session.query(Referral).filter_by(status=REWARDED).one()
    assert rewarded.first_purchase_id == purchase.id
    assert rewarded.rewarded_at is not None
    # The spendable reward lands on the canonical ledger once (FR-009).
    (canonical,) = _canonical_grants(db_session)
    assert (canonical.user_id, canonical.delta) == (referrer.id, REFERRAL_REWARD_CREDITS)


def test_pending_non_first_purchase_stays_pending_without_reward(db_session: Session, pair):
    referrer, referred = pair
    _in_state(db_session, PENDING, referrer, referred)
    db_session.add(CreditsLedger(user_id=referred.id, change_type="Purchase", credits_delta=5))
    db_session.commit()

    # The purchase count is now 2.
    record_purchase(db_session, user=referred, credits_delta=5, payment_verified=True)
    db_session.commit()

    assert _state(db_session, referred) == PENDING
    assert _grants(db_session) == 0
    assert db_session.query(Referral).filter_by(status=REWARDED).count() == 0


def test_rewarded_further_purchases_are_no_ops(db_session: Session, pair):
    referrer, referred = pair
    _in_state(db_session, REWARDED, referrer, referred)
    before = (_grants(db_session), db_session.query(Referral).count())

    record_purchase(db_session, user=referred, credits_delta=5, payment_verified=True)
    record_purchase(db_session, user=referred, credits_delta=5, payment_verified=True)
    db_session.commit()

    assert _state(db_session, referred) == REWARDED
    assert (_grants(db_session), db_session.query(Referral).count()) == before
    assert _grants(db_session) == 1  # illegal: Rewarded -> Rewarded with a second Grant
    assert len(_canonical_grants(db_session)) == 1


def test_none_purchase_creates_no_referral_or_grant(db_session: Session, pair):
    _, referred = pair
    record_purchase(db_session, user=referred, credits_delta=5, payment_verified=True)
    db_session.commit()
    assert _state(db_session, referred) == NONE
    assert _grants(db_session) == 0
    assert db_session.query(Referral).count() == 0


def test_pending_unverified_purchase_is_refused_without_reward(db_session: Session, pair):
    """Illegal: a reward triggered by a client-submitted purchase (FR-033)."""
    referrer, referred = pair
    _in_state(db_session, PENDING, referrer, referred)
    before = _snapshot(db_session)

    with pytest.raises(ValueError, match="FR-033"):
        record_purchase(db_session, user=referred, credits_delta=5)
    db_session.rollback()

    assert _state(db_session, referred) == PENDING
    assert _snapshot(db_session) == before
    assert _canonical_grants(db_session) == []
