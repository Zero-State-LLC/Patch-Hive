"""Append-only persistence for Decision Intelligence proposals.

This module persists diagnostic/advisory receipts only. It has no canonical
inventory dependency and performs no confirmation transition.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from intelligence.models import DecisionReceiptRecord
from intelligence.module_service import DecisionProposal


def persist_decision_proposal(
    db: Session,
    proposal: DecisionProposal,
) -> DecisionReceiptRecord:
    """Persist one proposal idempotently by immutable packet hash."""
    packet = proposal.packet
    request = proposal.request
    policy = proposal.policy
    packet_hash = packet.result_hash()

    existing = (
        db.query(DecisionReceiptRecord)
        .filter(
            (DecisionReceiptRecord.packet_hash == packet_hash)
            | (DecisionReceiptRecord.id == packet.decision_id)
        )
        .first()
    )
    if existing is not None:
        return existing

    candidate_set_hash = (
        request.candidate_set_hash() if hasattr(request, "candidate_set_hash") else None
    )
    rubric_hash = request.rubric_hash() if hasattr(request, "rubric_hash") else None

    record = DecisionReceiptRecord(
        id=packet.decision_id,
        request_id=request.request_id,
        schema_version=packet.schema_version,
        provider=packet.provider,
        provider_version=packet.provider_version,
        purpose=request.purpose.value,
        evidence_hash=request.evidence_hash,
        candidate_set_hash=candidate_set_hash,
        rubric_hash=rubric_hash,
        answer_type=packet.answer_type,
        selected_choice=packet.selected_choice,
        score=packet.score,
        probability_yes=packet.probability_yes,
        confidence=packet.confidence,
        provider_status=packet.provider_status,
        error_code=packet.error_code,
        policy_version=policy.policy_version,
        disposition=policy.disposition.value,
        reason_codes=list(policy.reason_codes),
        packet_hash=packet_hash,
        raw_payload_hash=packet.raw_payload_hash,
        created_at=packet.created_at,
    )
    db.add(record)
    db.flush()
    return record
