"""Append-only persistence for Decision Intelligence proposals.

This module persists diagnostic/advisory receipts only. It has no canonical
inventory dependency and performs no confirmation transition.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from intelligence.models import DecisionReceiptKeyRecord, DecisionReceiptRecord
from intelligence.module_service import DecisionProposal


class IdempotencyConflict(ValueError):
    """The same idempotency key was reused for a different evidence payload."""


@dataclass(frozen=True)
class StoredOutcome:
    """What a key was answered with: the shared receipt plus the policy outcome bound to the key."""

    receipt: DecisionReceiptRecord
    policy_version: str
    disposition: str
    reason_codes: tuple[str, ...]


class IdempotencyKeyTaken(Exception):
    """A concurrent request bound this key first; `outcome` is its committed answer."""

    def __init__(self, outcome: StoredOutcome) -> None:
        super().__init__("IDEMPOTENCY_KEY_TAKEN")
        self.outcome = outcome


def lock_idempotency_key(db: Session, *, request_id: str, idempotency_key: str) -> None:
    """Serialize resolutions that share a key until the transaction ends.

    Postgres only (transaction-scoped advisory lock); a second request blocks here, then
    finds the first one's committed binding. Elsewhere the unique key in
    persist_decision_proposal is the backstop.
    """
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    digest = hashlib.sha256(f"{request_id}\0{idempotency_key}".encode()).digest()
    db.execute(
        text("SELECT pg_advisory_xact_lock(:k)"),
        {"k": int.from_bytes(digest[:8], "big", signed=True)},
    )


def find_idempotent_outcome(
    db: Session,
    *,
    request_id: str,
    idempotency_key: str,
    evidence_hash: str,
) -> StoredOutcome | None:
    """Return the stored outcome for this key, or None when the key is unused.

    Raises IdempotencyConflict when the key was used with a different evidence hash.
    Performs no provider call.
    """
    binding = db.get(DecisionReceiptKeyRecord, (request_id, idempotency_key))
    if binding is None:
        return None
    if binding.evidence_hash != evidence_hash:
        raise IdempotencyConflict("IDEMPOTENCY_KEY_CONFLICT")
    receipt = db.get(DecisionReceiptRecord, binding.receipt_id)
    return StoredOutcome(
        receipt=receipt,
        policy_version=binding.policy_version,
        disposition=binding.disposition,
        reason_codes=tuple(binding.reason_codes or ()),
    )


def persist_decision_proposal(
    db: Session,
    proposal: DecisionProposal,
    *,
    raise_if_bound: bool = False,
) -> DecisionReceiptRecord:
    """Persist one proposal idempotently by immutable packet hash.

    Every accepted key is bound to a receipt, including when the provider decision is
    deduplicated onto an older receipt. With raise_if_bound, a key that is already
    bound raises IdempotencyKeyTaken (a concurrent request committed first), also when
    losing the insert race; otherwise an already-bound key returns its receipt.
    """
    request = proposal.request
    existing = find_idempotent_outcome(
        db,
        request_id=request.request_id,
        idempotency_key=request.idempotency_key,
        evidence_hash=request.evidence_hash,
    )
    if existing is not None:
        if raise_if_bound:
            raise IdempotencyKeyTaken(existing)
        return existing.receipt

    try:
        # A savepoint keeps a lost race from discarding the caller's other work.
        with db.begin_nested():
            record = _insert_or_reuse_receipt(db, proposal)
            db.add(
                DecisionReceiptKeyRecord(
                    request_id=request.request_id,
                    idempotency_key=request.idempotency_key,
                    evidence_hash=request.evidence_hash,
                    policy_version=proposal.policy.policy_version,
                    disposition=proposal.policy.disposition.value,
                    reason_codes=list(proposal.policy.reason_codes),
                    receipt_id=record.id,
                )
            )
            db.flush()
    except IntegrityError:
        # Lost the insert race to a concurrent request.
        winner = find_idempotent_outcome(
            db,
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            evidence_hash=request.evidence_hash,
        )
        if winner is None:
            raise
        if raise_if_bound:
            raise IdempotencyKeyTaken(winner) from None
        return winner.receipt
    return record


def _insert_or_reuse_receipt(db: Session, proposal: DecisionProposal) -> DecisionReceiptRecord:
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
