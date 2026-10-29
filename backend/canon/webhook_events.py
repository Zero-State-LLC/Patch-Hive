"""Provider webhook event processor (spec 004 FR-011, FR-014, research R1).

``receive_stripe_webhook`` verifies and records an event, then calls
``process_stripe_event`` in the same transaction. The processor dispatches by event type
and leaves the record in a final disposition with ``processed_at`` set:

- ``processed``: a handler applied the event.
- ``duplicate``: a handler found the effect already applied (for example, the same
  provider payment under a new event id).
- ``unresolved``: the event cannot be applied safely. It carries a ``reason_code`` for
  operator review, and any writes the handler made are rolled back, so it grants nothing.
- ``ignored``: no handler exists for the event type.

No event stays ``received``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from sqlalchemy.orm import Session

from canon.models import StripeEventRecordModel

EventStatus = Literal["processed", "duplicate", "unresolved", "ignored"]
FINAL_EVENT_STATUSES: frozenset[str] = frozenset(
    {"processed", "duplicate", "unresolved", "ignored"}
)


@dataclass(frozen=True)
class EventDisposition:
    status: EventStatus
    reason_code: str | None = None


class UnresolvedEventError(Exception):
    """Raised by a handler that cannot apply an event safely."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


EventHandler = Callable[[Session, dict[str, Any]], EventDisposition]


def _machine_not_built(_session: Session, _event: dict[str, Any]) -> EventDisposition:
    # Fail closed (FR-014): these events move money or tiers, so an operator must see
    # them until their machine exists. Machine B (T046) and Machine C (T049) replace
    # these entries with real handlers.
    return EventDisposition("unresolved", "HANDLER_NOT_IMPLEMENTED")


# The four event types the observed integration handled (STRIPE_INTEGRATION_PROMPT.md).
EVENT_HANDLERS: dict[str, EventHandler] = {
    "checkout.session.completed": _machine_not_built,
    "customer.subscription.created": _machine_not_built,
    "customer.subscription.updated": _machine_not_built,
    "customer.subscription.deleted": _machine_not_built,
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

    The handler runs in a savepoint. An unresolved outcome rolls the savepoint back. An
    unexpected exception propagates so the caller rolls back the whole delivery and the
    provider retries it.
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
            if disposition.status == "unresolved":
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
