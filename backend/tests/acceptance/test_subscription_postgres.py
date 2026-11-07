"""Spec 004 T049 on Postgres: Machine C grants once per period, in one transaction.

SQLite cannot show these properties: it ignores ``FOR UPDATE`` and does not block a
concurrent insert on a unique key. The migration's refusing downgrade is checked here
too, on the real schema.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

import canon.subscriptions as subscriptions
import core.config as core_config
from canon.exports import credit_balance, receive_stripe_webhook
from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderSubscriptionRecord,
    StripeEventRecordModel,
    SubscriptionCheckoutRecord,
    SubscriptionPeriodGrantRecord,
)
from monetization.models import CreditsLedger, Referral
from monetization.referrals import REFERRAL_REWARD_CREDITS, create_referral

TS = 1_700_000_000
SECRET = "whsec_machine_c_pg"
P1 = 1_730_000_000
MONTH = 30 * 86_400
PRICE_CORE = "price_pg_core"


@pytest.fixture(autouse=True)
def _prices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        core_config,
        "settings",
        SimpleNamespace(
            subscription_price_id_core=PRICE_CORE,
            subscription_price_id_pro="price_pg_pro",
            subscription_price_id_studio="price_pg_studio",
            subscription_credits_core=25,
            subscription_credits_pro=100,
            subscription_studio_fair_use_exports_per_period=100,
        ),
    )


def _customer(session: Session, user_id: int) -> None:
    session.add(
        ProviderCustomerRecord(
            user_id=user_id,
            provider_customer_id=f"cus_{user_id}",
            created_at=datetime.now(timezone.utc),
        )
    )
    session.commit()


def _invoice_payload(event_id: str, user_id: int, invoice_id: str = "in_pg") -> bytes:
    obj = {
        "id": invoice_id,
        "object": "invoice",
        "customer": f"cus_{user_id}",
        "subscription": "sub_pg",
        "status": "paid",
        "amount_paid": 499,
        "currency": "usd",
        "lines": {
            "data": [{"price": {"id": PRICE_CORE}, "period": {"start": P1, "end": P1 + MONTH}}]
        },
    }
    return json.dumps(
        {
            "id": event_id,
            "type": "invoice.paid",
            "created": TS,
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


def _deliver_concurrently(migrated_db: sessionmaker, payloads: list[bytes]) -> list[str]:
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


def _assert_granted_once(db_session: Session, user_id: int) -> None:
    db_session.expire_all()
    assert db_session.query(ProviderSubscriptionRecord).count() == 1
    assert db_session.query(SubscriptionPeriodGrantRecord).count() == 1
    grants = db_session.query(CanonicalCreditLedgerEntryRecord).filter_by(
        user_id=user_id, entry_type="grant"
    )
    assert grants.count() == 1
    assert credit_balance(db_session, user_id) == 25
    assert db_session.query(CreditsLedger).filter_by(change_type="Purchase").count() == 1


def test_concurrent_invoice_deliveries_for_one_period_grant_once_and_reward_once(
    migrated_db: sessionmaker, db_session: Session, create_user
) -> None:
    """Two event ids for one paid invoice, at once, before any subscription event (EC-2):
    both race to create the record, then on the period grant (FR-016, SC-005)."""
    referrer = create_user("pg-mc-referrer", "pg-pass")
    user = create_user("pg-mc-buyer", "pg-pass")
    create_referral(db_session, referrer=referrer, referred=user)
    db_session.commit()
    _customer(db_session, user.id)

    statuses = _deliver_concurrently(
        migrated_db,
        [_invoice_payload("evt_pg_c_a", user.id), _invoice_payload("evt_pg_c_b", user.id)],
    )

    assert statuses == ["duplicate", "processed"]
    _assert_granted_once(db_session, user.id)
    # OQ-3 ``A_both``: the first paid invoice wrote exactly one referral reward.
    assert db_session.query(Referral).filter_by(status="Rewarded").count() == 1
    assert credit_balance(db_session, referrer.id) == REFERRAL_REWARD_CREDITS


def test_concurrent_deliveries_of_one_event_and_a_duplicate_invoice_grant_once(
    migrated_db: sessionmaker, db_session: Session, create_user
) -> None:
    user = create_user("pg-mc-buyer2", "pg-pass")
    _customer(db_session, user.id)
    same = _invoice_payload("evt_pg_c_same", user.id)

    _deliver_concurrently(
        migrated_db,
        [same, same, _invoice_payload("evt_pg_c_other", user.id, invoice_id="in_pg_2")],
    )

    # One event record per event id: the repeated id is an intake duplicate, and of the
    # two ids exactly one granted the period.
    db_session.expire_all()
    records = db_session.query(StripeEventRecordModel).all()
    assert sorted(r.stripe_event_id for r in records) == ["evt_pg_c_other", "evt_pg_c_same"]
    assert sorted(r.status for r in records) == ["duplicate", "processed"]
    (duplicate,) = [r for r in records if r.status == "duplicate"]
    assert duplicate.reason_code == "PERIOD_ALREADY_GRANTED"
    _assert_granted_once(db_session, user.id)


def test_a_failure_after_the_grant_rolls_back_the_whole_delivery(
    db_session: Session, create_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = create_user("pg-mc-buyer3", "pg-pass")
    _customer(db_session, user.id)

    def boom(*_args, **_kwargs):
        raise RuntimeError("referral evaluation failed")

    monkeypatch.setattr(subscriptions, "record_purchase", boom)
    with pytest.raises(RuntimeError):
        _receive(db_session, _invoice_payload("evt_pg_c_fail", user.id))
    db_session.rollback()

    assert db_session.get(StripeEventRecordModel, "evt_pg_c_fail") is None
    assert db_session.query(ProviderSubscriptionRecord).count() == 0
    assert db_session.query(SubscriptionPeriodGrantRecord).count() == 0
    assert db_session.query(CanonicalCreditLedgerEntryRecord).count() == 0


class _SlowProvider:
    """Fake provider; the session call is slow so overlapping requests really overlap."""

    def __init__(self) -> None:
        self.sessions = 0
        self._lock = threading.Lock()

    def create_customer(self, *, user_id: int, idempotency_key: str) -> str:
        return f"cus_{user_id}"

    def create_subscription_checkout_session(self, **_kwargs):
        from canon.checkout import ProviderCheckoutSession

        with self._lock:
            self.sessions += 1
            index = self.sessions
        threading.Event().wait(0.3)
        return ProviderCheckoutSession(id=f"cs_pg_sub_{index}", url=f"https://co.test/{index}")


def test_concurrent_checkout_requests_open_one_subscription_checkout(
    migrated_db: sessionmaker, db_session: Session, create_user
) -> None:
    """Codex P1 on #219: two requests before either session is paid must not open two
    independently billed subscriptions."""
    from tests.unit.test_commerce_subscriptions import _c_settings

    user = create_user("pg-mc-buyer5", "pg-pass")
    _customer(db_session, user.id)
    provider = _SlowProvider()
    barrier = threading.Barrier(2)
    urls: list[str] = []
    errors: list[BaseException] = []

    def request() -> None:
        session = migrated_db()
        try:
            from community.models import User

            me = session.get(User, user.id)
            barrier.wait(timeout=10)
            started = subscriptions.start_subscription_checkout(
                session, user=me, tier="pro", provider=provider, app_settings=_c_settings()
            )
            session.commit()
            urls.append(started.checkout_url)
        except BaseException as exc:  # pragma: no cover - surfaced below
            session.rollback()
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=request) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert provider.sessions == 1
    assert len(urls) == 2 and len(set(urls)) == 1
    db_session.expire_all()
    assert db_session.query(SubscriptionCheckoutRecord).count() == 1


def _alembic(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_the_migration_refuses_to_downgrade_with_rows_and_round_trips_empty(
    migrated_db: sessionmaker, db_session: Session, database_url: str, create_user
) -> None:
    config = _alembic(database_url)
    user = create_user("pg-mc-buyer4", "pg-pass")
    _customer(db_session, user.id)
    _receive(db_session, _invoice_payload("evt_pg_c_mig", user.id))
    db_session.commit()
    db_session.close()
    # The per-test truncation empties alembic_version too; the schema is at head.
    command.stamp(config, "head")

    with pytest.raises(RuntimeError, match="refusing to downgrade 20261102_subscriptions"):
        command.downgrade(config, "20261102_purchase_refunds")

    engine = migrated_db.kw["bind"]
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM subscription_period_grants"))
        conn.execute(text("DELETE FROM provider_subscriptions"))
    command.downgrade(config, "20261102_purchase_refunds")
    try:
        with engine.connect() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                )
            }
        assert "provider_subscriptions" not in tables
        assert "subscription_period_grants" not in tables
    finally:
        command.upgrade(config, "head")
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    # Head is the T050 export fair-use revision, which revises this one.
    assert version == "20261106_catalog_load_runs"
