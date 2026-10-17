"""Bounded decision services for module evidence resolution.

These services construct questions and proposals only. They never create or mutate
SystemInventoryRevision, ModuleRevision, CapabilityPort, or other canonical objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from intelligence.contracts import (
    ChoiceOption,
    ChoiceRequest,
    DecisionPacket,
    DecisionPurpose,
    ProbabilityRequest,
)
from intelligence.policy import DecisionPolicy, PolicyResult
from intelligence.provider import DecisionProvider


MODULE_FAMILIES = (
    "source",
    "processor",
    "modulation",
    "control",
    "utility",
    "sequencing",
    "unknown",
)
PORT_SEMANTICS = (
    "audio_input",
    "audio_output",
    "cv_input",
    "cv_output",
    "gate",
    "clock",
    "trigger",
    "multifunction",
    "unknown",
)


@dataclass(frozen=True)
class CatalogCandidate:
    candidate_id: str
    manufacturer: str | None
    model: str | None
    revision: str | None = None
    device_type: str | None = None
    hp: int | None = None

    def description(self) -> str:
        fields = [
            self.manufacturer or "UNKNOWN_MANUFACTURER",
            self.model or "UNKNOWN_MODEL",
        ]
        if self.revision:
            fields.append(f"revision={self.revision}")
        if self.device_type:
            fields.append(f"type={self.device_type}")
        if self.hp is not None:
            fields.append(f"hp={self.hp}")
        return " | ".join(fields)


@dataclass(frozen=True)
class DecisionProposal:
    request: ChoiceRequest | ProbabilityRequest
    packet: DecisionPacket
    policy: PolicyResult


class ModuleDecisionService:
    def __init__(self, provider: DecisionProvider, policy: DecisionPolicy) -> None:
        self._provider = provider
        self._policy = policy

    def rank_identity(
        self,
        *,
        request_id: str,
        evidence_hash: str,
        evidence_refs: tuple[str, ...],
        normalized_evidence: dict,
        candidates: Iterable[CatalogCandidate],
        idempotency_key: str,
    ) -> DecisionProposal:
        ordered = sorted(candidates, key=lambda item: item.candidate_id)
        if not ordered:
            raise ValueError("module identity ranking requires server-supplied catalog candidates")
        choices = tuple(
            ChoiceOption(choice_id=item.candidate_id, description=item.description())
            for item in ordered
        ) + (ChoiceOption(choice_id="none_of_above", description="No supplied catalog candidate matches"),)
        request = ChoiceRequest(
            request_id=request_id,
            purpose=DecisionPurpose.module_identity,
            evidence_hash=evidence_hash,
            evidence_refs=evidence_refs,
            context=dict(normalized_evidence),
            idempotency_key=idempotency_key,
            question=(
                "Which server-supplied catalog candidate best matches the normalized "
                "observations? Select none_of_above when evidence is insufficient or conflicts."
            ),
            choices=choices,
        )
        packet = self._provider.choose(request)
        return DecisionProposal(request=request, packet=packet, policy=self._policy.evaluate(packet))

    def classify_family(
        self,
        *,
        request_id: str,
        evidence_hash: str,
        normalized_evidence: dict,
        idempotency_key: str,
    ) -> DecisionProposal:
        request = ChoiceRequest(
            request_id=request_id,
            purpose=DecisionPurpose.module_family,
            evidence_hash=evidence_hash,
            context=dict(normalized_evidence),
            idempotency_key=idempotency_key,
            question="Classify the module's primary functional family from observed evidence only.",
            choices=tuple(
                ChoiceOption(choice_id=value, description=f"module family: {value}")
                for value in MODULE_FAMILIES
            ),
        )
        packet = self._provider.choose(request)
        return DecisionProposal(request=request, packet=packet, policy=self._policy.evaluate(packet))

    def classify_capability(
        self,
        *,
        request_id: str,
        evidence_hash: str,
        normalized_evidence: dict,
        allowed_capabilities: tuple[str, ...],
        idempotency_key: str,
    ) -> DecisionProposal:
        if not allowed_capabilities:
            raise ValueError("capability classification requires a bounded vocabulary")
        values = tuple(dict.fromkeys((*allowed_capabilities, "unknown")))
        request = ChoiceRequest(
            request_id=request_id,
            purpose=DecisionPurpose.capability,
            evidence_hash=evidence_hash,
            context=dict(normalized_evidence),
            idempotency_key=idempotency_key,
            question="Select the best-supported capability from the server-supplied vocabulary.",
            choices=tuple(ChoiceOption(choice_id=value) for value in values),
        )
        packet = self._provider.choose(request)
        return DecisionProposal(request=request, packet=packet, policy=self._policy.evaluate(packet))

    def classify_port(
        self,
        *,
        request_id: str,
        evidence_hash: str,
        normalized_evidence: dict,
        idempotency_key: str,
    ) -> DecisionProposal:
        request = ChoiceRequest(
            request_id=request_id,
            purpose=DecisionPurpose.port_semantics,
            evidence_hash=evidence_hash,
            context=dict(normalized_evidence),
            idempotency_key=idempotency_key,
            question=(
                "Classify this observed port by signal role. Select unknown when label, "
                "direction, or signal evidence is insufficient."
            ),
            choices=tuple(ChoiceOption(choice_id=value) for value in PORT_SEMANTICS),
        )
        packet = self._provider.choose(request)
        return DecisionProposal(request=request, packet=packet, policy=self._policy.evaluate(packet))

    def detect_conflict(
        self,
        *,
        request_id: str,
        evidence_hash: str,
        normalized_evidence: dict,
        idempotency_key: str,
    ) -> DecisionProposal:
        request = ProbabilityRequest(
            request_id=request_id,
            purpose=DecisionPurpose.evidence_conflict,
            evidence_hash=evidence_hash,
            context=dict(normalized_evidence),
            idempotency_key=idempotency_key,
            question="Do the normalized evidence claims materially conflict?",
            true_criteria="Two or more material claims cannot simultaneously describe the same device/port.",
            false_criteria="Claims are compatible, complementary, or differ only in non-material detail.",
        )
        packet = self._provider.probability(request)
        return DecisionProposal(request=request, packet=packet, policy=self._policy.evaluate(packet))
