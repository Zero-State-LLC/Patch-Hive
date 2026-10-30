"""Spec 004 T042 on Postgres: canonical ledger rows cannot be updated or deleted (FR-008)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from canon.models import CanonicalCreditLedgerEntryRecord

NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)


@pytest.fixture()
def ledger_entry(db_session: Session, create_user) -> CanonicalCreditLedgerEntryRecord:
    user = create_user("ledger-owner", "ledger-pass")
    entry = CanonicalCreditLedgerEntryRecord(
        id="grant-append-only",
        user_id=user.id,
        delta=5,
        entry_type="grant",
        idempotency_key="grant:append-only",
        created_at=NOW,
    )
    db_session.add(entry)
    db_session.commit()
    return entry


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE canonical_credit_ledger SET delta = 500 WHERE id = 'grant-append-only'",
        "DELETE FROM canonical_credit_ledger WHERE id = 'grant-append-only'",
    ],
)
def test_ledger_rows_are_append_only(db_session: Session, ledger_entry, statement: str) -> None:
    with pytest.raises(DBAPIError, match="canonical_credit_ledger is append-only"):
        db_session.execute(text(statement))
    db_session.rollback()
    assert db_session.scalar(
        text("SELECT delta FROM canonical_credit_ledger WHERE id = 'grant-append-only'")
    ) == 5


def test_a_correction_is_a_new_row(db_session: Session, ledger_entry) -> None:
    db_session.add(
        CanonicalCreditLedgerEntryRecord(
            id="reversal-append-only",
            user_id=ledger_entry.user_id,
            delta=-5,
            entry_type="reversal",
            idempotency_key="reversal:append-only",
            created_at=NOW,
        )
    )
    db_session.commit()
    assert db_session.scalar(
        text("SELECT SUM(delta) FROM canonical_credit_ledger WHERE user_id = :u"),
        {"u": ledger_entry.user_id},
    ) == 0
