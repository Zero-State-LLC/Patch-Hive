"""Spec 004 OQ-2 (T053): refunds and disputes through ``POST /api/canon/webhooks/stripe``.

Signed fixture events with a test secret; the payment is credited the same way first.
No network, no live keys.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from canon.exports import credit_balance
from canon.models import CanonicalCreditLedgerEntryRecord, StripeEventRecordModel
from tests.api.test_canon_export_api import _webhook_settings
from core import get_db
from main import app
from tests.unit.test_commerce_credit_checkout import _open_checkout, _session_object, _user


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _post(client: TestClient, secret: str, event_id: str, event_type: str, obj: dict[str, Any]):
    payload = json.dumps(
        {"id": event_id, "type": event_type, "livemode": False, "data": {"object": obj}}
    ).encode()
    timestamp = int(time.time())
    digest = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return client.post(
        "/api/canon/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": f"t={timestamp},v1={digest}"},
    )


@pytest.fixture
def credited(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    secret = _webhook_settings(monkeypatch, environment="development", test_mode=True)
    user = _user(db_session, "api-refund-buyer")
    payment = _open_checkout(db_session, user)
    resp = _post(
        client, secret, "evt_api_paid", "checkout.session.completed", _session_object(payment)
    )
    assert resp.status_code == 200 and resp.json()["status"] == "processed", resp.text
    db_session.refresh(payment)
    return secret, user, payment


def _charge(payment, refunded: int) -> dict[str, Any]:
    return {
        "id": "ch_api",
        "object": "charge",
        "payment_intent": payment.provider_payment_id,
        "customer": f"cus_{payment.user_id}",
        "amount": payment.amount_cents,
        "amount_refunded": refunded,
        "currency": payment.currency,
    }


def test_a_refund_webhook_answers_processed_and_reverses_once(
    client: TestClient, db_session: Session, credited
) -> None:
    secret, user, payment = credited

    first = _post(client, secret, "evt_api_refund", "charge.refunded", _charge(payment, 300))
    again = _post(client, secret, "evt_api_refund", "charge.refunded", _charge(payment, 300))
    other = _post(client, secret, "evt_api_refund_2", "charge.refunded", _charge(payment, 300))

    assert first.status_code == 200, first.text
    assert (first.json()["status"], first.json()["reason_code"]) == ("processed", None)
    assert again.json()["duplicate"] is True
    assert (other.json()["status"], other.json()["reason_code"]) == (
        "duplicate",
        "REFUND_ALREADY_RECORDED",
    )
    refunds = db_session.query(CanonicalCreditLedgerEntryRecord).filter_by(entry_type="refund")
    assert [entry.delta for entry in refunds] == [-15]
    assert credit_balance(db_session, user.id) == 15
    db_session.refresh(payment)
    assert payment.status == "partially_refunded"


def test_a_refund_beyond_the_unspent_balance_is_listed_for_the_operator(
    client: TestClient, db_session: Session, credited
) -> None:
    secret, user, payment = credited
    db_session.add(
        CanonicalCreditLedgerEntryRecord(
            id="debit-api-refund",
            user_id=user.id,
            delta=-25,
            entry_type="debit",
            idempotency_key="test-spend:api-refund",
            export_id=None,
        )
    )
    db_session.commit()

    resp = _post(client, secret, "evt_api_refund_spent", "charge.refunded", _charge(payment, 600))

    assert resp.status_code == 200, resp.text
    assert (resp.json()["status"], resp.json()["reason_code"]) == (
        "unresolved",
        "REFUND_EXCEEDS_UNSPENT",
    )
    assert credit_balance(db_session, user.id) == 0
    record = db_session.get(StripeEventRecordModel, "evt_api_refund_spent")
    assert record.status == "unresolved" and record.processed_at is not None


@pytest.mark.parametrize(
    ("event_type", "obj", "reason"),
    [
        ("charge.dispute.created", {"object": "dispute"}, "DISPUTE_OPENED"),
        ("refund.failed", {"object": "refund", "status": "failed"}, "REFUND_FAILED"),
        (
            "charge.refunded",
            {"object": "charge", "amount": 600, "amount_refunded": 600, "currency": "usd"},
            "PAYMENT_RECORD_NOT_FOUND",
        ),
    ],
)
def test_disputes_failed_refunds_and_unknown_payments_answer_unresolved(
    client: TestClient,
    db_session: Session,
    credited,
    event_type: str,
    obj: dict[str, Any],
    reason: str,
) -> None:
    secret, user, payment = credited
    payment_intent = (
        "pi_unknown" if reason == "PAYMENT_RECORD_NOT_FOUND" else payment.provider_payment_id
    )

    resp = _post(
        client, secret, "evt_api_reversal", event_type, {**obj, "payment_intent": payment_intent}
    )

    assert resp.status_code == 200, resp.text
    assert (resp.json()["status"], resp.json()["reason_code"]) == ("unresolved", reason)
    assert credit_balance(db_session, user.id) == payment.credits
