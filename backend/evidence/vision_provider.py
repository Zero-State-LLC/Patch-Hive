"""Provider-neutral visual evidence acquisition.

Vision providers produce *evidence only*. They must never mutate canonical
system inventory. Product code normalizes provider output into
`canon.visual_contracts` and requires explicit confirmation before inventory
revision creation.

Adapters:
- MockDeterministicVisionProvider — CI-safe, seed-stable
- RecordedFixtureVisionProvider — replay recorded JSON fixtures
- (future) cloud / local model implementations behind the same protocol
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from canon.visual_contracts import (
    ClassificationCandidate,
    ConnectionCandidate,
    ImageQualityReport,
    ImageRegion,
    ProviderReceipt,
    ResolutionStatus,
)

PIPELINE_VERSION = "vision-evidence.v1"


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_json(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VisionProviderContext:
    image_asset_id: str
    image_bytes: bytes
    request_id: str
    seed: int = 0


class VisionEvidenceProvider(Protocol):
    """Provider-neutral interface for visual system intelligence evidence."""

    provider_name: str
    model_name: str
    model_version: str

    def assess_image_quality(self, ctx: VisionProviderContext) -> ImageQualityReport: ...

    def detect_system_regions(self, ctx: VisionProviderContext) -> Sequence[ImageRegion]: ...

    def detect_devices(self, ctx: VisionProviderContext) -> Sequence[ClassificationCandidate]: ...

    def classify_candidates(
        self, ctx: VisionProviderContext, candidates: Sequence[ClassificationCandidate]
    ) -> Sequence[ClassificationCandidate]: ...

    def detect_ports(
        self, ctx: VisionProviderContext, device_candidates: Sequence[ClassificationCandidate]
    ) -> Sequence[ClassificationCandidate]: ...

    def detect_controls(
        self, ctx: VisionProviderContext, device_candidates: Sequence[ClassificationCandidate]
    ) -> Sequence[ClassificationCandidate]: ...

    def infer_visible_connections(
        self, ctx: VisionProviderContext, device_candidates: Sequence[ClassificationCandidate]
    ) -> Sequence[ConnectionCandidate]: ...


def build_provider_receipt(
    *,
    provider: str,
    model: str,
    model_version: str,
    request_id: str,
    input_hash: str,
    response_payload: Any,
    latency_ms: int | None = None,
    cost_metadata: Mapping[str, Any] | None = None,
) -> ProviderReceipt:
    return ProviderReceipt(
        provider=provider,
        model=model,
        model_version=model_version,
        pipeline_version=PIPELINE_VERSION,
        request_id=request_id,
        input_hash=input_hash,
        response_hash=_sha256_json(response_payload),
        latency_ms=latency_ms,
        cost_metadata=dict(cost_metadata or {}),
    )


def assert_candidates_are_untrusted(candidates: Sequence[ClassificationCandidate]) -> None:
    """Fail closed if a provider response attempts self-confirmation."""

    for candidate in candidates:
        if candidate.classification_status is ResolutionStatus.USER_CONFIRMED:
            raise ValueError(
                f"provider output attempted USER_CONFIRMED for {candidate.candidate_id}"
            )


class MockDeterministicVisionProvider:
    """Seed-stable mock provider for CI and local development.

    Detection content is derived from the image content hash so identical inputs
    produce identical evidence without live model calls.
    """

    provider_name = "mock"
    model_name = "deterministic-fixture"
    model_version = "1.0.0"

    def __init__(self, *, min_bytes_for_accept: int = 32) -> None:
        self.min_bytes_for_accept = min_bytes_for_accept

    def _input_hash(self, ctx: VisionProviderContext) -> str:
        return _sha256_bytes(ctx.image_bytes)

    def assess_image_quality(self, ctx: VisionProviderContext) -> ImageQualityReport:
        accepted = len(ctx.image_bytes) >= self.min_bytes_for_accept
        reasons: tuple[str, ...] = () if accepted else ("IMAGE_TOO_SMALL",)
        return ImageQualityReport(
            image_asset_id=ctx.image_asset_id,
            accepted=accepted,
            blur_score=0.1 if accepted else 0.9,
            glare_score=0.05,
            coverage_score=0.8 if accepted else 0.0,
            rotation_degrees=0.0,
            perspective_skew=0.05,
            reasons=reasons,
            status=ResolutionStatus.OBSERVED if accepted else ResolutionStatus.NOT_COMPUTABLE,
        )

    def detect_system_regions(self, ctx: VisionProviderContext) -> Sequence[ImageRegion]:
        if not self.assess_image_quality(ctx).accepted:
            return ()
        digest = self._input_hash(ctx)
        return (
            ImageRegion(
                region_id=f"region-{digest[:12]}",
                image_asset_id=ctx.image_asset_id,
                bbox=(0.05, 0.1, 0.9, 0.8),
                label="rack_overview",
                confidence=0.72,
                status=ResolutionStatus.OBSERVED,
            ),
        )

    def detect_devices(self, ctx: VisionProviderContext) -> Sequence[ClassificationCandidate]:
        quality = self.assess_image_quality(ctx)
        if not quality.accepted:
            return ()
        digest = self._input_hash(ctx)
        evidence_id = f"evidence-{digest[:16]}"
        receipt = build_provider_receipt(
            provider=self.provider_name,
            model=self.model_name,
            model_version=self.model_version,
            request_id=ctx.request_id,
            input_hash=digest,
            response_payload={"devices": 2, "seed": ctx.seed},
            latency_ms=1,
        )
        # Two ranked but unconfirmed candidates — never USER_CONFIRMED.
        candidates = (
            ClassificationCandidate(
                candidate_id=f"cand-mod-a-{digest[:8]}",
                entity_type="module",
                manufacturer="MockAudio",
                model="Oscillator A",
                revision=None,
                confidence=0.81,
                confidence_method="mock_hash_rank",
                alternative_candidates=(f"cand-mod-a-alt-{digest[:8]}",),
                classification_status=ResolutionStatus.INFERRED,
                evidence_id=evidence_id,
                image_region_id=f"region-{digest[:12]}",
                provider_receipt=receipt,
            ),
            ClassificationCandidate(
                candidate_id=f"cand-mod-b-{digest[:8]}",
                entity_type="module",
                manufacturer="MockAudio",
                model="VCA B",
                revision=None,
                confidence=0.64,
                confidence_method="mock_hash_rank",
                alternative_candidates=(),
                classification_status=ResolutionStatus.INFERRED,
                evidence_id=evidence_id,
                image_region_id=f"region-{digest[:12]}",
                provider_receipt=receipt,
            ),
        )
        assert_candidates_are_untrusted(candidates)
        return candidates

    def classify_candidates(
        self, ctx: VisionProviderContext, candidates: Sequence[ClassificationCandidate]
    ) -> Sequence[ClassificationCandidate]:
        # Re-emit with stable confidence; still untrusted.
        assert_candidates_are_untrusted(candidates)
        return tuple(candidates)

    def detect_ports(
        self, ctx: VisionProviderContext, device_candidates: Sequence[ClassificationCandidate]
    ) -> Sequence[ClassificationCandidate]:
        # P1 capability — mock returns empty (NOT_COMPUTABLE at product level).
        return ()

    def detect_controls(
        self, ctx: VisionProviderContext, device_candidates: Sequence[ClassificationCandidate]
    ) -> Sequence[ClassificationCandidate]:
        return ()

    def infer_visible_connections(
        self, ctx: VisionProviderContext, device_candidates: Sequence[ClassificationCandidate]
    ) -> Sequence[ConnectionCandidate]:
        # Cable inference is optional/P1; mock does not invent connections.
        return ()


class RecordedFixtureVisionProvider:
    """Replay a pre-recorded detection packet (no live provider calls)."""

    provider_name = "fixture"
    model_name = "recorded"
    model_version = "1.0.0"

    def __init__(self, packet: Mapping[str, Any]) -> None:
        self._packet = dict(packet)

    def assess_image_quality(self, ctx: VisionProviderContext) -> ImageQualityReport:
        raw = self._packet.get("quality") or {
            "image_asset_id": ctx.image_asset_id,
            "accepted": True,
            "status": "OBSERVED",
        }
        if "image_asset_id" not in raw:
            raw = {**raw, "image_asset_id": ctx.image_asset_id}
        return ImageQualityReport.model_validate(raw)

    def detect_system_regions(self, ctx: VisionProviderContext) -> Sequence[ImageRegion]:
        return tuple(ImageRegion.model_validate(item) for item in self._packet.get("regions", []))

    def detect_devices(self, ctx: VisionProviderContext) -> Sequence[ClassificationCandidate]:
        candidates = tuple(
            ClassificationCandidate.model_validate(item) for item in self._packet.get("devices", [])
        )
        assert_candidates_are_untrusted(candidates)
        return candidates

    def classify_candidates(
        self, ctx: VisionProviderContext, candidates: Sequence[ClassificationCandidate]
    ) -> Sequence[ClassificationCandidate]:
        return tuple(candidates)

    def detect_ports(
        self, ctx: VisionProviderContext, device_candidates: Sequence[ClassificationCandidate]
    ) -> Sequence[ClassificationCandidate]:
        return tuple(
            ClassificationCandidate.model_validate(item) for item in self._packet.get("ports", [])
        )

    def detect_controls(
        self, ctx: VisionProviderContext, device_candidates: Sequence[ClassificationCandidate]
    ) -> Sequence[ClassificationCandidate]:
        return tuple(
            ClassificationCandidate.model_validate(item)
            for item in self._packet.get("controls", [])
        )

    def infer_visible_connections(
        self, ctx: VisionProviderContext, device_candidates: Sequence[ClassificationCandidate]
    ) -> Sequence[ConnectionCandidate]:
        return tuple(
            ConnectionCandidate.model_validate(item) for item in self._packet.get("connections", [])
        )


def collect_evidence_packet(
    provider: VisionEvidenceProvider, ctx: VisionProviderContext
) -> dict[str, Any]:
    """Run the P0 evidence pipeline and return a serializable packet.

    The packet is evidence only. Callers must run confirmation before inventory.
    """

    quality = provider.assess_image_quality(ctx)
    if not quality.accepted:
        return {
            "image_asset_id": ctx.image_asset_id,
            "quality": quality.model_dump(mode="json"),
            "regions": [],
            "devices": [],
            "ports": [],
            "controls": [],
            "connections": [],
            "status": ResolutionStatus.NOT_COMPUTABLE.value,
        }

    regions = list(provider.detect_system_regions(ctx))
    devices = list(provider.detect_devices(ctx))
    devices = list(provider.classify_candidates(ctx, devices))
    assert_candidates_are_untrusted(devices)
    ports = list(provider.detect_ports(ctx, devices))
    controls = list(provider.detect_controls(ctx, devices))
    connections = list(provider.infer_visible_connections(ctx, devices))

    return {
        "image_asset_id": ctx.image_asset_id,
        "quality": quality.model_dump(mode="json"),
        "regions": [region.model_dump(mode="json") for region in regions],
        "devices": [device.model_dump(mode="json") for device in devices],
        "ports": [port.model_dump(mode="json") for port in ports],
        "controls": [control.model_dump(mode="json") for control in controls],
        "connections": [conn.model_dump(mode="json") for conn in connections],
        "status": ResolutionStatus.INFERRED.value,
        "pipeline_version": PIPELINE_VERSION,
        "provider": provider.provider_name,
        "model": provider.model_name,
        "model_version": provider.model_version,
    }


def bind_packet_to_evidence(packet: Mapping[str, Any], evidence_id: str) -> dict[str, Any]:
    """Point every candidate in a packet at the evidence record that will retain it.

    Providers label candidates with their own evidence id (the mock derives one from
    the image hash). The stored ClassificationEvidenceRecord id is the one clients
    and Decision Intelligence address, so candidates must carry that id.
    """

    bound = dict(packet)
    for key in ("devices", "ports", "controls"):
        items = packet.get(key)
        if items:
            bound[key] = [{**item, "evidence_id": evidence_id} for item in items]
    return bound
