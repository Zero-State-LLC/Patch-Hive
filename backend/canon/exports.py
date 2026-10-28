"""Atomic export/ledger service and test-mode Stripe webhook adapter."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from canon.contracts import ExportRequest, canonical_sha256
from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    CanonicalExportRecord,
    StripeEventRecordModel,
)


class ExportBoundaryError(ValueError):
    """Stable export boundary error without internal details."""


def _stable_id(prefix: str, key: str) -> str:
    return f"{prefix}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]}"


def credit_balance(session: Session, user_id: int) -> int:
    return int(
        session.scalar(
            select(func.coalesce(func.sum(CanonicalCreditLedgerEntryRecord.delta), 0)).where(
                CanonicalCreditLedgerEntryRecord.user_id == user_id
            )
        )
        or 0
    )


def _serialize_user_credits(session: Session, user_id: int) -> None:
    """Serialize concurrent debit attempts for one user when the dialect supports it."""
    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else ""
    if dialect == "postgresql":
        # Transaction-scoped advisory lock; key is the signed 32-bit form of user_id.
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(user_id)})
        return
    # Best-effort lock for SQLite/tests: lock existing ledger rows for the user.
    session.scalars(
        select(CanonicalCreditLedgerEntryRecord)
        .where(CanonicalCreditLedgerEntryRecord.user_id == user_id)
        .with_for_update()
    ).all()


def request_export(
    session: Session,
    request: ExportRequest,
    *,
    artifact_manifest_hash: str,
    export_version: str,
) -> CanonicalExportRecord:
    """Create an export and its debit atomically; retries return the first export."""

    existing = session.scalar(
        select(CanonicalExportRecord).where(
            CanonicalExportRecord.idempotency_key == request.idempotency_key,
            CanonicalExportRecord.user_id == request.user_id,
        )
    )
    if existing is not None:
        return existing

    _serialize_user_credits(session, request.user_id)

    # Re-check after acquiring the user lock in case a concurrent writer won.
    existing = session.scalar(
        select(CanonicalExportRecord).where(
            CanonicalExportRecord.idempotency_key == request.idempotency_key,
            CanonicalExportRecord.user_id == request.user_id,
        )
    )
    if existing is not None:
        return existing
    if credit_balance(session, request.user_id) < request.credit_cost:
        raise ExportBoundaryError("INSUFFICIENT_CREDITS")

    # Ids and the debit key are scoped to the user, as the idempotency key is.
    scoped_key = f"{request.user_id}:{request.idempotency_key}"
    export_id = _stable_id("export", scoped_key)
    ledger_id = _stable_id("ledger", f"export:{scoped_key}")
    export = CanonicalExportRecord(
        id=export_id,
        user_id=request.user_id,
        source_run_id=request.source_run_id,
        source_rig_revision_id=request.source_rig_revision_id,
        artifact_manifest_hash=artifact_manifest_hash,
        export_version=export_version,
        license=request.license,
        credit_cost=request.credit_cost,
        ledger_entry_id=ledger_id,
        idempotency_key=request.idempotency_key,
        status="queued",
        created_at=request.requested_at,
    )
    debit = CanonicalCreditLedgerEntryRecord(
        id=ledger_id,
        user_id=request.user_id,
        delta=-request.credit_cost,
        entry_type="debit",
        idempotency_key=f"export:{_stable_id('debit', scoped_key)}",
        export_id=export_id,
        created_at=request.requested_at,
    )
    try:
        with session.begin_nested():
            # Insert export before debit: ledger.export_id FK requires the export row.
            session.add(export)
            session.flush()
            session.add(debit)
            session.flush()
    except IntegrityError:
        winner = session.scalar(
            select(CanonicalExportRecord).where(
                CanonicalExportRecord.idempotency_key == request.idempotency_key,
                CanonicalExportRecord.user_id == request.user_id,
            )
        )
        if winner is not None:
            return winner
        raise
    return export


def compensate_failed_export(
    session: Session,
    export: CanonicalExportRecord,
    *,
    occurred_at: datetime,
) -> CanonicalCreditLedgerEntryRecord | None:
    """Add one immutable reversal for a terminal failure."""

    refund_key = f"refund:{export.id}"
    existing = session.scalar(
        select(CanonicalCreditLedgerEntryRecord).where(
            CanonicalCreditLedgerEntryRecord.idempotency_key == refund_key
        )
    )
    if existing is not None:
        return existing
    if export.credit_cost == 0:
        export.status = "failed"
        return None
    reversal = CanonicalCreditLedgerEntryRecord(
        id=_stable_id("ledger", refund_key),
        user_id=export.user_id,
        delta=export.credit_cost,
        entry_type="reversal",
        idempotency_key=refund_key,
        export_id=export.id,
        created_at=occurred_at,
    )
    export.status = "refunded"
    session.add(reversal)
    session.flush()
    return reversal


@dataclass(frozen=True)
class ReconciliationReport:
    user_id: int
    balance: int
    export_debits: int
    reversals: int
    anomalies: tuple[str, ...]


def reconcile_ledger(session: Session, user_id: int) -> ReconciliationReport:
    entries = tuple(
        session.scalars(
            select(CanonicalCreditLedgerEntryRecord).where(
                CanonicalCreditLedgerEntryRecord.user_id == user_id
            )
        )
    )
    exports = tuple(
        session.scalars(
            select(CanonicalExportRecord).where(CanonicalExportRecord.user_id == user_id)
        )
    )
    by_export: dict[str, list[CanonicalCreditLedgerEntryRecord]] = {}
    for entry in entries:
        if entry.export_id:
            by_export.setdefault(entry.export_id, []).append(entry)
    anomalies: list[str] = []
    for export in exports:
        related = by_export.get(export.id, [])
        debits = [entry for entry in related if entry.entry_type == "debit"]
        reversals = [entry for entry in related if entry.entry_type in {"refund", "reversal"}]
        if export.credit_cost and len(debits) != 1:
            anomalies.append(f"{export.id}: expected one debit, found {len(debits)}")
        if export.status == "refunded" and len(reversals) != 1:
            anomalies.append(f"{export.id}: expected one reversal, found {len(reversals)}")
    return ReconciliationReport(
        user_id=user_id,
        balance=sum(entry.delta for entry in entries),
        export_debits=sum(-entry.delta for entry in entries if entry.entry_type == "debit"),
        reversals=sum(
            entry.delta for entry in entries if entry.entry_type in {"refund", "reversal"}
        ),
        anomalies=tuple(sorted(anomalies)),
    )


def verify_stripe_webhook(
    session: Session,
    *,
    payload: bytes,
    signature_header: str,
    secret: str,
    test_mode: bool = True,
    now: int | None = None,
    tolerance_seconds: int = 300,
) -> tuple[StripeEventRecordModel, dict[str, Any]]:
    """Verify Stripe-style signatures and reject replay conflicts/livemode events."""

    fields = dict(part.split("=", 1) for part in signature_header.split(",") if "=" in part)
    try:
        timestamp = int(fields["t"])
        supplied = fields["v1"]
    except (KeyError, ValueError) as exc:
        raise ExportBoundaryError("WEBHOOK_SIGNATURE_INVALID") from exc
    current = int(time.time()) if now is None else now
    if abs(current - timestamp) > tolerance_seconds:
        raise ExportBoundaryError("WEBHOOK_SIGNATURE_EXPIRED")
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + payload,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise ExportBoundaryError("WEBHOOK_SIGNATURE_INVALID")
    try:
        event = json.loads(payload)
        event_id = str(event["id"])
        event_type = str(event["type"])
        livemode = bool(event["livemode"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ExportBoundaryError("WEBHOOK_PAYLOAD_INVALID") from exc
    if test_mode and livemode:
        raise ExportBoundaryError("LIVEMODE_EVENT_REJECTED")

    payload_hash = canonical_sha256(event)
    existing = session.get(StripeEventRecordModel, event_id)
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise ExportBoundaryError("WEBHOOK_REPLAY_CONFLICT")
        return existing, event
    record = StripeEventRecordModel(
        stripe_event_id=event_id,
        event_type=event_type,
        payload_hash=payload_hash,
        livemode=livemode,
        status="received",
        received_at=datetime.fromtimestamp(timestamp, tz=timezone.utc),
    )
    session.add(record)
    session.flush()
    return record, event
