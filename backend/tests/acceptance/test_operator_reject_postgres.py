"""Spec 004 T001 D4 on Postgres: a reject racing a paid event never credits a closed checkout.

The reject and the provider's next event run on their own connections and take the payment
row lock in turn. Whichever gets it first, the checkout ends in one consistent outcome. SQLite
ignores ``FOR UPDATE``, so this needs Postgres.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from canon.exports import receive_stripe_webhook
from canon.models import (
    CanonicalAdminAuditEventRecord,
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderPaymentRecord,
    StripeEventRecordModel,
)
from canon.webhook_events import reject_unresolved_event

SECRET = "whsec_reject_race"
TS = 1_700_000_000


def _paid_event(buyer_id: int) -> tuple[bytes, str]:
    payload = json.dumps(
        {
            "id": "evt_pg_paid",
            "type": "checkout.session.completed",
            "livemode": False,
            "data": {
                "object": {
                    "id": "cs_pg_reject",
                    "object": "checkout.session",
                    "mode": "payment",
                    "customer": f"cus_{buyer_id}",
                    "payment_intent": "pi_pg_reject",
                    "payment_status": "paid",
                    "amount_total": 600,
                    "currency": "usd",
                    "metadata": {
                        "user_id": str(buyer_id),
                        "credits": "30",
                        "purchase_type": "one_time",
                        "payment_record_id": "pay-cs_pg_reject",
                    },
                }
            },
        }
    ).encode()
    signature = hmac.new(SECRET.encode(), f"{TS}.".encode() + payload, hashlib.sha256).hexdigest()
    return payload, f"t={TS},v1={signature}"


def test_a_reject_racing_a_paid_event_ends_in_one_consistent_outcome(
    migrated_db: sessionmaker, db_session: Session, create_user
) -> None:
    admin = create_user("pg-rejecter", "pg-pass", role="Admin")
    buyer = create_user("pg-reject-buyer", "pg-pass")
    admin_id, buyer_id = admin.id, buyer.id
    now = datetime.now(timezone.utc)
    db_session.add(
        ProviderCustomerRecord(
            user_id=buyer_id, provider_customer_id=f"cus_{buyer_id}", created_at=now
        )
    )
    db_session.add(
        ProviderPaymentRecord(
            id="pay-cs_pg_reject",
            user_id=buyer_id,
            checkout_session_id="cs_pg_reject",
            credits=30,
            amount_cents=600,
            currency="usd",
            status="open",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        StripeEventRecordModel(
            stripe_event_id="evt_pg_bad",
            event_type="checkout.session.completed",
            payload_hash="0" * 64,
            livemode=False,
            object_id="cs_pg_reject",
            status="unresolved",
            reason_code="CUSTOMER_MISMATCH",
            received_at=now,
            processed_at=now,
        )
    )
    db_session.commit()
    payload, signature = _paid_event(buyer_id)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def reject() -> None:
        session = migrated_db()
        try:
            barrier.wait(timeout=10)
            record = session.get(StripeEventRecordModel, "evt_pg_bad")
            reject_unresolved_event(
                session, record, actor_user_id=admin_id, actor_role="Admin", reason="not ours"
            )
            session.commit()
        except BaseException as exc:  # noqa: BLE001 - reported by the assertion below
            errors.append(exc)
        finally:
            session.close()

    def deliver() -> None:
        session = migrated_db()
        try:
            barrier.wait(timeout=10)
            receive_stripe_webhook(
                session, payload=payload, signature_header=signature, secret=SECRET, now=TS
            )
            session.commit()
        except BaseException as exc:  # noqa: BLE001 - reported by the assertion below
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=reject), threading.Thread(target=deliver)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors, errors

    db_session.expire_all()
    payment = db_session.get(ProviderPaymentRecord, "pay-cs_pg_reject")
    purchases = db_session.query(CanonicalCreditLedgerEntryRecord).filter_by(entry_type="purchase")
    paid_event = db_session.get(StripeEventRecordModel, "evt_pg_paid")
    assert db_session.get(StripeEventRecordModel, "evt_pg_bad").status == "rejected"
    assert db_session.query(CanonicalAdminAuditEventRecord).count() == 1
    if payment.status == "credited":
        assert (purchases.count(), paid_event.status) == (1, "processed")
    else:
        assert payment.status == "abandoned"
        assert purchases.count() == 0
        assert (paid_event.status, paid_event.reason_code) == (
            "unresolved",
            "PAYMENT_STATE_CONFLICT",
        )
