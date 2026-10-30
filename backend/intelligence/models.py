"""Append-only persistence records for non-canonical decision receipts."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, String, event

from core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DecisionReceiptRecord(Base):
    """Diagnostic/provenance record only. It has no foreign key into canonical artifacts."""

    __tablename__ = "decision_receipts"
    id = Column(String(64), primary_key=True)
    request_id = Column(String(128), nullable=False, index=True)
    schema_version = Column(String(64), nullable=False)
    provider = Column(String(100), nullable=False)
    provider_version = Column(String(100), nullable=False)
    purpose = Column(String(100), nullable=False, index=True)
    evidence_hash = Column(String(64), nullable=False, index=True)
    candidate_set_hash = Column(String(64), nullable=True)
    rubric_hash = Column(String(64), nullable=True)
    answer_type = Column(String(32), nullable=False)
    selected_choice = Column(String(255), nullable=True)
    score = Column(Float, nullable=True)
    probability_yes = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    provider_status = Column(String(32), nullable=False)
    error_code = Column(String(100), nullable=True)
    policy_version = Column(String(100), nullable=False)
    disposition = Column(String(32), nullable=False)
    reason_codes = Column(JSON, nullable=False)
    packet_hash = Column(String(64), nullable=False, unique=True)
    raw_payload_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class DecisionReceiptKeyRecord(Base):
    """Binds one accepted idempotency key to the receipt that answered it.

    Receipts are append-only and one receipt can answer several keys (a provider
    decision id can recur), so keys live in their own table. The primary key is the
    (request_id, idempotency_key) uniqueness the resolution path relies on.
    """

    __tablename__ = "decision_receipt_keys"

    request_id = Column(String(128), primary_key=True)
    idempotency_key = Column(String(128), primary_key=True)
    evidence_hash = Column(String(64), nullable=False)
    receipt_id = Column(
        String(64),
        ForeignKey("decision_receipts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


@event.listens_for(DecisionReceiptRecord, "before_update")
def _deny_update(_mapper, _connection, _target) -> None:
    raise ValueError("decision receipts are append-only")


@event.listens_for(DecisionReceiptRecord, "before_delete")
def _deny_delete(_mapper, _connection, _target) -> None:
    raise ValueError("decision receipts are append-only")


@event.listens_for(DecisionReceiptKeyRecord, "before_update")
def _deny_key_update(_mapper, _connection, _target) -> None:
    raise ValueError("decision receipt keys are append-only")


@event.listens_for(DecisionReceiptKeyRecord, "before_delete")
def _deny_key_delete(_mapper, _connection, _target) -> None:
    raise ValueError("decision receipt keys are append-only")
