"""Spec 004 T049: Machine C over HTTP.

``POST /api/canon/checkout/subscription`` and ``POST /api/canon/subscription/cancel``
behind ``ENABLE_SUBSCRIPTION_CHECKOUT``, and signed fixture subscription and invoice
events through ``POST /api/canon/webhooks/stripe``. No network, no live keys.
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

import canon.routes as canon_routes
from canon.exports import credit_balance
from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderSubscriptionRecord,
    SubscriptionPeriodGrantRecord,
)
from community.models import User
from core import create_access_token, get_db, settings
from main import app
from tests.api.test_canon_export_api import _webhook_settings
from tests.unit.test_commerce_subscriptions import (
    PRICES,
    FakeSubscriptionProvider,
    _customer,
    _invoice,
    _subscription,
)


@pytest.fixture
def provider() -> FakeSubscriptionProvider:
    return FakeSubscriptionProvider()


@pytest.fixture
def client(db_session: Session, provider: FakeSubscriptionProvider):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[canon_routes.get_subscription_provider] = lambda: provider
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user(db_session: Session) -> User:
    row = User(
        username="api-subscriber",
        email="api-subscriber@example.com",
        password_hash="hashed",
        referral_code="apisubscriber",
        role="User",
        display_name="api-subscriber",
    )
    db_session.add(row)
    db_session.commit()
    return row


def _headers(user: User) -> dict[str, str]:
    token = create_access_token({"user_id": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def _subscriptions_on(monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> None:
    values = {
        "enable_subscription_checkout": True,
        "environment": "development",
        "allow_production_payments": False,
        "stripe_test_mode": True,
        "stripe_secret_key": "sk_test_fixture",
        "subscription_price_id_core": PRICES["core"],
        "subscription_price_id_pro": PRICES["pro"],
        "subscription_price_id_studio": PRICES["studio"],
    }
    values.update(overrides)
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(canon_routes, "settings", settings)


def _post_event(
    client: TestClient, secret: str, event_id: str, event_type: str, obj: dict[str, Any]
):
    payload = json.dumps(
        {
            "id": event_id,
            "type": event_type,
            "created": 1_700_000_000,
            "livemode": False,
            "data": {"object": obj},
        }
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


@pytest.mark.parametrize(
    ("overrides", "status", "code"),
    [
        ({"enable_subscription_checkout": False}, 403, "PAYMENTS_DISABLED"),
        (
            {"enable_subscription_checkout": False, "enable_credit_checkout": True},
            403,
            "PAYMENTS_DISABLED",
        ),
        ({"environment": "production"}, 403, "PRODUCTION_PAYMENTS_DISABLED"),
        ({"stripe_secret_key": ""}, 503, "STRIPE_SECRET_KEY_MISSING"),
        ({"stripe_secret_key": "sk_live_fixture"}, 503, "LIVE_KEY_REFUSED"),
        ({"subscription_price_id_pro": ""}, 503, "SUBSCRIPTION_PRICE_MISSING"),
    ],
)
def test_subscription_checkout_is_refused_unless_on_and_test_mode(
    client: TestClient,
    db_session: Session,
    provider: FakeSubscriptionProvider,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, Any],
    status: int,
    code: str,
) -> None:
    _subscriptions_on(monkeypatch, **overrides)
    resp = client.post(
        "/api/canon/checkout/subscription", json={"tier": "pro"}, headers=_headers(user)
    )
    assert resp.status_code == status, resp.text
    assert resp.json()["detail"] == code
    assert provider.calls == []
    assert db_session.query(ProviderCustomerRecord).count() == 0


def test_subscription_checkout_is_off_with_default_settings(
    client: TestClient, provider: FakeSubscriptionProvider, user: User
) -> None:
    resp = client.post(
        "/api/canon/checkout/subscription", json={"tier": "core"}, headers=_headers(user)
    )
    assert (resp.status_code, resp.json()["detail"]) == (403, "PAYMENTS_DISABLED")
    cancel = client.post("/api/canon/subscription/cancel", headers=_headers(user))
    assert (cancel.status_code, cancel.json()["detail"]) == (403, "PAYMENTS_DISABLED")
    assert provider.calls == []


def test_an_enabled_subscription_checkout_opens_a_session_and_grants_nothing(
    client: TestClient,
    db_session: Session,
    provider: FakeSubscriptionProvider,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _subscriptions_on(monkeypatch)
    resp = client.post(
        "/api/canon/checkout/subscription", json={"tier": "studio"}, headers=_headers(user)
    )

    assert resp.status_code == 201, resp.text
    assert resp.json() == {
        "tier": "studio",
        "checkout_session_id": "cs_sub_test",
        "checkout_url": "https://checkout.example.test/sub",
    }
    assert provider.calls[-1][1]["price_id"] == PRICES["studio"]
    assert db_session.query(ProviderSubscriptionRecord).count() == 0
    assert db_session.query(CanonicalCreditLedgerEntryRecord).count() == 0


@pytest.mark.parametrize("tier", ["free", "CORE ", "", 3])
def test_an_invalid_tier_is_rejected(
    client: TestClient,
    provider: FakeSubscriptionProvider,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
    tier: Any,
) -> None:
    _subscriptions_on(monkeypatch)
    resp = client.post(
        "/api/canon/checkout/subscription", json={"tier": tier}, headers=_headers(user)
    )
    assert resp.status_code == 422
    assert provider.calls == []


def test_subscription_checkout_needs_a_signed_in_user(
    client: TestClient, provider: FakeSubscriptionProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    _subscriptions_on(monkeypatch)
    assert client.post("/api/canon/checkout/subscription", json={"tier": "pro"}).status_code == 401
    assert client.post("/api/canon/subscription/cancel").status_code == 401
    assert provider.calls == []


def test_signed_events_record_grant_once_and_cancel_at_period_end(
    client: TestClient,
    db_session: Session,
    provider: FakeSubscriptionProvider,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = _webhook_settings(monkeypatch, environment="development", test_mode=True)
    _subscriptions_on(monkeypatch)
    _customer(db_session, user)

    created = _post_event(
        client,
        secret,
        "evt_api_c1",
        "customer.subscription.created",
        _subscription("sub_api", user.id),
    )
    paid = _post_event(
        client, secret, "evt_api_c2", "invoice.paid", _invoice("in_api", "sub_api", user.id)
    )
    again = _post_event(
        client, secret, "evt_api_c3", "invoice.paid", _invoice("in_api", "sub_api", user.id)
    )

    assert created.json()["status"] == "processed", created.text
    assert paid.json()["status"] == "processed", paid.text
    assert (again.json()["status"], again.json()["reason_code"]) == (
        "duplicate",
        "PERIOD_ALREADY_GRANTED",
    )
    assert db_session.query(SubscriptionPeriodGrantRecord).count() == 1
    assert credit_balance(db_session, user.id) == 25

    cancel = client.post("/api/canon/subscription/cancel", headers=_headers(user))
    assert cancel.status_code == 200, cancel.text
    body = cancel.json()
    assert (body["provider_subscription_id"], body["cancel_at_period_end"], body["status"]) == (
        "sub_api",
        True,
        "active",
    )
    assert provider.calls[-1][0] == "cancel"

    second = client.post(
        "/api/canon/checkout/subscription", json={"tier": "pro"}, headers=_headers(user)
    )
    assert (second.status_code, second.json()["detail"]) == (409, "SUBSCRIPTION_EXISTS")


def test_cancel_without_a_subscription_is_404(
    client: TestClient,
    provider: FakeSubscriptionProvider,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _subscriptions_on(monkeypatch)
    resp = client.post("/api/canon/subscription/cancel", headers=_headers(user))
    assert (resp.status_code, resp.json()["detail"]) == (404, "SUBSCRIPTION_NOT_FOUND")
    assert provider.calls == []


def test_an_unknown_price_event_is_unresolved_over_http(
    client: TestClient, db_session: Session, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = _webhook_settings(monkeypatch, environment="development", test_mode=True)
    _subscriptions_on(monkeypatch, subscription_price_id_core="price_other")
    _customer(db_session, user)

    resp = _post_event(
        client, secret, "evt_api_bad", "invoice.paid", _invoice("in_api", "sub_api", user.id)
    )

    assert (resp.json()["status"], resp.json()["reason_code"]) == ("unresolved", "PRICE_UNKNOWN")
    assert db_session.query(SubscriptionPeriodGrantRecord).count() == 0
    assert credit_balance(db_session, user.id) == 0
