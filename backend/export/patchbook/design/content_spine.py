"""Content spine: load sealed PatchCompilations for Design Engine Layer A (KD-11/19/20)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from canon.contracts import (
    ArtifactManifest,
    ManifestArtifact,
    PatchCompilation,
    PatchEdge,
    PatchGraph,
    PatchNode,
    PatchPlan,
    PatchPort,
    PatchStep,
    PatchVariation,
    StageReceipt,
    ValidationIssue,
    ValidationReport,
    canonical_json,
    canonical_sha256,
)
from canon.compiler import compile_patch
from canon.models import GeneratedPatchRecord, PatchLibraryRecord, RigRevisionRecord
from patches.models import Patch
from runs.bridge import native_artifact_manifest_hash
from runs.models import Run

LoadPath = Literal["generated_patches", "compile_on_export"]


class ContentSpineError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class LoadedLibraryItem:
    position: int
    compilation: PatchCompilation
    orm_patch_id: int | None = None
    generated_patch_id: str | None = None


@dataclass(frozen=True)
class LoadedLibrary:
    source_run_id: str
    source_rig_revision_id: str
    bridge_artifact_manifest_hash: str
    library_content_hash: str
    load_path: LoadPath
    items: tuple[LoadedLibraryItem, ...]


_GEN_RUN_RE = re.compile(r"^gen-run-(\d+)-([0-9a-f]{16})$")


def parse_integer_run_id(source_run_id: str) -> int:
    match = _GEN_RUN_RE.match(source_run_id)
    if match:
        return int(match.group(1))
    # legacy-run-N
    if source_run_id.startswith("legacy-run-"):
        return int(source_run_id.split("-")[-1])
    raise ContentSpineError(
        "EXPORT_RUN_ID_UNPARSEABLE", f"Cannot parse run id from {source_run_id}"
    )


def library_content_hash(items: list[LoadedLibraryItem] | tuple[LoadedLibraryItem, ...]) -> str:
    payload = [
        {"position": item.position, "canonical_hash": item.compilation.canonical_hash_value()}
        for item in sorted(items, key=lambda i: i.position)
    ]
    return canonical_sha256(payload)


def load_patch_compilations(
    session: Session,
    *,
    source_run_id: str,
    source_rig_revision_id: str,
    artifact_manifest_hash: str,
    require_sealed: bool = False,
) -> LoadedLibrary:
    """Path A then Path B. Never uses builder.py as Layer A."""

    library = (
        session.query(PatchLibraryRecord).filter(PatchLibraryRecord.run_id == source_run_id).first()
    )
    if library is not None:
        if library.artifact_manifest_hash != artifact_manifest_hash:
            raise ContentSpineError(
                "EXPORT_BRIDGE_HASH_MISMATCH",
                "artifact_manifest_hash does not match patch library bridge binding",
            )
        generated = (
            session.query(GeneratedPatchRecord)
            .filter(GeneratedPatchRecord.patch_library_id == library.id)
            .order_by(GeneratedPatchRecord.position.asc())
            .all()
        )
        if generated:
            items = tuple(
                LoadedLibraryItem(
                    position=int(row.position),
                    compilation=_compilation_from_generated(row),
                    generated_patch_id=str(row.id),
                )
                for row in generated
            )
            # Prefer sealed row hashes (reconstruction may re-wrap receipts)
            content_hash = canonical_sha256(
                [
                    {"position": int(row.position), "canonical_hash": str(row.canonical_hash)}
                    for row in generated
                ]
            )
            return LoadedLibrary(
                source_run_id=source_run_id,
                source_rig_revision_id=source_rig_revision_id,
                bridge_artifact_manifest_hash=artifact_manifest_hash,
                library_content_hash=content_hash,
                load_path="generated_patches",
                items=items,
            )
        if require_sealed:
            raise ContentSpineError(
                "EXPORT_SEALED_PATCHES_REQUIRED",
                "REQUIRE_SEALED_GENERATED_PATCHES set but no GeneratedPatchRecord rows",
            )

    # Path B — compile-on-export from run-bound ORM patches
    return _load_path_b(
        session,
        source_run_id=source_run_id,
        source_rig_revision_id=source_rig_revision_id,
        artifact_manifest_hash=artifact_manifest_hash,
    )


def _load_path_b(
    session: Session,
    *,
    source_run_id: str,
    source_rig_revision_id: str,
    artifact_manifest_hash: str,
) -> LoadedLibrary:
    int_run_id = parse_integer_run_id(source_run_id)
    run = session.query(Run).filter(Run.id == int_run_id).first()
    if run is None:
        raise ContentSpineError("EXPORT_RUN_NOT_FOUND", f"Run {int_run_id} not found")

    revision = session.get(RigRevisionRecord, source_rig_revision_id)
    if revision is None:
        raise ContentSpineError("EXPORT_RIG_REVISION_NOT_FOUND", "Rig revision missing")

    canonical_rig = revision.canonical_rig if isinstance(revision.canonical_rig, dict) else {}
    rack_id = int(canonical_rig.get("rack_id") or run.rack_id)
    content_hash = _content_hash_from_revision(revision)
    expected = native_artifact_manifest_hash(int_run_id, rack_id, content_hash)
    if expected != artifact_manifest_hash:
        # Also accept library row hash if present without recompute match (bridge may have used live snapshot)
        library = (
            session.query(PatchLibraryRecord)
            .filter(PatchLibraryRecord.run_id == source_run_id)
            .first()
        )
        if library is None or library.artifact_manifest_hash != artifact_manifest_hash:
            raise ContentSpineError(
                "EXPORT_BRIDGE_HASH_MISMATCH",
                "artifact_manifest_hash does not match sealed rig revision binding",
            )

    patches = session.query(Patch).filter(Patch.run_id == int_run_id).order_by(Patch.id.asc()).all()
    if not patches:
        # Fallback: rack-scoped patches for the run's rack if run_id not stamped
        patches = (
            session.query(Patch)
            .filter(Patch.rack_id == int(run.rack_id))
            .order_by(Patch.id.asc())
            .all()
        )
    if not patches:
        raise ContentSpineError("EXPORT_NO_PATCHES", "No patches for run")

    items_list: list[LoadedLibraryItem] = []
    for position, patch in enumerate(patches):
        compilation = seal_orm_patch_to_compilation(
            patch,
            source_run_id=source_run_id,
            source_rig_revision_id=source_rig_revision_id,
            rig_snapshot=canonical_rig,
            position=position,
        )
        items_list.append(
            LoadedLibraryItem(
                position=position,
                compilation=compilation,
                orm_patch_id=int(patch.id),  # type: ignore[arg-type]
            )
        )
    items = tuple(items_list)
    return LoadedLibrary(
        source_run_id=source_run_id,
        source_rig_revision_id=source_rig_revision_id,
        bridge_artifact_manifest_hash=artifact_manifest_hash,
        library_content_hash=library_content_hash(items),
        load_path="compile_on_export",
        items=items,
    )


def _content_hash_from_revision(revision: RigRevisionRecord) -> str:
    # RigRevisionRecord.canonical_hash stores full rack content hash at bridge time
    if revision.canonical_hash and len(str(revision.canonical_hash)) == 64:
        return str(revision.canonical_hash)
    from runs.bridge import rack_content_hash

    if isinstance(revision.canonical_rig, dict):
        return rack_content_hash(revision.canonical_rig)
    raise ContentSpineError("EXPORT_RIG_SNAPSHOT_INVALID", "canonical_rig missing")


def orm_patch_nodes_and_edges(
    connections: list[dict[str, Any]],
) -> tuple[tuple[PatchNode, ...], tuple[PatchEdge, ...]]:
    """Normalized nodes and edges from a patch's sorted cable list.

    Shared by the dual-write adapter and the canonical compiler path so both read the
    same graph (spec 001 T030).
    """
    module_ids: set[str] = set()
    for conn in connections:
        module_ids.add(str(conn.get("from_module_id", "UNKNOWN")))
        module_ids.add(str(conn.get("to_module_id", "UNKNOWN")))
    if not module_ids:
        module_ids.add("UNKNOWN")

    nodes: list[PatchNode] = []
    ports_by_key: dict[str, PatchPort] = {}
    for mid in sorted(module_ids):
        label = f"Module {mid}"
        node_ports: list[PatchPort] = []
        # Collect ports used by this module
        used: set[tuple[str, str]] = set()
        for conn in connections:
            if str(conn.get("from_module_id")) == mid:
                used.add((str(conn.get("from_port") or "UNKNOWN"), "output"))
            if str(conn.get("to_module_id")) == mid:
                used.add((str(conn.get("to_port") or "UNKNOWN"), "input"))
        if not used:
            used.add(("UNKNOWN", "bidirectional"))
        for port_name, direction in sorted(used):
            port_id = f"{mid}:{port_name}:{direction}"
            signal = "unknown"
            for conn in connections:
                if (
                    str(conn.get("from_module_id")) == mid
                    and str(conn.get("from_port")) == port_name
                ):
                    signal = _map_signal(conn.get("cable_type"))
                if str(conn.get("to_module_id")) == mid and str(conn.get("to_port")) == port_name:
                    signal = _map_signal(conn.get("cable_type"))
            port = PatchPort(
                port_id=port_id,
                module_instance_id=mid,
                module_port_id=port_name,
                label=port_name,
                direction=direction,  # type: ignore[arg-type]
                signal_type=signal,  # type: ignore[arg-type]
            )
            ports_by_key[port_id] = port
            node_ports.append(port)
        nodes.append(
            PatchNode(
                node_id=f"node-{mid}",
                module_instance_id=mid,
                label=label,
                ports=tuple(node_ports),
            )
        )

    edges: list[PatchEdge] = []
    for idx, conn in enumerate(connections):
        src_mid = str(conn.get("from_module_id", "UNKNOWN"))
        dst_mid = str(conn.get("to_module_id", "UNKNOWN"))
        src_port = str(conn.get("from_port") or "UNKNOWN")
        dst_port = str(conn.get("to_port") or "UNKNOWN")
        src_id = f"{src_mid}:{src_port}:output"
        dst_id = f"{dst_mid}:{dst_port}:input"
        if src_id not in ports_by_key or dst_id not in ports_by_key:
            continue
        edges.append(
            PatchEdge(
                edge_id=f"edge-{idx}",
                source_port_id=src_id,
                target_port_id=dst_id,
                signal_type=_map_signal(conn.get("cable_type")),  # type: ignore[arg-type]
            )
        )
    return tuple(nodes), tuple(edges)


def _sorted_connections(patch: Patch) -> list[dict[str, Any]]:
    return sorted(
        list(patch.connections or []),
        key=lambda c: (
            str(c.get("from_module_id", "")),
            str(c.get("from_port", "")),
            str(c.get("to_module_id", "")),
            str(c.get("to_port", "")),
            str(c.get("cable_type", "")),
        ),
    )


def compile_orm_patch(
    patch: Patch,
    *,
    source_run_id: str,
    source_rig_revision_id: str,
    intent_suffix: str = "",
) -> PatchCompilation:
    """Run the canonical compiler on a validated patch (spec 001 FR-004, T030).

    Same nodes and edges as ``seal_orm_patch_to_compilation``, but the plan, report and
    stage receipts come from ``canon.compiler.compile_patch``. The timestamp is fixed so the
    result does not depend on the wall clock. ``intent_suffix`` tells apart two patches in
    one run that have the same cables and description, whose ids would otherwise collide.
    """
    nodes, edges = orm_patch_nodes_and_edges(_sorted_connections(patch))
    return compile_patch(
        run_id=source_run_id,
        rig_revision_id=source_rig_revision_id,
        seed=int(patch.generation_seed or 0),
        intent=str(patch.description or patch.name or "NOT_COMPUTABLE") + intent_suffix,
        nodes=nodes,
        edges=edges,
        created_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
        title=str(patch.name) if patch.name else None,
    )


def seal_orm_patch_to_compilation(
    patch: Patch,
    *,
    source_run_id: str,
    source_rig_revision_id: str,
    rig_snapshot: dict[str, Any],
    position: int = 0,
) -> PatchCompilation:
    """Deterministic pure seal from immutable run-bound patch JSON (Path B)."""
    # Fixed timestamp for determinism (Layer A seal must not depend on wall clock)
    now = datetime(1970, 1, 1, tzinfo=timezone.utc)
    seed = int(patch.generation_seed or 0)
    gen_version = str(patch.generation_version or "1.0.0")
    artifact_base = f"patch-{patch.id}-{position}"

    connections = _sorted_connections(patch)

    nodes, edges = orm_patch_nodes_and_edges(connections)

    graph = PatchGraph(
        artifact_id=f"{artifact_base}-graph",
        entity_id=str(patch.id),
        generator_version=gen_version,
        generation_seed=seed,
        source_run_id=source_run_id,
        source_rig_revision_id=source_rig_revision_id,
        created_at=now,
        nodes=nodes,
        edges=edges,
    ).seal()

    steps = _plan_steps_from_connections(connections)
    plan = PatchPlan(
        artifact_id=f"{artifact_base}-plan",
        entity_id=str(patch.id),
        generator_version=gen_version,
        generation_seed=seed,
        source_run_id=source_run_id,
        source_rig_revision_id=source_rig_revision_id,
        created_at=now,
        title=str(patch.name or "UNKNOWN"),
        intent=str(patch.description or "NOT_COMPUTABLE"),
        steps=steps,
        variations=(),
    ).seal()

    issues: list[ValidationIssue] = []
    if not edges:
        issues.append(
            ValidationIssue(
                code="NO_CABLES",
                severity="warning",
                message="Patch has no cable edges",
            )
        )
    valid = not any(i.severity in {"error", "critical"} for i in issues)
    report = ValidationReport(
        artifact_id=f"{artifact_base}-validation",
        entity_id=str(patch.id),
        generator_version=gen_version,
        generation_seed=seed,
        source_run_id=source_run_id,
        source_rig_revision_id=source_rig_revision_id,
        created_at=now,
        valid=valid,
        issues=tuple(issues),
    ).seal()

    receipt = StageReceipt(
        artifact_id=f"{artifact_base}-receipt",
        entity_id=str(patch.id),
        generator_version=gen_version,
        generation_seed=seed,
        source_run_id=source_run_id,
        source_rig_revision_id=source_rig_revision_id,
        created_at=now,
        stage="design_engine",
        operation="seal_orm_patch_to_compilation",
        operation_version="0.1.0",
        determinism_class="deterministic",
        input_hash=canonical_sha256(
            {"connections": connections, "patch_id": patch.id, "seed": seed}
        ),
        output_hash=graph.canonical_hash or "",
    ).seal()

    graph_bytes = graph.canonical_json().encode("utf-8")
    plan_bytes = plan.canonical_json().encode("utf-8")
    val_bytes = report.canonical_json().encode("utf-8")
    manifest = ArtifactManifest(
        artifact_id=f"{artifact_base}-manifest",
        entity_id=str(patch.id),
        generator_version=gen_version,
        generation_seed=seed,
        source_run_id=source_run_id,
        source_rig_revision_id=source_rig_revision_id,
        created_at=now,
        artifacts=(
            ManifestArtifact(
                path="patch_graph.json",
                media_type="application/json",
                byte_length=len(graph_bytes),
                sha256=canonical_sha256(graph.canonical_dict()),
            ),
            ManifestArtifact(
                path="patch_plan.json",
                media_type="application/json",
                byte_length=len(plan_bytes),
                sha256=canonical_sha256(plan.canonical_dict()),
            ),
            ManifestArtifact(
                path="validation_report.json",
                media_type="application/json",
                byte_length=len(val_bytes),
                sha256=canonical_sha256(report.canonical_dict()),
            ),
        ),
        stage_receipts=(receipt,),
    ).seal()

    return PatchCompilation(
        patch_graph=graph,
        patch_plan=plan,
        validation_report=report,
        variations=(),
        stage_receipts=(receipt,),
        artifact_manifest=manifest,
    )


def _map_signal(cable_type: Any) -> str:
    raw = str(cable_type or "unknown").lower()
    if raw in {"audio", "cv", "gate", "trigger", "clock", "unknown"}:
        return raw
    if "cv" in raw:
        return "cv"
    if "gate" in raw:
        return "gate"
    if "trig" in raw:
        return "trigger"
    if "clock" in raw:
        return "clock"
    if "audio" in raw or "out" in raw:
        return "audio"
    return "unknown"


def _plan_steps_from_connections(connections: list[dict[str, Any]]) -> tuple[PatchStep, ...]:
    phases = ("prep", "threshold", "peak", "release", "seal")
    if not connections:
        return tuple(
            PatchStep(
                position=i,
                phase=phase,  # type: ignore[arg-type]
                instruction=f"{phase}: no cables (UNKNOWN topology)",
                expected_result="NOT_COMPUTABLE",
            )
            for i, phase in enumerate(phases)
        )

    # Distribute connections across phases; ensure all five phases present
    steps: list[PatchStep] = []
    n = len(connections)
    for i, phase in enumerate(phases):
        # Map phase to a connection index
        conn_idx = min(i, n - 1) if n else 0
        if i < n:
            conn = connections[i]
            instruction = (
                f"Connect {conn.get('from_module_id', 'UNKNOWN')} "
                f"{conn.get('from_port', 'UNKNOWN')} → "
                f"{conn.get('to_module_id', 'UNKNOWN')} "
                f"{conn.get('to_port', 'UNKNOWN')}"
            )
        else:
            conn = connections[conn_idx]
            instruction = f"{phase}: verify prior connection {conn.get('from_port', 'UNKNOWN')}"
        steps.append(
            PatchStep(
                position=i,
                phase=phase,  # type: ignore[arg-type]
                instruction=instruction,
                expected_result="Signal path established" if i < n else "Stable operation",
            )
        )
    # Append remaining cables as peak-phase extras with unique positions
    for j in range(5, n):
        conn = connections[j]
        steps.append(
            PatchStep(
                position=j,
                phase="peak",
                instruction=(
                    f"Connect {conn.get('from_module_id', 'UNKNOWN')} "
                    f"{conn.get('from_port', 'UNKNOWN')} → "
                    f"{conn.get('to_module_id', 'UNKNOWN')} "
                    f"{conn.get('to_port', 'UNKNOWN')}"
                ),
                expected_result="Signal path established",
            )
        )
    return tuple(steps)


def _compilation_from_generated(row: GeneratedPatchRecord) -> PatchCompilation:
    graph = PatchGraph.model_validate(row.patch_graph)
    plan = PatchPlan.model_validate(row.patch_plan)
    report = ValidationReport.model_validate(row.validation_report)
    variations_raw = row.variations or []
    variations = tuple(PatchVariation.model_validate(v) for v in variations_raw)
    # Minimal stage + manifest for sealed rows that may lack full compilation wrapper
    now = datetime(1970, 1, 1, tzinfo=timezone.utc)
    receipt = StageReceipt(
        artifact_id=f"{row.id}-receipt",
        entity_id=str(row.id),
        generator_version=graph.generator_version,
        generation_seed=graph.generation_seed,
        source_run_id=graph.source_run_id,
        source_rig_revision_id=graph.source_rig_revision_id,
        created_at=now,
        stage="generated_patches",
        operation="load_generated_patch",
        operation_version="0.1.0",
        determinism_class="deterministic",
        input_hash=str(row.canonical_hash),
        output_hash=str(row.canonical_hash),
    ).seal()
    manifest = ArtifactManifest(
        artifact_id=f"{row.id}-manifest",
        entity_id=str(row.id),
        generator_version=graph.generator_version,
        generation_seed=graph.generation_seed,
        source_run_id=graph.source_run_id,
        source_rig_revision_id=graph.source_rig_revision_id,
        created_at=now,
        artifacts=(
            ManifestArtifact(
                path="patch_graph.json",
                media_type="application/json",
                byte_length=len(canonical_json(row.patch_graph).encode("utf-8")),
                sha256=canonical_sha256(row.patch_graph),
            ),
        ),
        stage_receipts=(receipt,),
    ).seal()
    return PatchCompilation(
        patch_graph=graph,
        patch_plan=plan,
        validation_report=report,
        variations=variations,
        stage_receipts=(receipt,),
        artifact_manifest=manifest,
    )
