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

``handle_payment_reversal_event`` handles refunds and disputes of a credited payment
(spec 004 OQ-2 ``A_reverse_unspent``, T053); see its docstring for the rules.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from canon.exports import _serialize_user_credits, credit_balance
from canon.models import (
    CanonicalAdminAuditEventRecord,
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderPaymentRecord,
    StripeEventRecordModel,
)
from canon.webhook_events import (
    COMMERCE_OPERATOR_ROLES,
    FINAL_EVENT_STATUSES,
    EventDisposition,
    InvalidEventTransitionError,
    UnresolvedEventError,
    _hash_state,
)
from community.models import User
from monetization.referrals import record_purchase

# An input bound for one checkout, not a spec price rule.
MAX_CREDITS_PER_CHECKOUT = 1000
TEST_KEY_PREFIXES = ("sk_test_", "rk_test_")
PURCHASE_TYPE = "one_time"
SUBSCRIPTION_PURCHASE_TYPE = "subscription"

CHECKOUT_COMPLETED = "checkout.session.completed"
ASYNC_PAYMENT_SUCCEEDED = "checkout.session.async_payment_succeeded"
ASYNC_PAYMENT_FAILED = "checkout.session.async_payment_failed"
CHECKOUT_EXPIRED = "checkout.session.expired"
CHECKOUT_EVENT_TYPES = frozenset(
    {CHECKOUT_COMPLETED, ASYNC_PAYMENT_SUCCEEDED, ASYNC_PAYMENT_FAILED, CHECKOUT_EXPIRED}
)

OPEN_STATUSES = frozenset({"open", "pending"})
CLOSED_STATUSES = frozenset({"failed", "abandoned"})
# Credited, then possibly refunded (OQ-2, T053): the purchase entry exists.
CREDITED_STATUSES = frozenset({"credited", "partially_refunded", "refunded"})


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


class CheckoutSessionRetriever(Protocol):
    def retrieve_checkout_session(self, session_id: str) -> dict[str, Any]: ...


class StripeCheckoutProvider:
    """Minimal Stripe REST client for the calls Machine B makes.

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
        return self._request("POST", path, headers=headers, form=form)

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        form: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.request(
                    method, f"{self._api_base}{path}", data=form, headers=headers
                )
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

    def create_subscription_checkout_session(
        self,
        *,
        customer_id: str,
        user_id: int,
        tier: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> ProviderCheckoutSession:
        """Machine C ``choose_tier``: a ``subscription``-mode session for one tier price."""

        form = {
            "mode": "subscription",
            "customer": customer_id,
            "client_reference_id": str(user_id),
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata[user_id]": str(user_id),
            "metadata[tier]": tier,
            "metadata[purchase_type]": SUBSCRIPTION_PURCHASE_TYPE,
            "subscription_data[metadata][user_id]": str(user_id),
            "subscription_data[metadata][tier]": tier,
        }
        body = self._post("/v1/checkout/sessions", form, idempotency_key)
        session_id, url = body.get("id"), body.get("url")
        if not isinstance(session_id, str) or not session_id or not isinstance(url, str) or not url:
            raise PaymentProviderError("provider returned no checkout session")
        return ProviderCheckoutSession(id=session_id, url=url)

    def cancel_subscription_at_period_end(
        self, *, subscription_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        """Machine C ``cancel_requested``: ``cancel_at_period_end=true`` at the provider."""

        path = f"/v1/subscriptions/{quote(subscription_id, safe='')}"
        return self._post(path, {"cancel_at_period_end": "true"}, idempotency_key)

    def retrieve_checkout_session(self, session_id: str) -> dict[str, Any]:
        """``GET /v1/checkout/sessions/{id}``: the session as the provider has it now."""

        path = f"/v1/checkout/sessions/{quote(session_id, safe='')}"
        return self._request("GET", path, headers={"Authorization": f"Bearer {self._secret_key}"})


def credit_charge_cents(credits: int, *, price_cents: int, minimum_cents: int) -> int:
    """OQ-1 (provisional): ``max(minimum, credits * price)``, the observed rule."""

    if credits < 1:
        raise ValueError("credits must be positive")
    return max(minimum_cents, credits * price_cents)


def checkout_gate(app_settings: Any, *, flag: str = "enable_credit_checkout") -> None:
    """Refuse checkout unless payments are on, allowed here, and the key is safe.

    ``flag`` names the machine's own switch: ``enable_credit_checkout`` (Machine B) or
    ``enable_subscription_checkout`` (Machine C, T049). The other refusals are shared.

    - The flag off: ``PAYMENTS_DISABLED`` (FR-019).
    - Production without ``ALLOW_PRODUCTION_PAYMENTS``: ``PRODUCTION_PAYMENTS_DISABLED``.
    - No secret key: ``STRIPE_SECRET_KEY_MISSING``.
    - A non-test key while ``STRIPE_TEST_MODE=true``, or anywhere production payments are
      not activated: ``LIVE_KEY_REFUSED``.
    """

    if not bool(getattr(app_settings, flag, False)):
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

    if payment.status in CREDITED_STATUSES:
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
        # Machine C (T049): a subscription Checkout Session writes nothing. The record
        # comes from ``customer.subscription.*`` and the period grant from
        # ``invoice.paid`` (canon.subscriptions); an expired session is Abandoned with no
        # record.
        return EventDisposition("ignored", "SUBSCRIPTION_SESSION_NO_EFFECT")
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


# --- Refunds and disputes (OQ-2, T053) ---------------------------------------------------

CHARGE_REFUNDED = "charge.refunded"
REFUND_FAILED = "refund.failed"
DISPUTE_CREATED = "charge.dispute.created"


def refund_key(payment_id: str, refunded_cents: int) -> str:
    """One canonical ``refund`` entry per cumulative refunded amount of a payment."""

    return f"purchase-refund:{payment_id}:{refunded_cents}"


def credits_for_refund(*, credits: int, amount_cents: int, refunded_cents: int) -> int:
    """Credits a cumulative refund takes back: ``floor(credits * refunded / amount)``.

    Proportional to the amount paid (the minimum charge included), rounded down, so a
    partial refund never takes back more than its share and a full refund takes back
    exactly ``credits``. It is computed on the cumulative amount, so rounding never adds
    up across several partial refunds.
    """

    if amount_cents <= 0 or credits <= 0:
        raise ValueError("a payment has a positive amount and credit count")
    refunded = max(0, min(refunded_cents, amount_cents))
    return credits * refunded // amount_cents


def _cents(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _locked_payment_by_provider_id(
    session: Session, payment_id: str | None
) -> ProviderPaymentRecord | None:
    if payment_id is None:
        return None
    return (
        session.query(ProviderPaymentRecord)
        .filter_by(provider_payment_id=payment_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )


def _refund(session: Session, obj: dict[str, Any]) -> EventDisposition:
    """``charge.refunded``: reverse the purchase's still-unspent credits (OQ-2)."""

    if obj.get("object", "charge") != "charge":
        raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")
    payment_id = _object_id(obj.get("payment_intent"))
    if payment_id is None:
        raise UnresolvedEventError("PAYMENT_ID_MISSING")
    amount = _cents(obj.get("amount"))
    refunded = _cents(obj.get("amount_refunded"))
    if amount is None or refunded is None:
        raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")
    payment = _locked_payment_by_provider_id(session, payment_id)
    if payment is None:
        raise UnresolvedEventError("PAYMENT_RECORD_NOT_FOUND")
    if (
        amount != payment.amount_cents
        or str(obj.get("currency") or "").lower() != payment.currency
        or refunded > payment.amount_cents
    ):
        raise UnresolvedEventError("AMOUNT_MISMATCH")
    link = session.query(ProviderCustomerRecord).filter_by(user_id=payment.user_id).one_or_none()
    if link is None or _object_id(obj.get("customer")) != link.provider_customer_id:
        raise UnresolvedEventError("CUSTOMER_MISMATCH")
    if payment.status not in CREDITED_STATUSES:
        # A refund of a payment PatchHive never credited: an operator must look.
        raise UnresolvedEventError("PAYMENT_STATE_CONFLICT")
    if refunded <= int(payment.refunded_cents or 0):
        # The same cumulative amount again, or an older one delivered late.
        return EventDisposition("duplicate", "REFUND_ALREADY_RECORDED")

    reversed_before = int(payment.refund_reversed_credits or 0)
    unrecovered_before = int(payment.refund_unrecovered_credits or 0)
    owed = (
        credits_for_refund(
            credits=payment.credits, amount_cents=payment.amount_cents, refunded_cents=refunded
        )
        - reversed_before
        - unrecovered_before
    )
    # Serialize with export debits for this user, then cap at the unspent balance so
    # the balance never goes negative.
    _serialize_user_credits(session, payment.user_id)
    balance = credit_balance(session, payment.user_id)
    reversed_now = max(0, min(owed, balance))
    unrecovered_now = owed - reversed_now
    if reversed_now:
        key = refund_key(payment_id, refunded)
        if session.query(CanonicalCreditLedgerEntryRecord).filter_by(idempotency_key=key).first():
            raise UnresolvedEventError("LEDGER_ENTRY_CONFLICT")
        session.add(
            CanonicalCreditLedgerEntryRecord(
                id=f"refund-{sha256(key.encode('utf-8')).hexdigest()[:24]}",
                user_id=payment.user_id,
                delta=-reversed_now,
                entry_type="refund",
                idempotency_key=key,
                export_id=None,
                created_at=datetime.now(timezone.utc),
            )
        )
    payment.refunded_cents = refunded
    payment.refund_reversed_credits = reversed_before + reversed_now
    payment.refund_unrecovered_credits = unrecovered_before + unrecovered_now
    _touch(payment, "refunded" if refunded == payment.amount_cents else "partially_refunded")
    session.flush()
    if unrecovered_now:
        # The spent remainder goes to an operator; the reversal above still commits.
        return EventDisposition("unresolved", "REFUND_EXCEEDS_UNSPENT", commit_effects=True)
    return EventDisposition("processed")


def _require_known_payment(session: Session, obj: dict[str, Any], object_type: str) -> None:
    if obj.get("object", object_type) != object_type:
        raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")
    if _locked_payment_by_provider_id(session, _object_id(obj.get("payment_intent"))) is None:
        raise UnresolvedEventError("PAYMENT_RECORD_NOT_FOUND")


def handle_payment_reversal_event(session: Session, event: dict[str, Any]) -> EventDisposition:
    """Apply a refund or dispute of a Machine B payment (OQ-2 ``A_reverse_unspent``).

    The payment is found by the provider payment id (``payment_intent``) on its record.

    - ``charge.refunded`` (full or partial): ``amount_refunded`` is cumulative. The
      credits it takes back are ``credits_for_refund`` of that amount, less what earlier
      refunds already took back. They are reversed with one append-only canonical
      ``refund`` entry keyed ``purchase-refund:<payment_id>:<amount_refunded>``, capped
      at the user's current canonical balance, so a balance never goes negative. Credits
      already spent are recorded on the record as ``refund_unrecovered_credits`` and the
      event is ``unresolved`` (``REFUND_EXCEEDS_UNSPENT``) for the operator, with the
      reversal committed. The record becomes ``partially_refunded`` or ``refunded``. An
      amount no higher than one already applied is ``duplicate``.
    - ``refund.failed``: ``unresolved`` (``REFUND_FAILED``); credits are not restored
      automatically.
    - ``charge.dispute.created``: ``unresolved`` (``DISPUTE_OPENED``) with no reversal;
      the dispute outcome is unknown when it opens.
    - An unknown payment, a currency or amount mismatch or a malformed payload is
      ``unresolved`` with a reason code, as for checkout events.

    A referral reward is never revoked: the reward is the referrer's grant, and nothing
    here touches the referrer's ledger or the ``Referral`` rows (FR-030).
    """

    event_type = event.get("type")
    obj = event["data"]["object"]
    if event_type == CHARGE_REFUNDED:
        return _refund(session, obj)
    if event_type == REFUND_FAILED:
        _require_known_payment(session, obj, "refund")
        raise UnresolvedEventError("REFUND_FAILED")
    if event_type == DISPUTE_CREATED:
        _require_known_payment(session, obj, "dispute")
        raise UnresolvedEventError("DISPUTE_OPENED")
    raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")


# --- Operator resolve (T048b) ------------------------------------------------------------

RESOLVE_ACTION = "commerce.event.resolve"


class ResolveRefusedError(Exception):
    """Resolve is refused before any write. ``code`` is safe to return."""

    def __init__(self, code: str, *, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class ResolveOutcome:
    record: StripeEventRecordModel
    audit: CanonicalAdminAuditEventRecord


def _event_state(record: StripeEventRecordModel) -> dict[str, Any]:
    return {"status": record.status, "reason_code": record.reason_code}


def _apply_retrieved_session(
    session: Session, record: StripeEventRecordModel, obj: dict[str, Any]
) -> EventDisposition:
    """Run Machine B fulfillment once on the retrieved session, in a savepoint."""

    if obj.get("mode") == "subscription":
        # Machine C (T049) has no operator resolve; an operator rejects instead.
        raise ResolveRefusedError("RESOLVE_NOT_SUPPORTED")
    if obj.get("payment_status") != "paid":
        # Resolve only credits: a session the provider does not report paid stays with
        # the operator, who may reject it.
        return EventDisposition("unresolved", "SESSION_NOT_PAID")
    event = {"id": record.stripe_event_id, "type": CHECKOUT_COMPLETED, "data": {"object": obj}}
    savepoint = session.begin_nested()
    try:
        disposition = handle_checkout_session_event(session, event)
    except UnresolvedEventError as exc:
        savepoint.rollback()
        return EventDisposition("unresolved", exc.reason_code)
    except Exception:
        savepoint.rollback()
        raise
    if disposition.status not in FINAL_EVENT_STATUSES or disposition.status == "ignored":
        savepoint.rollback()
        raise ValueError(f"handler returned invalid status {disposition.status!r}")
    if disposition.status == "unresolved":
        savepoint.rollback()
    else:
        savepoint.commit()
    return disposition


def resolve_unresolved_event(
    session: Session,
    stripe_event_id: str,
    *,
    provider: CheckoutSessionRetriever,
    app_settings: Any,
    actor_user_id: int,
    actor_role: str,
    reason: str,
) -> ResolveOutcome:
    """Machine B ``Unresolved --operator_resolves--> Credited`` (OQ-5 ``A_refetch_session``).

    PatchHive keeps only the payload hash of an event, so the Checkout Session is
    retrieved from the provider by the ``object_id`` stored at intake, and Machine B's
    idempotent fulfillment runs once on what the provider reports. The event leaves
    ``unresolved`` only if that credits (``processed``) or finds the payment already
    credited (``duplicate``); otherwise it stays ``unresolved`` with the new reason code.
    Either way one ``CanonicalAdminAuditEventRecord`` is written. The caller commits.

    Refused with no write at all (the caller rolls back):

    - ``LookupError``: no such event.
    - ``InvalidEventTransitionError``: the event is not ``unresolved``.
    - ``ResolveRefusedError``: not a Machine B event, or no stored object id (409); the
      provider returned a different object (502); the retrieved session is in
      ``subscription`` mode (409 ``RESOLVE_NOT_SUPPORTED``: Machine C has no resolve).
    - ``CheckoutUnavailableError``: the payments flags or key refuse, as for checkout.
    - ``PaymentProviderError``: the session could not be retrieved.
    """

    if actor_role not in COMMERCE_OPERATOR_ROLES:
        raise PermissionError("only an Admin may resolve a commerce event")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("a reason is required")
    # The row lock makes two overlapping resolves (or a resolve and a reject) take turns:
    # the second sees the first's final status and is refused.
    record = (
        session.query(StripeEventRecordModel)
        .filter(StripeEventRecordModel.stripe_event_id == stripe_event_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if record is None:
        raise LookupError(stripe_event_id)
    if record.status != "unresolved":
        raise InvalidEventTransitionError(record.status)
    if record.event_type not in CHECKOUT_EVENT_TYPES:
        raise ResolveRefusedError("RESOLVE_NOT_SUPPORTED")
    object_id = record.object_id
    if not object_id:
        raise ResolveRefusedError("OBJECT_ID_MISSING")
    checkout_gate(app_settings)

    obj = provider.retrieve_checkout_session(object_id)
    if (
        not isinstance(obj, dict)
        or obj.get("id") != object_id
        or obj.get("object", "checkout.session") != "checkout.session"
        or bool(obj.get("livemode", record.livemode)) != bool(record.livemode)
    ):
        raise ResolveRefusedError("PROVIDER_OBJECT_MISMATCH", status_code=502)

    before = _event_state(record)
    disposition = _apply_retrieved_session(session, record, obj)
    record.status = disposition.status
    record.reason_code = disposition.reason_code
    record.processed_at = datetime.now(timezone.utc)
    audit = CanonicalAdminAuditEventRecord(
        id=f"audit-{uuid.uuid4().hex}",
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=RESOLVE_ACTION,
        target_type="stripe_event",
        target_id=record.stripe_event_id,
        before_hash=_hash_state(before),
        after_hash=_hash_state(_event_state(record)),
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )
    session.add(audit)
    session.flush()
    return ResolveOutcome(record=record, audit=audit)
