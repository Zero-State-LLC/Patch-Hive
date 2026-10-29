"""Spec 004 T045 on Postgres: a failed processing step rolls back the whole delivery.

SQLite's driver commits a released savepoint opened outside a transaction, so these
checks need real transactions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

import canon.webhook_events as webhook_events
from canon.exports import receive_stripe_webhook
from canon.models import CanonicalCreditLedgerEntryRecord, StripeEventRecordModel
from canon.webhook_events import EventDisposition

TS = 1_700_000_000
SECRET = "whsec_processor_pg"


def _receive(session: Session, event_id: str, event_type: str):
    payload = json.dumps(
        {"id": event_id, "type": event_type, "livemode": False, "data": {"object": {}}}
    ).encode()
    signature = hmac.new(SECRET.encode(), f"{TS}.".encode() + payload, hashlib.sha256).hexdigest()
    return receive_stripe_webhook(
        session,
        payload=payload,
        signature_header=f"t={TS},v1={signature}",
        secret=SECRET,
        now=TS,
    )


def _writes_a_grant_then(user_id: int, outcome):
    def handler(session: Session, event: dict) -> EventDisposition:
        session.add(
            CanonicalCreditLedgerEntryRecord(
                id=f"grant-{event['id']}",
                user_id=user_id,
                delta=5,
                entry_type="grant",
                idempotency_key=f"test:{event['id']}",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.flush()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return handler


@pytest.mark.parametrize(
    "outcome,error",
    [
        (RuntimeError("boom"), RuntimeError),
        (EventDisposition("received"), ValueError),  # type: ignore[arg-type]
        (EventDisposition("unresolved"), ValueError),
    ],
    ids=["handler-error", "not-final", "no-reason"],
)
def test_a_failed_processing_step_leaves_no_event_and_no_grant(
    db_session: Session, create_user, monkeypatch: pytest.MonkeyPatch, outcome, error
) -> None:
    user = create_user("pg-buyer", "pg-pass")
    monkeypatch.setitem(
        webhook_events.EVENT_HANDLERS, "test.handled", _writes_a_grant_then(user.id, outcome)
    )

    with pytest.raises(error):
        _receive(db_session, "evt_pg_fail", "test.handled")
    db_session.rollback()

    assert db_session.get(StripeEventRecordModel, "evt_pg_fail") is None
    assert db_session.query(CanonicalCreditLedgerEntryRecord).count() == 0


def test_an_unresolved_event_commits_with_its_reason_and_no_grant(
    db_session: Session, create_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = create_user("pg-buyer2", "pg-pass")
    monkeypatch.setitem(
        webhook_events.EVENT_HANDLERS,
        "test.handled",
        _writes_a_grant_then(user.id, EventDisposition("unresolved", "CUSTOMER_NOT_FOUND")),
    )

    _receive(db_session, "evt_pg_unres", "test.handled")
    db_session.commit()

    record = db_session.get(StripeEventRecordModel, "evt_pg_unres")
    assert (record.status, record.reason_code) == ("unresolved", "CUSTOMER_NOT_FOUND")
    assert record.processed_at is not None
    assert db_session.query(CanonicalCreditLedgerEntryRecord).count() == 0
