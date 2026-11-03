"""Spec 004 T049, Machine C: subscriptions.

Checkout opens behind ``ENABLE_SUBSCRIPTION_CHECKOUT`` with a fake provider; the
subscription record and the per-period grant come from signed fixture webhook events
(``receive_stripe_webhook``). No network, no live keys.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy.orm import Session

import core.config as core_config
from canon.checkout import (
    CheckoutUnavailableError,
    PaymentProviderError,
    ProviderCheckoutSession,
    StripeCheckoutProvider,
)
from canon.exports import credit_balance, receive_stripe_webhook
from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderSubscriptionRecord,
    SubscriptionCheckoutRecord,
    SubscriptionPeriodGrantRecord,
)
from canon.subscriptions import (
    SubscriptionRefusedError,
    plan_for_tier,
    request_subscription_cancel,
    start_subscription_checkout,
    subscription_period_key,
    tier_for_price,
)
from canon.subscriptions import _as_epoch as _epoch
from canon.webhook_events import UnresolvedEventError
from community.models import User
from core.config import Settings
from monetization.models import CreditsLedger, Referral
from monetization.referrals import REFERRAL_REWARD_CREDITS, create_referral
from tests.unit.test_commerce_credit_checkout import _settings as _b_settings

TS = 1_700_000_000
SECRET = "whsec_machine_c"
P1 = 1_730_000_000
MONTH = 30 * 86_400
PRICES = {"core": "price_test_core", "pro": "price_test_pro", "studio": "price_test_studio"}


def _c_settings(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "enable_credit_checkout": False,
        "enable_subscription_checkout": True,
        "subscription_price_id_core": PRICES["core"],
        "subscription_price_id_pro": PRICES["pro"],
        "subscription_price_id_studio": PRICES["studio"],
        "subscription_credits_core": 25,
        "subscription_credits_pro": 100,
        "subscription_studio_fair_use_exports_per_period": 100,
    }
    values.update(overrides)
    return _b_settings(**values)


@pytest.fixture
def machine_c(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """The webhook side reads ``core.config.settings``; point it at the test prices."""

    app_settings = _c_settings()
    monkeypatch.setattr(core_config, "settings", app_settings)
    return app_settings


class FakeSubscriptionProvider:
    def __init__(self, *, cancel_body: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.cancel_body = cancel_body

    def create_customer(self, *, user_id: int, idempotency_key: str) -> str:
        self.calls.append(("customer", {"user_id": user_id}))
        return f"cus_{user_id}"

    def create_subscription_checkout_session(self, **kwargs: Any) -> ProviderCheckoutSession:
        self.calls.append(("session", kwargs))
        count = sum(1 for name, _ in self.calls if name == "session")
        suffix = "" if count == 1 else f"_{count}"
        return ProviderCheckoutSession(
            id=f"cs_sub_test{suffix}", url=f"https://checkout.example.test/sub{suffix}"
        )

    def cancel_subscription_at_period_end(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("cancel", kwargs))
        if self.cancel_body is not None:
            return self.cancel_body
        return {"id": kwargs["subscription_id"], "cancel_at_period_end": True}


def _user(session: Session, name: str = "subscriber") -> User:
    user = User(
        username=name,
        email=f"{name}@example.com",
        password_hash="hashed",
        referral_code=f"code-{name}",
        role="User",
        display_name=name,
    )
    session.add(user)
    session.commit()
    return user


def _customer(session: Session, user: User) -> ProviderCustomerRecord:
    from datetime import datetime, timezone

    link = ProviderCustomerRecord(
        user_id=user.id,
        provider_customer_id=f"cus_{user.id}",
        created_at=datetime.now(timezone.utc),
    )
    session.add(link)
    session.commit()
    return link


def _subscription(
    sub_id: str,
    user_id: int,
    *,
    tier: str = "core",
    status: str = "active",
    start: int = P1,
    end: int = P1 + MONTH,
    cancel: bool = False,
    **overrides: Any,
) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "id": sub_id,
        "object": "subscription",
        "customer": f"cus_{user_id}",
        "status": status,
        "cancel_at_period_end": cancel,
        "current_period_start": start,
        "current_period_end": end,
        "items": {"object": "list", "data": [{"id": "si_1", "price": {"id": PRICES[tier]}}]},
        "metadata": {"user_id": str(user_id), "tier": tier},
    }
    obj.update(overrides)
    return obj


def _invoice(
    invoice_id: str,
    sub_id: str,
    user_id: int,
    *,
    tier: str = "core",
    start: int = P1,
    end: int = P1 + MONTH,
    amount: int = 499,
    **overrides: Any,
) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "id": invoice_id,
        "object": "invoice",
        "customer": f"cus_{user_id}",
        "subscription": sub_id,
        "status": "paid",
        "amount_paid": amount,
        "currency": "usd",
        "billing_reason": "subscription_create",
        "lines": {
            "object": "list",
            "data": [
                {
                    "id": "il_1",
                    "price": {"id": PRICES[tier]},
                    "period": {"start": start, "end": end},
                }
            ],
        },
    }
    obj.update(overrides)
    return obj


def _deliver(
    session: Session, event_id: str, event_type: str, obj: dict[str, Any], *, created: int = TS
):
    payload = json.dumps(
        {
            "id": event_id,
            "type": event_type,
            "created": created,
            "livemode": False,
            "data": {"object": obj},
        }
    ).encode()
    signature = hmac.new(SECRET.encode(), f"{TS}.".encode() + payload, hashlib.sha256).hexdigest()
    intake = receive_stripe_webhook(
        session,
        payload=payload,
        signature_header=f"t={TS},v1={signature}",
        secret=SECRET,
        now=TS,
    )
    session.commit()
    return intake


def _disposition(intake) -> tuple[str, str | None]:
    return intake.record.status, intake.record.reason_code


def _record(session: Session, sub_id: str) -> ProviderSubscriptionRecord | None:
    session.expire_all()
    return (
        session.query(ProviderSubscriptionRecord)
        .filter_by(provider_subscription_id=sub_id)
        .one_or_none()
    )


def _grants(session: Session) -> list[SubscriptionPeriodGrantRecord]:
    return (
        session.query(SubscriptionPeriodGrantRecord)
        .order_by(SubscriptionPeriodGrantRecord.period_start)
        .all()
    )


def _ledger_grants(session: Session, user: User) -> list[CanonicalCreditLedgerEntryRecord]:
    return (
        session.query(CanonicalCreditLedgerEntryRecord)
        .filter_by(user_id=user.id, entry_type="grant")
        .all()
    )


def _legacy_purchases(session: Session) -> list[CreditsLedger]:
    return session.query(CreditsLedger).filter_by(change_type="Purchase").all()


def _nothing_granted(session: Session) -> bool:
    return (
        session.query(SubscriptionPeriodGrantRecord).count() == 0
        and session.query(CanonicalCreditLedgerEntryRecord).count() == 0
        and session.query(CreditsLedger).count() == 0
    )


# --- Settings ----------------------------------------------------------------------------


def test_subscription_settings_keep_their_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ENABLE_SUBSCRIPTION_CHECKOUT",
        "SUBSCRIPTION_PRICE_ID_CORE",
        "SUBSCRIPTION_PRICE_ID_PRO",
        "SUBSCRIPTION_PRICE_ID_STUDIO",
        "SUBSCRIPTION_CREDITS_CORE",
        "SUBSCRIPTION_CREDITS_PRO",
        "SUBSCRIPTION_STUDIO_FAIR_USE_EXPORTS_PER_PERIOD",
        "STRIPE_TEST_MODE",
        "ALLOW_PRODUCTION_PAYMENTS",
    ):
        monkeypatch.delenv(name, raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.enable_subscription_checkout is False
    assert defaults.stripe_test_mode is True
    assert defaults.allow_production_payments is False
    assert (
        defaults.subscription_price_id_core,
        defaults.subscription_price_id_pro,
        defaults.subscription_price_id_studio,
    ) == ("", "", "")
    # OQ-1 (provisional) credits and the OQ-8 fair-use default.
    assert (defaults.subscription_credits_core, defaults.subscription_credits_pro) == (25, 100)
    assert defaults.subscription_studio_fair_use_exports_per_period == 100
    # With no price configured, no price maps to a tier.
    assert tier_for_price(defaults, "price_anything") is None
    assert tier_for_price(defaults, "") is None


def test_price_ids_map_to_tiers_from_settings_only() -> None:
    app_settings = _c_settings()
    assert {tier: tier_for_price(app_settings, PRICES[tier]) for tier in PRICES} == {
        "core": "core",
        "pro": "pro",
        "studio": "studio",
    }
    assert tier_for_price(app_settings, "price_unknown") is None
    # One price configured for two tiers cannot be told apart: it maps to none.
    shared = _c_settings(subscription_price_id_pro=PRICES["core"])
    assert tier_for_price(shared, PRICES["core"]) is None


def test_tier_plans_are_credits_for_core_and_pro_and_a_flag_for_studio() -> None:
    app_settings = _c_settings(subscription_studio_fair_use_exports_per_period=40)
    core, pro, studio = (plan_for_tier(app_settings, tier) for tier in ("core", "pro", "studio"))
    assert (core.credits, core.unlimited, core.fair_use_export_cap) == (25, False, None)
    assert (pro.credits, pro.unlimited, pro.fair_use_export_cap) == (100, False, None)
    # FR-004: no numeric sentinel; the entitlement is a flag with a fair-use cap (OQ-8).
    assert (studio.credits, studio.unlimited, studio.fair_use_export_cap) == (0, True, 40)
    for bad in (
        {"subscription_credits_core": 0},
        {"subscription_studio_fair_use_exports_per_period": 0},
    ):
        tier = "core" if "subscription_credits_core" in bad else "studio"
        with pytest.raises(UnresolvedEventError, match="TIER_CONFIG_INVALID"):
            plan_for_tier(_c_settings(**bad), tier)


def test_the_period_key_is_subscription_and_period_start() -> None:
    assert subscription_period_key("sub_1", P1) == f"subscription-period:sub_1:{P1}"


# --- choose_tier -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"enable_subscription_checkout": False}, "PAYMENTS_DISABLED"),
        # The credit checkout flag does not open subscriptions.
        (
            {"enable_subscription_checkout": False, "enable_credit_checkout": True},
            "PAYMENTS_DISABLED",
        ),
        ({"environment": "production"}, "PRODUCTION_PAYMENTS_DISABLED"),
        ({"stripe_secret_key": ""}, "STRIPE_SECRET_KEY_MISSING"),
        ({"stripe_secret_key": "sk_live_fixture"}, "LIVE_KEY_REFUSED"),
        ({"stripe_test_mode": False, "stripe_secret_key": "sk_live_x"}, "LIVE_KEY_REFUSED"),
        ({"subscription_price_id_pro": ""}, "SUBSCRIPTION_PRICE_MISSING"),
        ({"subscription_price_id_core": PRICES["pro"]}, "SUBSCRIPTION_PRICE_MISSING"),
    ],
)
def test_subscription_checkout_is_refused_before_any_provider_call(
    db_session: Session, overrides: dict[str, Any], code: str
) -> None:
    user = _user(db_session)
    provider = FakeSubscriptionProvider()
    with pytest.raises(CheckoutUnavailableError, match=code):
        start_subscription_checkout(
            db_session,
            user=user,
            tier="pro",
            provider=provider,
            app_settings=_c_settings(**overrides),
        )
    assert provider.calls == []
    assert db_session.query(ProviderCustomerRecord).count() == 0


@pytest.mark.parametrize("tier", ["free", "", "enterprise", None])
def test_an_invalid_tier_is_refused(db_session: Session, tier) -> None:
    user = _user(db_session)
    provider = FakeSubscriptionProvider()
    with pytest.raises(ValueError, match="INVALID_TIER"):
        start_subscription_checkout(
            db_session, user=user, tier=tier, provider=provider, app_settings=_c_settings()
        )
    assert provider.calls == []


@pytest.mark.parametrize("tier", ["core", "pro", "studio"])
def test_an_enabled_checkout_opens_a_subscription_session_and_writes_no_record(
    db_session: Session, tier: str
) -> None:
    user = _user(db_session)
    provider = FakeSubscriptionProvider()

    started = start_subscription_checkout(
        db_session, user=user, tier=tier, provider=provider, app_settings=_c_settings()
    )
    db_session.commit()

    assert (started.tier, started.checkout_session_id) == (tier, "cs_sub_test")
    (_, customer), (_, session_call) = provider.calls
    assert customer == {"user_id": user.id}
    assert session_call["price_id"] == PRICES[tier]
    assert session_call["tier"] == tier
    assert session_call["customer_id"] == f"cus_{user.id}"
    assert session_call["idempotency_key"].startswith("patchhive-subscription-checkout:")
    # Machine C writes no record until the provider reports the subscription; only the
    # checkout reservation.
    assert db_session.query(ProviderSubscriptionRecord).count() == 0
    (reservation,) = db_session.query(SubscriptionCheckoutRecord).all()
    assert (reservation.checkout_session_id, reservation.tier, reservation.status) == (
        "cs_sub_test",
        tier,
        "open",
    )
    assert _epoch(reservation.expires_at) == session_call["expires_at"]
    assert _nothing_granted(db_session)


def _start(db_session: Session, user: User, provider, tier: str = "pro"):
    started = start_subscription_checkout(
        db_session, user=user, tier=tier, provider=provider, app_settings=_c_settings()
    )
    db_session.commit()
    return started


def test_a_repeated_request_reuses_the_open_checkout(db_session: Session) -> None:
    """Two requests before either session is paid open one subscription checkout."""
    user = _user(db_session)
    provider = FakeSubscriptionProvider()

    first = _start(db_session, user, provider)
    second = _start(db_session, user, provider)

    assert second == first
    assert [name for name, _ in provider.calls] == ["customer", "session"]
    assert db_session.query(SubscriptionCheckoutRecord).count() == 1
    with pytest.raises(SubscriptionRefusedError) as other_tier:
        _start(db_session, user, provider, tier="studio")
    assert (other_tier.value.code, other_tier.value.status_code) == (
        "SUBSCRIPTION_CHECKOUT_OPEN",
        409,
    )
    assert [name for name, _ in provider.calls] == ["customer", "session"]


def test_an_expired_checkout_no_longer_blocks(db_session: Session, machine_c) -> None:
    user = _user(db_session)
    provider = FakeSubscriptionProvider()
    first = _start(db_session, user, provider)

    # By the provider's own expiry event ...
    _deliver(
        db_session,
        "evt_expired",
        "checkout.session.expired",
        {"id": first.checkout_session_id, "object": "checkout.session", "mode": "subscription"},
    )
    second = _start(db_session, user, provider, tier="studio")
    assert second.checkout_session_id != first.checkout_session_id

    # ... or once its expiry time has passed.
    from datetime import datetime, timezone

    reservation = (
        db_session.query(SubscriptionCheckoutRecord)
        .filter_by(checkout_session_id=second.checkout_session_id)
        .one()
    )
    reservation.expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    db_session.commit()
    third = _start(db_session, user, provider)
    assert third.checkout_session_id not in {
        first.checkout_session_id,
        second.checkout_session_id,
    }
    statuses = sorted(r.status for r in db_session.query(SubscriptionCheckoutRecord))
    assert statuses == ["expired", "open", "open"]


def test_a_completed_checkout_blocks_until_its_subscription_is_terminal(
    db_session: Session, machine_c
) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    provider = FakeSubscriptionProvider()
    first = _start(db_session, user, provider)

    completed = _deliver(
        db_session,
        "evt_done",
        "checkout.session.completed",
        {
            "id": first.checkout_session_id,
            "object": "checkout.session",
            "mode": "subscription",
            "subscription": "sub_1",
        },
    )
    assert _disposition(completed) == ("processed", None)
    # Paid, but the subscription event has not arrived: still one subscription only.
    with pytest.raises(SubscriptionRefusedError, match="SUBSCRIPTION_EXISTS"):
        _start(db_session, user, provider)

    _deliver(db_session, "evt_c1", "customer.subscription.created", _subscription("sub_1", user.id))
    with pytest.raises(SubscriptionRefusedError, match="SUBSCRIPTION_EXISTS"):
        _start(db_session, user, provider)
    _deliver(db_session, "evt_c2", "customer.subscription.deleted", _subscription("sub_1", user.id))
    _start(db_session, user, provider)
    assert [name for name, _ in provider.calls].count("session") == 2
    # Nothing about the session itself grants.
    assert _ledger_grants(db_session, user) == []


def test_a_user_with_a_live_subscription_cannot_open_another(
    db_session: Session, machine_c
) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(db_session, "evt_c1", "customer.subscription.created", _subscription("sub_1", user.id))
    provider = FakeSubscriptionProvider()

    with pytest.raises(SubscriptionRefusedError) as excinfo:
        start_subscription_checkout(
            db_session, user=user, tier="pro", provider=provider, app_settings=_c_settings()
        )
    assert (excinfo.value.code, excinfo.value.status_code) == ("SUBSCRIPTION_EXISTS", 409)
    assert provider.calls == []

    # Canceled: resubscribing starts a new subscription from NONE.
    _deliver(db_session, "evt_c2", "customer.subscription.deleted", _subscription("sub_1", user.id))
    start_subscription_checkout(
        db_session, user=user, tier="pro", provider=provider, app_settings=_c_settings()
    )
    assert [name for name, _ in provider.calls] == ["session"]


def test_the_stripe_client_sends_a_subscription_mode_session_without_the_key_in_errors() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/checkout/sessions":
            return httpx.Response(200, json={"id": "cs_1", "url": "https://checkout.test/1"})
        return httpx.Response(500, json={"error": "boom"})

    client = StripeCheckoutProvider("sk_test_secret_value", transport=httpx.MockTransport(handler))
    created = client.create_subscription_checkout_session(
        customer_id="cus_1",
        user_id=7,
        tier="pro",
        price_id=PRICES["pro"],
        success_url="https://app.test/ok",
        cancel_url="https://app.test/no",
        expires_at=1_700_003_600,
        idempotency_key="key-1",
    )
    assert created == ProviderCheckoutSession(id="cs_1", url="https://checkout.test/1")
    form = {k: v[0] for k, v in parse_qs(seen[0].content.decode()).items()}
    assert form["mode"] == "subscription"
    assert form["expires_at"] == "1700003600"
    assert form["line_items[0][price]"] == PRICES["pro"]
    assert form["line_items[0][quantity]"] == "1"
    assert form["metadata[user_id]"] == "7"
    assert form["metadata[tier]"] == "pro"
    assert form["subscription_data[metadata][user_id]"] == "7"
    assert "price_data" not in seen[0].content.decode()
    assert seen[0].headers["Idempotency-Key"] == "key-1"

    with pytest.raises(PaymentProviderError) as excinfo:
        client.cancel_subscription_at_period_end(subscription_id="sub_1", idempotency_key="k")
    assert "sk_test_secret_value" not in str(excinfo.value)
    assert seen[1].url.path == "/v1/subscriptions/sub_1"
    assert parse_qs(seen[1].content.decode()) == {"cancel_at_period_end": ["true"]}


# --- customer.subscription.* --------------------------------------------------------------


def test_subscription_created_records_the_subscription_and_grants_nothing(
    db_session: Session, machine_c
) -> None:
    user = _user(db_session)
    _customer(db_session, user)

    intake = _deliver(
        db_session,
        "evt_created",
        "customer.subscription.created",
        _subscription("sub_1", user.id, tier="pro"),
    )

    assert _disposition(intake) == ("processed", None)
    record = _record(db_session, "sub_1")
    assert (record.user_id, record.tier, record.status, record.price_id) == (
        user.id,
        "pro",
        "active",
        PRICES["pro"],
    )
    assert (_epoch(record.current_period_start), _epoch(record.current_period_end)) == (
        P1,
        P1 + MONTH,
    )
    assert record.cancel_at_period_end is False
    assert record.purchase_recorded_at is None
    # Grants come only from invoice.paid.
    assert _nothing_granted(db_session)


def test_subscription_updated_syncs_fields_and_grants_nothing(
    db_session: Session, machine_c
) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(db_session, "evt_1", "customer.subscription.created", _subscription("sub_1", user.id))
    _deliver(db_session, "evt_2", "invoice.paid", _invoice("in_1", "sub_1", user.id))

    # Same period, cancel flag set at the provider, then a past_due status.
    first = _deliver(
        db_session,
        "evt_3",
        "customer.subscription.updated",
        _subscription("sub_1", user.id, cancel=True),
        created=TS + 1,
    )
    second = _deliver(
        db_session,
        "evt_4",
        "customer.subscription.updated",
        _subscription("sub_1", user.id, cancel=True, status="past_due"),
        created=TS + 2,
    )

    assert _disposition(first) == ("processed", None)
    assert _disposition(second) == ("processed", None)
    record = _record(db_session, "sub_1")
    assert (record.status, record.cancel_at_period_end) == ("past_due", True)
    assert len(_grants(db_session)) == 1
    assert credit_balance(db_session, user.id) == 25


def test_an_update_that_changes_nothing_is_a_duplicate(db_session: Session, machine_c) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(db_session, "evt_1", "customer.subscription.created", _subscription("sub_1", user.id))

    again = _deliver(
        db_session, "evt_2", "customer.subscription.updated", _subscription("sub_1", user.id)
    )

    assert _disposition(again) == ("duplicate", "SUBSCRIPTION_UNCHANGED")


def test_an_unchanged_newer_snapshot_still_advances_the_watermark(
    db_session: Session, machine_c
) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(
        db_session,
        "evt_1",
        "customer.subscription.created",
        _subscription("sub_1", user.id),
        created=TS,
    )
    unchanged = _deliver(
        db_session,
        "evt_2",
        "customer.subscription.updated",
        _subscription("sub_1", user.id),
        created=TS + 20,
    )
    late = _deliver(
        db_session,
        "evt_3",
        "customer.subscription.updated",
        _subscription("sub_1", user.id, status="past_due"),
        created=TS + 10,
    )

    assert _disposition(unchanged) == ("duplicate", "SUBSCRIPTION_UNCHANGED")
    assert _disposition(late) == ("duplicate", "STALE_EVENT")
    record = _record(db_session, "sub_1")
    assert (record.status, record.last_event_created) == ("active", TS + 20)


def test_a_same_second_incomplete_snapshot_never_moves_an_active_record_back(
    db_session: Session, machine_c
) -> None:
    """Codex P2 on #219: invoice.paid made the record ``active``; the creation snapshot
    from the same second (``incomplete``) arrives later and must not win."""
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(db_session, "evt_inv", "invoice.paid", _invoice("in_1", "sub_1", user.id), created=TS)

    late = _deliver(
        db_session,
        "evt_created",
        "customer.subscription.created",
        _subscription("sub_1", user.id, status="incomplete"),
        created=TS,
    )

    assert _disposition(late) == ("duplicate", "STALE_EVENT")
    assert _record(db_session, "sub_1").status == "active"
    provider = FakeSubscriptionProvider()
    request_subscription_cancel(
        db_session, user=user, provider=provider, app_settings=_c_settings()
    )
    assert [name for name, _ in provider.calls] == ["cancel"]


def test_a_same_second_snapshot_at_the_same_or_a_later_stage_applies(
    db_session: Session, machine_c
) -> None:
    """Equal timestamps are not all rejected: a same-stage change (active to past_due,
    a cancel flag) and a forward move (incomplete to active) apply."""
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(
        db_session,
        "evt_1",
        "customer.subscription.created",
        _subscription("sub_1", user.id, status="incomplete"),
        created=TS,
    )
    forward = _deliver(
        db_session,
        "evt_2",
        "customer.subscription.updated",
        _subscription("sub_1", user.id),
        created=TS,
    )
    same_stage = _deliver(
        db_session,
        "evt_3",
        "customer.subscription.updated",
        _subscription("sub_1", user.id, status="past_due", cancel=True),
        created=TS,
    )

    assert _disposition(forward) == ("processed", None)
    assert _disposition(same_stage) == ("processed", None)
    record = _record(db_session, "sub_1")
    assert (record.status, record.cancel_at_period_end) == ("past_due", True)


def _proration_line(*, newer_shape: bool = False) -> dict[str, Any]:
    line: dict[str, Any] = {
        "id": "il_prorate",
        "price": {"id": PRICES["pro"]},
        "period": {"start": P1 + MONTH // 2, "end": P1 + MONTH},
    }
    if newer_shape:
        line["parent"] = {
            "type": "subscription_item_details",
            "subscription_item_details": {"proration": True, "subscription": "sub_1"},
        }
    else:
        line["proration"] = True
    return line


@pytest.mark.parametrize("newer_shape", [False, True])
def test_a_proration_only_invoice_grants_nothing(
    db_session: Session, machine_c, newer_shape: bool
) -> None:
    """Codex P2 on #219, OQ-7: a mid-period upgrade billed at once is no new period."""
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(db_session, "evt_1", "invoice.paid", _invoice("in_1", "sub_1", user.id))

    prorated = _deliver(
        db_session,
        "evt_2",
        "invoice.paid",
        _invoice(
            "in_2",
            "sub_1",
            user.id,
            amount=500,
            billing_reason="subscription_update",
            lines={"data": [_proration_line(newer_shape=newer_shape)]},
        ),
    )

    assert _disposition(prorated) == ("ignored", "INVOICE_PRORATION_ONLY")
    assert len(_grants(db_session)) == 1
    assert credit_balance(db_session, user.id) == 25


def test_proration_lines_never_select_the_period(db_session: Session, machine_c) -> None:
    """A renewal invoice carrying earlier prorations grants its full-period line only."""
    user = _user(db_session)
    _customer(db_session, user)
    full = {
        "id": "il_full",
        "price": {"id": PRICES["pro"]},
        "period": {"start": P1 + MONTH, "end": P1 + 2 * MONTH},
        "proration": False,
    }

    intake = _deliver(
        db_session,
        "evt_1",
        "invoice.paid",
        _invoice(
            "in_1",
            "sub_1",
            user.id,
            amount=1499,
            billing_reason="subscription_cycle",
            lines={"data": [_proration_line(), full]},
        ),
    )

    assert _disposition(intake) == ("processed", None)
    (grant,) = _grants(db_session)
    assert (grant.grant_key, grant.tier) == (subscription_period_key("sub_1", P1 + MONTH), "pro")
    assert credit_balance(db_session, user.id) == 100


def test_a_malformed_proration_flag_is_unresolved(db_session: Session, machine_c) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    line = _proration_line()
    line["proration"] = "yes"

    intake = _deliver(
        db_session,
        "evt_1",
        "invoice.paid",
        _invoice("in_1", "sub_1", user.id, lines={"data": [line]}),
    )

    assert _disposition(intake) == ("unresolved", "EVENT_PAYLOAD_MALFORMED")
    assert _nothing_granted(db_session)


def test_an_older_event_delivered_late_does_not_roll_the_record_back(
    db_session: Session, machine_c
) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(
        db_session,
        "evt_new",
        "customer.subscription.updated",
        _subscription("sub_1", user.id, status="past_due"),
        created=TS + 10,
    )

    late = _deliver(
        db_session,
        "evt_old",
        "customer.subscription.created",
        _subscription("sub_1", user.id, status="incomplete"),
        created=TS,
    )

    assert _disposition(late) == ("duplicate", "STALE_EVENT")
    assert _record(db_session, "sub_1").status == "past_due"


def test_a_tier_change_is_stored_from_the_price_and_credits_from_the_next_period(
    db_session: Session, machine_c
) -> None:
    """OQ-7 ``A_next_period_no_proration``."""
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(db_session, "evt_1", "customer.subscription.created", _subscription("sub_1", user.id))
    _deliver(db_session, "evt_2", "invoice.paid", _invoice("in_1", "sub_1", user.id))

    upgrade = _deliver(
        db_session,
        "evt_3",
        "customer.subscription.updated",
        _subscription("sub_1", user.id, tier="pro", metadata={"user_id": str(user.id)}),
        created=TS + 1,
    )
    assert _disposition(upgrade) == ("processed", None)
    assert _record(db_session, "sub_1").tier == "pro"
    # No proration grant mid-period.
    assert credit_balance(db_session, user.id) == 25

    _deliver(
        db_session,
        "evt_4",
        "invoice.paid",
        _invoice(
            "in_2",
            "sub_1",
            user.id,
            tier="pro",
            start=P1 + MONTH,
            end=P1 + 2 * MONTH,
            amount=1499,
            billing_reason="subscription_cycle",
        ),
        created=TS + 2,
    )
    assert [grant.tier for grant in _grants(db_session)] == ["core", "pro"]
    assert credit_balance(db_session, user.id) == 125


def test_subscription_deleted_sets_canceled_and_keeps_credits(
    db_session: Session, machine_c
) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(db_session, "evt_1", "customer.subscription.created", _subscription("sub_1", user.id))
    _deliver(db_session, "evt_2", "invoice.paid", _invoice("in_1", "sub_1", user.id))

    deleted = _deliver(
        db_session,
        "evt_3",
        "customer.subscription.deleted",
        _subscription("sub_1", user.id, status="canceled"),
        created=TS + 5,
    )

    assert _disposition(deleted) == ("processed", None)
    record = _record(db_session, "sub_1")
    assert record.status == "canceled"
    assert record.canceled_at is not None
    assert credit_balance(db_session, user.id) == 25

    # Canceled is final: Canceled -> Active is illegal.
    revived = _deliver(
        db_session,
        "evt_4",
        "customer.subscription.updated",
        _subscription("sub_1", user.id, status="active"),
        created=TS + 6,
    )
    assert _disposition(revived) == ("duplicate", "SUBSCRIPTION_ALREADY_CANCELED")
    assert _record(db_session, "sub_1").status == "canceled"


def test_a_deletion_of_a_known_subscription_needs_no_price_mapping(
    db_session: Session, machine_c, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(db_session, "evt_1", "customer.subscription.created", _subscription("sub_1", user.id))
    monkeypatch.setattr(machine_c, "subscription_price_id_core", "price_rotated")

    deleted = _deliver(
        db_session,
        "evt_2",
        "customer.subscription.deleted",
        _subscription("sub_1", user.id, status="canceled"),
        created=TS - 100,
    )

    assert _disposition(deleted) == ("processed", None)
    assert _record(db_session, "sub_1").status == "canceled"


def test_the_newer_api_shape_with_the_period_on_the_item_is_understood(
    db_session: Session, machine_c
) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    obj = _subscription("sub_1", user.id)
    del obj["current_period_start"], obj["current_period_end"]
    obj["items"]["data"][0].update({"current_period_start": P1, "current_period_end": P1 + MONTH})

    intake = _deliver(db_session, "evt_1", "customer.subscription.created", obj)

    assert _disposition(intake) == ("processed", None)
    assert _epoch(_record(db_session, "sub_1").current_period_end) == P1 + MONTH


SUBSCRIPTION_UNRESOLVED = [
    ("unknown-customer", {"customer": "cus_nobody"}, "CUSTOMER_NOT_FOUND"),
    ("no-customer", {"customer": None}, "EVENT_PAYLOAD_MALFORMED"),
    ("not-a-subscription", {"object": "invoice"}, "EVENT_PAYLOAD_MALFORMED"),
    ("no-id", {"id": None}, "EVENT_PAYLOAD_MALFORMED"),
    (
        "unknown-price",
        {"items": {"data": [{"id": "si_1", "price": {"id": "price_other"}}]}},
        "PRICE_UNKNOWN",
    ),
    ("no-items", {"items": {"data": []}}, "SUBSCRIPTION_ITEMS_UNSUPPORTED"),
    (
        "two-items",
        {
            "items": {
                "data": [
                    {"id": "si_1", "price": {"id": PRICES["core"]}},
                    {"id": "si_2", "price": {"id": PRICES["pro"]}},
                ]
            }
        },
        "SUBSCRIPTION_ITEMS_UNSUPPORTED",
    ),
    ("unknown-status", {"status": "frozen"}, "STATUS_UNKNOWN"),
    ("no-period", {"current_period_end": None}, "PERIOD_MALFORMED"),
    ("backwards-period", {"current_period_end": P1 - 1}, "PERIOD_MALFORMED"),
    ("cancel-flag-not-bool", {"cancel_at_period_end": "yes"}, "EVENT_PAYLOAD_MALFORMED"),
    ("other-user-metadata", {"metadata": {"user_id": "999"}}, "METADATA_MALFORMED"),
]


@pytest.mark.parametrize(
    ("change", "reason"),
    [(case[1], case[2]) for case in SUBSCRIPTION_UNRESOLVED],
    ids=[case[0] for case in SUBSCRIPTION_UNRESOLVED],
)
def test_an_unmappable_subscription_event_is_unresolved_and_writes_nothing(
    db_session: Session, machine_c, change: dict[str, Any], reason: str
) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    obj = _subscription("sub_1", user.id)
    obj.update(change)

    intake = _deliver(db_session, "evt_bad", "customer.subscription.created", obj)

    assert _disposition(intake) == ("unresolved", reason)
    assert db_session.query(ProviderSubscriptionRecord).count() == 0
    assert _nothing_granted(db_session)


def test_a_subscription_moved_to_another_customer_is_unresolved(
    db_session: Session, machine_c
) -> None:
    owner = _user(db_session, "owner")
    other = _user(db_session, "other")
    _customer(db_session, owner)
    _customer(db_session, other)
    _deliver(db_session, "evt_1", "customer.subscription.created", _subscription("sub_1", owner.id))

    intake = _deliver(
        db_session,
        "evt_2",
        "customer.subscription.updated",
        _subscription("sub_1", other.id, status="past_due"),
        created=TS + 1,
    )

    assert _disposition(intake) == ("unresolved", "CUSTOMER_MISMATCH")
    record = _record(db_session, "sub_1")
    assert (record.user_id, record.status) == (owner.id, "active")


# --- invoice.paid -------------------------------------------------------------------------


def test_the_first_paid_invoice_grants_the_period_and_records_one_purchase(
    db_session: Session, machine_c
) -> None:
    """FR-016 and OQ-3 ``A_both``: a separate grant plus a verified purchase."""
    referrer = _user(db_session, "referrer")
    user = _user(db_session)
    create_referral(db_session, referrer=referrer, referred=user)
    db_session.commit()
    _customer(db_session, user)
    _deliver(db_session, "evt_1", "customer.subscription.created", _subscription("sub_1", user.id))

    intake = _deliver(db_session, "evt_2", "invoice.paid", _invoice("in_1", "sub_1", user.id))

    assert _disposition(intake) == ("processed", None)
    (grant,) = _grants(db_session)
    key = subscription_period_key("sub_1", P1)
    assert (grant.grant_key, grant.tier, grant.credits, grant.unlimited) == (key, "core", 25, False)
    assert grant.provider_invoice_id == "in_1"
    (entry,) = _ledger_grants(db_session, user)
    assert (entry.idempotency_key, entry.delta, entry.id) == (key, 25, grant.ledger_entry_id)
    assert credit_balance(db_session, user.id) == 25
    (purchase,) = _legacy_purchases(db_session)
    assert (purchase.user_id, purchase.credits_delta) == (user.id, 0)
    assert _record(db_session, "sub_1").purchase_recorded_at is not None
    # Machine A: the referrer is rewarded once (FR-028).
    assert db_session.query(Referral).filter_by(status="Rewarded").count() == 1
    assert credit_balance(db_session, referrer.id) == REFERRAL_REWARD_CREDITS


def test_a_repeated_invoice_for_a_granted_period_is_a_duplicate(
    db_session: Session, machine_c
) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    obj = _invoice("in_1", "sub_1", user.id)
    _deliver(db_session, "evt_1", "invoice.paid", obj)

    redelivered = _deliver(db_session, "evt_1", "invoice.paid", obj)
    new_event_id = _deliver(db_session, "evt_2", "invoice.paid", obj)
    other_invoice = _deliver(
        db_session, "evt_3", "invoice.paid", _invoice("in_9", "sub_1", user.id)
    )

    assert redelivered.duplicate is True
    assert _disposition(new_event_id) == ("duplicate", "PERIOD_ALREADY_GRANTED")
    assert _disposition(other_invoice) == ("duplicate", "PERIOD_ALREADY_GRANTED")
    assert len(_grants(db_session)) == 1
    assert credit_balance(db_session, user.id) == 25
    assert len(_legacy_purchases(db_session)) == 1


def test_each_new_period_grants_once_and_only_the_first_is_a_purchase(
    db_session: Session, machine_c
) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    for index in range(3):
        start = P1 + index * MONTH
        _deliver(
            db_session,
            f"evt_{index}",
            "invoice.paid",
            _invoice(f"in_{index}", "sub_1", user.id, start=start, end=start + MONTH),
        )

    assert [_epoch(grant.period_start) for grant in _grants(db_session)] == [
        P1,
        P1 + MONTH,
        P1 + 2 * MONTH,
    ]
    assert credit_balance(db_session, user.id) == 75
    assert len(_legacy_purchases(db_session)) == 1


def test_pro_grants_its_credits(db_session: Session, machine_c) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(db_session, "evt_1", "invoice.paid", _invoice("in_1", "sub_1", user.id, tier="pro"))
    assert credit_balance(db_session, user.id) == 100


def test_studio_grants_the_unlimited_entitlement_with_its_fair_use_cap_and_no_credits(
    db_session: Session, machine_c, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-004 and OQ-8 ``A_flag_with_fair_use``: a flag, never a numeric sentinel."""
    monkeypatch.setattr(machine_c, "subscription_studio_fair_use_exports_per_period", 60)
    user = _user(db_session)
    _customer(db_session, user)

    intake = _deliver(
        db_session, "evt_1", "invoice.paid", _invoice("in_1", "sub_1", user.id, tier="studio")
    )

    assert _disposition(intake) == ("processed", None)
    (grant,) = _grants(db_session)
    assert (grant.tier, grant.unlimited, grant.credits, grant.fair_use_export_cap) == (
        "studio",
        True,
        0,
        60,
    )
    assert grant.ledger_entry_id is None
    assert _ledger_grants(db_session, user) == []
    assert credit_balance(db_session, user.id) == 0
    # Still the subscription's first paid invoice: one verified purchase (OQ-3).
    assert len(_legacy_purchases(db_session)) == 1


def test_an_invoice_before_the_subscription_event_creates_the_record(
    db_session: Session, machine_c
) -> None:
    """EC-2: the invoice may arrive first; the later, older created event is stale."""
    user = _user(db_session)
    _customer(db_session, user)

    paid = _deliver(
        db_session, "evt_inv", "invoice.paid", _invoice("in_1", "sub_1", user.id), created=TS + 5
    )
    late = _deliver(
        db_session,
        "evt_created",
        "customer.subscription.created",
        _subscription("sub_1", user.id, status="incomplete"),
        created=TS,
    )

    assert _disposition(paid) == ("processed", None)
    assert _disposition(late) == ("duplicate", "STALE_EVENT")
    record = _record(db_session, "sub_1")
    assert (record.status, record.tier) == ("active", "core")
    assert credit_balance(db_session, user.id) == 25


def test_the_newer_invoice_shape_is_understood(db_session: Session, machine_c) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    obj = _invoice("in_1", "sub_1", user.id)
    del obj["subscription"]
    obj["parent"] = {
        "type": "subscription_details",
        "subscription_details": {"subscription": "sub_1"},
    }
    line = obj["lines"]["data"][0]
    del line["price"]
    line["pricing"] = {"type": "price_details", "price_details": {"price": PRICES["pro"]}}

    intake = _deliver(db_session, "evt_1", "invoice.paid", obj)

    assert _disposition(intake) == ("processed", None)
    (grant,) = _grants(db_session)
    assert (grant.grant_key, grant.tier) == (subscription_period_key("sub_1", P1), "pro")


INVOICE_UNRESOLVED = [
    ("unknown-customer", {"customer": "cus_nobody"}, "CUSTOMER_NOT_FOUND"),
    ("not-paid", {"status": "open"}, "INVOICE_NOT_PAID"),
    ("not-an-invoice", {"object": "charge"}, "EVENT_PAYLOAD_MALFORMED"),
    ("no-subscription", {"subscription": None}, "INVOICE_NOT_SUBSCRIPTION"),
    ("zero-amount", {"amount_paid": 0}, "INVOICE_AMOUNT_ZERO"),
    ("bad-amount", {"amount_paid": "499"}, "EVENT_PAYLOAD_MALFORMED"),
    (
        "unknown-price",
        {"lines": {"data": [{"price": {"id": "price_x"}, "period": {"start": P1, "end": P1 + 1}}]}},
        "PRICE_UNKNOWN",
    ),
    ("no-lines", {"lines": {"data": []}}, "INVOICE_LINES_UNSUPPORTED"),
    ("lines-missing", {"lines": None}, "EVENT_PAYLOAD_MALFORMED"),
    (
        "two-priced-lines",
        {
            "lines": {
                "data": [
                    {"price": {"id": PRICES["core"]}, "period": {"start": P1, "end": P1 + 1}},
                    {"price": {"id": PRICES["pro"]}, "period": {"start": P1, "end": P1 + 1}},
                ]
            }
        },
        "INVOICE_LINES_UNSUPPORTED",
    ),
    (
        "no-period",
        {"lines": {"data": [{"price": {"id": PRICES["core"]}}]}},
        "PERIOD_MALFORMED",
    ),
]


@pytest.mark.parametrize(
    ("change", "reason"),
    [(case[1], case[2]) for case in INVOICE_UNRESOLVED],
    ids=[case[0] for case in INVOICE_UNRESOLVED],
)
def test_an_unmappable_invoice_is_unresolved_and_grants_nothing(
    db_session: Session, machine_c, change: dict[str, Any], reason: str
) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    obj = _invoice("in_1", "sub_1", user.id)
    obj.update(change)

    intake = _deliver(db_session, "evt_bad", "invoice.paid", obj)

    assert _disposition(intake) == ("unresolved", reason)
    assert db_session.query(ProviderSubscriptionRecord).count() == 0
    assert _nothing_granted(db_session)


def test_an_invoice_for_another_customers_subscription_is_unresolved(
    db_session: Session, machine_c
) -> None:
    owner = _user(db_session, "owner")
    other = _user(db_session, "other")
    _customer(db_session, owner)
    _customer(db_session, other)
    _deliver(db_session, "evt_1", "customer.subscription.created", _subscription("sub_1", owner.id))

    intake = _deliver(db_session, "evt_2", "invoice.paid", _invoice("in_1", "sub_1", other.id))

    assert _disposition(intake) == ("unresolved", "CUSTOMER_MISMATCH")
    assert _nothing_granted(db_session)


def test_an_invalid_tier_configuration_is_unresolved(
    db_session: Session, machine_c, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(machine_c, "subscription_credits_core", 0)
    user = _user(db_session)
    _customer(db_session, user)

    intake = _deliver(db_session, "evt_1", "invoice.paid", _invoice("in_1", "sub_1", user.id))

    assert _disposition(intake) == ("unresolved", "TIER_CONFIG_INVALID")
    assert _nothing_granted(db_session)


def test_a_grant_is_append_only(db_session: Session, machine_c) -> None:
    user = _user(db_session)
    _customer(db_session, user)
    _deliver(db_session, "evt_1", "invoice.paid", _invoice("in_1", "sub_1", user.id))
    (grant,) = _grants(db_session)

    grant.credits = 999
    with pytest.raises(ValueError, match="append-only"):
        db_session.flush()
    db_session.rollback()


# --- cancel_requested ---------------------------------------------------------------------


def _active(db_session: Session, user: User, **overrides: Any) -> None:
    _customer(db_session, user)
    _deliver(
        db_session,
        "evt_active",
        "customer.subscription.created",
        _subscription("sub_1", user.id, **overrides),
    )


def test_cancel_sets_cancel_at_period_end_at_the_provider_and_locally(
    db_session: Session, machine_c
) -> None:
    user = _user(db_session)
    _active(db_session, user)
    provider = FakeSubscriptionProvider()

    record = request_subscription_cancel(
        db_session, user=user, provider=provider, app_settings=_c_settings()
    )
    db_session.commit()

    assert provider.calls == [
        (
            "cancel",
            {
                "subscription_id": "sub_1",
                "idempotency_key": "patchhive-subscription-cancel:sub_1",
            },
        )
    ]
    assert (record.cancel_at_period_end, record.status) == (True, "active")
    # Cancelling again is a no-op with no provider call.
    request_subscription_cancel(
        db_session, user=user, provider=provider, app_settings=_c_settings()
    )
    assert len(provider.calls) == 1


def test_cancel_is_refused_without_an_active_subscription(db_session: Session, machine_c) -> None:
    user = _user(db_session)
    provider = FakeSubscriptionProvider()
    with pytest.raises(SubscriptionRefusedError) as missing:
        request_subscription_cancel(
            db_session, user=user, provider=provider, app_settings=_c_settings()
        )
    assert (missing.value.code, missing.value.status_code) == ("SUBSCRIPTION_NOT_FOUND", 404)

    _active(db_session, user, status="past_due")
    with pytest.raises(SubscriptionRefusedError) as not_active:
        request_subscription_cancel(
            db_session, user=user, provider=provider, app_settings=_c_settings()
        )
    assert (not_active.value.code, not_active.value.status_code) == (
        "SUBSCRIPTION_NOT_ACTIVE",
        409,
    )
    assert provider.calls == []


def test_cancel_is_refused_when_subscriptions_are_off(db_session: Session, machine_c) -> None:
    user = _user(db_session)
    _active(db_session, user)
    provider = FakeSubscriptionProvider()
    with pytest.raises(CheckoutUnavailableError, match="PAYMENTS_DISABLED"):
        request_subscription_cancel(
            db_session,
            user=user,
            provider=provider,
            app_settings=_c_settings(enable_subscription_checkout=False),
        )
    assert provider.calls == []


def test_cancel_fails_closed_when_the_provider_does_not_confirm(
    db_session: Session, machine_c
) -> None:
    user = _user(db_session)
    _active(db_session, user)
    provider = FakeSubscriptionProvider(cancel_body={"id": "sub_1", "cancel_at_period_end": False})

    with pytest.raises(PaymentProviderError):
        request_subscription_cancel(
            db_session, user=user, provider=provider, app_settings=_c_settings()
        )
    db_session.rollback()
    assert _record(db_session, "sub_1").cancel_at_period_end is False
