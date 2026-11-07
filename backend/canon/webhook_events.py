"""Provider webhook event processor (spec 004 FR-011, FR-014, research R1).

``receive_stripe_webhook`` verifies and records an event, then calls
``process_stripe_event`` in the same transaction. The processor dispatches by event type
and leaves the record in a final disposition with ``processed_at`` set:

- ``processed``: a handler applied the event.
- ``duplicate``: a handler found the effect already applied (for example, the same
  provider payment under a new event id).
- ``unresolved``: the event cannot be applied safely. It carries a ``reason_code`` for
  operator review, and any writes the handler made are rolled back, so it grants nothing.
  The one exception is a disposition with ``commit_effects=True``: the handler applied
  the safe part of the event and an operator must settle the rest (a refund larger than
  the credits still unspent, spec 004 OQ-2). Its writes commit with the record.
- ``ignored``: no handler exists for the event type.

No event stays ``received``. An operator may then move an ``unresolved`` event to
``rejected`` (spec 004 Machine B ``operator_rejects``, T048): it grants nothing, closes
the event's checkout if that is still open, and writes one
``CanonicalAdminAuditEventRecord``. ``operator_resolves`` (T048b) is
``canon.checkout.resolve_unresolved_event``.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Literal

from sqlalchemy.orm import Session

from canon.models import CanonicalAdminAuditEventRecord, StripeEventRecordModel

EventStatus = Literal["processed", "duplicate", "unresolved", "ignored"]
FINAL_EVENT_STATUSES: frozenset[str] = frozenset(
    {"processed", "duplicate", "unresolved", "ignored"}
)


@dataclass(frozen=True)
class EventDisposition:
    status: EventStatus
    reason_code: str | None = None
    # Only meaningful with ``unresolved``: keep the handler's writes (see module doc).
    commit_effects: bool = False


class UnresolvedEventError(Exception):
    """Raised by a handler that cannot apply an event safely."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


EventHandler = Callable[[Session, dict[str, Any]], EventDisposition]


def _machine_c(session: Session, event: dict[str, Any]) -> EventDisposition:
    # Machine C (T049): subscription records; never grants.
    from canon.subscriptions import handle_subscription_event

    return handle_subscription_event(session, event)


def _machine_c_invoice(session: Session, event: dict[str, Any]) -> EventDisposition:
    # Machine C (T049): the only subscription grant trigger.
    from canon.subscriptions import handle_invoice_paid

    return handle_invoice_paid(session, event)


def _machine_b(session: Session, event: dict[str, Any]) -> EventDisposition:
    # Machine B (T046), one-time credit checkout. Imported here because canon.checkout
    # imports this module.
    from canon.checkout import handle_checkout_session_event

    return handle_checkout_session_event(session, event)


def _machine_b_refund(session: Session, event: dict[str, Any]) -> EventDisposition:
    # Machine B refunds and disputes (spec 004 OQ-2 ``A_reverse_unspent``, T053).
    from canon.checkout import handle_payment_reversal_event

    return handle_payment_reversal_event(session, event)


# The event types the observed integration handled (STRIPE_INTEGRATION_PROMPT.md), plus
# the delayed-payment and expiry outcomes of a Checkout Session (research 2026-11-01 §2).
EVENT_HANDLERS: dict[str, EventHandler] = {
    "checkout.session.completed": _machine_b,
    "checkout.session.async_payment_succeeded": _machine_b,
    "checkout.session.async_payment_failed": _machine_b,
    "checkout.session.expired": _machine_b,
    # Refunds and disputes of a Machine B payment (OQ-2, T053). ``charge.refunded``
    # carries the cumulative ``amount_refunded`` and is the only event that reverses
    # credits; ``refund.failed`` and ``charge.dispute.created`` go to an operator.
    "charge.refunded": _machine_b_refund,
    "refund.failed": _machine_b_refund,
    "charge.dispute.created": _machine_b_refund,
    # Machine C (T049): ``customer.subscription.*`` sync the subscription record and
    # ``invoice.paid`` grants once per billing period (research 2026-11-01 §3).
    "customer.subscription.created": _machine_c,
    "customer.subscription.updated": _machine_c,
    "customer.subscription.deleted": _machine_c,
    "invoice.paid": _machine_c_invoice,
}


def _has_data_object(event: dict[str, Any]) -> bool:
    data = event.get("data")
    return isinstance(data, dict) and isinstance(data.get("object"), dict)


def process_stripe_event(
    session: Session,
    record: StripeEventRecordModel,
    event: dict[str, Any],
    *,
    handlers: dict[str, EventHandler] | None = None,
) -> EventDisposition:
    """Dispatch ``event`` by type and set the record's final status and ``processed_at``.

    The handler runs in a savepoint. An unresolved outcome rolls the savepoint back unless
    the handler set ``commit_effects``. An unexpected exception propagates so the caller
    rolls back the whole delivery and the provider retries it.
    """

    registry = EVENT_HANDLERS if handlers is None else handlers
    handler = registry.get(record.event_type)
    if handler is None:
        disposition = EventDisposition("ignored")
    elif not _has_data_object(event):
        disposition = EventDisposition("unresolved", "EVENT_PAYLOAD_MALFORMED")
    else:
        savepoint = session.begin_nested()
        try:
            disposition = handler(session, event)
        except UnresolvedEventError as exc:
            savepoint.rollback()
            disposition = EventDisposition("unresolved", exc.reason_code)
        except Exception:
            savepoint.rollback()
            raise
        else:
            if disposition.status not in FINAL_EVENT_STATUSES:
                savepoint.rollback()
                raise ValueError(f"handler returned invalid status {disposition.status!r}")
            if disposition.status == "unresolved" and not disposition.commit_effects:
                savepoint.rollback()
            else:
                savepoint.commit()
    if disposition.status == "unresolved" and not disposition.reason_code:
        raise ValueError("an unresolved event needs a reason code")

    record.status = disposition.status
    record.reason_code = disposition.reason_code
    record.processed_at = datetime.now(timezone.utc)
    session.flush()
    return disposition


# Spec 004 OQ-5 (recommendation, T048): only the Admin role may dispose of a commerce
# event an operator reviews, and every action needs a reason.
COMMERCE_OPERATOR_ROLES: frozenset[str] = frozenset({"Admin"})
REJECTED = "rejected"


class InvalidEventTransitionError(Exception):
    """The event is not in a state the requested operator action may leave."""


def _hash_state(state: dict[str, Any]) -> str:
    return sha256(json.dumps(state, sort_keys=True).encode("utf-8")).hexdigest()


def reject_unresolved_event(
    session: Session,
    record: StripeEventRecordModel,
    *,
    actor_user_id: int,
    actor_role: str,
    reason: str,
) -> CanonicalAdminAuditEventRecord:
    """Machine B ``Unresolved --operator_rejects--> Abandoned``: grant nothing.

    Only an ``unresolved`` event may be rejected, checked and written in one conditional
    update; any other status (including a concurrent reject that won) raises
    ``InvalidEventTransitionError`` and changes nothing. The record keeps its
    ``reason_code`` so the original failure stays visible. The event's checkout closes too
    if it is still open, so a later event cannot credit it (T001 D4); the audit hashes
    cover that change. Imported here because canon.checkout imports this module.
    """

    if actor_role not in COMMERCE_OPERATOR_ROLES:
        raise PermissionError("only an Admin may reject a commerce event")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("a reason is required")
    before: dict[str, Any] = {"status": "unresolved", "reason_code": record.reason_code}
    # A conditional update makes the check and the write one step, so of two overlapping
    # rejects only one changes the row and writes an audit record; the other sees 0 rows.
    changed = (
        session.query(StripeEventRecordModel)
        .filter(
            StripeEventRecordModel.stripe_event_id == record.stripe_event_id,
            StripeEventRecordModel.status == "unresolved",
        )
        .update({StripeEventRecordModel.status: REJECTED}, synchronize_session=False)
    )
    session.refresh(record)
    if changed != 1:
        raise InvalidEventTransitionError(record.status)
    from canon.checkout import close_rejected_checkout

    after: dict[str, Any] = {"status": record.status, "reason_code": record.reason_code}
    checkout_left = close_rejected_checkout(session, record)
    if checkout_left is not None:
        before["checkout_status"] = checkout_left
        after["checkout_status"] = "abandoned"
    audit = CanonicalAdminAuditEventRecord(
        id=f"audit-{uuid.uuid4().hex}",
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="commerce.event.reject",
        target_type="stripe_event",
        target_id=record.stripe_event_id,
        before_hash=_hash_state(before),
        after_hash=_hash_state(after),
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )
    session.add(audit)
    session.flush()
    return audit
