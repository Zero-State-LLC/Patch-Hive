"""Spec 004 T046: ``POST /api/canon/checkout/credits`` behind the payments flag."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import canon.routes as canon_routes
from canon.checkout import PaymentProviderError, ProviderCheckoutSession
from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderPaymentRecord,
)
from community.models import User
from core import create_access_token, get_db, settings
from main import app


class FakeProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[str] = []

    def create_customer(self, *, user_id: int, idempotency_key: str) -> str:
        self.calls.append("customer")
        if self.fail:
            raise PaymentProviderError("provider answered 500")
        return f"cus_{user_id}"

    def create_checkout_session(self, **kwargs: Any) -> ProviderCheckoutSession:
        self.calls.append("session")
        return ProviderCheckoutSession(id="cs_test_api", url="https://checkout.example.test/api")


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def client(db_session: Session, provider: FakeProvider):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[canon_routes.get_checkout_provider] = lambda: provider
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user(db_session: Session) -> User:
    row = User(
        username="api-buyer",
        email="api-buyer@example.com",
        password_hash="hashed",
        referral_code="apibuyer",
        role="User",
        display_name="api-buyer",
    )
    db_session.add(row)
    db_session.commit()
    return row


def _headers(user: User) -> dict[str, str]:
    token = create_access_token({"user_id": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def _payments(monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> None:
    values = {
        "enable_credit_checkout": True,
        "environment": "development",
        "allow_production_payments": False,
        "stripe_test_mode": True,
        "stripe_secret_key": "sk_test_fixture",
    }
    values.update(overrides)
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(canon_routes, "settings", settings)


def _nothing_written(db_session: Session) -> bool:
    return (
        db_session.query(ProviderPaymentRecord).count() == 0
        and db_session.query(ProviderCustomerRecord).count() == 0
        and db_session.query(CanonicalCreditLedgerEntryRecord).count() == 0
    )


@pytest.mark.parametrize(
    ("overrides", "status", "code"),
    [
        ({"enable_credit_checkout": False}, 403, "PAYMENTS_DISABLED"),
        ({"environment": "production"}, 403, "PRODUCTION_PAYMENTS_DISABLED"),
        ({"stripe_secret_key": ""}, 503, "STRIPE_SECRET_KEY_MISSING"),
        ({"stripe_secret_key": "sk_live_fixture"}, 503, "LIVE_KEY_REFUSED"),
    ],
)
def test_checkout_is_refused_unless_payments_are_on_and_test_mode(
    client: TestClient,
    db_session: Session,
    provider: FakeProvider,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, Any],
    status: int,
    code: str,
) -> None:
    _payments(monkeypatch, **overrides)
    resp = client.post("/api/canon/checkout/credits", json={"credits": 30}, headers=_headers(user))
    assert resp.status_code == status, resp.text
    assert resp.json()["detail"] == code
    assert provider.calls == []
    assert _nothing_written(db_session)


def test_checkout_is_off_with_default_settings(
    client: TestClient, db_session: Session, provider: FakeProvider, user: User
) -> None:
    resp = client.post("/api/canon/checkout/credits", json={"credits": 30}, headers=_headers(user))
    assert (resp.status_code, resp.json()["detail"]) == (403, "PAYMENTS_DISABLED")
    assert provider.calls == []


def test_an_enabled_checkout_opens_a_session_and_grants_nothing(
    client: TestClient,
    db_session: Session,
    provider: FakeProvider,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _payments(monkeypatch)
    resp = client.post("/api/canon/checkout/credits", json={"credits": 30}, headers=_headers(user))

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["checkout_url"] == "https://checkout.example.test/api"
    assert (body["credits"], body["amount_cents"], body["currency"], body["status"]) == (
        30,
        600,
        "usd",
        "open",
    )
    payment = db_session.get(ProviderPaymentRecord, body["payment_id"])
    assert payment.checkout_session_id == "cs_test_api"
    assert db_session.query(CanonicalCreditLedgerEntryRecord).count() == 0


@pytest.mark.parametrize("credits", [0, -5, 1001, "lots"])
def test_an_invalid_quantity_is_rejected(
    client: TestClient,
    db_session: Session,
    provider: FakeProvider,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
    credits: Any,
) -> None:
    _payments(monkeypatch)
    resp = client.post(
        "/api/canon/checkout/credits", json={"credits": credits}, headers=_headers(user)
    )
    assert resp.status_code == 422
    assert provider.calls == []


def test_checkout_needs_a_signed_in_user(
    client: TestClient, provider: FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    _payments(monkeypatch)
    resp = client.post("/api/canon/checkout/credits", json={"credits": 30})
    assert resp.status_code == 401
    assert provider.calls == []


def test_a_provider_failure_answers_502_and_writes_nothing(
    client: TestClient,
    db_session: Session,
    provider: FakeProvider,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _payments(monkeypatch)
    provider.fail = True
    resp = client.post("/api/canon/checkout/credits", json={"credits": 30}, headers=_headers(user))
    assert (resp.status_code, resp.json()["detail"]) == (502, "PAYMENT_PROVIDER_ERROR")
    assert _nothing_written(db_session)
