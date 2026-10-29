"""Spec 004 T040/T041: webhook key rotation, concurrent duplicates, live-mode gate, startup."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session

from canon.contracts import canonical_sha256
from canon.exports import ExportBoundaryError, receive_stripe_webhook, verify_stripe_webhook
from canon.models import StripeEventRecordModel
from core.startup_policy import validate_stripe_mode_startup_policy

TS = 1_700_000_000
SECRET = "whsec_current"
OLD_SECRET = "whsec_retiring"


def _v1(payload: bytes, secret: str, timestamp: int = TS) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()


def _event(event_id: str = "evt_1", *, livemode: bool = False, amount: int = 1) -> bytes:
    return json.dumps(
        {"id": event_id, "type": "payment_intent.succeeded", "livemode": livemode, "amount": amount}
    ).encode()


def _receive(session: Session, payload: bytes, header: str, **kwargs):
    return receive_stripe_webhook(
        session, payload=payload, signature_header=header, secret=SECRET, now=TS, **kwargs
    )


# --- T040: any v1 may match (secret rotation) ---------------------------------------


def test_a_match_on_the_second_v1_value_is_accepted(db_session: Session) -> None:
    payload = _event()
    header = f"t={TS},v1={_v1(payload, OLD_SECRET)},v1={_v1(payload, SECRET)}"
    intake = _receive(db_session, payload, header)
    assert intake.record.stripe_event_id == "evt_1"
    assert intake.duplicate is False


def test_a_match_on_the_first_v1_value_is_accepted(db_session: Session) -> None:
    payload = _event()
    header = f"t={TS},v1={_v1(payload, SECRET)},v1={_v1(payload, OLD_SECRET)}"
    assert _receive(db_session, payload, header).record.stripe_event_id == "evt_1"


@pytest.mark.parametrize(
    "header_for",
    [
        lambda p: f"t={TS},v1={_v1(p, OLD_SECRET)},v1={_v1(p, 'whsec_other')}",
        lambda p: f"t={TS},v0={_v1(p, SECRET)}",
        lambda p: f"t={TS}",
        lambda p: f"v1={_v1(p, SECRET)}",
        lambda p: f"t={TS},t={TS},v1={_v1(p, SECRET)}",
        lambda p: f"t=notanumber,v1={_v1(p, SECRET)}",
    ],
)
def test_no_matching_v1_or_a_malformed_header_is_rejected(db_session: Session, header_for) -> None:
    payload = _event()
    with pytest.raises(ExportBoundaryError, match="WEBHOOK_SIGNATURE_INVALID"):
        _receive(db_session, payload, header_for(payload))
    assert db_session.get(StripeEventRecordModel, "evt_1") is None


def test_the_timestamp_tolerance_still_applies_with_several_v1_values(db_session: Session) -> None:
    payload = _event()
    old = TS - 301
    header = f"t={old},v1={_v1(payload, OLD_SECRET, old)},v1={_v1(payload, SECRET, old)}"
    with pytest.raises(ExportBoundaryError, match="WEBHOOK_SIGNATURE_EXPIRED"):
        _receive(db_session, payload, header)


# --- T040: a concurrent duplicate is a duplicate, not a 500 ---------------------------


def _insert_winner(session: Session, payload: bytes) -> None:
    """Commit the event as a concurrent delivery would, outside this session's identity map."""
    event = json.loads(payload)
    session.execute(
        insert(StripeEventRecordModel.__table__).values(
            stripe_event_id=event["id"],
            event_type=event["type"],
            payload_hash=canonical_sha256(event),
            livemode=False,
            status="received",
            received_at=datetime(2023, 11, 14, tzinfo=timezone.utc),
        )
    )
    session.commit()


def _miss_first_lookup(monkeypatch: pytest.MonkeyPatch, session: Session) -> list[int]:
    """The racing delivery's first lookup ran before the winner committed."""
    real_get = session.get
    calls: list[int] = []

    def racing_get(model, ident, *args, **kwargs):
        calls.append(1)
        if model is StripeEventRecordModel and len(calls) == 1:
            return None
        return real_get(model, ident, *args, **kwargs)

    monkeypatch.setattr(session, "get", racing_get)
    return calls


def test_a_concurrent_duplicate_rolls_back_a_savepoint_and_answers_duplicate(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _event()
    _insert_winner(db_session, payload)
    calls = _miss_first_lookup(monkeypatch, db_session)

    intake = _receive(db_session, payload, f"t={TS},v1={_v1(payload, SECRET)}")

    assert len(calls) == 2  # missed lookup, then the reload after IntegrityError
    assert intake.duplicate is True
    assert intake.record.stripe_event_id == "evt_1"
    # Only the savepoint rolled back: the outer transaction is still usable.
    db_session.commit()
    assert db_session.query(StripeEventRecordModel).count() == 1


def test_a_concurrent_delivery_with_a_different_payload_is_a_replay_conflict(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _insert_winner(db_session, _event(amount=1))
    _miss_first_lookup(monkeypatch, db_session)
    other = _event(amount=2)
    with pytest.raises(ExportBoundaryError, match="WEBHOOK_REPLAY_CONFLICT"):
        _receive(db_session, other, f"t={TS},v1={_v1(other, SECRET)}")


def test_a_sequential_redelivery_answers_duplicate(db_session: Session) -> None:
    payload = _event()
    header = f"t={TS},v1={_v1(payload, SECRET)}"
    assert _receive(db_session, payload, header).duplicate is False
    assert _receive(db_session, payload, header).duplicate is True


# --- T041: live-mode events only in production ------------------------------------------


@pytest.mark.parametrize(
    "test_mode,production",
    [(True, False), (False, False), (True, True)],
)
def test_a_livemode_event_is_rejected_unless_production_without_test_mode(
    db_session: Session, test_mode: bool, production: bool
) -> None:
    payload = _event("evt_live", livemode=True)
    with pytest.raises(ExportBoundaryError, match="LIVEMODE_EVENT_REJECTED"):
        _receive(
            db_session,
            payload,
            f"t={TS},v1={_v1(payload, SECRET)}",
            test_mode=test_mode,
            production=production,
        )
    assert db_session.get(StripeEventRecordModel, "evt_live") is None


def test_the_default_rejects_livemode_even_with_test_mode_off(db_session: Session) -> None:
    payload = _event("evt_live", livemode=True)
    with pytest.raises(ExportBoundaryError, match="LIVEMODE_EVENT_REJECTED"):
        verify_stripe_webhook(
            db_session,
            payload=payload,
            signature_header=f"t={TS},v1={_v1(payload, SECRET)}",
            secret=SECRET,
            test_mode=False,
            now=TS,
        )


def test_production_without_test_mode_records_a_livemode_event(db_session: Session) -> None:
    payload = _event("evt_live", livemode=True)
    intake = _receive(
        db_session, payload, f"t={TS},v1={_v1(payload, SECRET)}", test_mode=False, production=True
    )
    assert intake.record.livemode is True


# --- T041: startup refuses STRIPE_TEST_MODE=false outside production ----------------------


@pytest.mark.parametrize("environment", ["development", "staging", "test", "prod", " Staging ", ""])
def test_startup_refuses_live_stripe_outside_production(environment: str) -> None:
    with pytest.raises(RuntimeError, match="STRIPE_TEST_MODE=false is allowed only in production"):
        validate_stripe_mode_startup_policy(
            SimpleNamespace(environment=environment, stripe_test_mode=False)
        )


@pytest.mark.parametrize(
    "environment,test_mode",
    [("staging", True), ("development", True), ("production", False), ("Production", True)],
)
def test_startup_allows_test_mode_anywhere_and_live_mode_in_production(
    environment: str, test_mode: bool
) -> None:
    validate_stripe_mode_startup_policy(
        SimpleNamespace(environment=environment, stripe_test_mode=test_mode)
    )


def test_startup_defaults_to_test_mode_when_unset() -> None:
    validate_stripe_mode_startup_policy(SimpleNamespace(environment="staging"))


def test_main_lifespan_runs_the_stripe_mode_policy() -> None:
    import inspect

    import main

    assert "validate_stripe_mode_startup_policy(settings)" in inspect.getsource(main.lifespan)
