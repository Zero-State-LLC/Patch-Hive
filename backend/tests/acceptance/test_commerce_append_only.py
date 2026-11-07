"""Spec 004 FR-008, FR-021 and FR-029 on Postgres: T001 D5 and D6.

The legacy ledgers, the referral rows and the subscription period grants reject ``UPDATE`` and
``DELETE``, and a referral code can change only while it's empty or as its account is deleted.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from account.deletion import anonymize_user
from account.models import CreditLedgerEntry
from account.services import ensure_referral_code
from canon.models import ProviderSubscriptionRecord, SubscriptionPeriodGrantRecord
from community.models import User
from monetization.models import CreditsLedger, Referral
from monetization.referrals import create_referral, record_purchase

NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


@pytest.fixture()
def rows(db_session: Session, create_user) -> SimpleNamespace:
    owner = create_user("guard-owner", "guard-pass")
    referred = create_user("guard-referred", "guard-pass")
    ledger = CreditsLedger(user_id=owner.id, change_type="Grant", credits_delta=5)
    entry = CreditLedgerEntry(user_id=owner.id, entry_type="Grant", amount=5)
    referral = Referral(referrer_user_id=owner.id, referred_user_id=referred.id, status="Pending")
    subscription = ProviderSubscriptionRecord(
        id="sub-guard",
        user_id=owner.id,
        provider_subscription_id="sub_guard",
        provider_customer_id="cus_guard",
        price_id="price_guard",
        tier="core",
        status="active",
        current_period_start=NOW,
        current_period_end=NOW + timedelta(days=30),
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add_all([ledger, entry, referral, subscription])
    db_session.flush()
    grant = SubscriptionPeriodGrantRecord(
        id="subgrant-guard",
        subscription_record_id=subscription.id,
        user_id=owner.id,
        grant_key="subscription-period:sub_guard:1",
        provider_invoice_id="in_guard",
        tier="studio",
        period_start=NOW,
        period_end=NOW + timedelta(days=30),
        credits=0,
        unlimited=True,
        fair_use_export_cap=100,
        created_at=NOW,
    )
    db_session.add(grant)
    db_session.commit()
    return SimpleNamespace(owner_id=owner.id, referred_id=referred.id)


@pytest.mark.parametrize(
    "table, update",
    [
        ("credits_ledger", "credits_delta = 500"),
        ("credit_ledger_entries", "amount = 500"),
        ("referrals", "status = 'Rewarded'"),
        ("subscription_period_grants", "credits = 500"),
    ],
)
@pytest.mark.parametrize("verb", ["UPDATE", "DELETE"])
def test_these_rows_are_append_only(
    db_session: Session, rows: SimpleNamespace, table: str, update: str, verb: str
) -> None:
    before = db_session.execute(text(f"SELECT * FROM {table}")).fetchall()
    statement = f"UPDATE {table} SET {update}" if verb == "UPDATE" else f"DELETE FROM {table}"

    with pytest.raises(DBAPIError, match=f"{table} is append-only"):
        db_session.execute(text(statement))
    db_session.rollback()

    assert db_session.execute(text(f"SELECT * FROM {table}")).fetchall() == before


def test_a_user_with_ledger_rows_cannot_be_hard_deleted(
    db_session: Session, rows: SimpleNamespace
) -> None:
    """The cascades reach the triggers too. Account deletion anonymizes instead (OQ-12)."""
    with pytest.raises(DBAPIError, match="is append-only"):
        db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": rows.owner_id})
    db_session.rollback()
    assert db_session.get(User, rows.owner_id) is not None


def test_a_reward_still_appends_on_top_of_the_pending_row(
    db_session: Session, create_user
) -> None:
    referrer = create_user("guard-referrer", "guard-pass")
    buyer = create_user("guard-buyer", "guard-pass")
    create_referral(db_session, referrer=referrer, referred=buyer)
    db_session.commit()

    record_purchase(db_session, user=buyer, credits_delta=5, payment_verified=True)
    db_session.commit()

    statuses = [
        row.status
        for row in db_session.query(Referral).filter_by(referred_user_id=buyer.id).order_by(Referral.id)
    ]
    assert statuses == ["Pending", "Rewarded"]


def test_a_referral_code_cannot_change(db_session: Session, create_user) -> None:
    user = create_user("guard-code", "guard-pass")
    code = user.referral_code
    user.referral_code = "A-NEW-CODE"

    with pytest.raises(DBAPIError, match="users.referral_code is immutable"):
        db_session.commit()
    db_session.rollback()

    assert db_session.get(User, user.id).referral_code == code


def test_a_deleted_accounts_code_cannot_change_again(db_session: Session, create_user) -> None:
    """The code changes only in the update that deletes the account, not afterwards."""
    user = create_user("guard-later", "guard-pass")
    user_id = user.id
    anonymize_user(db_session, user)
    db_session.commit()
    code = db_session.get(User, user_id).referral_code

    with pytest.raises(DBAPIError, match="users.referral_code is immutable"):
        db_session.execute(
            text("UPDATE users SET referral_code = 'AFTER-DELETE' WHERE id = :id"), {"id": user_id}
        )
    db_session.rollback()

    assert db_session.get(User, user_id).referral_code == code


def test_account_deletion_replaces_the_code_so_the_old_one_stops_resolving(
    db_session: Session, create_user
) -> None:
    user = create_user("guard-leaver", "guard-pass")
    user_id, old_code = user.id, user.referral_code

    anonymize_user(db_session, user)
    db_session.commit()

    stored = db_session.get(User, user_id)
    assert stored.deleted_at is not None
    assert stored.referral_code != old_code
    assert db_session.query(User).filter_by(referral_code=old_code).first() is None


def test_an_empty_code_can_still_be_filled(db_session: Session, create_user) -> None:
    user = create_user("guard-empty", "guard-pass")
    db_session.execute(text("ALTER TABLE users DISABLE TRIGGER trg_users_keep_referral_code"))
    db_session.execute(text("UPDATE users SET referral_code = '' WHERE id = :id"), {"id": user.id})
    db_session.execute(text("ALTER TABLE users ENABLE TRIGGER trg_users_keep_referral_code"))
    db_session.commit()
    db_session.refresh(user)

    code = ensure_referral_code(db_session, user)

    assert code
    assert db_session.get(User, user.id).referral_code == code


def test_other_columns_of_a_user_still_update(db_session: Session, create_user) -> None:
    user = create_user("guard-profile", "guard-pass")
    user.display_name = "New name"
    db_session.commit()
    assert db_session.get(User, user.id).display_name == "New name"


def _triggers(engine) -> set[str]:
    with engine.connect() as conn:
        return {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname LIKE ANY "
                    "(ARRAY['trg_credits_ledger_%', 'trg_credit_ledger_entries_%', "
                    "'trg_referrals_%', 'trg_subscription_period_grants_%', "
                    "'trg_users_keep_referral_code'])"
                )
            )
        }


def test_the_migration_round_trips(migrated_db: sessionmaker, database_url: str) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    engine = migrated_db.kw["bind"]
    # The per-test truncation empties alembic_version too; the schema is at head.
    command.stamp(config, "head")
    assert len(_triggers(engine)) == 9

    command.downgrade(config, "20261106_catalog_load_runs")
    try:
        assert _triggers(engine) == set()
    finally:
        command.upgrade(config, "head")

    assert len(_triggers(engine)) == 9
