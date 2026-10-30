"""Test fixture: a fixed two-module demo rig run through metrics, layouts and compile.

Moved out of ``canon`` (spec 001 T030, research R1): generation compiles real racks in
``patches.routes.run_generation``; this demo rig is test data only. Composes ``runes`` +
``compiler``. Does not reimplement historical VL2 ``patchhive.pipeline.run``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from canon.compiler import PatchCompilation, compile_patch
from canon.contracts import (
    CanonicalRig,
    EpistemicStatus,
    LayoutPlacement,
    ModulePort,
    ModuleRevision,
    PatchEdge,
    PatchNode,
    PatchPort,
    RigMetricsPacket,
    RigModule,
    RigSpec,
    SuggestedLayout,
    canonical_sha256,
)
from canon.runes import build_canonical_rig, map_metrics


@dataclass(frozen=True)
class PipelineBundle:
    rig_id: str
    rig: CanonicalRig
    metrics: RigMetricsPacket
    layouts: tuple[SuggestedLayout, ...]
    compilation: PatchCompilation


def _revision(
    *,
    revision_id: str,
    gallery_id: str,
    manufacturer: str,
    name: str,
    hp: int,
    created_at: datetime,
) -> ModuleRevision:
    return ModuleRevision(
        module_revision_id=revision_id,
        module_gallery_id=gallery_id,
        manufacturer=manufacturer,
        name=name,
        hp=hp,
        # Declared ports: a module with none makes routing_flex_score NOT_COMPUTABLE, and
        # the demo layouts scale that score.
        ports=(
            ModulePort(port_id="in", label="IN", direction="input", signal_type="audio"),
            ModulePort(port_id="out", label="OUT", direction="output", signal_type="audio"),
        ),
        status=EpistemicStatus.confirmed,
        created_at=created_at,
    )


def _demo_nodes_and_edges() -> tuple[tuple[PatchNode, ...], tuple[PatchEdge, ...]]:
    nodes = (
        PatchNode(
            node_id="filter",
            module_instance_id="filter",
            label="Filter",
            ports=(
                PatchPort(
                    port_id="filter.in",
                    module_instance_id="filter",
                    module_port_id="in",
                    label="IN",
                    direction="input",
                    signal_type="audio",
                    voltage_min=-5,
                    voltage_max=5,
                ),
            ),
        ),
        PatchNode(
            node_id="oscillator",
            module_instance_id="oscillator",
            label="Oscillator",
            ports=(
                PatchPort(
                    port_id="oscillator.out",
                    module_instance_id="oscillator",
                    module_port_id="out",
                    label="OUT",
                    direction="output",
                    signal_type="audio",
                    voltage_min=-5,
                    voltage_max=5,
                ),
            ),
        ),
    )
    edges = (
        PatchEdge(
            edge_id="cable-1",
            source_port_id="oscillator.out",
            target_port_id="filter.in",
            signal_type="audio",
        ),
    )
    return nodes, edges


def _three_layouts(
    rig: CanonicalRig,
    metrics: RigMetricsPacket,
    *,
    run_id: str,
    seed: int,
    created_at: datetime,
) -> tuple[SuggestedLayout, ...]:
    """Three deterministic layout variants (beginner / performance / experimental labels)."""
    base_placements = tuple(
        LayoutPlacement(instance_id=module.instance_id, row=0, start_hp=module.position)
        for module in rig.modules
    )
    labels = ("Beginner source order", "Performance source order", "Experimental source order")
    layouts: list[SuggestedLayout] = []
    for index, label in enumerate(labels):
        payload = {"placements": base_placements, "variant": index, "label": label}
        layout_id = f"layout-{canonical_sha256(payload)[:24]}"
        score = round(metrics.routing_flex_score * (1.0 - index * 0.05), 6)
        layouts.append(
            SuggestedLayout(
                artifact_id=layout_id,
                entity_id=rig.rig_revision_id,
                generator_version="canon-layout.1.0.0",
                generation_seed=seed + index,
                source_run_id=run_id,
                source_rig_revision_id=rig.rig_revision_id,
                created_at=created_at,
                layout_id=layout_id,
                label=label,
                placements=base_placements,
                score=score,
                confidence=1.0 if metrics.total_hp is not None else 0.5,
                status=(
                    EpistemicStatus.confirmed
                    if metrics.total_hp is not None
                    else EpistemicStatus.missing
                ),
            ).seal()
        )
    return tuple(layouts)


def run_canon_pipeline(
    *,
    rig_id: str = "rig.demo.v1",
    seed: int = 101,
    intent: str = "A stable subtractive voice",
    created_at: datetime | None = None,
) -> PipelineBundle:
    """Build metrics, three layout suggestions, and a sealed patch compilation."""
    stamped = created_at or datetime(2025, 12, 21, tzinfo=timezone.utc)
    revisions = {
        "mod-rev-osc": _revision(
            revision_id="mod-rev-osc",
            gallery_id="gallery-osc",
            manufacturer="MockAudio",
            name="Oscillator A",
            hp=12,
            created_at=stamped,
        ),
        "mod-rev-filter": _revision(
            revision_id="mod-rev-filter",
            gallery_id="gallery-filter",
            manufacturer="MockAudio",
            name="Filter Z",
            hp=8,
            created_at=stamped,
        ),
    }
    rig_spec = RigSpec(
        rig_id=rig_id,
        name="Demo voice",
        modules=(
            RigModule(instance_id="oscillator", module_revision_id="mod-rev-osc", position=0),
            RigModule(instance_id="filter", module_revision_id="mod-rev-filter", position=1),
        ),
    )
    rig = build_canonical_rig(rig_spec, revisions)
    run_id = f"gen-run-{seed}"
    metrics = map_metrics(rig, revisions, run_id=run_id, seed=seed, created_at=stamped)
    layouts = _three_layouts(rig, metrics, run_id=run_id, seed=seed, created_at=stamped)
    nodes, edges = _demo_nodes_and_edges()
    compilation = compile_patch(
        run_id=run_id,
        rig_revision_id=rig.rig_revision_id,
        seed=seed,
        intent=intent,
        nodes=nodes,
        edges=edges,
        created_at=stamped,
    )
    return PipelineBundle(
        rig_id=rig.rig_id,
        rig=rig,
        metrics=metrics,
        layouts=layouts,
        compilation=compilation,
    )
