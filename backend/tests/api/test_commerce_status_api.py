"""Spec 004 T090 (T001 D8b): ``GET /api/canon/commerce``, what a user can buy and what they hold.

An offer appears only while its checkout gate passes. Plan offers carry no price, because tier
prices live at the provider and aren't ratified (OQ-1). No network, no live keys.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from canon.models import ProviderSubscriptionRecord
from community.models import User
from core import create_access_token, get_db, settings
from main import app
from tests.unit.test_canon_contracts import _persist_hierarchy
from tests.unit.test_commerce_subscriptions import PRICES
from tests.unit.test_commerce_tier_entitlements import _studio_grant
from tests.unit.test_commerce_tier_entitlements import _subscription as tier_subscription

NOW = datetime.now(timezone.utc)


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user(db_session: Session) -> User:
    row = User(
        username="commerce-reader",
        email="commerce-reader@example.com",
        password_hash="hashed",
        referral_code="commercereader",
        role="User",
        display_name="commerce-reader",
    )
    db_session.add(row)
    db_session.commit()
    return row


def _headers(user: User) -> dict[str, str]:
    token = create_access_token({"user_id": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def _read(client: TestClient, user: User) -> dict:
    response = client.get("/api/canon/commerce", headers=_headers(user))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def checkout_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "enable_credit_checkout", True)
    monkeypatch.setattr(settings, "enable_subscription_checkout", True)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fixture")
    monkeypatch.setattr(settings, "subscription_price_id_core", PRICES["core"])
    monkeypatch.setattr(settings, "subscription_price_id_pro", PRICES["pro"])
    monkeypatch.setattr(settings, "subscription_price_id_studio", PRICES["studio"])


def _subscription(
    db: Session, user: User, *, tier: str = "core", status: str = "active", cancel: bool = False
) -> ProviderSubscriptionRecord:
    record = ProviderSubscriptionRecord(
        id=f"sub-{user.id}",
        user_id=user.id,
        provider_subscription_id=f"sub_{user.id}",
        provider_customer_id=f"cus_{user.id}",
        price_id=PRICES[tier],
        tier=tier,
        status=status,
        cancel_at_period_end=cancel,
        current_period_start=NOW - timedelta(days=5),
        current_period_end=NOW + timedelta(days=25),
        created_at=NOW,
        updated_at=NOW,
    )
    db.add(record)
    db.commit()
    return record


def test_it_needs_a_signed_in_user(client: TestClient) -> None:
    assert client.get("/api/canon/commerce").status_code == 401


def test_with_the_flags_off_there_is_nothing_to_buy(client: TestClient, user: User) -> None:
    assert settings.enable_credit_checkout is False
    assert _read(client, user) == {
        "test_mode": True,
        "credit_offer": None,
        "plan_offers": [],
        "subscription": None,
        "allowance": None,
    }


def test_open_checkout_offers_credits_and_priced_plans_only(
    client: TestClient, user: User, checkout_open: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "subscription_price_id_pro", "")

    data = _read(client, user)

    assert data["credit_offer"] == {
        "price_cents": 20,
        "minimum_charge_cents": 500,
        "currency": "usd",
        "max_credits": data["credit_offer"]["max_credits"],
    }
    assert data["credit_offer"]["max_credits"] > 0
    assert data["plan_offers"] == [
        {
            "tier": "core",
            "credits_per_period": 25,
            "unlimited": False,
            "fair_use_exports_per_period": None,
        },
        {
            "tier": "studio",
            "credits_per_period": 0,
            "unlimited": True,
            "fair_use_exports_per_period": 100,
        },
    ]


@pytest.mark.parametrize(
    "changes",
    [
        {"stripe_secret_key": ""},
        {"stripe_secret_key": "sk_live_fixture"},
        {"environment": "production"},
    ],
    ids=["no-key", "live-key", "production-not-activated"],
)
def test_a_closed_gate_offers_nothing_even_with_the_flags_on(
    client: TestClient,
    user: User,
    checkout_open: None,
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, str],
) -> None:
    for name, value in changes.items():
        monkeypatch.setattr(settings, name, value)

    data = _read(client, user)

    assert (data["credit_offer"], data["plan_offers"]) == (None, [])


def test_a_plan_holder_sees_the_plan_and_no_offers_and_no_provider_ids(
    client: TestClient, db_session: Session, user: User, checkout_open: None
) -> None:
    _subscription(db_session, user, tier="core")

    data = _read(client, user)

    assert data["plan_offers"] == []
    held = data["subscription"]
    assert held["status"] == "active"
    assert held["can_cancel"] is True
    assert held["cancel_at_period_end"] is False
    assert held["plan"]["credits_per_period"] == 25
    assert "provider_subscription_id" not in held and "provider_customer_id" not in held


@pytest.mark.parametrize(
    "status, cancel, can_cancel",
    [
        ("active", False, True),
        ("trialing", False, True),
        ("past_due", False, True),
        ("unpaid", False, False),
        ("active", True, False),
    ],
)
def test_can_cancel_follows_decision_43(
    client: TestClient,
    db_session: Session,
    user: User,
    checkout_open: None,
    status: str,
    cancel: bool,
    can_cancel: bool,
) -> None:
    _subscription(db_session, user, status=status, cancel=cancel)
    assert _read(client, user)["subscription"]["can_cancel"] is can_cancel


def test_with_the_flag_off_a_plan_still_shows_but_cannot_be_cancelled_here(
    client: TestClient, db_session: Session, user: User
) -> None:
    """The cancel route answers 403 with the flag off, so the page mustn't offer it (T001 O10)."""
    _subscription(db_session, user)

    held = _read(client, user)["subscription"]

    assert held["status"] == "active"
    assert held["can_cancel"] is False


def test_a_canceled_subscription_is_no_longer_held(
    client: TestClient, db_session: Session, user: User, checkout_open: None
) -> None:
    _subscription(db_session, user, status="canceled")

    data = _read(client, user)

    assert data["subscription"] is None
    assert len(data["plan_offers"]) == 3


def test_the_studio_allowance_counts_real_exports_against_the_cap(
    export_fulfillment_pending, client: TestClient, db_session: Session
) -> None:
    owner, _patch = _persist_hierarchy(db_session)
    now = datetime.now(timezone.utc)
    record = tier_subscription(db_session, owner, created_at=now - timedelta(days=1))
    period_end = now + timedelta(days=29)
    _studio_grant(db_session, record, cap=2, start=now - timedelta(days=1), end=period_end)

    before = _read(client, owner)["allowance"]
    assert (before["exports_used"], before["export_cap"]) == (0, 2)
    assert before["period_end"].startswith(period_end.date().isoformat())

    created = client.post(
        "/api/canon/exports",
        headers=_headers(owner),
        json={
            "source_run_id": "run-1",
            "source_rig_revision_id": "rig-rev-1",
            "artifact_manifest_hash": "a" * 64,
            "idempotency_key": "allowance-a",
        },
    )
    assert created.status_code == 201, created.text

    after = _read(client, owner)["allowance"]
    assert (after["exports_used"], after["export_cap"]) == (1, 2)


def test_a_credit_plan_has_no_allowance(
    client: TestClient, db_session: Session, user: User
) -> None:
    _subscription(db_session, user, tier="core")
    assert _read(client, user)["allowance"] is None
