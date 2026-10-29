"""
Tests for referral credit rewards.
"""

from sqlalchemy.orm import Session

from community.models import User
from monetization.models import CreditsLedger, Export, Referral
from monetization.referrals import REFERRAL_REWARD_CREDITS, create_referral, record_purchase


def _create_user(db_session: Session, username: str, email: str, referral_code: str) -> User:
    user = User(
        username=username,
        email=email,
        password_hash="hashed",
        referral_code=referral_code,
        role="User",
        display_name=username,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_referral_reward_on_first_purchase(db_session: Session):
    referrer = _create_user(db_session, "referrer", "referrer@example.com", "refcode")
    referred = _create_user(db_session, "referred", "referred@example.com", "newcode")
    referral = create_referral(db_session, referrer=referrer, referred=referred)
    db_session.commit()

    assert db_session.query(CreditsLedger).filter(CreditsLedger.change_type == "Grant").count() == 0

    record_purchase(db_session, user=referred, credits_delta=5, notes="Credits purchase")
    db_session.commit()

    assert db_session.query(Export).count() == 0

    reward_entry = (
        db_session.query(CreditsLedger)
        .filter(
            CreditsLedger.user_id == referrer.id,
            CreditsLedger.change_type == "Grant",
            CreditsLedger.referral_id == referral.id,
        )
        .one()
    )
    assert reward_entry.credits_delta == REFERRAL_REWARD_CREDITS
    assert reward_entry.notes == f"Referral reward: {referred.id}"
    balance = (
        db_session.query(CreditsLedger)
        .filter(CreditsLedger.user_id == referrer.id)
        .with_entities(CreditsLedger.credits_delta)
        .all()
    )
    assert sum(entry.credits_delta for entry in balance) == REFERRAL_REWARD_CREDITS

    referral_rows = (
        db_session.query(Referral)
        .filter(Referral.referrer_user_id == referrer.id, Referral.referred_user_id == referred.id)
        .all()
    )
    statuses = {row.status for row in referral_rows}
    assert statuses == {"Pending", "Rewarded"}
    rewarded_row = next(row for row in referral_rows if row.status == "Rewarded")
    assert rewarded_row.first_purchase_id is not None


def test_referral_reward_only_once(db_session: Session):
    referrer = _create_user(db_session, "referrer2", "referrer2@example.com", "refcode2")
    referred = _create_user(db_session, "referred2", "referred2@example.com", "newcode2")
    create_referral(db_session, referrer=referrer, referred=referred)
    db_session.commit()

    record_purchase(db_session, user=referred, credits_delta=5)
    record_purchase(db_session, user=referred, credits_delta=2)
    db_session.commit()

    rewards = (
        db_session.query(CreditsLedger)
        .filter(CreditsLedger.user_id == referrer.id, CreditsLedger.change_type == "Grant")
        .all()
    )
    assert len(rewards) == 1


def test_purchase_without_referral_no_reward(db_session: Session):
    user = _create_user(db_session, "solo", "solo@example.com", "solocode")
    record_purchase(db_session, user=user, credits_delta=3)
    db_session.commit()

    rewards = db_session.query(CreditsLedger).filter(CreditsLedger.change_type == "Grant").all()
    assert rewards == []


def test_self_referral_rejected(db_session: Session):
    user = _create_user(db_session, "selfy", "selfy@example.com", "selfcode")
    try:
        create_referral(db_session, referrer=user, referred=user)
    except ValueError as exc:
        assert "cannot be the same" in str(exc)


def test_a_referral_reward_is_spendable_once(db_session: Session):
    """Spec 004 FR-009: the reward lands in the canonical ledger that spending reads."""
    from canon.exports import credit_balance

    referrer = _create_user(db_session, "referrer3", "referrer3@example.com", "refcode3")
    referred = _create_user(db_session, "referred3", "referred3@example.com", "newcode3")
    create_referral(db_session, referrer=referrer, referred=referred)
    db_session.commit()

    record_purchase(db_session, user=referred, credits_delta=5)
    record_purchase(db_session, user=referred, credits_delta=2)
    db_session.commit()

    assert credit_balance(db_session, referrer.id) == REFERRAL_REWARD_CREDITS
