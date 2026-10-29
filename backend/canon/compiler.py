"""Pure deterministic patch compiler and safety validator."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime
from typing import Iterable, TypedDict

from canon.contracts import (
    ArtifactManifest,
    ManifestArtifact,
    PatchCompilation,
    PatchEdge,
    PatchGraph,
    PatchNode,
    PatchPlan,
    PatchStep,
    PatchVariation,
    StageReceipt,
    ValidationIssue,
    ValidationReport,
    canonical_json,
    canonical_sha256,
)

GENERATOR_VERSION = "canon-compiler.1.0.0"


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\x1f".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:24]}"


class ArtifactFields(TypedDict):
    artifact_id: str
    entity_id: str
    generator_version: str
    generation_seed: int
    source_run_id: str
    source_rig_revision_id: str
    created_at: datetime


def _artifact_fields(
    *,
    artifact_id: str,
    entity_id: str,
    run_id: str,
    rig_revision_id: str,
    seed: int,
    created_at: datetime,
) -> ArtifactFields:
    return {
        "artifact_id": artifact_id,
        "entity_id": entity_id,
        "generator_version": GENERATOR_VERSION,
        "generation_seed": seed,
        "source_run_id": run_id,
        "source_rig_revision_id": rig_revision_id,
        "created_at": created_at,
    }


def _cycle_edges(edges: tuple[PatchEdge, ...], ports_to_nodes: dict[str, str]) -> set[str]:
    adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in edges:
        source = ports_to_nodes[edge.source_port_id]
        target = ports_to_nodes[edge.target_port_id]
        adjacency[source].append((target, edge.edge_id))

    cycle_edge_ids: set[str] = set()

    def visit(node: str, path_nodes: list[str], path_edges: list[str]) -> None:
        if node in path_nodes:
            index = path_nodes.index(node)
            cycle_edge_ids.update(path_edges[index:])
            return
        if len(path_nodes) > len(ports_to_nodes):
            return
        for neighbor, edge_id in adjacency[node]:
            visit(neighbor, [*path_nodes, node], [*path_edges, edge_id])

    for node in sorted(adjacency):
        visit(node, [], [])
    return cycle_edge_ids


def validate_patch_graph(graph: PatchGraph, plan: PatchPlan) -> ValidationReport:
    """Validate direction, signal, voltage, modes, normals, and feedback safety."""

    ports = {port.port_id: port for node in graph.nodes for port in node.ports}
    ports_to_nodes = {port.port_id: node.node_id for node in graph.nodes for port in node.ports}
    issues: list[ValidationIssue] = []
    cycle_edges = _cycle_edges(graph.edges, ports_to_nodes)

    for edge in graph.edges:
        source = ports[edge.source_port_id]
        target = ports[edge.target_port_id]
        if source.direction not in {"output", "bidirectional"}:
            issues.append(
                ValidationIssue(
                    code="SOURCE_DIRECTION_INVALID",
                    severity="error",
                    message=f"{source.label} is not an output.",
                    edge_id=edge.edge_id,
                )
            )
        if target.direction not in {"input", "bidirectional"}:
            issues.append(
                ValidationIssue(
                    code="TARGET_DIRECTION_INVALID",
                    severity="error",
                    message=f"{target.label} is not an input.",
                    edge_id=edge.edge_id,
                )
            )
        if "unknown" in {source.signal_type, target.signal_type, edge.signal_type}:
            issues.append(
                ValidationIssue(
                    code="UNSUPPORTED_CAPABILITY_CLAIM",
                    severity="warning",
                    message="Signal compatibility is unknown and requires confirmation.",
                    edge_id=edge.edge_id,
                )
            )
        elif len({source.signal_type, target.signal_type, edge.signal_type}) != 1:
            issues.append(
                ValidationIssue(
                    code="SIGNAL_TYPE_MISMATCH",
                    severity="error",
                    message="Cable signal class does not match both connected ports.",
                    edge_id=edge.edge_id,
                )
            )
        if (
            source.voltage_max is not None
            and target.voltage_max is not None
            and source.voltage_max > target.voltage_max
            and not edge.attenuate
        ):
            issues.append(
                ValidationIssue(
                    code="ATTENUATION_REQUIRED",
                    severity="critical",
                    message="Source voltage exceeds the target range; attenuate before patching.",
                    edge_id=edge.edge_id,
                )
            )
        if edge.breaks_normal:
            issues.append(
                ValidationIssue(
                    code="NORMALLED_CONNECTION_BREAK",
                    severity="info",
                    message="Inserting this cable breaks a normalled connection.",
                    edge_id=edge.edge_id,
                )
            )
        if edge.edge_id in cycle_edges and edge.feedback_cycle_id is None:
            issues.append(
                ValidationIssue(
                    code="UNDECLARED_FEEDBACK_CYCLE",
                    severity="error",
                    message="Feedback cycles must be explicit and explained before use.",
                    edge_id=edge.edge_id,
                )
            )

    for node in graph.nodes:
        required_modes = sorted({mode for port in node.ports for mode in port.active_modes if mode})
        if required_modes and node.active_mode not in required_modes:
            issues.append(
                ValidationIssue(
                    code="ACTIVE_MODE_UNCONFIRMED",
                    severity="warning",
                    message=f"Confirm an active mode for {node.label}: {', '.join(required_modes)}.",
                    module_instance_id=node.module_instance_id,
                )
            )

    prep_steps = [step for step in plan.steps if step.phase == "prep"]
    if not any(step.warning for step in prep_steps):
        issues.append(
            ValidationIssue(
                code="STARTUP_WARNING_MISSING",
                severity="warning",
                message="The prep phase should state startup and level-safety checks.",
            )
        )

    ordered = tuple(
        sorted(issues, key=lambda issue: (issue.severity, issue.code, issue.edge_id or ""))
    )
    blocking = any(issue.severity in {"error", "critical"} for issue in ordered)
    fields = _artifact_fields(
        artifact_id=_stable_id("validation", graph.artifact_id),
        entity_id=graph.entity_id,
        run_id=graph.source_run_id,
        rig_revision_id=graph.source_rig_revision_id,
        seed=graph.generation_seed,
        created_at=graph.created_at,
    )
    return ValidationReport(valid=not blocking, issues=ordered, **fields).seal()


def compile_patch(
    *,
    run_id: str,
    rig_revision_id: str,
    seed: int,
    intent: str,
    nodes: Iterable[PatchNode],
    edges: Iterable[PatchEdge],
    created_at: datetime,
    title: str | None = None,
) -> PatchCompilation:
    """Compile a complete, byte-stable patch artifact set from normalized inputs.

    ``title`` names the plan (the patch's own name on the generation path). It is part of
    the input hash. Without it the plan is titled ``Signal Path <hash>``.
    """

    ordered_nodes = tuple(sorted(nodes, key=lambda node: node.node_id))
    ordered_edges = tuple(sorted(edges, key=lambda edge: edge.edge_id))
    input_payload = {
        "run_id": run_id,
        "rig_revision_id": rig_revision_id,
        "seed": seed,
        "intent": intent,
        "nodes": ordered_nodes,
        "edges": ordered_edges,
        **({"title": title} if title is not None else {}),
    }
    input_hash = canonical_sha256(input_payload)
    patch_id = _stable_id("patch", input_hash, GENERATOR_VERSION, seed)
    common = _artifact_fields(
        artifact_id=patch_id,
        entity_id=patch_id,
        run_id=run_id,
        rig_revision_id=rig_revision_id,
        seed=seed,
        created_at=created_at,
    )
    graph = PatchGraph(nodes=ordered_nodes, edges=ordered_edges, **common).seal()
    plan_title = title if title is not None else f"Signal Path {input_hash[:8].upper()}"
    phases = ("prep", "threshold", "peak", "release", "seal")
    instructions = (
        "Power down, set levels low, and verify every destination range.",
        "Establish the primary source-to-destination path.",
        "Raise modulation gradually while monitoring the output.",
        "Reduce modulation and output levels in a controlled order.",
        "Return levels low, remove feedback paths, then power down if rewiring.",
    )
    steps = tuple(
        PatchStep(
            position=index,
            phase=phase,  # type: ignore[arg-type]
            instruction=instructions[index],
            warning=instructions[index] if phase == "prep" else None,
        )
        for index, phase in enumerate(phases)
    )
    variation = PatchVariation(
        variation_id=_stable_id("variation", patch_id, 0),
        label="Primary deterministic variation",
        generation_seed=seed,
        graph_hash=graph.canonical_hash or graph.computed_hash(),
    )
    plan_fields = _artifact_fields(
        artifact_id=_stable_id("plan", patch_id),
        entity_id=patch_id,
        run_id=run_id,
        rig_revision_id=rig_revision_id,
        seed=seed,
        created_at=created_at,
    )
    plan = PatchPlan(
        title=plan_title,
        intent=intent,
        steps=steps,
        variations=(variation,),
        **plan_fields,
    ).seal()
    report = validate_patch_graph(graph, plan)

    stage_specs = (
        ("normalize", "RUNE.PATCHHIVE.BUILD_CANONICAL_RIG", input_hash, input_hash),
        ("generate", "RUNE.PATCHHIVE.GENERATE_PATCH", input_hash, graph.canonical_hash or ""),
        (
            "validate",
            "RUNE.PATCHHIVE.VALIDATE_PATCH",
            graph.canonical_hash or "",
            report.canonical_hash or "",
        ),
    )
    receipts_list: list[StageReceipt] = []
    for stage, operation, stage_input, stage_output in stage_specs:
        receipt_fields = _artifact_fields(
            artifact_id=_stable_id("receipt", patch_id, stage),
            entity_id=patch_id,
            run_id=run_id,
            rig_revision_id=rig_revision_id,
            seed=seed,
            created_at=created_at,
        )
        receipts_list.append(
            StageReceipt(
                stage=stage,
                operation=operation,
                operation_version=GENERATOR_VERSION,
                determinism_class="deterministic",
                input_hash=stage_input,
                output_hash=stage_output,
                **receipt_fields,
            ).seal()
        )
    receipts = tuple(receipts_list)
    artifacts_payload = {
        "patch_graph.json": graph,
        "patch_plan.json": plan,
        "validation_report.json": report,
    }
    artifacts = tuple(
        ManifestArtifact(
            path=path,
            media_type="application/json",
            byte_length=len(canonical_json(value).encode("utf-8")),
            sha256=canonical_sha256(value),
        )
        for path, value in sorted(artifacts_payload.items())
    )
    manifest_fields = _artifact_fields(
        artifact_id=_stable_id("manifest", patch_id),
        entity_id=patch_id,
        run_id=run_id,
        rig_revision_id=rig_revision_id,
        seed=seed,
        created_at=created_at,
    )
    manifest = ArtifactManifest(
        artifacts=artifacts,
        stage_receipts=receipts,
        **manifest_fields,
    ).seal()
    return PatchCompilation(
        patch_graph=graph,
        patch_plan=plan,
        validation_report=report,
        variations=(variation,),
        stage_receipts=receipts,
        artifact_manifest=manifest,
    )
