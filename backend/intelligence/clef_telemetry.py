"""Structured resolution telemetry separating provider failure from low confidence."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum

from intelligence.contracts import DecisionPacket
from intelligence.policy import DecisionDisposition, PolicyResult


class OutcomeCategory(str, Enum):
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    ABSTAINED = "ABSTAINED"
    PROPOSED = "PROPOSED"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class ResolutionTelemetry:
    provider: str
    provider_version: str
    category: OutcomeCategory
    adapter_state: str | None
    error_code: str | None
    disposition: str | None
    reason_codes: tuple[str, ...]
    resolution_state: str | None
    latency_ms: int | None
    has_confidence: bool


def telemetry_for_provider_failure(
    *,
    provider: str,
    provider_version: str,
    error_code: str,
    adapter_state: str | None,
    resolution_state: str | None,
    latency_ms: int | None = None,
) -> ResolutionTelemetry:
    category = (
        OutcomeCategory.DISABLED
        if error_code == "CLEF_DISABLED"
        else OutcomeCategory.PROVIDER_FAILURE
    )
    return ResolutionTelemetry(
        provider=provider,
        provider_version=provider_version,
        category=category,
        adapter_state=adapter_state,
        error_code=error_code,
        disposition=None,
        reason_codes=(),
        resolution_state=resolution_state,
        latency_ms=latency_ms,
        has_confidence=False,
    )


def categorize_policy_result(result: PolicyResult) -> OutcomeCategory:
    disposition = result.disposition
    if disposition is DecisionDisposition.AUTO_PROPOSE:
        return OutcomeCategory.PROPOSED
    if disposition is DecisionDisposition.USER_REVIEW:
        return OutcomeCategory.REVIEW
    if disposition is DecisionDisposition.REJECT:
        return OutcomeCategory.REJECTED
    if disposition is DecisionDisposition.ESCALATE:
        if any(code.startswith("PROVIDER_") for code in result.reason_codes):
            return OutcomeCategory.PROVIDER_FAILURE
        return OutcomeCategory.REVIEW
    if "ABSTAINED_UNKNOWN" in result.reason_codes:
        return OutcomeCategory.ABSTAINED
    return OutcomeCategory.LOW_CONFIDENCE


def telemetry_for_policy_result(
    *,
    packet: DecisionPacket,
    result: PolicyResult,
    resolution_state: str | None,
    latency_ms: int | None = None,
) -> ResolutionTelemetry:
    return ResolutionTelemetry(
        provider=packet.provider,
        provider_version=packet.provider_version,
        category=categorize_policy_result(result),
        adapter_state=None,
        error_code=None,
        disposition=result.disposition.value,
        reason_codes=result.reason_codes,
        resolution_state=resolution_state,
        latency_ms=latency_ms,
        has_confidence=packet.confidence is not None,
    )


def to_log_record(t: ResolutionTelemetry) -> dict[str, object]:
    return {
        "event": "patchhive.decision.resolution",
        "provider": t.provider,
        "provider_version": t.provider_version,
        "category": t.category.value,
        "adapter_state": t.adapter_state,
        "error_code": t.error_code,
        "disposition": t.disposition,
        "reason_codes": list(t.reason_codes),
        "resolution_state": t.resolution_state,
        "latency_ms": t.latency_ms,
        "has_confidence": t.has_confidence,
    }


def emit(
    t: ResolutionTelemetry, logger: logging.Logger | None = None
) -> dict[str, object]:
    target = (
        logger
        if logger is not None
        else logging.getLogger("patchhive.decision.telemetry")
    )
    record = to_log_record(t)
    target.info(json.dumps(record, sort_keys=True))
    return record
