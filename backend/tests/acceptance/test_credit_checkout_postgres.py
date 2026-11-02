"""Spec 004 T046 on Postgres: Machine B credits in one transaction, once.

SQLite cannot show either property: its driver commits a released savepoint opened
outside a transaction, and it ignores ``FOR UPDATE``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session, sessionmaker

import canon.checkout as checkout
from canon.exports import credit_balance, receive_stripe_webhook
from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderPaymentRecord,
    StripeEventRecordModel,
)
from monetization.models import CreditsLedger

TS = 1_700_000_000
SECRET = "whsec_machine_b_pg"


def _open_payment(session: Session, user_id: int, session_id: str) -> ProviderPaymentRecord:
    now = datetime.now(timezone.utc)
    session.add(
        ProviderCustomerRecord(
            user_id=user_id, provider_customer_id=f"cus_{user_id}", created_at=now
        )
    )
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


def _payload(event_id: str, event_type: str, payment: ProviderPaymentRecord) -> bytes:
    obj = {
        "id": payment.checkout_session_id,
        "mode": "payment",
        "customer": f"cus_{payment.user_id}",
        "payment_intent": "pi_pg",
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
        {"id": event_id, "type": event_type, "livemode": False, "data": {"object": obj}}
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


def test_a_failure_after_the_purchase_entry_rolls_back_the_whole_delivery(
    db_session: Session, create_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = create_user("pg-mb-buyer", "pg-pass")
    payment = _open_payment(db_session, user.id, "cs_pg_fail")

    def boom(*_args, **_kwargs):
        raise RuntimeError("referral evaluation failed")

    monkeypatch.setattr(checkout, "record_purchase", boom)
    with pytest.raises(RuntimeError):
        _receive(db_session, _payload("evt_pg_mb_fail", "checkout.session.completed", payment))
    db_session.rollback()

    assert db_session.get(StripeEventRecordModel, "evt_pg_mb_fail") is None
    assert db_session.query(CanonicalCreditLedgerEntryRecord).count() == 0
    assert db_session.query(CreditsLedger).count() == 0
    db_session.refresh(payment)
    assert payment.status == "open"


def test_a_paid_completion_commits_the_purchase_and_the_event_together(
    db_session: Session, create_user
) -> None:
    user = create_user("pg-mb-buyer2", "pg-pass")
    payment = _open_payment(db_session, user.id, "cs_pg_ok")

    _receive(db_session, _payload("evt_pg_mb_ok", "checkout.session.completed", payment))
    db_session.commit()

    record = db_session.get(StripeEventRecordModel, "evt_pg_mb_ok")
    assert (record.status, record.object_id) == ("processed", "cs_pg_ok")
    assert credit_balance(db_session, user.id) == 30
    assert db_session.query(CreditsLedger).filter_by(change_type="Purchase").count() == 1


def test_concurrent_deliveries_for_one_payment_credit_once(
    migrated_db: sessionmaker, db_session: Session, create_user
) -> None:
    """Two event ids for the same paid session, delivered at once (FR-012)."""
    user = create_user("pg-mb-buyer3", "pg-pass")
    payment = _open_payment(db_session, user.id, "cs_pg_race")
    payloads = [
        _payload("evt_pg_race_a", "checkout.session.completed", payment),
        _payload("evt_pg_race_b", "checkout.session.async_payment_succeeded", payment),
    ]
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
    assert sorted(statuses) == ["duplicate", "processed"]
    db_session.expire_all()
    purchases = db_session.query(CanonicalCreditLedgerEntryRecord).filter_by(entry_type="purchase")
    assert purchases.count() == 1
    assert credit_balance(db_session, user.id) == 30
    assert db_session.query(CreditsLedger).filter_by(change_type="Purchase").count() == 1
