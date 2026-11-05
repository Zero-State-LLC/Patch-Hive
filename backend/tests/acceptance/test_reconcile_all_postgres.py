"""`python -m canon.reconcile_all` on Postgres: read-only transaction, exit code by result."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from canon.models import CanonicalCreditLedgerEntryRecord

NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)


@pytest.fixture()
def granted_user(db_session: Session, create_user):
    user = create_user("reconcile-owner", "reconcile-pass")
    db_session.add(
        CanonicalCreditLedgerEntryRecord(
            id="grant-reconcile",
            user_id=user.id,
            delta=5,
            entry_type="grant",
            idempotency_key="grant:reconcile",
            created_at=NOW,
        )
    )
    db_session.commit()
    return user


def test_the_reconcile_transaction_is_read_only(db_session: Session, granted_user) -> None:
    import canon.reconcile_all as reconcile_cli

    report = reconcile_cli.run(db_session)
    assert report["status"] == "ok" and report["balance_total"] == 5

    with pytest.raises(DBAPIError, match="read-only transaction"):
        db_session.execute(text("UPDATE users SET display_name = 'changed'"))
    db_session.rollback()


def test_main_reports_ok_against_postgres(
    migrated_db: sessionmaker, granted_user, monkeypatch, capsys
) -> None:
    import canon.reconcile_all as reconcile_cli
    import core.database

    monkeypatch.setattr(core.database, "SessionLocal", migrated_db)

    assert reconcile_cli.main([]) == 0
    report = json.loads(capsys.readouterr().out.strip())
    assert report["users_checked"] == 1 and report["ledger_entries"] == 1
    assert "reconcile-owner" not in json.dumps(report)
