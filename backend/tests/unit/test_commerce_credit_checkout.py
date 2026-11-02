"""Spec 004 T046, Machine B: one-time credit checkout.

Checkout opens behind the payments flag with a fake provider; fulfillment runs through
signed fixture webhook events (``receive_stripe_webhook``). No network, no live keys.
"""

from __future__ import annotations

import hashlib
import hmac
import itertools
import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

import canon.checkout as checkout
from canon.checkout import (
    CheckoutUnavailableError,
    PaymentProviderError,
    ProviderCheckoutSession,
    StripeCheckoutProvider,
    checkout_gate,
    credit_charge_cents,
    get_or_create_customer,
    start_credit_checkout,
)
from canon.exports import credit_balance, receive_stripe_webhook
from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderPaymentRecord,
    StripeEventRecordModel,
)
from community.models import User
from core.config import Settings
from monetization.models import CreditsLedger, Referral
from monetization.referrals import REFERRAL_REWARD_CREDITS, create_referral

TS = 1_700_000_000
SECRET = "whsec_machine_b"
_SESSION_IDS = itertools.count(1)


def _settings(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "enable_credit_checkout": True,
        "environment": "development",
        "allow_production_payments": False,
        "stripe_test_mode": True,
        "stripe_secret_key": "sk_test_fixture",
        "credit_price_cents": 20,
        "credit_minimum_charge_cents": 500,
        "credit_currency": "usd",
        "frontend_base_url": "https://app.example.test",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeProvider:
    def __init__(self) -> None:
        self.customers: list[dict[str, Any]] = []
        self.sessions: list[dict[str, Any]] = []

    def create_customer(self, *, user_id: int, idempotency_key: str) -> str:
        self.customers.append({"user_id": user_id, "idempotency_key": idempotency_key})
        return f"cus_{user_id}"

    def create_checkout_session(self, **kwargs: Any) -> ProviderCheckoutSession:
        self.sessions.append(kwargs)
        index = next(_SESSION_IDS)
        return ProviderCheckoutSession(
            id=f"cs_test_{index}", url=f"https://checkout.example.test/{index}"
        )


def _user(session: Session, name: str = "buyer") -> User:
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


def _open_checkout(session: Session, user: User, credits: int = 30) -> ProviderPaymentRecord:
    started = start_credit_checkout(
        session, user=user, credits=credits, provider=FakeProvider(), app_settings=_settings()
    )
    session.commit()
    return started.payment


def _session_object(payment: ProviderPaymentRecord, **overrides: Any) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "id": payment.checkout_session_id,
        "object": "checkout.session",
        "mode": "payment",
        "customer": f"cus_{payment.user_id}",
        "payment_intent": f"pi_{payment.checkout_session_id}",
        "payment_status": "paid",
        "amount_total": payment.amount_cents,
        "currency": payment.currency,
        "metadata": {
            "user_id": str(payment.user_id),
            "credits": str(payment.credits),
            "purchase_type": "one_time",
            "payment_record_id": payment.id,
        },
    }
    obj.update(overrides)
    return obj


def _deliver(session: Session, event_id: str, event_type: str, obj: dict[str, Any]):
    payload = json.dumps(
        {"id": event_id, "type": event_type, "livemode": False, "data": {"object": obj}}
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


def _purchases(session: Session) -> list[CanonicalCreditLedgerEntryRecord]:
    return session.query(CanonicalCreditLedgerEntryRecord).filter_by(entry_type="purchase").all()


def _legacy_purchases(session: Session) -> int:
    return session.query(CreditsLedger).filter_by(change_type="Purchase").count()


# --- request_credits -------------------------------------------------------------------


@pytest.mark.parametrize(("credits", "cents"), [(1, 500), (25, 500), (26, 520), (100, 2000)])
def test_the_charge_is_twenty_cents_a_credit_with_a_five_dollar_minimum(credits, cents) -> None:
    """OQ-1 (provisional) and the observed rule ``max(500, credits * 20)``."""
    assert credit_charge_cents(credits, price_cents=20, minimum_cents=500) == cents


def test_payments_flags_keep_their_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ENABLE_CREDIT_CHECKOUT",
        "STRIPE_SECRET_KEY",
        "STRIPE_TEST_MODE",
        "ALLOW_PRODUCTION_PAYMENTS",
    ):
        monkeypatch.delenv(name, raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.enable_credit_checkout is False
    assert defaults.stripe_test_mode is True
    assert defaults.allow_production_payments is False
    assert defaults.stripe_secret_key == ""
    with pytest.raises(CheckoutUnavailableError, match="PAYMENTS_DISABLED"):
        checkout_gate(defaults)


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"enable_credit_checkout": False}, "PAYMENTS_DISABLED"),
        ({"environment": "production"}, "PRODUCTION_PAYMENTS_DISABLED"),
        ({"stripe_secret_key": ""}, "STRIPE_SECRET_KEY_MISSING"),
        ({"stripe_secret_key": "sk_live_fixture"}, "LIVE_KEY_REFUSED"),
        ({"stripe_secret_key": "rk_live_fixture"}, "LIVE_KEY_REFUSED"),
        # Test mode off outside production still refuses a live key.
        ({"stripe_test_mode": False, "stripe_secret_key": "sk_live_x"}, "LIVE_KEY_REFUSED"),
        # Production with payments allowed but still in test mode: test keys only.
        (
            {
                "environment": "production",
                "allow_production_payments": True,
                "stripe_secret_key": "sk_live_x",
            },
            "LIVE_KEY_REFUSED",
        ),
    ],
)
def test_checkout_is_refused_before_any_provider_call(
    db_session: Session, overrides: dict[str, Any], code: str
) -> None:
    user = _user(db_session)
    provider = FakeProvider()
    with pytest.raises(CheckoutUnavailableError, match=code):
        start_credit_checkout(
            db_session,
            user=user,
            credits=30,
            provider=provider,
            app_settings=_settings(**overrides),
        )
    assert provider.customers == [] and provider.sessions == []
    assert db_session.query(ProviderPaymentRecord).count() == 0
    assert db_session.query(ProviderCustomerRecord).count() == 0


@pytest.mark.parametrize("key", ["sk_test_fixture", "rk_test_fixture"])
def test_a_test_key_passes_the_gate(key: str) -> None:
    checkout_gate(_settings(stripe_secret_key=key))


def test_opening_a_checkout_writes_an_open_record_and_grants_nothing(db_session: Session) -> None:
    user = _user(db_session)
    provider = FakeProvider()

    started = start_credit_checkout(
        db_session, user=user, credits=30, provider=provider, app_settings=_settings()
    )
    db_session.commit()

    payment = started.payment
    assert (payment.status, payment.credits, payment.amount_cents, payment.currency) == (
        "open",
        30,
        600,
        "usd",
    )
    assert payment.provider_payment_id is None
    assert (
        started.checkout_url == f"https://checkout.example.test/{payment.checkout_session_id[8:]}"
    )
    (sent,) = provider.sessions
    assert sent["customer_id"] == f"cus_{user.id}"
    assert sent["payment_record_id"] == payment.id
    assert (sent["credits"], sent["amount_cents"]) == (30, 600)
    assert sent["success_url"].startswith("https://app.example.test/")
    assert sent["cancel_url"].startswith("https://app.example.test/")
    assert credit_balance(db_session, user.id) == 0
    assert _legacy_purchases(db_session) == 0


@pytest.mark.parametrize("credits", [0, -1, checkout.MAX_CREDITS_PER_CHECKOUT + 1])
def test_an_invalid_quantity_is_refused(db_session: Session, credits: int) -> None:
    user = _user(db_session)
    provider = FakeProvider()
    with pytest.raises(ValueError):
        start_credit_checkout(
            db_session, user=user, credits=credits, provider=provider, app_settings=_settings()
        )
    assert provider.sessions == []


def test_a_user_gets_one_provider_customer(db_session: Session) -> None:
    """FR-020: the second checkout reuses the link and makes no customer call."""
    user = _user(db_session)
    provider = FakeProvider()
    for _ in range(2):
        start_credit_checkout(
            db_session, user=user, credits=30, provider=provider, app_settings=_settings()
        )
        db_session.commit()

    assert len(provider.customers) == 1
    assert provider.customers[0]["idempotency_key"] == f"patchhive-customer:{user.id}"
    assert db_session.query(ProviderCustomerRecord).count() == 1
    assert db_session.query(ProviderPaymentRecord).count() == 2


def test_a_concurrent_first_checkout_keeps_the_winning_customer_link(db_session: Session) -> None:
    user = _user(db_session)

    class RacingProvider(FakeProvider):
        def create_customer(self, *, user_id: int, idempotency_key: str) -> str:
            # Another request links the user while this one waits on the provider.
            db_session.add(ProviderCustomerRecord(user_id=user_id, provider_customer_id="cus_w"))
            db_session.flush()
            return "cus_loser"

    link = get_or_create_customer(db_session, user=user, provider=RacingProvider())
    db_session.commit()

    assert link.provider_customer_id == "cus_w"
    assert db_session.query(ProviderCustomerRecord).count() == 1


# --- checkout_completed and the async outcomes ----------------------------------------


def test_a_paid_completion_credits_once_through_the_purchase_path(db_session: Session) -> None:
    user = _user(db_session)
    payment = _open_checkout(db_session, user, credits=30)

    intake = _deliver(
        db_session, "evt_paid", "checkout.session.completed", _session_object(payment)
    )

    assert (intake.record.status, intake.record.reason_code) == ("processed", None)
    assert intake.record.object_id == payment.checkout_session_id
    (entry,) = _purchases(db_session)
    payment_id = f"pi_{payment.checkout_session_id}"
    assert (entry.user_id, entry.delta, entry.idempotency_key) == (
        user.id,
        30,
        f"purchase:{payment_id}",
    )
    assert credit_balance(db_session, user.id) == 30
    legacy = db_session.query(CreditsLedger).filter_by(change_type="Purchase").one()
    assert (legacy.user_id, legacy.credits_delta) == (user.id, 30)
    db_session.refresh(payment)
    assert (payment.status, payment.provider_payment_id) == ("credited", payment_id)
    assert payment.credited_at is not None


def test_a_duplicate_delivery_credits_nothing_more(db_session: Session) -> None:
    """FR-012: the same event id, then a new event id for the same payment."""
    user = _user(db_session)
    payment = _open_checkout(db_session, user)
    obj = _session_object(payment)

    _deliver(db_session, "evt_a", "checkout.session.completed", obj)
    again = _deliver(db_session, "evt_a", "checkout.session.completed", obj)
    other = _deliver(db_session, "evt_b", "checkout.session.async_payment_succeeded", obj)

    assert again.duplicate is True
    assert (other.record.status, other.record.reason_code) == (
        "duplicate",
        "PAYMENT_ALREADY_RECORDED",
    )
    assert len(_purchases(db_session)) == 1
    assert _legacy_purchases(db_session) == 1
    assert credit_balance(db_session, user.id) == payment.credits


def test_an_unpaid_completion_waits_then_async_success_credits(db_session: Session) -> None:
    user = _user(db_session)
    payment = _open_checkout(db_session, user)

    first = _deliver(
        db_session,
        "evt_unpaid",
        "checkout.session.completed",
        _session_object(payment, payment_status="unpaid"),
    )
    db_session.refresh(payment)
    assert first.record.status == "processed"
    assert payment.status == "pending"
    assert _purchases(db_session) == []

    settled = _deliver(
        db_session,
        "evt_settled",
        "checkout.session.async_payment_succeeded",
        _session_object(payment),
    )
    db_session.refresh(payment)
    assert settled.record.status == "processed"
    assert payment.status == "credited"
    assert len(_purchases(db_session)) == 1


def test_an_async_success_before_the_unpaid_completion_still_credits_once(
    db_session: Session,
) -> None:
    """Delivery order is not guaranteed."""
    user = _user(db_session)
    payment = _open_checkout(db_session, user)

    _deliver(
        db_session, "evt_s", "checkout.session.async_payment_succeeded", _session_object(payment)
    )
    late = _deliver(
        db_session,
        "evt_late",
        "checkout.session.completed",
        _session_object(payment, payment_status="unpaid"),
    )

    assert (late.record.status, late.record.reason_code) == (
        "duplicate",
        "CHECKOUT_ALREADY_ADVANCED",
    )
    db_session.refresh(payment)
    assert payment.status == "credited"
    assert len(_purchases(db_session)) == 1


def test_an_async_failure_fails_the_payment_without_credit(db_session: Session) -> None:
    user = _user(db_session)
    payment = _open_checkout(db_session, user)
    _deliver(
        db_session,
        "evt_unpaid",
        "checkout.session.completed",
        _session_object(payment, payment_status="unpaid"),
    )

    failed = _deliver(
        db_session,
        "evt_failed",
        "checkout.session.async_payment_failed",
        _session_object(payment, payment_status="unpaid"),
    )
    db_session.refresh(payment)
    assert failed.record.status == "processed"
    assert payment.status == "failed"
    assert _purchases(db_session) == [] and _legacy_purchases(db_session) == 0

    # Illegal Abandoned -> Credited: a later "paid" report goes to an operator.
    late = _deliver(
        db_session, "evt_paid_late", "checkout.session.completed", _session_object(payment)
    )
    assert (late.record.status, late.record.reason_code) == (
        "unresolved",
        "PAYMENT_STATE_CONFLICT",
    )
    db_session.refresh(payment)
    assert payment.status == "failed"
    assert _purchases(db_session) == []


def test_an_expired_session_is_abandoned_without_credit(db_session: Session) -> None:
    user = _user(db_session)
    payment = _open_checkout(db_session, user)
    obj = _session_object(payment, payment_status="unpaid", payment_intent=None)

    expired = _deliver(db_session, "evt_exp", "checkout.session.expired", obj)
    again = _deliver(db_session, "evt_exp2", "checkout.session.expired", obj)

    db_session.refresh(payment)
    assert expired.record.status == "processed"
    assert payment.status == "abandoned"
    assert (again.record.status, again.record.reason_code) == (
        "duplicate",
        "CHECKOUT_ALREADY_CLOSED",
    )
    assert _purchases(db_session) == [] and _legacy_purchases(db_session) == 0
    assert db_session.query(CreditsLedger).count() == 0


def test_a_credited_payment_reported_expired_goes_to_an_operator(db_session: Session) -> None:
    user = _user(db_session)
    payment = _open_checkout(db_session, user)
    _deliver(db_session, "evt_paid", "checkout.session.completed", _session_object(payment))

    late = _deliver(db_session, "evt_exp", "checkout.session.expired", _session_object(payment))

    assert (late.record.status, late.record.reason_code) == (
        "unresolved",
        "PAYMENT_STATE_CONFLICT",
    )
    db_session.refresh(payment)
    assert payment.status == "credited"
    assert len(_purchases(db_session)) == 1


def test_an_expanded_payment_intent_object_is_accepted(db_session: Session) -> None:
    user = _user(db_session)
    payment = _open_checkout(db_session, user)

    _deliver(
        db_session,
        "evt_exp_pi",
        "checkout.session.completed",
        _session_object(payment, payment_intent={"id": "pi_expanded", "object": "payment_intent"}),
    )

    (entry,) = _purchases(db_session)
    assert entry.idempotency_key == "purchase:pi_expanded"


def _metadata(payment: ProviderPaymentRecord, **changes: Any) -> dict[str, Any]:
    metadata = {
        "user_id": str(payment.user_id),
        "credits": str(payment.credits),
        "purchase_type": "one_time",
    }
    metadata.update(changes)
    return metadata


UNRESOLVED_CASES = [
    ("unknown-session", lambda p: {"id": "cs_unknown"}, "PAYMENT_RECORD_NOT_FOUND"),
    ("no-session-id", lambda p: {"id": None}, "EVENT_PAYLOAD_MALFORMED"),
    ("subscription-mode", lambda p: {"mode": "subscription"}, "HANDLER_NOT_IMPLEMENTED"),
    ("no-mode", lambda p: {"mode": None}, "CHECKOUT_MODE_UNKNOWN"),
    ("no-metadata", lambda p: {"metadata": None}, "METADATA_MALFORMED"),
    ("other-user", lambda p: {"metadata": _metadata(p, user_id="999")}, "METADATA_MALFORMED"),
    ("more-credits", lambda p: {"metadata": _metadata(p, credits="9999")}, "METADATA_MALFORMED"),
    (
        "wrong-type",
        lambda p: {"metadata": _metadata(p, purchase_type="subscription")},
        "METADATA_MALFORMED",
    ),
    ("other-customer", lambda p: {"customer": "cus_other"}, "CUSTOMER_MISMATCH"),
    ("other-amount", lambda p: {"amount_total": 1}, "AMOUNT_MISMATCH"),
    ("other-currency", lambda p: {"currency": "eur"}, "AMOUNT_MISMATCH"),
    ("no-payment-id", lambda p: {"payment_intent": None}, "PAYMENT_ID_MISSING"),
    (
        "no-payment-required",
        lambda p: {"payment_status": "no_payment_required"},
        "PAYMENT_STATUS_UNEXPECTED",
    ),
]


@pytest.mark.parametrize(
    ("change", "reason"),
    [(case[1], case[2]) for case in UNRESOLVED_CASES],
    ids=[case[0] for case in UNRESOLVED_CASES],
)
def test_a_malformed_or_unmappable_completion_is_unresolved_and_grants_nothing(
    db_session: Session, change, reason: str
) -> None:
    """FR-014: the payment record, not the event, decides who gets what."""
    user = _user(db_session)
    payment = _open_checkout(db_session, user)

    intake = _deliver(
        db_session,
        "evt_bad",
        "checkout.session.completed",
        _session_object(payment, **change(payment)),
    )

    assert (intake.record.status, intake.record.reason_code) == ("unresolved", reason)
    assert _purchases(db_session) == []
    assert _legacy_purchases(db_session) == 0
    db_session.refresh(payment)
    assert payment.status == "open"
    assert payment.provider_payment_id is None


def test_a_payment_id_already_used_by_another_checkout_is_unresolved(db_session: Session) -> None:
    user = _user(db_session)
    first = _open_checkout(db_session, user)
    second = _open_checkout(db_session, user)
    _deliver(db_session, "evt_1", "checkout.session.completed", _session_object(first))

    clash = _deliver(
        db_session,
        "evt_2",
        "checkout.session.completed",
        _session_object(second, payment_intent=first.provider_payment_id),
    )

    assert (clash.record.status, clash.record.reason_code) == ("unresolved", "PAYMENT_ID_CONFLICT")
    assert len(_purchases(db_session)) == 1


def test_a_referred_users_first_provider_purchase_rewards_the_referrer_once(
    db_session: Session,
) -> None:
    """FR-028: the provider path goes through ``record_purchase`` and Machine A."""
    referrer = _user(db_session, "referrer")
    referred = _user(db_session, "referred")
    create_referral(db_session, referrer=referrer, referred=referred)
    db_session.commit()
    payment = _open_checkout(db_session, referred)
    obj = _session_object(payment)

    _deliver(db_session, "evt_ref", "checkout.session.completed", obj)
    _deliver(db_session, "evt_ref_again", "checkout.session.async_payment_succeeded", obj)

    assert db_session.query(Referral).filter_by(status="Rewarded").count() == 1
    assert credit_balance(db_session, referrer.id) == REFERRAL_REWARD_CREDITS
    assert credit_balance(db_session, referred.id) == payment.credits


def test_a_checkout_event_records_its_object_id_at_intake(db_session: Session) -> None:
    """T048b needs the Checkout Session id to retrieve the object later."""
    _deliver(db_session, "evt_obj", "checkout.session.expired", {"id": "cs_not_ours"})
    record = db_session.get(StripeEventRecordModel, "evt_obj")
    assert record.object_id == "cs_not_ours"
    assert (record.status, record.reason_code) == ("unresolved", "CHECKOUT_MODE_UNKNOWN")


# --- Stripe REST client ---------------------------------------------------------------


def test_the_stripe_client_sends_form_requests_with_idempotency_keys() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/customers":
            return httpx.Response(200, json={"id": "cus_123"})
        return httpx.Response(200, json={"id": "cs_test_9", "url": "https://checkout.test/9"})

    client = StripeCheckoutProvider(
        "sk_test_fixture", api_base="https://stripe.test", transport=httpx.MockTransport(handle)
    )
    assert client.create_customer(user_id=7, idempotency_key="patchhive-customer:7") == "cus_123"
    created = client.create_checkout_session(
        customer_id="cus_123",
        user_id=7,
        payment_record_id="pay-1",
        credits=30,
        amount_cents=600,
        currency="usd",
        success_url="https://app.test/ok",
        cancel_url="https://app.test/no",
        idempotency_key="patchhive-checkout:pay-1",
    )

    assert created == ProviderCheckoutSession(id="cs_test_9", url="https://checkout.test/9")
    customer_req, session_req = seen
    assert customer_req.headers["Authorization"] == "Bearer sk_test_fixture"
    assert customer_req.headers["Idempotency-Key"] == "patchhive-customer:7"
    customer_form = dict(httpx.QueryParams(customer_req.content.decode()))
    # Only the user id goes to the provider: no email or name.
    assert customer_form == {"metadata[user_id]": "7"}
    form = dict(httpx.QueryParams(session_req.content.decode()))
    assert session_req.headers["Idempotency-Key"] == "patchhive-checkout:pay-1"
    assert form["mode"] == "payment"
    assert form["customer"] == "cus_123"
    assert form["line_items[0][price_data][unit_amount]"] == "600"
    assert form["line_items[0][price_data][currency]"] == "usd"
    assert form["metadata[user_id]"] == "7"
    assert form["metadata[credits]"] == "30"
    assert form["metadata[purchase_type]"] == "one_time"


def test_a_provider_error_does_not_leak_the_key() -> None:
    client = StripeCheckoutProvider(
        "sk_test_secretvalue",
        api_base="https://stripe.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(402, json={"error": {}})),
    )
    with pytest.raises(PaymentProviderError) as excinfo:
        client.create_customer(user_id=1, idempotency_key="k")
    assert "sk_test_secretvalue" not in str(excinfo.value)
