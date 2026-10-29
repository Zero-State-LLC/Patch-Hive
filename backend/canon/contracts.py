"""Versioned, transport-independent contracts for the canonical PatchHive MVP."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "patchhive.canon.v1"


class EpistemicStatus(str, Enum):
    confirmed = "confirmed"
    inferred = "inferred"
    disputed = "disputed"
    missing = "missing"


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="python", exclude_none=True))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        instant = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return (
            instant.astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical JSON does not permit non-finite numbers")
        return 0.0 if value == 0 else value
    if isinstance(value, dict):
        return {str(key): _normalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class CanonicalContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SCHEMA_VERSION

    def canonical_dict(self) -> dict[str, Any]:
        normalized = _normalize(self)
        if not isinstance(normalized, dict):  # pragma: no cover - model invariant
            raise TypeError("canonical contract must normalize to an object")
        return normalized

    def canonical_json(self) -> str:
        return canonical_json(self)

    def canonical_hash_value(self) -> str:
        return canonical_sha256(self)


class EvidenceRecord(CanonicalContract):
    evidence_id: str
    source_type: Literal["manual", "gallery", "photo", "provider", "import"]
    source_ref: str | None = None
    captured_at: datetime
    payload_hash: str | None = None
    confidence: float = Field(ge=0, le=1)
    status: EpistemicStatus


class ArtifactContract(CanonicalContract):
    artifact_id: str
    entity_id: str
    generator_version: str
    generation_seed: int
    canonical_hash: str | None = None
    source_run_id: str
    source_rig_revision_id: str
    created_at: datetime
    provenance: tuple[EvidenceRecord, ...] = ()
    confidence: float = Field(default=1.0, ge=0, le=1)
    status: EpistemicStatus = EpistemicStatus.confirmed

    def computed_hash(self) -> str:
        return canonical_sha256(self.model_dump(exclude={"canonical_hash"}))

    def seal(self) -> Self:
        return self.model_copy(update={"canonical_hash": self.computed_hash()})


class DetectedModule(CanonicalContract):
    detection_id: str
    label_guess: str
    manufacturer_guess: str | None = None
    hp_guess: int | None = Field(default=None, ge=1)
    evidence: tuple[EvidenceRecord, ...]
    confidence: float = Field(ge=0, le=1)
    status: EpistemicStatus = EpistemicStatus.inferred


class ResolvedModuleRef(CanonicalContract):
    detection_id: str
    module_gallery_id: str | None = None
    module_revision_id: str | None = None
    evidence: tuple[EvidenceRecord, ...] = ()
    confidence: float = Field(ge=0, le=1)
    status: EpistemicStatus


class ModulePort(CanonicalContract):
    port_id: str
    label: str
    direction: Literal["input", "output", "bidirectional"]
    signal_type: Literal["audio", "cv", "gate", "trigger", "clock", "unknown"]
    voltage_min: float | None = None
    voltage_max: float | None = None
    active_modes: tuple[str, ...] = ()


class ModuleGalleryEntry(CanonicalContract):
    module_gallery_id: str
    manufacturer: str
    name: str
    current_revision_id: str | None = None
    status: EpistemicStatus


class ModuleRevision(CanonicalContract):
    module_revision_id: str
    module_gallery_id: str
    previous_revision_id: str | None = None
    manufacturer: str
    name: str
    hp: int | None = Field(default=None, ge=1)
    ports: tuple[ModulePort, ...] = ()
    normalled_connections: tuple[tuple[str, str], ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()
    status: EpistemicStatus
    created_at: datetime


class RigModule(CanonicalContract):
    instance_id: str
    module_revision_id: str
    position: int = Field(ge=0)


class RigSpec(CanonicalContract):
    rig_id: str
    name: str
    modules: tuple[RigModule, ...]
    evidence: tuple[EvidenceRecord, ...] = ()


class CanonicalRig(CanonicalContract):
    rig_id: str
    rig_revision_id: str
    modules: tuple[RigModule, ...]
    canonical_hash: str

    @model_validator(mode="after")
    def unique_instances(self) -> "CanonicalRig":
        ids = [module.instance_id for module in self.modules]
        if len(ids) != len(set(ids)):
            raise ValueError("rig module instance IDs must be unique")
        return self


class RigRevision(CanonicalContract):
    rig_revision_id: str
    rig_id: str
    previous_revision_id: str | None = None
    canonical_rig: CanonicalRig
    created_at: datetime


NOT_COMPUTABLE = "NOT_COMPUTABLE"

# A score is a number, or ``NOT_COMPUTABLE`` while its formula is undefined (spec 001 OQ-11).
MetricScore = Annotated[float, Field(ge=0)] | Literal["NOT_COMPUTABLE"]


class RigMetricsPacket(ArtifactContract):
    # ``rig_id`` and ``category_counts`` are optional so packets sealed before FR-027
    # (spec 001) still validate; None fields drop out of the canonical hash.
    rig_id: str | None = None
    module_count: int = Field(ge=0)
    category_counts: dict[str, int] | None = None
    total_hp: int | None = Field(default=None, ge=0)
    modulation_budget: MetricScore | None = None
    routing_flex_score: MetricScore
    clock_coherence_score: MetricScore | None = None
    chaos_headroom: MetricScore | None = None
    learning_gradient_index: MetricScore | None = None
    performance_density_index: MetricScore | None = None
    confidence_notes: tuple[str, ...] = ()


class LayoutPlacement(CanonicalContract):
    instance_id: str
    row: int = Field(ge=0)
    start_hp: int = Field(ge=0)


class SuggestedLayout(ArtifactContract):
    layout_id: str
    label: str
    placements: tuple[LayoutPlacement, ...]
    score: float


class PatchPort(CanonicalContract):
    port_id: str
    module_instance_id: str
    module_port_id: str
    label: str
    direction: Literal["input", "output", "bidirectional"]
    signal_type: Literal["audio", "cv", "gate", "trigger", "clock", "unknown"]
    voltage_min: float | None = None
    voltage_max: float | None = None
    active_modes: tuple[str, ...] = ()


class PatchNode(CanonicalContract):
    node_id: str
    module_instance_id: str
    label: str
    active_mode: str | None = None
    ports: tuple[PatchPort, ...] = ()


class PatchEdge(CanonicalContract):
    edge_id: str
    source_port_id: str
    target_port_id: str
    signal_type: Literal["audio", "cv", "gate", "trigger", "clock", "unknown"]
    attenuate: bool = False
    breaks_normal: bool = False
    feedback_cycle_id: str | None = None


class PatchGraph(ArtifactContract):
    nodes: tuple[PatchNode, ...]
    edges: tuple[PatchEdge, ...]

    @model_validator(mode="after")
    def graph_integrity(self) -> "PatchGraph":
        ports = {port.port_id: port for node in self.nodes for port in node.ports}
        if len(ports) != sum(len(node.ports) for node in self.nodes):
            raise ValueError("patch port IDs must be unique")
        for edge in self.edges:
            if edge.source_port_id not in ports or edge.target_port_id not in ports:
                raise ValueError(f"edge {edge.edge_id} references an unknown port")
        return self


class PatchStep(CanonicalContract):
    position: int = Field(ge=0)
    phase: Literal["prep", "threshold", "peak", "release", "seal"]
    instruction: str
    expected_result: str | None = None
    warning: str | None = None


class PatchVariation(CanonicalContract):
    variation_id: str
    label: str
    generation_seed: int
    graph_hash: str


class PatchPlan(ArtifactContract):
    title: str
    intent: str
    steps: tuple[PatchStep, ...]
    variations: tuple[PatchVariation, ...] = ()

    @model_validator(mode="after")
    def required_phases(self) -> "PatchPlan":
        phases = {step.phase for step in self.steps}
        missing = {"prep", "threshold", "peak", "release", "seal"} - phases
        if missing:
            raise ValueError(f"patch plan missing phases: {', '.join(sorted(missing))}")
        return self


class ValidationIssue(CanonicalContract):
    code: str
    severity: Literal["info", "warning", "error", "critical"]
    message: str
    edge_id: str | None = None
    module_instance_id: str | None = None
    remediation: str | None = None


class ValidationReport(ArtifactContract):
    valid: bool
    issues: tuple[ValidationIssue, ...] = ()

    @model_validator(mode="after")
    def validity_matches_issues(self) -> "ValidationReport":
        blocking = any(issue.severity in {"error", "critical"} for issue in self.issues)
        if self.valid == blocking:
            raise ValueError("valid must be false exactly when blocking issues exist")
        return self


class SymbolicPatchEnvelope(ArtifactContract):
    topology_hash: str
    signal_domains: tuple[str, ...]
    feedback_cycle_ids: tuple[str, ...] = ()
    closure_strength: float = Field(ge=0, le=1)


class ManifestArtifact(CanonicalContract):
    path: str
    media_type: str
    byte_length: int = Field(ge=0)
    sha256: str


class StageReceipt(ArtifactContract):
    stage: str
    operation: str
    operation_version: str
    determinism_class: Literal["deterministic", "evidence_acquisition"]
    input_hash: str
    output_hash: str
    permitted_side_effects: tuple[str, ...] = ()


class ArtifactManifest(ArtifactContract):
    artifacts: tuple[ManifestArtifact, ...]
    stage_receipts: tuple[StageReceipt, ...] = ()


class GenerationRequest(CanonicalContract):
    request_id: str
    user_id: int
    rig_revision_id: str
    seed: int
    generator_version: str
    idempotency_key: str
    requested_at: datetime


class GenerationJob(CanonicalContract):
    job_id: str
    request_id: str
    run_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    attempts: int = Field(default=0, ge=0)
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class ExportRequest(CanonicalContract):
    request_id: str
    user_id: int
    source_run_id: str
    source_rig_revision_id: str
    formats: tuple[Literal["pdf", "svg", "json", "zip"], ...]
    license: str
    credit_cost: int = Field(ge=0)
    idempotency_key: str
    requested_at: datetime


class ExportRecord(CanonicalContract):
    export_id: str
    user_id: int
    source_run_id: str
    source_rig_revision_id: str
    artifact_manifest_hash: str
    export_version: str
    license: str
    credit_cost: int = Field(ge=0)
    ledger_entry_id: str
    status: Literal["queued", "running", "succeeded", "failed", "refunded"]
    created_at: datetime


class CreditLedgerEntry(CanonicalContract):
    ledger_entry_id: str
    user_id: int
    delta: int
    entry_type: Literal["purchase", "debit", "grant", "refund", "reversal"]
    idempotency_key: str
    export_id: str | None = None
    created_at: datetime


class StripeEventRecord(CanonicalContract):
    stripe_event_id: str
    event_type: str
    payload_hash: str
    livemode: bool
    status: Literal["received", "processed", "duplicate", "unresolved", "ignored", "rejected"]
    received_at: datetime
    processed_at: datetime | None = None
    reason_code: str | None = None


class AdminAuditEvent(CanonicalContract):
    audit_event_id: str
    actor_user_id: int
    actor_role: str
    action: str
    target_type: str
    target_id: str
    before_hash: str | None = None
    after_hash: str | None = None
    reason: str
    created_at: datetime


class UserPatchAnnotation(CanonicalContract):
    annotation_id: str
    user_id: int
    patch_id: str
    notes: str | None = None
    favorite: bool = False
    tried: bool = False
    updated_at: datetime


class PatchCompilation(CanonicalContract):
    """Complete output of the deterministic patch compilation boundary."""

    patch_graph: PatchGraph
    patch_plan: PatchPlan
    validation_report: ValidationReport
    variations: tuple[PatchVariation, ...]
    stage_receipts: tuple[StageReceipt, ...]
    artifact_manifest: ArtifactManifest
