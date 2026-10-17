"""Flag-gated evidence-resolution orchestration for Decision Intelligence.

The command accepts exactly one retained evidence record. Its candidate universe
is derived only from that record's immutable packet. The result is advisory and
is persisted as a DecisionReceipt; canonical inventory is never touched.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from canon.models import ClassificationEvidenceRecord
from canon.visual_contracts import ClassificationCandidate
from intelligence.module_service import CatalogCandidate, DecisionProposal, ModuleDecisionService
from intelligence.persistence import persist_decision_proposal
from intelligence.policy import DecisionPolicy
from intelligence.provider import DecisionProvider


class DecisionIntelligenceDisabled(RuntimeError):
    pass


class EvidenceResolutionError(ValueError):
    pass


def resolve_module_identity(
    db: Session,
    *,
    evidence_id: str,
    provider: DecisionProvider,
    policy: DecisionPolicy,
    enabled: bool,
    idempotency_key: str,
) -> DecisionProposal:
    if not enabled:
        raise DecisionIntelligenceDisabled("Decision Intelligence is disabled")

    evidence = db.get(ClassificationEvidenceRecord, evidence_id)
    if evidence is None:
        raise EvidenceResolutionError("evidence record not found")

    packet = evidence.evidence_packet or {}
    raw_devices = packet.get("devices") or []
    candidates: list[CatalogCandidate] = []
    normalized_devices: list[dict] = []

    for raw in raw_devices:
        try:
            candidate = ClassificationCandidate.model_validate(raw)
        except Exception as exc:
            raise EvidenceResolutionError(
                "malformed candidate in bounded evidence packet"
            ) from exc
        if candidate.evidence_id != evidence_id:
            raise EvidenceResolutionError("candidate evidence binding does not match record")
        if candidate.entity_type not in {"device", "module"}:
            continue
        candidates.append(
            CatalogCandidate(
                candidate_id=candidate.candidate_id,
                manufacturer=candidate.manufacturer,
                model=candidate.model,
                revision=candidate.revision,
                device_type=candidate.entity_type,
            )
        )
        normalized_devices.append(
            {
                "candidate_id": candidate.candidate_id,
                "manufacturer": candidate.manufacturer,
                "model": candidate.model,
                "revision": candidate.revision,
                "confidence": candidate.confidence,
                "classification_status": candidate.classification_status.value,
            }
        )

    if not candidates:
        raise EvidenceResolutionError("evidence record contains no bounded module candidates")

    service = ModuleDecisionService(provider, policy)
    proposal = service.rank_identity(
        request_id=f"module-identity:{evidence_id}",
        evidence_hash=evidence_id,
        evidence_refs=(str(evidence.image_asset_id), evidence_id),
        normalized_evidence={
            "evidence_status": str(evidence.status),
            "vision_provider": str(evidence.provider),
            "pipeline_version": str(evidence.pipeline_version),
            "devices": normalized_devices,
        },
        candidates=candidates,
        idempotency_key=idempotency_key,
    )
    persist_decision_proposal(db, proposal)
    return proposal
