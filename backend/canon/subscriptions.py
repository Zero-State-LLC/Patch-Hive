"""Spec 004 Machine C: subscriptions (T049).

``start_subscription_checkout`` is the ``choose_tier`` row. Behind ``checkout_gate`` with
its own flag (``ENABLE_SUBSCRIPTION_CHECKOUT``, off by default) and the same production
and test-key refusals as Machine B, it gets or creates the user's one provider customer
and creates a ``subscription``-mode Checkout Session for the tier's configured price. It
writes no subscription record (an abandoned checkout leaves none, Machine C
``checkout_canceled_or_expired``), only a ``SubscriptionCheckoutRecord`` that reserves
checkout for the user: a repeated request reuses the open session until it expires.

The webhook side runs inside ``process_stripe_event``'s savepoint:

- ``customer.subscription.created`` / ``updated`` keep the one record per provider
  subscription id in sync: the tier (from the provider price, never client input; OQ-7
  ``A_next_period_no_proration``), the provider status, the current period and
  ``cancel_at_period_end`` (FR-015). They never grant. ``customer.subscription.deleted``
  sets ``canceled`` (FR-018) and keeps granted credits.
- ``invoice.paid`` is the only grant trigger (research 2026-11-01 §3, OQ-4
  ``A_stripe_mapping``). It grants once per billing period, keyed
  ``subscription-period:<subscription_id>:<period_start>`` (FR-016, SC-005), for the tier
  of the price billed on the invoice: CORE and PRO get a canonical ``grant`` entry with
  the tier's credits; STUDIO gets the explicit unlimited entitlement and the owner's
  fair-use cap on the period grant, and no credits (FR-004, OQ-8 ``A_flag_with_fair_use``).
  The subscription's first paid invoice also goes through
  ``record_purchase(payment_verified=True)``, so it can qualify a referral (OQ-3
  ``A_both``, FR-028).
- An unknown customer, a price that maps to no tier, or a payload the record cannot vouch
  for is ``unresolved`` with a reason code and grants nothing (FR-014). A repeated effect
  is ``duplicate`` (FR-012).

Operator resolve (T048b) does not support Machine C: a subscription event stays
``RESOLVE_NOT_SUPPORTED`` and an operator rejects it instead.

Out of scope here (T050): resolving the user's tier and spending the STUDIO entitlement.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from canon.checkout import (
    CheckoutUnavailableError,
    PaymentProviderError,
    ProviderCheckoutSession,
    _object_id,
    checkout_gate,
    get_or_create_customer,
)
from canon.models import (
    SUBSCRIPTION_STATUSES,
    SUBSCRIPTION_TIERS,
    CanonicalCreditLedgerEntryRecord,
    ProviderCustomerRecord,
    ProviderSubscriptionRecord,
    SubscriptionCheckoutRecord,
    SubscriptionPeriodGrantRecord,
)
from canon.webhook_events import EventDisposition, UnresolvedEventError
import core.config as core_config
from community.models import User
from monetization.referrals import record_purchase

SUBSCRIPTION_FLAG = "enable_subscription_checkout"


def _app_settings() -> Any:
    # Webhook handlers take no settings argument; read the live instance at call time so
    # a reloaded ``core.config`` (tests, acceptance) is the one consulted.
    return core_config.settings


SUBSCRIPTION_CREATED = "customer.subscription.created"
SUBSCRIPTION_UPDATED = "customer.subscription.updated"
SUBSCRIPTION_DELETED = "customer.subscription.deleted"
INVOICE_PAID = "invoice.paid"
SUBSCRIPTION_EVENT_TYPES = frozenset(
    {SUBSCRIPTION_CREATED, SUBSCRIPTION_UPDATED, SUBSCRIPTION_DELETED}
)

PROVIDER_STATUSES = frozenset(SUBSCRIPTION_STATUSES)
CANCELED = "canceled"
# A user with a subscription in one of these statuses cannot open a second checkout:
# two live subscriptions would bill and grant twice.
TERMINAL_STATUSES = frozenset({"canceled", "incomplete_expired"})
# Provider session lifetime (Stripe allows 30 minutes to 24 hours).
CHECKOUT_TTL_SECONDS = 3600


class SubscriptionRefusedError(Exception):
    """A subscription action is refused before any provider call. ``code`` is safe."""

    def __init__(self, code: str, *, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class SubscriptionProvider(Protocol):
    def create_customer(self, *, user_id: int, idempotency_key: str) -> str: ...

    def create_subscription_checkout_session(
        self,
        *,
        customer_id: str,
        user_id: int,
        tier: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        expires_at: int,
        idempotency_key: str,
    ) -> ProviderCheckoutSession: ...

    def cancel_subscription_at_period_end(
        self, *, subscription_id: str, idempotency_key: str
    ) -> dict[str, Any]: ...


# --- Tier plans (settings, never hardcoded price ids) -----------------------------------


@dataclass(frozen=True)
class TierPlan:
    tier: str
    credits: int
    unlimited: bool
    fair_use_export_cap: int | None


def _setting_int(app_settings: Any, name: str) -> int | None:
    value = getattr(app_settings, name, None)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def price_id_for_tier(app_settings: Any, tier: str) -> str:
    return str(getattr(app_settings, f"subscription_price_id_{tier}", "") or "").strip()


def tier_for_price(app_settings: Any, price_id: str | None) -> str | None:
    """The tier whose configured price id is ``price_id``; ``None`` if none is.

    Two tiers configured with one price id cannot be told apart, so that price maps to
    no tier (fail closed).
    """

    if not price_id:
        return None
    matches = [
        tier for tier in SUBSCRIPTION_TIERS if price_id_for_tier(app_settings, tier) == price_id
    ]
    return matches[0] if len(matches) == 1 else None


def plan_for_tier(app_settings: Any, tier: str) -> TierPlan:
    """OQ-1 credits for CORE and PRO; OQ-8 flag and fair-use cap for STUDIO."""

    if tier == "studio":
        cap = _setting_int(app_settings, "subscription_studio_fair_use_exports_per_period")
        if cap is None:
            raise UnresolvedEventError("TIER_CONFIG_INVALID")
        return TierPlan(tier=tier, credits=0, unlimited=True, fair_use_export_cap=cap)
    credits = _setting_int(app_settings, f"subscription_credits_{tier}")
    if tier not in SUBSCRIPTION_TIERS or credits is None:
        raise UnresolvedEventError("TIER_CONFIG_INVALID")
    return TierPlan(tier=tier, credits=credits, unlimited=False, fair_use_export_cap=None)


def subscription_period_key(subscription_id: str, period_start: int) -> str:
    return f"subscription-period:{subscription_id}:{period_start}"


# --- choose_tier and cancel_requested ----------------------------------------------------


@dataclass(frozen=True)
class StartedSubscriptionCheckout:
    tier: str
    checkout_session_id: str
    checkout_url: str


def _live_subscription(session: Session, user_id: int) -> ProviderSubscriptionRecord | None:
    return (
        session.query(ProviderSubscriptionRecord)
        .filter(
            ProviderSubscriptionRecord.user_id == user_id,
            ProviderSubscriptionRecord.status.notin_(TERMINAL_STATUSES),
        )
        .order_by(ProviderSubscriptionRecord.created_at.desc())
        .first()
    )


def start_subscription_checkout(
    session: Session,
    *,
    user: User,
    tier: str,
    provider: SubscriptionProvider,
    app_settings: Any,
) -> StartedSubscriptionCheckout:
    """Machine C ``NONE --choose_tier--> CheckoutOpen``. The caller commits.

    Refusals, before any provider call: the ``checkout_gate`` codes for
    ``ENABLE_SUBSCRIPTION_CHECKOUT``; ``ValueError`` for a tier other than CORE, PRO or
    STUDIO; ``SUBSCRIPTION_PRICE_MISSING`` (503) when the tier has no configured price;
    ``SUBSCRIPTION_EXISTS`` (409) when the user already has a live subscription.
    """

    checkout_gate(app_settings, flag=SUBSCRIPTION_FLAG)
    tier = (tier or "").strip().lower()
    if tier not in SUBSCRIPTION_TIERS:
        raise ValueError("INVALID_TIER")
    price_id = price_id_for_tier(app_settings, tier)
    if not price_id or tier_for_price(app_settings, price_id) != tier:
        raise CheckoutUnavailableError("SUBSCRIPTION_PRICE_MISSING", status_code=503)
    # Serialize this user's checkout requests: the row lock makes the reservation check
    # below and the new reservation one step, so two requests cannot both open a session.
    session.query(User).filter(User.id == user.id).with_for_update().one()
    if _live_subscription(session, user.id) is not None:
        raise SubscriptionRefusedError("SUBSCRIPTION_EXISTS")
    now = datetime.now(timezone.utc)
    outstanding = _outstanding_checkout(session, user.id, now)
    if outstanding is not None:
        if outstanding.status == "completed":
            # Paid; its subscription event has not arrived yet.
            raise SubscriptionRefusedError("SUBSCRIPTION_EXISTS")
        if outstanding.tier != tier:
            raise SubscriptionRefusedError("SUBSCRIPTION_CHECKOUT_OPEN")
        # The same tier again: reuse the open session rather than open a second one.
        return StartedSubscriptionCheckout(
            tier=tier,
            checkout_session_id=outstanding.checkout_session_id,
            checkout_url=outstanding.checkout_url,
        )
    customer = get_or_create_customer(session, user=user, provider=provider)
    base = str(app_settings.frontend_base_url).rstrip("/")
    expires_at = int(now.timestamp()) + CHECKOUT_TTL_SECONDS
    created = provider.create_subscription_checkout_session(
        customer_id=customer.provider_customer_id,
        user_id=user.id,
        tier=tier,
        price_id=price_id,
        success_url=f"{base}/account?subscription=success",
        cancel_url=f"{base}/account?subscription=canceled",
        expires_at=expires_at,
        idempotency_key=f"patchhive-subscription-checkout:{uuid.uuid4().hex}",
    )
    session.add(
        SubscriptionCheckoutRecord(
            id=f"subco-{uuid.uuid4().hex}",
            user_id=user.id,
            checkout_session_id=created.id,
            checkout_url=created.url,
            tier=tier,
            status="open",
            expires_at=_at(expires_at),
            created_at=now,
            updated_at=now,
        )
    )
    session.flush()
    return StartedSubscriptionCheckout(
        tier=tier, checkout_session_id=created.id, checkout_url=created.url
    )


def _outstanding_checkout(
    session: Session, user_id: int, now: datetime
) -> SubscriptionCheckoutRecord | None:
    """The user's checkout that still blocks a new one, if any.

    An ``open`` one blocks until its provider expiry. A ``completed`` one blocks until
    the subscription it created is recorded (that record then decides).
    """

    rows = (
        session.query(SubscriptionCheckoutRecord)
        .filter(
            SubscriptionCheckoutRecord.user_id == user_id,
            SubscriptionCheckoutRecord.status.in_(("open", "completed")),
        )
        .order_by(SubscriptionCheckoutRecord.created_at.desc())
        .all()
    )
    current = int(now.timestamp())
    for row in rows:
        if row.status == "open" and (_as_epoch(row.expires_at) or 0) > current:
            return row
        if row.status == "completed" and (
            not row.provider_subscription_id
            or session.query(ProviderSubscriptionRecord)
            .filter_by(provider_subscription_id=row.provider_subscription_id)
            .first()
            is None
        ):
            return row
    return None


def handle_subscription_checkout_session(
    session: Session, event: dict[str, Any]
) -> EventDisposition:
    """A ``subscription``-mode Checkout Session event: settle the user's reservation.

    ``checkout.session.completed`` marks it ``completed`` with the session's
    subscription; ``checkout.session.expired`` marks it ``expired`` (Machine C
    ``Abandoned``: no subscription record). Nothing is granted: the record comes from
    ``customer.subscription.*`` and the grant from ``invoice.paid``. A session with no
    reservation, or an event that changes nothing, is ``ignored``.
    """

    obj = event["data"]["object"]
    no_effect = EventDisposition("ignored", "SUBSCRIPTION_SESSION_NO_EFFECT")
    reservation = (
        session.query(SubscriptionCheckoutRecord)
        .filter_by(checkout_session_id=obj.get("id"))
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if reservation is None or reservation.status != "open":
        return no_effect
    event_type = event.get("type")
    if event_type == "checkout.session.completed":
        reservation.status = "completed"
        reservation.provider_subscription_id = _object_id(obj.get("subscription"))
    elif event_type == "checkout.session.expired":
        reservation.status = "expired"
    else:
        return no_effect
    reservation.updated_at = datetime.now(timezone.utc)
    session.flush()
    return EventDisposition("processed")


def request_subscription_cancel(
    session: Session,
    *,
    user: User,
    provider: SubscriptionProvider,
    app_settings: Any,
) -> ProviderSubscriptionRecord:
    """Machine C ``Active --cancel_requested--> CancelScheduled`` (FR-017). Caller commits.

    The user's own ``active`` subscription is flagged to end at the period end, at the
    provider and locally; access and granted credits stay until then. Already flagged:
    returned as is, with no provider call. Refused (``SubscriptionRefusedError``):
    ``SUBSCRIPTION_NOT_FOUND`` (404) with no live subscription, ``SUBSCRIPTION_NOT_ACTIVE``
    (409) when its provider status is not ``active``.
    """

    checkout_gate(app_settings, flag=SUBSCRIPTION_FLAG)
    live = _live_subscription(session, user.id)
    if live is None:
        raise SubscriptionRefusedError("SUBSCRIPTION_NOT_FOUND", status_code=404)
    record = (
        session.query(ProviderSubscriptionRecord)
        .filter_by(id=live.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    if record.cancel_at_period_end:
        return record
    if record.status != "active":
        raise SubscriptionRefusedError("SUBSCRIPTION_NOT_ACTIVE")
    body = provider.cancel_subscription_at_period_end(
        subscription_id=record.provider_subscription_id,
        idempotency_key=f"patchhive-subscription-cancel:{record.provider_subscription_id}",
    )
    if (
        not isinstance(body, dict)
        or body.get("id") != record.provider_subscription_id
        or body.get("cancel_at_period_end") is not True
    ):
        raise PaymentProviderError("provider did not confirm the cancellation")
    record.cancel_at_period_end = True
    record.updated_at = datetime.now(timezone.utc)
    session.flush()
    return record


# --- Webhook side ------------------------------------------------------------------------


def _epoch(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _at(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def _as_epoch(value: datetime | None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:  # SQLite returns naive UTC datetimes
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


def _price_id(container: Any) -> str | None:
    """A price id from a subscription item or invoice line, in either API shape."""

    if not isinstance(container, dict):
        return None
    price = _object_id(container.get("price"))
    if price is not None:
        return price
    pricing = container.get("pricing")
    details = pricing.get("price_details") if isinstance(pricing, dict) else None
    if isinstance(details, dict):
        return _object_id(details.get("price"))
    return None


def _list_data(value: Any) -> list[Any] | None:
    data = value.get("data") if isinstance(value, dict) else None
    return data if isinstance(data, list) else None


def _customer_link(session: Session, obj: dict[str, Any]) -> tuple[str, ProviderCustomerRecord]:
    customer_id = _object_id(obj.get("customer"))
    if customer_id is None:
        raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")
    link = (
        session.query(ProviderCustomerRecord)
        .filter_by(provider_customer_id=customer_id)
        .one_or_none()
    )
    if link is None:
        raise UnresolvedEventError("CUSTOMER_NOT_FOUND")
    return customer_id, link


def _check_metadata_user(obj: dict[str, Any], user_id: int) -> None:
    metadata = obj.get("metadata")
    if metadata is None:
        return
    if not isinstance(metadata, dict):
        raise UnresolvedEventError("METADATA_MALFORMED")
    if "user_id" in metadata and metadata.get("user_id") != str(user_id):
        raise UnresolvedEventError("METADATA_MALFORMED")


def _locked_subscription(
    session: Session, subscription_id: str
) -> ProviderSubscriptionRecord | None:
    return (
        session.query(ProviderSubscriptionRecord)
        .filter_by(provider_subscription_id=subscription_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )


@dataclass(frozen=True)
class _SubscriptionFields:
    price_id: str
    tier: str
    status: str
    period_start: int
    period_end: int
    cancel_at_period_end: bool


def _lock_or_create(
    session: Session,
    *,
    subscription_id: str,
    link: ProviderCustomerRecord,
    customer_id: str,
    fields: _SubscriptionFields,
    event_created: int | None,
) -> tuple[ProviderSubscriptionRecord, bool]:
    """The locked record for ``subscription_id``, created from ``fields`` if absent.

    Returns ``(record, created)``. Two concurrent first events for one subscription race
    on the unique provider id; the loser re-reads the winner's row under the lock.
    """

    record = _locked_subscription(session, subscription_id)
    if record is not None:
        return record, False
    now = datetime.now(timezone.utc)
    record = ProviderSubscriptionRecord(
        id=f"sub-{uuid.uuid4().hex}",
        user_id=link.user_id,
        provider_subscription_id=subscription_id,
        provider_customer_id=customer_id,
        price_id=fields.price_id,
        tier=fields.tier,
        status=fields.status,
        current_period_start=_at(fields.period_start),
        current_period_end=_at(fields.period_end),
        cancel_at_period_end=fields.cancel_at_period_end,
        last_event_created=event_created,
        canceled_at=now if fields.status == CANCELED else None,
        created_at=now,
        updated_at=now,
    )
    try:
        with session.begin_nested():
            session.add(record)
            session.flush()
    except IntegrityError:
        winner = _locked_subscription(session, subscription_id)
        if winner is None:
            raise
        return winner, False
    return record, True


def _subscription_fields(
    obj: dict[str, Any], *, deleted: bool, app_settings: Any
) -> _SubscriptionFields:
    items = _list_data(obj.get("items"))
    if not items or len(items) != 1 or not isinstance(items[0], dict):
        # One tier price per subscription; anything else is not a PatchHive plan.
        raise UnresolvedEventError("SUBSCRIPTION_ITEMS_UNSUPPORTED")
    item = items[0]
    price_id = _price_id(item)
    tier = tier_for_price(app_settings, price_id)
    if price_id is None or tier is None:
        raise UnresolvedEventError("PRICE_UNKNOWN")
    status = CANCELED if deleted else obj.get("status")
    if status not in PROVIDER_STATUSES:
        raise UnresolvedEventError("STATUS_UNKNOWN")
    # The period is top-level in older API versions and on the item in newer ones.
    start = _epoch(obj.get("current_period_start")) or _epoch(item.get("current_period_start"))
    end = _epoch(obj.get("current_period_end")) or _epoch(item.get("current_period_end"))
    if start is None or end is None or end <= start:
        raise UnresolvedEventError("PERIOD_MALFORMED")
    cancel_flag = obj.get("cancel_at_period_end", False)
    if not isinstance(cancel_flag, bool):
        raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")
    return _SubscriptionFields(
        price_id=price_id,
        tier=tier,
        status=status,
        period_start=start,
        period_end=end,
        cancel_at_period_end=cancel_flag,
    )


def _apply_fields(
    record: ProviderSubscriptionRecord, fields: _SubscriptionFields, event_created: int | None
) -> bool:
    """Sync the record to ``fields``. Returns whether any tracked field changed.

    A newer event advances ``last_event_created`` even when it changes nothing, so a
    delayed older snapshot cannot roll the record back past it.
    """

    if event_created is not None and (
        record.last_event_created is None or event_created > record.last_event_created
    ):
        record.last_event_created = event_created
    before = (
        record.price_id,
        record.tier,
        record.status,
        _as_epoch(record.current_period_start),
        _as_epoch(record.current_period_end),
        bool(record.cancel_at_period_end),
    )
    after = (
        fields.price_id,
        fields.tier,
        fields.status,
        fields.period_start,
        fields.period_end,
        fields.cancel_at_period_end,
    )
    if before == after:
        return False
    now = datetime.now(timezone.utc)
    record.price_id = fields.price_id
    record.tier = fields.tier
    record.status = fields.status
    record.current_period_start = _at(fields.period_start)
    record.current_period_end = _at(fields.period_end)
    record.cancel_at_period_end = fields.cancel_at_period_end
    if fields.status == CANCELED and record.canceled_at is None:
        record.canceled_at = now
    record.updated_at = now
    return True


# Provider status progression, used only to order two snapshots with the same event
# ``created`` second (Stripe timestamps have one-second resolution). ``incomplete`` comes
# only before the first payment; ``incomplete_expired`` and ``canceled`` are terminal.
_STATUS_STAGE: dict[str, int] = {
    "incomplete": 0,
    "trialing": 1,
    "active": 1,
    "past_due": 1,
    "unpaid": 1,
    "paused": 1,
    "incomplete_expired": 2,
    "canceled": 2,
}


def _is_stale(record: ProviderSubscriptionRecord, event_created: int | None, status: Any) -> bool:
    """Whether an incoming snapshot with ``status`` is older than the record's state.

    An earlier ``created`` time is stale. At the same second, arrival order says
    nothing, so the provider's status progression decides: a snapshot from an earlier
    stage (for example ``incomplete`` after the record is ``active``) is stale, and one
    from the same or a later stage applies. A subscription never moves backward from a
    paid stage to ``incomplete``.
    """

    if event_created is None or record.last_event_created is None:
        return False
    if event_created < record.last_event_created:
        return True
    if event_created > record.last_event_created:
        return False
    incoming = _STATUS_STAGE.get(status) if isinstance(status, str) else None
    current = _STATUS_STAGE.get(record.status)
    return incoming is not None and current is not None and incoming < current


def handle_subscription_event(session: Session, event: dict[str, Any]) -> EventDisposition:
    """Apply ``customer.subscription.created``, ``updated`` or ``deleted``. Never grants.

    - The customer must be a known provider customer (``CUSTOMER_NOT_FOUND``) and own the
      record (``CUSTOMER_MISMATCH``); metadata, if it names a user, must agree.
    - The single subscription item's price must map to a tier through the
      ``SUBSCRIPTION_PRICE_ID_*`` settings (``PRICE_UNKNOWN``). Except on ``deleted`` of
      a known record, which only needs the customer to match.
    - The status must be a provider status (``STATUS_UNKNOWN``); ``deleted`` stores
      ``canceled``. A ``canceled`` record is final: later events are ``duplicate``
      (``SUBSCRIPTION_ALREADY_CANCELED``); resubscribing makes a new subscription.
    - An event older than the newest applied one is ``duplicate`` (``STALE_EVENT``), and
      an event that changes nothing is ``duplicate`` (``SUBSCRIPTION_UNCHANGED``).
    """

    event_type = event.get("type")
    obj = event["data"]["object"]
    subscription_id = obj.get("id")
    if (
        event_type not in SUBSCRIPTION_EVENT_TYPES
        or obj.get("object", "subscription") != "subscription"
        or not isinstance(subscription_id, str)
        or not subscription_id
    ):
        raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")
    deleted = event_type == SUBSCRIPTION_DELETED
    event_created = _epoch(event.get("created"))
    customer_id, link = _customer_link(session, obj)
    _check_metadata_user(obj, link.user_id)

    record = _locked_subscription(session, subscription_id)
    if record is not None:
        if record.user_id != link.user_id or record.provider_customer_id != customer_id:
            raise UnresolvedEventError("CUSTOMER_MISMATCH")
        if record.status == CANCELED:
            return EventDisposition("duplicate", "SUBSCRIPTION_ALREADY_CANCELED")
        if deleted:
            # Deletion is final at the provider, so it applies whatever arrived before.
            now = datetime.now(timezone.utc)
            record.status = CANCELED
            record.canceled_at = now
            cancel_flag = obj.get("cancel_at_period_end")
            if isinstance(cancel_flag, bool):
                record.cancel_at_period_end = cancel_flag
            if event_created is not None:
                record.last_event_created = event_created
            record.updated_at = now
            session.flush()
            return EventDisposition("processed")
        if _is_stale(record, event_created, obj.get("status")):
            return EventDisposition("duplicate", "STALE_EVENT")

    fields = _subscription_fields(obj, deleted=deleted, app_settings=_app_settings())
    if record is None:
        record, created = _lock_or_create(
            session,
            subscription_id=subscription_id,
            link=link,
            customer_id=customer_id,
            fields=fields,
            event_created=event_created,
        )
        if created:
            return EventDisposition("processed")
        # A concurrent first event won the insert; apply this one on top of it.
        if record.user_id != link.user_id or record.provider_customer_id != customer_id:
            raise UnresolvedEventError("CUSTOMER_MISMATCH")
        if record.status == CANCELED:
            return EventDisposition("duplicate", "SUBSCRIPTION_ALREADY_CANCELED")
        if not deleted and _is_stale(record, event_created, fields.status):
            return EventDisposition("duplicate", "STALE_EVENT")
    if not _apply_fields(record, fields, event_created):
        return EventDisposition("duplicate", "SUBSCRIPTION_UNCHANGED")
    session.flush()
    return EventDisposition("processed")


def _invoice_subscription_id(obj: dict[str, Any]) -> str | None:
    """The invoice's subscription, top-level (older API versions) or under ``parent``."""

    subscription = _object_id(obj.get("subscription"))
    if subscription is not None:
        return subscription
    parent = obj.get("parent")
    details = parent.get("subscription_details") if isinstance(parent, dict) else None
    if isinstance(details, dict):
        return _object_id(details.get("subscription"))
    return None


def _is_proration(line: dict[str, Any]) -> bool:
    """Whether an invoice line is a proration, in either API shape.

    Older versions carry ``proration`` on the line; newer ones under
    ``parent.subscription_item_details`` or ``parent.invoice_item_details``.
    """

    flags = [line.get("proration")]
    parent = line.get("parent")
    if isinstance(parent, dict):
        for key in ("subscription_item_details", "invoice_item_details"):
            details = parent.get(key)
            if isinstance(details, dict):
                flags.append(details.get("proration"))
    for flag in flags:
        if flag is not None and not isinstance(flag, bool):
            raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")
    return any(flag is True for flag in flags)


def _invoice_period_line(obj: dict[str, Any]) -> tuple[str, int, int] | None:
    """The one priced, non-proration line of a subscription invoice.

    Returns ``(price_id, start, end)``, or ``None`` when every priced line is a
    proration. The line's ``period`` is the service period the payment covers; the
    invoice's own ``period_start`` / ``period_end`` are not (for a renewal they describe
    the period before). A proration line's period starts when the proration was
    calculated, mid-period, so it never selects a period to grant (OQ-7: a tier change
    takes effect from the next period, no proration).
    """

    lines = _list_data(obj.get("lines"))
    if lines is None:
        raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")
    priced = [line for line in lines if isinstance(line, dict) and _price_id(line) is not None]
    full = [line for line in priced if not _is_proration(line)]
    if priced and not full:
        return None
    priced = full
    if len(priced) != 1:
        raise UnresolvedEventError("INVOICE_LINES_UNSUPPORTED")
    line = priced[0]
    price_id = _price_id(line) or ""
    period = line.get("period")
    start = _epoch(period.get("start")) if isinstance(period, dict) else None
    end = _epoch(period.get("end")) if isinstance(period, dict) else None
    if start is None or end is None or end <= start:
        raise UnresolvedEventError("PERIOD_MALFORMED")
    return price_id, start, end


def handle_invoice_paid(session: Session, event: dict[str, Any]) -> EventDisposition:
    """``invoice.paid``: grant the billed tier once for the invoice's period.

    The tier comes from the price on the invoice line (OQ-7: a tier change takes effect
    from the next period billed, with no proration grant). The grant is keyed
    ``subscription-period:<subscription_id>:<period_start>``; a second paid invoice or a
    redelivery for a granted period is ``duplicate`` (``PERIOD_ALREADY_GRANTED``). The
    subscription row lock serializes concurrent deliveries and the unique keys back it.

    If no subscription record exists yet (``invoice.paid`` delivered before
    ``customer.subscription.created``, EC-2), it is created from the invoice as
    ``active``, the status a paid subscription invoice implies; later subscription
    events keep it in sync. An existing record keeps the status its events gave it.

    Proration lines never select the period. An invoice with only proration lines is
    ``ignored`` (``INVOICE_PRORATION_ONLY``) and grants nothing.

    Refused (``unresolved``, nothing written): not a paid invoice (``INVOICE_NOT_PAID``),
    no subscription (``INVOICE_NOT_SUBSCRIPTION``), nothing paid
    (``INVOICE_AMOUNT_ZERO``), unknown customer or price, or a malformed line or period.
    """

    if event.get("type") != INVOICE_PAID:
        raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")
    obj = event["data"]["object"]
    invoice_id = obj.get("id")
    if (
        obj.get("object", "invoice") != "invoice"
        or not isinstance(invoice_id, str)
        or not invoice_id
    ):
        raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")
    if obj.get("status") != "paid":
        raise UnresolvedEventError("INVOICE_NOT_PAID")
    subscription_id = _invoice_subscription_id(obj)
    if subscription_id is None:
        raise UnresolvedEventError("INVOICE_NOT_SUBSCRIPTION")
    amount_paid = obj.get("amount_paid")
    if isinstance(amount_paid, bool) or not isinstance(amount_paid, int) or amount_paid < 0:
        raise UnresolvedEventError("EVENT_PAYLOAD_MALFORMED")
    if amount_paid == 0:
        # A zero invoice (trial, full discount) is not a paid period; PatchHive sells
        # neither, so an operator looks.
        raise UnresolvedEventError("INVOICE_AMOUNT_ZERO")
    customer_id, link = _customer_link(session, obj)
    period_line = _invoice_period_line(obj)
    if period_line is None:
        # Only proration lines (a mid-period tier change billed at once): no period
        # grant, the new tier's credits come with the next period (OQ-7).
        return EventDisposition("ignored", "INVOICE_PRORATION_ONLY")
    price_id, period_start, period_end = period_line
    tier = tier_for_price(_app_settings(), price_id)
    if tier is None:
        raise UnresolvedEventError("PRICE_UNKNOWN")
    plan = plan_for_tier(_app_settings(), tier)
    event_created = _epoch(event.get("created"))

    record, _created = _lock_or_create(
        session,
        subscription_id=subscription_id,
        link=link,
        customer_id=customer_id,
        fields=_SubscriptionFields(
            price_id=price_id,
            tier=tier,
            status="active",
            period_start=period_start,
            period_end=period_end,
            cancel_at_period_end=False,
        ),
        event_created=event_created,
    )
    if record.user_id != link.user_id or record.provider_customer_id != customer_id:
        raise UnresolvedEventError("CUSTOMER_MISMATCH")

    key = subscription_period_key(subscription_id, period_start)
    if session.query(SubscriptionPeriodGrantRecord).filter_by(grant_key=key).first():
        return EventDisposition("duplicate", "PERIOD_ALREADY_GRANTED")
    if (
        session.query(SubscriptionPeriodGrantRecord)
        .filter_by(provider_invoice_id=invoice_id)
        .first()
    ):
        # The same invoice granted for another period: inconsistent, an operator looks.
        raise UnresolvedEventError("INVOICE_ALREADY_GRANTED")
    if session.query(CanonicalCreditLedgerEntryRecord).filter_by(idempotency_key=key).first():
        raise UnresolvedEventError("LEDGER_ENTRY_CONFLICT")
    user = session.get(User, record.user_id)
    if user is None:
        raise UnresolvedEventError("USER_NOT_FOUND")

    now = datetime.now(timezone.utc)
    digest = sha256(key.encode("utf-8")).hexdigest()[:24]
    ledger_id: str | None = None
    if not plan.unlimited:
        ledger_id = f"grant-{digest}"
        session.add(
            CanonicalCreditLedgerEntryRecord(
                id=ledger_id,
                user_id=record.user_id,
                delta=plan.credits,
                entry_type="grant",
                idempotency_key=key,
                export_id=None,
                created_at=now,
            )
        )
        session.flush()
    session.add(
        SubscriptionPeriodGrantRecord(
            id=f"subgrant-{digest}",
            subscription_record_id=record.id,
            user_id=record.user_id,
            grant_key=key,
            provider_invoice_id=invoice_id,
            tier=tier,
            period_start=_at(period_start),
            period_end=_at(period_end),
            credits=plan.credits,
            unlimited=plan.unlimited,
            fair_use_export_cap=plan.fair_use_export_cap,
            ledger_entry_id=ledger_id,
            created_at=now,
        )
    )
    if record.purchase_recorded_at is None:
        # OQ-3 ``A_both``: the first paid invoice is a provider-verified purchase for
        # Machine A. The period credits are the grant above, so the legacy purchase
        # marker carries none.
        record_purchase(
            session,
            user=user,
            credits_delta=0,
            notes=f"Provider subscription invoice: {invoice_id}",
            payment_verified=True,
        )
        record.purchase_recorded_at = now
        record.updated_at = now
    session.flush()
    return EventDisposition("processed")
