"""Spec 004 T050 on Postgres: the STUDIO fair-use cap holds under concurrent spends.

SQLite cannot show this: it has no advisory lock, so two exports racing for the last
slot are only serialized on Postgres (``pg_advisory_xact_lock`` in ``request_export``).
The migration's refusing downgrade is checked here too, on the real schema.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

import canon.exports as exports
from canon.contracts import ExportRequest
from canon.exports import ExportBoundaryError, credit_balance, request_export
from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    CanonicalExportRecord,
    GenerationRunRecord,
    ProviderSubscriptionRecord,
    RigRevisionRecord,
    SubscriptionPeriodGrantRecord,
)
from cases.models import Case
from community.models import User
from racks.models import Rack

NOW = datetime.now(timezone.utc)


def _export_sources(db_session: Session) -> User:
    """The user, rig revision and run an export points at, flushed in FK order."""

    user = User(username="pg-studio", email="pg-studio@example.com", password_hash="hash")
    case = Case(
        brand="PatchHive", name="Test Case", total_hp=84, rows=1, hp_per_row=[84], source="test"
    )
    db_session.add_all((user, case))
    db_session.flush()
    rack = Rack(user_id=user.id, case_id=case.id, name="Canon Rig")
    db_session.add(rack)
    db_session.flush()
    db_session.add(
        RigRevisionRecord(
            id="rig-rev-1",
            rig_id=rack.id,
            schema_version="patchhive.canon.v1",
            canonical_rig={"modules": []},
            canonical_hash="a" * 64,
        )
    )
    db_session.flush()
    db_session.add(
        GenerationRunRecord(
            id="run-1",
            user_id=user.id,
            rig_revision_id="rig-rev-1",
            schema_version="patchhive.canon.v1",
            generator_version="1.0.0",
            generation_seed=7,
            normalized_input_hash="b" * 64,
        )
    )
    db_session.flush()
    return user


def _studio(db_session: Session, *, cap: int, credits: int = 0) -> int:
    user = _export_sources(db_session)
    record = ProviderSubscriptionRecord(
        id="subrec-pg-studio",
        user_id=user.id,
        provider_subscription_id="sub_pg_studio",
        provider_customer_id=f"cus_{user.id}",
        price_id="price_pg_studio",
        tier="studio",
        status="active",
        current_period_start=NOW - timedelta(days=1),
        current_period_end=NOW + timedelta(days=29),
        cancel_at_period_end=False,
        created_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(days=1),
    )
    db_session.add(record)
    db_session.flush()
    db_session.add(
        SubscriptionPeriodGrantRecord(
            id="subgrant-pg-studio",
            subscription_record_id=record.id,
            user_id=user.id,
            grant_key="subscription-period:sub_pg_studio:1",
            provider_invoice_id="in_pg_studio",
            tier="studio",
            period_start=NOW - timedelta(days=1),
            period_end=NOW + timedelta(days=29),
            credits=0,
            unlimited=True,
            fair_use_export_cap=cap,
            ledger_entry_id=None,
            created_at=NOW - timedelta(days=1),
        )
    )
    if credits:
        db_session.add(
            CanonicalCreditLedgerEntryRecord(
                id="grant-pg-studio",
                user_id=user.id,
                delta=credits,
                entry_type="grant",
                idempotency_key="grant-pg-studio",
                created_at=NOW,
            )
        )
    db_session.commit()
    return user.id


def _request(user_id: int, key: str) -> ExportRequest:
    return ExportRequest(
        request_id=key,
        user_id=user_id,
        source_run_id="run-1",
        source_rig_revision_id="rig-rev-1",
        formats=("pdf",),
        license="personal",
        credit_cost=3,
        idempotency_key=key,
        requested_at=datetime.now(timezone.utc),
    )


def _spend(session: Session, user_id: int, key: str) -> CanonicalExportRecord:
    export = request_export(
        session, _request(user_id, key), artifact_manifest_hash="a" * 64, export_version="1.0.0"
    )
    session.commit()
    return export


def _spend_concurrently(migrated_db: sessionmaker, user_id: int, keys: list[str]) -> list[str]:
    barrier = threading.Barrier(len(keys))
    outcomes: list[str] = []
    errors: list[BaseException] = []

    def spend(key: str) -> None:
        session = migrated_db()
        try:
            barrier.wait(timeout=10)
            _spend(session, user_id, key)
            outcomes.append("created")
        except ExportBoundaryError as exc:
            session.rollback()
            outcomes.append(str(exc))
        except BaseException as exc:  # pragma: no cover - surfaced below
            session.rollback()
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=spend, args=(key,)) for key in keys]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert errors == []
    return sorted(outcomes)


def test_two_concurrent_spends_for_the_last_slot_take_it_once(
    migrated_db: sessionmaker, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _studio(db_session, cap=2, credits=10)
    _spend(db_session, user_id, "studio-first")
    # Hold each spend between its count and its insert, so without the per-user lock
    # both would count one covered export and both take the last slot.
    count = exports._fair_use_exports

    def slow_count(session: Session, grant_id: str) -> int:
        seen = count(session, grant_id)
        threading.Event().wait(0.5)
        return seen

    monkeypatch.setattr(exports, "_fair_use_exports", slow_count)

    outcomes = _spend_concurrently(migrated_db, user_id, ["studio-a", "studio-b"])

    assert outcomes == ["FAIR_USE_CAP_REACHED", "created"]
    db_session.expire_all()
    covered = db_session.query(CanonicalExportRecord).filter_by(
        subscription_grant_id="subgrant-pg-studio"
    )
    assert covered.count() == 2
    # The cap never falls through to the ledger.
    assert credit_balance(db_session, user_id) == 10


def test_concurrent_spends_on_an_open_cap_all_succeed_without_debits(
    migrated_db: sessionmaker, db_session: Session
) -> None:
    user_id = _studio(db_session, cap=5)

    outcomes = _spend_concurrently(migrated_db, user_id, ["studio-x", "studio-y", "studio-z"])

    assert outcomes == ["created", "created", "created"]
    db_session.expire_all()
    assert db_session.query(CanonicalCreditLedgerEntryRecord).count() == 0


def test_a_covered_export_with_a_debit_is_refused_by_the_schema(db_session: Session) -> None:
    user_id = _studio(db_session, cap=1)
    with pytest.raises(Exception, match="ck_canonical_exports_grant_shape"):
        db_session.execute(
            text(
                "INSERT INTO canonical_exports (id, user_id, source_run_id, "
                "source_rig_revision_id, artifact_manifest_hash, export_version, license, "
                "credit_cost, idempotency_key, status, created_at, fulfill_attempts, "
                "subscription_grant_id) VALUES ('export-bad', :user_id, 'run-1', 'rig-rev-1', "
                ":hash, '1.0.0', 'personal', 3, 'bad-shape', 'queued', now(), 0, "
                "'subgrant-pg-studio')"
            ),
            {"user_id": user_id, "hash": "a" * 64},
        )
    db_session.rollback()


def _alembic(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_the_migration_refuses_to_downgrade_with_covered_exports_and_round_trips(
    migrated_db: sessionmaker, db_session: Session, database_url: str
) -> None:
    config = _alembic(database_url)
    user_id = _studio(db_session, cap=1)
    _spend(db_session, user_id, "studio-mig")
    db_session.close()
    # The per-test truncation empties alembic_version too; the schema is at head.
    command.stamp(config, "head")

    with pytest.raises(RuntimeError, match="refusing to downgrade 20261102_export_fair_use"):
        command.downgrade(config, "20261102_subscriptions")

    engine = migrated_db.kw["bind"]
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM canonical_exports"))
    command.downgrade(config, "20261102_subscriptions")
    try:
        with engine.connect() as conn:
            columns = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'canonical_exports'"
                    )
                )
            }
        assert "subscription_grant_id" not in columns
    finally:
        command.upgrade(config, "head")
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "20261102_export_fair_use"
