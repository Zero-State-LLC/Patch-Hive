"""Spec 004 T047 on Postgres: concurrent first provider purchases reward once.

Two checkouts by the same referred user complete at the same moment, each through its
own connection and the real webhook path. Each transaction sees only its own purchase,
so both look like the first one; the referral row lock (and the
``uq_referrals_one_reward`` index behind it) must still let only one reward through
(FR-026, FR-027, SC-002). SQLite ignores ``FOR UPDATE``, so this needs Postgres.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from canon.exports import credit_balance, receive_stripe_webhook
from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderPaymentRecord,
)
from monetization.models import CreditsLedger, Referral
from monetization.referrals import REFERRAL_REWARD_CREDITS, create_referral

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
