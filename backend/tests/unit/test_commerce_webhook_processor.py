"""Spec 004 T045: the webhook processor leaves every event in a final disposition.

FR-011, FR-014, research R1: dispatch by type in the webhook transaction; ``processed``,
``duplicate``, ``unresolved`` (with a reason code) or ``ignored``; ``processed_at`` set.
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
from canon.webhook_events import EventDisposition, UnresolvedEventError
from community.models import User

TS = 1_700_000_000
SECRET = "whsec_processor"


def _payload(event_id: str, event_type: str, *, data: object = None) -> bytes:
    event: dict = {"id": event_id, "type": event_type, "livemode": False}
    if data is not None:
        event["data"] = data
    return json.dumps(event).encode()


def _receive(session: Session, payload: bytes):
    signature = hmac.new(SECRET.encode(), f"{TS}.".encode() + payload, hashlib.sha256).hexdigest()
    return receive_stripe_webhook(
        session,
        payload=payload,
        signature_header=f"t={TS},v1={signature}",
        secret=SECRET,
        now=TS,
    )


def _user(session: Session) -> User:
    user = User(
        username="buyer",
        email="buyer@example.com",
        password_hash="hashed",
        referral_code="buyercode",
        role="User",
        display_name="buyer",
    )
    session.add(user)
    session.commit()
    return user


def _grant_writer(user_id: int, disposition: EventDisposition | None = None, *, error=None):
    calls: list[str] = []

    def handler(session: Session, event: dict) -> EventDisposition:
        calls.append(event["id"])
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
        if error is not None:
            raise error
        return disposition or EventDisposition("processed")

    handler.calls = calls  # type: ignore[attr-defined]
    return handler


def _ledger_count(session: Session) -> int:
    return session.query(CanonicalCreditLedgerEntryRecord).count()


def test_an_event_type_with_no_handler_is_ignored(db_session: Session) -> None:
    intake = _receive(db_session, _payload("evt_ignored", "charge.succeeded"))
    db_session.commit()

    record = db_session.get(StripeEventRecordModel, "evt_ignored")
    assert intake.duplicate is False
    assert record.status == "ignored"
    assert record.reason_code is None
    assert record.processed_at is not None


@pytest.mark.parametrize(
    "event_type",
    [
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ],
)
def test_a_payment_event_with_no_machine_yet_is_unresolved_and_grants_nothing(
    db_session: Session, event_type: str
) -> None:
    """Fail closed (FR-014) until Machines B and C (T046, T049) exist."""
    _receive(db_session, _payload("evt_pay", event_type, data={"object": {"id": "cs_1"}}))
    db_session.commit()

    record = db_session.get(StripeEventRecordModel, "evt_pay")
    assert record.status == "unresolved"
    assert record.reason_code == "HANDLER_NOT_IMPLEMENTED"
    assert record.processed_at is not None
    assert _ledger_count(db_session) == 0


@pytest.mark.parametrize("data", [None, "not-an-object", {"object": None}, {"object": []}])
def test_a_handled_event_without_a_data_object_is_unresolved(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, data
) -> None:
    user = _user(db_session)
    handler = _grant_writer(user.id)
    monkeypatch.setitem(webhook_events.EVENT_HANDLERS, "test.handled", handler)

    _receive(db_session, _payload("evt_bad", "test.handled", data=data))
    db_session.commit()

    record = db_session.get(StripeEventRecordModel, "evt_bad")
    assert record.status == "unresolved"
    assert record.reason_code == "EVENT_PAYLOAD_MALFORMED"
    assert handler.calls == []
    assert _ledger_count(db_session) == 0


def test_a_handler_that_applies_the_event_marks_it_processed_and_keeps_its_writes(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _user(db_session)
    monkeypatch.setitem(webhook_events.EVENT_HANDLERS, "test.handled", _grant_writer(user.id))

    _receive(db_session, _payload("evt_ok", "test.handled", data={"object": {}}))
    db_session.commit()

    record = db_session.get(StripeEventRecordModel, "evt_ok")
    assert record.status == "processed"
    assert record.reason_code is None
    assert record.processed_at is not None
    assert _ledger_count(db_session) == 1


def test_a_handler_can_report_a_duplicate_effect(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new event id carrying an effect already applied (FR-012) is ``duplicate``."""
    monkeypatch.setitem(
        webhook_events.EVENT_HANDLERS,
        "test.handled",
        lambda _session, _event: EventDisposition("duplicate", "PAYMENT_ALREADY_RECORDED"),
    )

    _receive(db_session, _payload("evt_dup", "test.handled", data={"object": {}}))
    db_session.commit()

    record = db_session.get(StripeEventRecordModel, "evt_dup")
    assert record.status == "duplicate"
    assert record.reason_code == "PAYMENT_ALREADY_RECORDED"
    assert record.processed_at is not None


@pytest.mark.parametrize(
    "make_handler",
    [
        lambda uid: _grant_writer(uid, error=UnresolvedEventError("CUSTOMER_NOT_FOUND")),
        lambda uid: _grant_writer(uid, EventDisposition("unresolved", "CUSTOMER_NOT_FOUND")),
    ],
    ids=["raised", "returned"],
)
def test_an_unresolved_outcome_rolls_back_the_handler_writes(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, make_handler
) -> None:
    user = _user(db_session)
    monkeypatch.setitem(webhook_events.EVENT_HANDLERS, "test.handled", make_handler(user.id))

    _receive(db_session, _payload("evt_unres", "test.handled", data={"object": {}}))
    db_session.commit()

    record = db_session.get(StripeEventRecordModel, "evt_unres")
    assert record.status == "unresolved"
    assert record.reason_code == "CUSTOMER_NOT_FOUND"
    assert record.processed_at is not None
    assert _ledger_count(db_session) == 0


def test_an_unexpected_handler_error_propagates_so_the_delivery_rolls_back(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _user(db_session)
    monkeypatch.setitem(
        webhook_events.EVENT_HANDLERS,
        "test.handled",
        _grant_writer(user.id, error=RuntimeError("boom")),
    )

    with pytest.raises(RuntimeError, match="boom"):
        _receive(db_session, _payload("evt_err", "test.handled", data={"object": {}}))
    db_session.rollback()

    # The handler's savepoint is rolled back. That the event row goes with the outer
    # rollback needs real transactions: tests/acceptance/test_webhook_processor_postgres.py.
    assert _ledger_count(db_session) == 0


@pytest.mark.parametrize(
    "disposition",
    [EventDisposition("received"), EventDisposition("unresolved")],  # type: ignore[arg-type]
    ids=["not-final", "no-reason"],
)
def test_a_handler_cannot_leave_an_event_received_or_unresolved_without_a_reason(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, disposition: EventDisposition
) -> None:
    monkeypatch.setitem(
        webhook_events.EVENT_HANDLERS, "test.handled", lambda _session, _event: disposition
    )

    with pytest.raises(ValueError):
        _receive(db_session, _payload("evt_inv", "test.handled", data={"object": {}}))


def test_a_redelivered_event_keeps_its_disposition_and_is_not_reprocessed(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _user(db_session)
    handler = _grant_writer(user.id)
    monkeypatch.setitem(webhook_events.EVENT_HANDLERS, "test.handled", handler)
    payload = _payload("evt_once", "test.handled", data={"object": {}})

    _receive(db_session, payload)
    db_session.commit()
    processed_at = db_session.get(StripeEventRecordModel, "evt_once").processed_at
    again = _receive(db_session, payload)
    db_session.commit()

    assert again.duplicate is True
    assert again.record.status == "processed"
    assert again.record.processed_at == processed_at
    assert handler.calls == ["evt_once"]
    assert _ledger_count(db_session) == 1


def test_no_stored_event_is_left_received(db_session: Session) -> None:
    for index, event_type in enumerate(["charge.succeeded", "checkout.session.completed"]):
        _receive(db_session, _payload(f"evt_{index}", event_type, data={"object": {}}))
    db_session.commit()

    statuses = {row.status for row in db_session.query(StripeEventRecordModel).all()}
    assert statuses == {"ignored", "unresolved"}
