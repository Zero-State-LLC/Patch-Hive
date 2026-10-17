"""Privacy-minimized telemetry projection for decision intelligence."""

from __future__ import annotations

from dataclasses import dataclass

from intelligence.contracts import DecisionPacket
from intelligence.policy import PolicyResult


@dataclass(frozen=True)
class DecisionTelemetry:
    provider: str
    provider_version: str
    answer_type: str
    provider_status: str
    disposition: str
    reason_codes: tuple[str, ...]
    has_confidence: bool
    has_raw_payload_hash: bool


def project_telemetry(packet: DecisionPacket, result: PolicyResult) -> DecisionTelemetry:
    """Exclude evidence text, context, refs, selected labels, and raw provider payloads."""
    return DecisionTelemetry(
        provider=packet.provider,
        provider_version=packet.provider_version,
        answer_type=packet.answer_type,
        provider_status=packet.provider_status,
        disposition=result.disposition.value,
        reason_codes=result.reason_codes,
        has_confidence=packet.confidence is not None,
        has_raw_payload_hash=packet.raw_payload_hash is not None,
    )
