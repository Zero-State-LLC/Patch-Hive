"""Confirmed inventory revisions and hardware-constrained patch gates.

Rules:
1. A generation run binds to exactly one immutable inventory revision.
2. Canonical generation never treats unresolved candidates as confirmed.
3. Missing technical data remains missing (NOT_COMPUTABLE when required).
4. Vision/provider output cannot create inventory items without confirmation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from canon.contracts import (
    PatchGraph,
    ValidationIssue,
    ValidationReport,
    canonical_sha256,
)
from canon.visual_contracts import (
    CapabilityPort,
    ClassificationCandidate,
    ConfirmationDecision,
    InventoryItem,
    ResolutionStatus,
    SystemCapability,
    SystemCapabilityGraph,
    SystemInventoryRevision,
)

INVENTORY_BUILDER_VERSION = "inventory-builder.1.0.0"
CAPABILITY_GRAPH_VERSION = "capability-graph.1.0.0"


class InventoryBuildError(ValueError):
    """Raised when confirmation policy cannot produce a valid inventory."""


def _stable_revision_id(system_id: str, payload: object) -> str:
    digest = canonical_sha256({"system_id": system_id, "payload": payload})
    return f"inv-rev-{digest[:24]}"


def build_system_inventory_revision(
    *,
    system_id: str,
    candidates: Sequence[ClassificationCandidate],
    decisions: Sequence[ConfirmationDecision],
    created_at: datetime,
    created_by: str | None = None,
    previous_revision_id: str | None = None,
    manual_items: Sequence[InventoryItem] = (),
) -> SystemInventoryRevision:
    """Create an immutable inventory revision from confirmation decisions.

    Only USER_CONFIRMED decisions and explicit manual items enter the inventory.
    Unresolved candidates are retained as IDs for review, not as modules.
    """

    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    decisions_by_candidate: dict[str, ConfirmationDecision] = {}
    for decision in sorted(decisions, key=lambda item: item.confirmed_at.isoformat()):
        decisions_by_candidate[decision.candidate_id] = decision

    items: list[InventoryItem] = list(manual_items)
    unresolved: list[str] = []

    for candidate in sorted(candidates, key=lambda item: item.candidate_id):
        decision = decisions_by_candidate.get(candidate.candidate_id)
        if decision is None:
            unresolved.append(candidate.candidate_id)
            continue
        if decision.status in {"reject", "defer"}:
            if decision.status == "defer":
                unresolved.append(candidate.candidate_id)
            continue
        if decision.status == "replace":
            if not decision.replacement_candidate_id:
                raise InventoryBuildError("replace decision requires replacement_candidate_id")
            replacement = candidate_by_id.get(decision.replacement_candidate_id)
            if replacement is None:
                raise InventoryBuildError(
                    f"replacement candidate {decision.replacement_candidate_id} not found"
                )
            revision_id = replacement.gallery_revision_id
            if not revision_id:
                raise InventoryBuildError(
                    "replacement candidate lacks gallery_revision_id; cannot invent identity"
                )
            items.append(
                InventoryItem(
                    instance_id=f"inst-{candidate.candidate_id}",
                    module_revision_id=revision_id,
                    manufacturer=replacement.manufacturer,
                    model=replacement.model,
                    resolution=ResolutionStatus.USER_CONFIRMED,
                    source_candidate_ids=(candidate.candidate_id, replacement.candidate_id),
                    evidence_ids=(candidate.evidence_id, replacement.evidence_id),
                    confirmed_by=decision.confirmed_by,
                    confirmed_at=decision.confirmed_at,
                )
            )
            continue
        if decision.status == "manual_add":
            items.append(
                InventoryItem(
                    instance_id=f"inst-{candidate.candidate_id}",
                    module_revision_id=decision.manual_module_revision_id or "",
                    manufacturer=candidate.manufacturer,
                    model=candidate.model,
                    resolution=ResolutionStatus.USER_CONFIRMED,
                    source_candidate_ids=(candidate.candidate_id,),
                    evidence_ids=(candidate.evidence_id,),
                    confirmed_by=decision.confirmed_by,
                    confirmed_at=decision.confirmed_at,
                )
            )
            continue
        # confirm
        if decision.resolved_status is not ResolutionStatus.USER_CONFIRMED:
            raise InventoryBuildError("confirm decision must be USER_CONFIRMED")
        if not candidate.gallery_revision_id:
            raise InventoryBuildError(
                f"candidate {candidate.candidate_id} confirmed without gallery_revision_id; "
                "missing identity remains NOT_COMPUTABLE"
            )
        items.append(
            InventoryItem(
                instance_id=f"inst-{candidate.candidate_id}",
                module_revision_id=candidate.gallery_revision_id,
                manufacturer=candidate.manufacturer,
                model=candidate.model,
                resolution=ResolutionStatus.USER_CONFIRMED,
                source_candidate_ids=(candidate.candidate_id,),
                evidence_ids=(candidate.evidence_id,),
                confirmed_by=decision.confirmed_by,
                confirmed_at=decision.confirmed_at,
            )
        )

    # Reject any item that is not user-confirmed (fail closed for generation readiness).
    confirmed_items = tuple(
        item for item in items if item.resolution is ResolutionStatus.USER_CONFIRMED
    )
    payload = {
        "system_id": system_id,
        "previous_revision_id": previous_revision_id,
        "items": [item.model_dump(mode="json") for item in confirmed_items],
        "unresolved": sorted(set(unresolved)),
        "builder_version": INVENTORY_BUILDER_VERSION,
    }
    revision_id = _stable_revision_id(system_id, payload)
    revision = SystemInventoryRevision(
        inventory_revision_id=revision_id,
        system_id=system_id,
        previous_revision_id=previous_revision_id,
        items=confirmed_items,
        unresolved_candidate_ids=tuple(sorted(set(unresolved))),
        created_at=created_at,
        created_by=created_by,
    )
    return revision.seal()


def build_system_capability_graph(
    *,
    inventory: SystemInventoryRevision,
    ports: Sequence[CapabilityPort] = (),
    capabilities: Sequence[SystemCapability] = (),
    missing_specifications: Sequence[str] = (),
) -> SystemCapabilityGraph:
    """Build a deterministic capability graph from a confirmed inventory."""

    confirmed_instances = {
        item.instance_id
        for item in inventory.items
        if item.resolution is ResolutionStatus.USER_CONFIRMED
    }
    for port in ports:
        if port.module_instance_id not in confirmed_instances:
            raise InventoryBuildError(
                f"port {port.port_id} references unconfirmed instance {port.module_instance_id}"
            )
    if not capabilities and inventory.items:
        capabilities = tuple(
            SystemCapability(
                capability_id=f"cap-{item.instance_id}",
                category="module",
                module_instance_ids=(item.instance_id,),
                signal_domains=(),
                notes="capability details missing" if not ports else None,
            )
            for item in inventory.items
            if item.resolution is ResolutionStatus.USER_CONFIRMED
        )
    graph = SystemCapabilityGraph(
        graph_id=f"cap-graph-{inventory.inventory_revision_id}",
        inventory_revision_id=inventory.inventory_revision_id,
        capabilities=tuple(capabilities),
        ports=tuple(ports),
        missing_specifications=tuple(missing_specifications),
    )
    return graph.seal()


def inventory_ready_for_generation(inventory: SystemInventoryRevision) -> bool:
    """True when at least one USER_CONFIRMED module exists and no blocking unknowns.

    Unresolved candidates may remain for later review; they do not block generation
    of patches that only use confirmed modules.

    This reads one revision. Generation reads the Rig's placements, so what the API reports
    as ready comes from ``patches.inventory_gate.evaluate_rack_inventory_gate``.
    """

    return any(item.resolution is ResolutionStatus.USER_CONFIRMED for item in inventory.items)


def enforce_confirmed_inventory_constraints(
    *,
    graph: PatchGraph,
    inventory: SystemInventoryRevision,
    capability_graph: SystemCapabilityGraph | None = None,
) -> ValidationReport:
    """Validate that a patch graph only uses confirmed inventory modules/ports.

    Returns a ValidationReport. Generation callers should treat `valid=False` as
    fail-closed (do not publish). When inventory has no confirmed modules, the
    report includes NOT_COMPUTABLE.
    """

    issues: list[ValidationIssue] = []
    confirmed_revisions = inventory.confirmed_module_revision_ids()
    confirmed_instances = {
        item.instance_id
        for item in inventory.items
        if item.resolution is ResolutionStatus.USER_CONFIRMED
    }

    if not confirmed_revisions:
        issues.append(
            ValidationIssue(
                code="NOT_COMPUTABLE",
                severity="critical",
                message=(
                    "No USER_CONFIRMED modules in inventory revision; "
                    "patch generation is not computable."
                ),
            )
        )

    if capability_graph is not None:
        if capability_graph.inventory_revision_id != inventory.inventory_revision_id:
            issues.append(
                ValidationIssue(
                    code="INVENTORY_REVISION_MISMATCH",
                    severity="critical",
                    message="Capability graph is bound to a different inventory revision.",
                )
            )
        allowed_ports = capability_graph.port_ids()
        allowed_instances = capability_graph.module_instance_ids() | confirmed_instances
    else:
        allowed_ports = frozenset()
        allowed_instances = confirmed_instances

    for node in graph.nodes:
        if node.module_instance_id not in allowed_instances:
            issues.append(
                ValidationIssue(
                    code="UNCONFIRMED_MODULE",
                    severity="error",
                    message=(
                        f"Module instance {node.module_instance_id} is not in the "
                        "confirmed inventory revision."
                    ),
                    module_instance_id=node.module_instance_id,
                )
            )

    if capability_graph is not None and allowed_ports:
        graph_ports = {port.port_id for node in graph.nodes for port in node.ports}
        for port_id in sorted(graph_ports):
            if port_id not in allowed_ports:
                issues.append(
                    ValidationIssue(
                        code="UNCONFIRMED_PORT",
                        severity="error",
                        message=f"Port {port_id} is not present on the confirmed capability graph.",
                    )
                )
        for edge in graph.edges:
            if edge.source_port_id not in allowed_ports or edge.target_port_id not in allowed_ports:
                issues.append(
                    ValidationIssue(
                        code="UNCONFIRMED_CONNECTION",
                        severity="error",
                        message=(
                            f"Edge {edge.edge_id} uses ports outside the confirmed capability graph."
                        ),
                        edge_id=edge.edge_id,
                    )
                )

    # Never allow generation against unresolved candidates masquerading as modules.
    unresolved = set(inventory.unresolved_candidate_ids)
    for node in graph.nodes:
        if node.module_instance_id in unresolved or node.module_instance_id.startswith("cand-"):
            issues.append(
                ValidationIssue(
                    code="CANDIDATE_AS_CANONICAL",
                    severity="critical",
                    message=(
                        f"Node {node.node_id} references unresolved candidate identity "
                        f"{node.module_instance_id}."
                    ),
                    module_instance_id=node.module_instance_id,
                )
            )

    fields = {
        "artifact_id": f"val-inv-{graph.artifact_id}",
        "entity_id": graph.entity_id,
        "generator_version": INVENTORY_BUILDER_VERSION,
        "generation_seed": graph.generation_seed,
        "source_run_id": graph.source_run_id,
        "source_rig_revision_id": inventory.inventory_revision_id,
        "created_at": graph.created_at,
    }
    blocking = any(issue.severity in {"error", "critical"} for issue in issues)
    return ValidationReport(
        **fields,
        valid=not blocking,
        issues=tuple(issues),
    )


def candidates_cannot_mutate_inventory(
    candidates: Iterable[ClassificationCandidate],
) -> None:
    """Contract guard: provider candidates must not carry USER_CONFIRMED status."""

    for candidate in candidates:
        if candidate.classification_status is ResolutionStatus.USER_CONFIRMED:
            raise InventoryBuildError(
                f"candidate {candidate.candidate_id} illegally self-confirmed"
            )
