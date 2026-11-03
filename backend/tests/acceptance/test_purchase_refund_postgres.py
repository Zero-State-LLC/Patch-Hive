"""Spec 004 OQ-2 ``A_reverse_unspent`` (T053) on Postgres: refunds reverse once, never negative.

SQLite cannot show these: it ignores ``FOR UPDATE`` and has no advisory locks, so the
row lock on the payment record and the per-user credit lock are only exercised here.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from canon.exports import credit_balance
from canon.models import CanonicalCreditLedgerEntryRecord, ProviderPaymentRecord
from tests.acceptance.test_credit_checkout_postgres import _open_payment, _receive


def _completed_payload(payment: ProviderPaymentRecord) -> bytes:
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
    event_id = f"evt_{payment.checkout_session_id}_paid"
    return json.dumps(
        {
            "id": event_id,
            "type": "checkout.session.completed",
            "livemode": False,
            "data": {"object": obj},
        }
    ).encode()


def _credited(session: Session, user_id: int, session_id: str) -> ProviderPaymentRecord:
    payment = _open_payment(session, user_id, session_id)
    intake = _receive(session, _completed_payload(payment))
    session.commit()
    assert intake.record.status == "processed"
    session.refresh(payment)
    return payment


def _refund_payload(event_id: str, payment: ProviderPaymentRecord, refunded: int) -> bytes:
    obj = {
        "id": f"ch_{payment.checkout_session_id}",
        "object": "charge",
        "payment_intent": payment.provider_payment_id,
        "customer": f"cus_{payment.user_id}",
        "amount": payment.amount_cents,
        "amount_refunded": refunded,
        "currency": payment.currency,
    }
    return json.dumps(
        {"id": event_id, "type": "charge.refunded", "livemode": False, "data": {"object": obj}}
    ).encode()


def _deliver_at_once(migrated_db: sessionmaker, payloads: list[bytes]) -> list[str]:
    barrier = threading.Barrier(len(payloads))
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
    return sorted(statuses)


def _refunds(session: Session, user_id: int) -> list[CanonicalCreditLedgerEntryRecord]:
    return (
        session.query(CanonicalCreditLedgerEntryRecord)
        .filter_by(user_id=user_id, entry_type="refund")
        .all()
    )


def test_concurrent_duplicate_refund_deliveries_reverse_once(
    migrated_db: sessionmaker, db_session: Session, create_user
) -> None:
    """Two event ids carrying the same cumulative refund, delivered at once."""
    user = create_user("pg-rf-buyer", "pg-pass")
    payment = _credited(db_session, user.id, "cs_pg_rf_race")

    statuses = _deliver_at_once(
        migrated_db,
        [
            _refund_payload("evt_pg_rf_a", payment, 600),
            _refund_payload("evt_pg_rf_b", payment, 600),
        ],
    )

    assert statuses == ["duplicate", "processed"]
    db_session.expire_all()
    (entry,) = _refunds(db_session, user.id)
    assert entry.delta == -30
    assert credit_balance(db_session, user.id) == 0
    db_session.refresh(payment)
    assert (payment.status, payment.refund_reversed_credits) == ("refunded", 30)


def test_a_refund_after_partial_spend_reverses_only_the_remainder_never_negative(
    db_session: Session, create_user
) -> None:
    user = create_user("pg-rf-spender", "pg-pass")
    payment = _credited(db_session, user.id, "cs_pg_rf_spent")
    db_session.add(
        CanonicalCreditLedgerEntryRecord(
            id="debit-pg-rf-spent",
            user_id=user.id,
            delta=-18,
            entry_type="debit",
            idempotency_key="test-spend:pg-rf-spent",
            export_id=None,
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    intake = _receive(db_session, _refund_payload("evt_pg_rf_spent", payment, 600))
    db_session.commit()

    # The reversal commits even though the event waits for the operator.
    db_session.expire_all()
    assert (intake.record.status, intake.record.reason_code) == (
        "unresolved",
        "REFUND_EXCEEDS_UNSPENT",
    )
    (entry,) = _refunds(db_session, user.id)
    assert entry.delta == -12
    assert credit_balance(db_session, user.id) == 0
    db_session.refresh(payment)
    assert (payment.refund_reversed_credits, payment.refund_unrecovered_credits) == (12, 18)


def test_a_refund_racing_a_spend_never_takes_the_balance_below_zero(
    migrated_db: sessionmaker, db_session: Session, create_user
) -> None:
    """The refund takes the same per-user credit lock as an export debit."""
    from canon.exports import _serialize_user_credits

    user = create_user("pg-rf-racer", "pg-pass")
    payment = _credited(db_session, user.id, "cs_pg_rf_spend_race")
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def spend() -> None:
        session = migrated_db()
        try:
            barrier.wait(timeout=10)
            _serialize_user_credits(session, user.id)
            if credit_balance(session, user.id) >= 20:
                session.add(
                    CanonicalCreditLedgerEntryRecord(
                        id="debit-pg-rf-race",
                        user_id=user.id,
                        delta=-20,
                        entry_type="debit",
                        idempotency_key="test-spend:pg-rf-race",
                        export_id=None,
                        created_at=datetime.now(timezone.utc),
                    )
                )
            session.commit()
        except BaseException as exc:  # pragma: no cover - surfaced below
            session.rollback()
            errors.append(exc)
        finally:
            session.close()

    def refund() -> None:
        session = migrated_db()
        try:
            barrier.wait(timeout=10)
            _receive(session, _refund_payload("evt_pg_rf_spend_race", payment, 600))
            session.commit()
        except BaseException as exc:  # pragma: no cover - surfaced below
            session.rollback()
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=spend), threading.Thread(target=refund)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    db_session.expire_all()
    assert credit_balance(db_session, user.id) == 0
    db_session.refresh(payment)
    assert payment.refund_reversed_credits + payment.refund_unrecovered_credits == 30
