"""Spec 004 Machine B: one-time credit checkout (T046).

``start_credit_checkout`` is the ``request_credits`` row: behind ``checkout_gate`` (the
payments flag, the production activation flag and a test-mode key), it gets or creates
the user's one provider customer (FR-020), creates a provider Checkout Session and writes
a ``ProviderPaymentRecord`` in state ``open``.

``handle_checkout_session_event`` is the webhook side. It runs inside
``process_stripe_event``'s savepoint, so everything it writes commits with the event
record or not at all:

- ``checkout.session.completed`` with ``payment_status == "paid"`` and
  ``checkout.session.async_payment_succeeded`` credit: one canonical ``purchase`` entry
  keyed ``purchase:<payment_id>`` plus ``record_purchase(payment_verified=True)``, which
  evaluates the referral reward (FR-011, FR-028, Machine A).
- ``checkout.session.completed`` with ``payment_status == "unpaid"`` (a delayed payment
  method) moves the record to ``pending`` and credits nothing yet.
- ``checkout.session.async_payment_failed`` marks the record ``failed`` and
  ``checkout.session.expired`` marks it ``abandoned``; neither writes a ledger entry.
- A repeated effect is ``duplicate`` (FR-012). Anything the record cannot vouch for is
  ``unresolved`` with a reason code and grants nothing (FR-014).

The user, credit count and amount come from the payment record the server wrote, never
from event metadata; the metadata only has to agree with it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Protocol

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderPaymentRecord,
)
from canon.webhook_events import EventDisposition, UnresolvedEventError
from community.models import User
from monetization.referrals import record_purchase

# An input bound for one checkout, not a spec price rule.
MAX_CREDITS_PER_CHECKOUT = 1000
TEST_KEY_PREFIXES = ("sk_test_", "rk_test_")
PURCHASE_TYPE = "one_time"

CHECKOUT_COMPLETED = "checkout.session.completed"
ASYNC_PAYMENT_SUCCEEDED = "checkout.session.async_payment_succeeded"
ASYNC_PAYMENT_FAILED = "checkout.session.async_payment_failed"
CHECKOUT_EXPIRED = "checkout.session.expired"
CHECKOUT_EVENT_TYPES = frozenset(
    {CHECKOUT_COMPLETED, ASYNC_PAYMENT_SUCCEEDED, ASYNC_PAYMENT_FAILED, CHECKOUT_EXPIRED}
)

OPEN_STATUSES = frozenset({"open", "pending"})
CLOSED_STATUSES = frozenset({"failed", "abandoned"})


class CheckoutUnavailableError(Exception):
    """Checkout is refused before any provider call. ``code`` is safe to return."""

    def __init__(self, code: str, *, status_code: int = 403) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class PaymentProviderError(Exception):
    """The provider call failed. The message never carries the secret key."""


@dataclass(frozen=True)
class ProviderCheckoutSession:
    id: str
    url: str


class CheckoutProvider(Protocol):
    def create_customer(self, *, user_id: int, idempotency_key: str) -> str: ...

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        user_id: int,
        payment_record_id: str,
        credits: int,
        amount_cents: int,
        currency: str,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> ProviderCheckoutSession: ...


class StripeCheckoutProvider:
    """Minimal Stripe REST client for the two calls Machine B makes.

    The customer carries only the PatchHive user id (no email or name): disclosure to
    the provider is NOT_COMPUTABLE in the spec, so the least is sent.
    """

    def __init__(
        self,
        secret_key: str,
        *,
        api_base: str = "https://api.stripe.com",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._secret_key = secret_key
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    def _post(self, path: str, form: dict[str, str], idempotency_key: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._secret_key}",
            "Idempotency-Key": idempotency_key,
        }
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.post(f"{self._api_base}{path}", data=form, headers=headers)
        except httpx.HTTPError as exc:
            raise PaymentProviderError(f"provider request failed: {type(exc).__name__}") from None
        if response.status_code >= 400:
            raise PaymentProviderError(f"provider answered {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            raise PaymentProviderError("provider answered with a non-JSON body") from None
        if not isinstance(body, dict):
            raise PaymentProviderError("provider answered with an unexpected body")
        return body

    def create_customer(self, *, user_id: int, idempotency_key: str) -> str:
        body = self._post("/v1/customers", {"metadata[user_id]": str(user_id)}, idempotency_key)
        customer_id = body.get("id")
        if not isinstance(customer_id, str) or not customer_id:
            raise PaymentProviderError("provider returned no customer id")
        return customer_id

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        user_id: int,
        payment_record_id: str,
        credits: int,
        amount_cents: int,
        currency: str,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> ProviderCheckoutSession:
        form = {
            "mode": "payment",
            "customer": customer_id,
            "client_reference_id": str(user_id),
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": currency,
            "line_items[0][price_data][unit_amount]": str(amount_cents),
            "line_items[0][price_data][product_data][name]": f"{credits} PatchHive credits",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata[user_id]": str(user_id),
            "metadata[credits]": str(credits),
            "metadata[purchase_type]": PURCHASE_TYPE,
            "metadata[payment_record_id]": payment_record_id,
        }
        body = self._post("/v1/checkout/sessions", form, idempotency_key)
        session_id, url = body.get("id"), body.get("url")
        if not isinstance(session_id, str) or not session_id or not isinstance(url, str) or not url:
            raise PaymentProviderError("provider returned no checkout session")
        return ProviderCheckoutSession(id=session_id, url=url)


def credit_charge_cents(credits: int, *, price_cents: int, minimum_cents: int) -> int:
    """OQ-1 (provisional): ``max(minimum, credits * price)``, the observed rule."""

    if credits < 1:
        raise ValueError("credits must be positive")
    return max(minimum_cents, credits * price_cents)


def checkout_gate(app_settings: Any) -> None:
    """Refuse checkout unless payments are on, allowed here, and the key is safe.

    - ``ENABLE_CREDIT_CHECKOUT`` off: ``PAYMENTS_DISABLED`` (FR-019).
    - Production without ``ALLOW_PRODUCTION_PAYMENTS``: ``PRODUCTION_PAYMENTS_DISABLED``.
    - No secret key: ``STRIPE_SECRET_KEY_MISSING``.
    - A non-test key while ``STRIPE_TEST_MODE=true``, or anywhere production payments are
      not activated: ``LIVE_KEY_REFUSED``.
    """

    if not bool(getattr(app_settings, "enable_credit_checkout", False)):
        raise CheckoutUnavailableError("PAYMENTS_DISABLED")
    production = str(getattr(app_settings, "environment", "")).strip().lower() == "production"
    allow = bool(getattr(app_settings, "allow_production_payments", False))
    if production and not allow:
        raise CheckoutUnavailableError("PRODUCTION_PAYMENTS_DISABLED")
    key = str(getattr(app_settings, "stripe_secret_key", "") or "").strip()
    if not key:
        raise CheckoutUnavailableError("STRIPE_SECRET_KEY_MISSING", status_code=503)
    test_mode = bool(getattr(app_settings, "stripe_test_mode", True))
    live_allowed = production and allow and not test_mode
    if not live_allowed and not key.startswith(TEST_KEY_PREFIXES):
        raise CheckoutUnavailableError("LIVE_KEY_REFUSED", status_code=503)


def get_or_create_customer(
    session: Session, *, user: User, provider: CheckoutProvider
) -> ProviderCustomerRecord:
    """Return the user's one provider customer link, creating it on first use (FR-020)."""

    link = session.query(ProviderCustomerRecord).filter_by(user_id=user.id).one_or_none()
    if link is not None:
        return link
    # The provider idempotency key makes two concurrent first checkouts get one customer.
    customer_id = provider.create_customer(
        user_id=user.id, idempotency_key=f"patchhive-customer:{user.id}"
    )
    link = ProviderCustomerRecord(
        user_id=user.id,
        provider_customer_id=customer_id,
        created_at=datetime.now(timezone.utc),
    )
    try:
        with session.begin_nested():
            session.add(link)
            session.flush()
    except IntegrityError:
        winner = session.query(ProviderCustomerRecord).filter_by(user_id=user.id).one_or_none()
        if winner is None:
            raise
        return winner
    return link


@dataclass(frozen=True)
class StartedCheckout:
    payment: ProviderPaymentRecord
    checkout_url: str


def start_credit_checkout(
    session: Session,
    *,
    user: User,
    credits: int,
    provider: CheckoutProvider,
    app_settings: Any,
) -> StartedCheckout:
    """Machine B ``NONE --request_credits--> CheckoutOpen``. The caller commits."""

    checkout_gate(app_settings)
    if not 1 <= credits <= MAX_CREDITS_PER_CHECKOUT:
        raise ValueError("credits out of range")
    amount = credit_charge_cents(
        credits,
        price_cents=int(app_settings.credit_price_cents),
        minimum_cents=int(app_settings.credit_minimum_charge_cents),
    )
    currency = str(app_settings.credit_currency).strip().lower()
    customer = get_or_create_customer(session, user=user, provider=provider)
    record_id = f"pay-{uuid.uuid4().hex}"
    base = str(app_settings.frontend_base_url).rstrip("/")
    created = provider.create_checkout_session(
        customer_id=customer.provider_customer_id,
        user_id=user.id,
        payment_record_id=record_id,
        credits=credits,
        amount_cents=amount,
        currency=currency,
        success_url=f"{base}/account?checkout=success",
        cancel_url=f"{base}/account?checkout=canceled",
        idempotency_key=f"patchhive-checkout:{record_id}",
    )
    now = datetime.now(timezone.utc)
    payment = ProviderPaymentRecord(
        id=record_id,
        user_id=user.id,
        checkout_session_id=created.id,
        provider_payment_id=None,
        credits=credits,
        amount_cents=amount,
        currency=currency,
        status="open",
        created_at=now,
        updated_at=now,
    )
    session.add(payment)
    session.flush()
    return StartedCheckout(payment=payment, checkout_url=created.url)


def purchase_key(payment_id: str) -> str:
    return f"purchase:{payment_id}"


def _object_id(value: Any) -> str | None:
    """A provider reference is a bare id or, when expanded, an object with ``id``."""

    if isinstance(value, dict):
        value = value.get("id")
    if isinstance(value, str) and value:
        return value
    return None


def _check_record_matches(
    session: Session, payment: ProviderPaymentRecord, obj: dict[str, Any]
) -> None:
    metadata = obj.get("metadata")
    if not isinstance(metadata, dict):
        raise UnresolvedEventError("METADATA_MALFORMED")
    if (
        metadata.get("user_id") != str(payment.user_id)
        or metadata.get("credits") != str(payment.credits)
        or metadata.get("purchase_type") != PURCHASE_TYPE
    ):
        raise UnresolvedEventError("METADATA_MALFORMED")
    link = session.query(ProviderCustomerRecord).filter_by(user_id=payment.user_id).one_or_none()
    if link is None:
        raise UnresolvedEventError("CUSTOMER_NOT_FOUND")
    if _object_id(obj.get("customer")) != link.provider_customer_id:
        raise UnresolvedEventError("CUSTOMER_MISMATCH")


def _touch(payment: ProviderPaymentRecord, status: str) -> None:
    payment.status = status
    payment.updated_at = datetime.now(timezone.utc)


def _credit(
    session: Session, payment: ProviderPaymentRecord, obj: dict[str, Any]
) -> EventDisposition:
    """Machine B ``CheckoutOpen --checkout_completed--> Credited``."""

    if payment.status == "credited":
        return EventDisposition("duplicate", "PAYMENT_ALREADY_RECORDED")
    if payment.status in CLOSED_STATUSES:
        # Illegal Abandoned -> Credited, yet the provider says it was paid: an operator
        # must look (spec 004 Machine B illegal transitions).
        raise UnresolvedEventError("PAYMENT_STATE_CONFLICT")
    if obj.get("amount_total") != payment.amount_cents or (
        str(obj.get("currency") or "").lower() != payment.currency
    ):
        raise UnresolvedEventError("AMOUNT_MISMATCH")
    payment_id = _object_id(obj.get("payment_intent"))
    if payment_id is None:
        raise UnresolvedEventError("PAYMENT_ID_MISSING")
    if payment.provider_payment_id not in (None, payment_id):
        raise UnresolvedEventError("PAYMENT_ID_MISMATCH")
    other = (
        session.query(ProviderPaymentRecord)
        .filter(
            ProviderPaymentRecord.provider_payment_id == payment_id,
            ProviderPaymentRecord.id != payment.id,
        )
        .first()
    )
    if other is not None:
        raise UnresolvedEventError("PAYMENT_ID_CONFLICT")
    key = purchase_key(payment_id)
    if session.query(CanonicalCreditLedgerEntryRecord).filter_by(idempotency_key=key).first():
        # The ledger has the purchase but the record is not credited: inconsistent state.
        raise UnresolvedEventError("LEDGER_ENTRY_CONFLICT")
    user = session.get(User, payment.user_id)
    if user is None:
        raise UnresolvedEventError("USER_NOT_FOUND")

    now = datetime.now(timezone.utc)
    session.add(
        CanonicalCreditLedgerEntryRecord(
            id=f"purchase-{sha256(key.encode('utf-8')).hexdigest()[:24]}",
            user_id=payment.user_id,
            delta=payment.credits,
            entry_type="purchase",
            idempotency_key=key,
            export_id=None,
            created_at=now,
        )
    )
    # The single purchase-recording path: the legacy Purchase row and Machine A.
    record_purchase(
        session,
        user=user,
        credits_delta=payment.credits,
        notes=f"Provider purchase: {payment_id}",
        payment_verified=True,
    )
    payment.provider_payment_id = payment_id
    payment.credited_at = now
    _touch(payment, "credited")
    session.flush()
    return EventDisposition("processed")


def handle_checkout_session_event(session: Session, event: dict[str, Any]) -> EventDisposition:
    """Apply one verified Checkout Session event to its payment record."""

    event_type = event.get("type")
    obj = event["data"]["object"]
    session_id = obj.get("id")
    if event_type not in CHECKOUT_EVENT_TYPES or not isinstance(session_id, str) or not session_id:
        raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")
    mode = obj.get("mode")
    if mode == "subscription":
        # Machine C (T049) is not built; fail closed.
        return EventDisposition("unresolved", "HANDLER_NOT_IMPLEMENTED")
    if mode != "payment":
        raise UnresolvedEventError("CHECKOUT_MODE_UNKNOWN")

    payment = (
        session.query(ProviderPaymentRecord)
        .filter_by(checkout_session_id=session_id)
        .with_for_update()
        .one_or_none()
    )
    if payment is None:
        raise UnresolvedEventError("PAYMENT_RECORD_NOT_FOUND")
    _check_record_matches(session, payment, obj)
    payment_status = obj.get("payment_status")

    if event_type in (CHECKOUT_COMPLETED, ASYNC_PAYMENT_SUCCEEDED):
        if payment_status == "paid":
            return _credit(session, payment, obj)
        if event_type == CHECKOUT_COMPLETED and payment_status == "unpaid":
            # A delayed payment method: wait for async_payment_succeeded or _failed.
            if payment.status == "open":
                pending_id = _object_id(obj.get("payment_intent"))
                if pending_id is not None and payment.provider_payment_id is None:
                    taken = (
                        session.query(ProviderPaymentRecord)
                        .filter(
                            ProviderPaymentRecord.provider_payment_id == pending_id,
                            ProviderPaymentRecord.id != payment.id,
                        )
                        .first()
                    )
                    if taken is not None:
                        raise UnresolvedEventError("PAYMENT_ID_CONFLICT")
                    payment.provider_payment_id = pending_id
                _touch(payment, "pending")
                session.flush()
                return EventDisposition("processed")
            # Already pending, or the async outcome arrived first.
            return EventDisposition("duplicate", "CHECKOUT_ALREADY_ADVANCED")
        raise UnresolvedEventError("PAYMENT_STATUS_UNEXPECTED")

    target = "failed" if event_type == ASYNC_PAYMENT_FAILED else "abandoned"
    if payment.status in OPEN_STATUSES:
        _touch(payment, target)
        session.flush()
        return EventDisposition("processed")
    if payment.status in CLOSED_STATUSES:
        return EventDisposition("duplicate", "CHECKOUT_ALREADY_CLOSED")
    # Credited and then reported failed or expired: an operator must look.
    raise UnresolvedEventError("PAYMENT_STATE_CONFLICT")
