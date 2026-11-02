"""Spec 004 T048b on Postgres: two overlapping operator resolves credit once.

Each resolve runs on its own connection. The event row lock makes them take turns, so
the second sees the first's final status and is refused with no write. SQLite ignores
``FOR UPDATE``, so this needs Postgres.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from canon.checkout import resolve_unresolved_event
from canon.exports import credit_balance
from canon.models import (
    CanonicalAdminAuditEventRecord,
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderPaymentRecord,
    StripeEventRecordModel,
)
from canon.webhook_events import InvalidEventTransitionError

SETTINGS = SimpleNamespace(
    enable_credit_checkout=True,
    environment="development",
    allow_production_payments=False,
    stripe_test_mode=True,
    stripe_secret_key="sk_test_fixture",
)


class SlowRetriever:
    """Holds the first resolve inside its lock long enough for the second to queue."""

    def __init__(self, obj: dict[str, Any]) -> None:
        self.obj = obj
        self.calls = 0

    def retrieve_checkout_session(self, session_id: str) -> dict[str, Any]:
        self.calls += 1
        time.sleep(0.5)
        return self.obj


def test_overlapping_resolves_credit_once_with_one_audit(
    migrated_db: sessionmaker, db_session: Session, create_user
) -> None:
    admin = create_user("pg-resolver", "pg-pass", role="Admin")
    buyer = create_user("pg-resolve-buyer", "pg-pass")
    now = datetime.now(timezone.utc)
    db_session.add(
        ProviderCustomerRecord(
            user_id=buyer.id, provider_customer_id=f"cus_{buyer.id}", created_at=now
        )
    )
    db_session.add(
        ProviderPaymentRecord(
            id="pay-cs_pg_resolve",
            user_id=buyer.id,
            checkout_session_id="cs_pg_resolve",
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
            stripe_event_id="evt_pg_resolve",
            event_type="checkout.session.completed",
            payload_hash="0" * 64,
            livemode=False,
            object_id="cs_pg_resolve",
            status="unresolved",
            reason_code="METADATA_MALFORMED",
            received_at=now,
            processed_at=now,
        )
    )
    db_session.commit()
    provider = SlowRetriever(
        {
            "id": "cs_pg_resolve",
            "object": "checkout.session",
            "livemode": False,
            "mode": "payment",
            "customer": f"cus_{buyer.id}",
            "payment_intent": "pi_pg_resolve",
            "payment_status": "paid",
            "amount_total": 600,
            "currency": "usd",
            "metadata": {"user_id": str(buyer.id), "credits": "30", "purchase_type": "one_time"},
        }
    )
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    errors: list[BaseException] = []

    def resolve() -> None:
        session = migrated_db()
        try:
            barrier.wait(timeout=10)
            outcome = resolve_unresolved_event(
                session,
                "evt_pg_resolve",
                provider=provider,
                app_settings=SETTINGS,
                actor_user_id=admin.id,
                actor_role="Admin",
                reason="provider shows it paid",
            )
            session.commit()
            outcomes.append(outcome.record.status)
        except InvalidEventTransitionError as exc:
            session.rollback()
            outcomes.append(f"refused:{exc}")
        except BaseException as exc:  # pragma: no cover - surfaced below
            session.rollback()
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=resolve) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert sorted(outcomes) == ["processed", "refused:processed"]
    assert provider.calls == 1
    db_session.expire_all()
    purchases = db_session.query(CanonicalCreditLedgerEntryRecord).filter_by(entry_type="purchase")
    assert purchases.count() == 1
    assert credit_balance(db_session, buyer.id) == 30
    assert db_session.query(CanonicalAdminAuditEventRecord).count() == 1
    assert db_session.get(StripeEventRecordModel, "evt_pg_resolve").status == "processed"
