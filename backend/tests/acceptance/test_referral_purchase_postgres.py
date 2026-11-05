"""Spec 004 T047 on Postgres: concurrent first provider purchases reward once.

Two checkouts by the same referred user complete at the same moment, each through its
own connection and the real webhook path. Each transaction sees only its own purchase,
so both look like the first one; the referral row lock (and the
``uq_referrals_one_reward`` index behind it) must still let only one reward through
(FR-026, FR-027, SC-002). SQLite ignores ``FOR UPDATE``, so this needs Postgres.

Owner decision 44 races the same path against account deletion: a reward and a deletion
of its referrer serialize on the referrer's row, so a reward is either paid before the
deletion or not at all.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from account.deletion import anonymize_user
from admin.models import AdminAuditLog
from canon.exports import credit_balance, receive_stripe_webhook
from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderPaymentRecord,
)
from community.models import User
from monetization.models import CreditsLedger, Referral
from monetization.referrals import REFERRAL_REWARD_CREDITS, create_referral, record_purchase

TS = 1_700_000_000
SECRET = "whsec_t047_pg"


def _open_payment(session: Session, user_id: int, session_id: str) -> ProviderPaymentRecord:
    now = datetime.now(timezone.utc)
    payment = ProviderPaymentRecord(
        id=f"pay-{session_id}",
        user_id=user_id,
        checkout_session_id=session_id,
        credits=30,
        amount_cents=600,
        currency="usd",
        status="open",
        created_at=now,
        updated_at=now,
    )
    session.add(payment)
    session.commit()
    return payment


def _payload(event_id: str, payment: ProviderPaymentRecord) -> bytes:
    obj = {
        "id": payment.checkout_session_id,
        "mode": "payment",
        "customer": f"cus_{payment.user_id}",
        "payment_intent": f"pi_{payment.checkout_session_id}",
        "payment_status": "paid",
        "amount_total": payment.amount_cents,
        "currency": "usd",
        "metadata": {
            "user_id": str(payment.user_id),
            "credits": str(payment.credits),
            "purchase_type": "one_time",
        },
    }
    return json.dumps(
        {
            "id": event_id,
            "type": "checkout.session.completed",
            "livemode": False,
            "data": {"object": obj},
        }
    ).encode()


def _receive(session: Session, payload: bytes):
    signature = hmac.new(SECRET.encode(), f"{TS}.".encode() + payload, hashlib.sha256).hexdigest()
    return receive_stripe_webhook(
        session,
        payload=payload,
        signature_header=f"t={TS},v1={signature}",
        secret=SECRET,
        now=TS,
    )


def test_concurrent_first_provider_purchases_write_one_referral_reward(
    migrated_db: sessionmaker, db_session: Session, create_user
) -> None:
    referrer = create_user("pg-t047-referrer", "pg-pass")
    referred = create_user("pg-t047-referred", "pg-pass")
    create_referral(db_session, referrer=referrer, referred=referred)
    db_session.add(
        ProviderCustomerRecord(
            user_id=referred.id,
            provider_customer_id=f"cus_{referred.id}",
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    payments = [
        _open_payment(db_session, referred.id, "cs_t047_pg_a"),
        _open_payment(db_session, referred.id, "cs_t047_pg_b"),
    ]
    payloads = [_payload(f"evt_t047_pg_{i}", p) for i, p in enumerate(payments)]
    barrier = threading.Barrier(2)
    statuses: list[str] = []
    errors: list[BaseException] = []

    def deliver(payload: bytes) -> None:
        session = migrated_db()
        try:
            barrier.wait(timeout=10)
            intake = _receive(session, payload)
            session.commit()
            statuses.append(intake.record.status)
        except BaseException as exc:  # pragma: no cover - surfaced below
            session.rollback()
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=deliver, args=(p,)) for p in payloads]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    # Both purchases are real and both credit the buyer; only the reward is single.
    assert statuses == ["processed", "processed"]
    db_session.expire_all()
    grants = (
        db_session.query(CanonicalCreditLedgerEntryRecord)
        .filter(
            CanonicalCreditLedgerEntryRecord.entry_type == "grant",
            CanonicalCreditLedgerEntryRecord.idempotency_key.like("referral-reward:%"),
        )
        .all()
    )
    assert [(g.user_id, g.delta) for g in grants] == [(referrer.id, REFERRAL_REWARD_CREDITS)]
    assert db_session.query(Referral).filter_by(status="Rewarded").count() == 1
    assert db_session.query(CreditsLedger).filter_by(change_type="Grant").count() == 1
    assert db_session.query(CreditsLedger).filter_by(change_type="Purchase").count() == 2
    assert credit_balance(db_session, referrer.id) == REFERRAL_REWARD_CREDITS
    assert credit_balance(db_session, referred.id) == 60


# --- Owner decision 44: a reward racing the deletion of its referrer ------------------------


def _referred_buyer(db_session: Session, create_user, prefix: str) -> tuple[User, User]:
    referrer = create_user(f"{prefix}-referrer", "pg-pass")
    referred = create_user(f"{prefix}-referred", "pg-pass")
    create_referral(db_session, referrer=referrer, referred=referred)
    db_session.add(
        ProviderCustomerRecord(
            user_id=referred.id,
            provider_customer_id=f"cus_{referred.id}",
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    return referrer, referred


def _wait_for_a_blocked_connection(migrated_db: sessionmaker, timeout: float = 15.0) -> None:
    probe = migrated_db()
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            blocked = probe.execute(
                text(
                    "select count(*) from pg_stat_activity "
                    "where datname = current_database() and wait_event_type = 'Lock'"
                )
            ).scalar()
            probe.rollback()
            if blocked:
                return
            time.sleep(0.02)
    finally:
        probe.close()
    raise AssertionError("no connection blocked on a lock")


def _reward_grants(session: Session) -> list[CanonicalCreditLedgerEntryRecord]:
    return (
        session.query(CanonicalCreditLedgerEntryRecord)
        .filter(
            CanonicalCreditLedgerEntryRecord.entry_type == "grant",
            CanonicalCreditLedgerEntryRecord.idempotency_key.like("referral-reward:%"),
        )
        .all()
    )


def _withheld_traces(session: Session) -> list[AdminAuditLog]:
    return session.query(AdminAuditLog).filter_by(action_type="referral_reward_withheld").all()


def test_a_reward_that_meets_an_uncommitted_deletion_waits_and_pays_nothing(
    migrated_db: sessionmaker, db_session: Session, create_user
) -> None:
    """The deletion holds the referrer's row and has not committed, so ``deleted_at`` still
    reads NULL to everyone else. Without the row lock the reward would pay into the
    account that is being deleted."""
    referrer, referred = _referred_buyer(db_session, create_user, "pg-d44-first")
    payment = _open_payment(db_session, referred.id, "cs_d44_pg_first")
    payload = _payload("evt_d44_pg_first", payment)
    statuses: list[str] = []
    errors: list[BaseException] = []

    def deliver() -> None:
        session = migrated_db()
        try:
            intake = _receive(session, payload)
            session.commit()
            statuses.append(intake.record.status)
        except BaseException as exc:  # pragma: no cover - surfaced below
            session.rollback()
            errors.append(exc)
        finally:
            session.close()

    deleter = migrated_db()
    thread = threading.Thread(target=deliver)
    try:
        anonymize_user(deleter, deleter.get(User, referrer.id))
        thread.start()
        _wait_for_a_blocked_connection(migrated_db)
        assert thread.is_alive()
        deleter.commit()
    finally:
        deleter.close()
        thread.join(timeout=30)

    assert errors == []
    # The buyer's purchase went through once the deletion finished.
    assert statuses == ["processed"]
    db_session.expire_all()
    assert credit_balance(db_session, referred.id) == payment.credits
    assert db_session.query(CreditsLedger).filter_by(change_type="Purchase").count() == 1
    # No reward of either kind reached the deleted account.
    assert db_session.get(User, referrer.id).deleted_at is not None
    assert _reward_grants(db_session) == []
    assert db_session.query(CreditsLedger).filter_by(change_type="Grant").count() == 0
    assert {row.status for row in db_session.query(Referral)} == {"Pending"}
    assert credit_balance(db_session, referrer.id) == 0
    assert len(_withheld_traces(db_session)) == 1


def test_a_deletion_that_meets_an_uncommitted_reward_waits_for_it(
    migrated_db: sessionmaker, db_session: Session, create_user
) -> None:
    """The other order: the reward is paid while the account is live, and the deletion
    only proceeds once it is committed. Nothing is revoked (FR-008)."""
    referrer, referred = _referred_buyer(db_session, create_user, "pg-d44-second")
    errors: list[BaseException] = []

    def delete_account() -> None:
        session = migrated_db()
        try:
            anonymize_user(session, session.get(User, referrer.id))
            session.commit()
        except BaseException as exc:  # pragma: no cover - surfaced below
            session.rollback()
            errors.append(exc)
        finally:
            session.close()

    buyer_session = migrated_db()
    thread = threading.Thread(target=delete_account)
    try:
        record_purchase(
            buyer_session,
            user=buyer_session.get(User, referred.id),
            credits_delta=0,
            payment_verified=True,
        )
        buyer_session.flush()
        thread.start()
        _wait_for_a_blocked_connection(migrated_db)
        assert thread.is_alive()
        buyer_session.commit()
    finally:
        buyer_session.close()
        thread.join(timeout=30)

    assert errors == []
    db_session.expire_all()
    assert db_session.get(User, referrer.id).deleted_at is not None
    assert [(g.user_id, g.delta) for g in _reward_grants(db_session)] == [
        (referrer.id, REFERRAL_REWARD_CREDITS)
    ]
    assert db_session.query(Referral).filter_by(status="Rewarded").count() == 1
    assert _withheld_traces(db_session) == []


def test_concurrent_first_purchases_with_a_deleted_referrer_leave_one_trace(
    migrated_db: sessionmaker, db_session: Session, create_user
) -> None:
    referrer, referred = _referred_buyer(db_session, create_user, "pg-d44-both")
    anonymize_user(db_session, db_session.get(User, referrer.id))
    db_session.commit()
    payments = [
        _open_payment(db_session, referred.id, "cs_d44_pg_a"),
        _open_payment(db_session, referred.id, "cs_d44_pg_b"),
    ]
    payloads = [_payload(f"evt_d44_pg_{i}", p) for i, p in enumerate(payments)]
    barrier = threading.Barrier(2)
    statuses: list[str] = []
    errors: list[BaseException] = []

    def deliver(payload: bytes) -> None:
        session = migrated_db()
        try:
            barrier.wait(timeout=10)
            intake = _receive(session, payload)
            session.commit()
            statuses.append(intake.record.status)
        except BaseException as exc:  # pragma: no cover - surfaced below
            session.rollback()
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=deliver, args=(p,)) for p in payloads]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert statuses == ["processed", "processed"]
    db_session.expire_all()
    assert credit_balance(db_session, referred.id) == 60
    assert _reward_grants(db_session) == []
    assert credit_balance(db_session, referrer.id) == 0
    assert len(_withheld_traces(db_session)) == 1
