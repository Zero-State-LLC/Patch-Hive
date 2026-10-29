"""Canonical rune operations with no framework or persistence coupling."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping

from canon.contracts import (
    CanonicalRig,
    DetectedModule,
    EpistemicStatus,
    LayoutPlacement,
    ModuleGalleryEntry,
    ModuleRevision,
    ResolvedModuleRef,
    RigMetricsPacket,
    RigSpec,
    SuggestedLayout,
    canonical_sha256,
)

DetectionProvider = Callable[[bytes], Iterable[dict[str, Any] | DetectedModule]]


def detect_modules(photo_bytes: bytes, provider: DetectionProvider) -> tuple[DetectedModule, ...]:
    """Treat provider output as untrusted evidence and validate every record."""

    if not photo_bytes:
        raise ValueError("photo evidence is empty")
    detections = tuple(
        item if isinstance(item, DetectedModule) else DetectedModule.model_validate(item)
        for item in provider(photo_bytes)
    )
    for detection in detections:
        if detection.status is EpistemicStatus.confirmed:
            raise ValueError("provider evidence cannot promote itself to confirmed truth")
    return tuple(sorted(detections, key=lambda item: item.detection_id))


def _normalized(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def resolve_modules(
    detections: Iterable[DetectedModule],
    gallery_entries: Iterable[ModuleGalleryEntry],
) -> tuple[ResolvedModuleRef, ...]:
    """Resolve evidence against confirmed gallery entries with stable tie-breaking."""

    gallery = tuple(gallery_entries)
    resolved: list[ResolvedModuleRef] = []
    for detection in sorted(detections, key=lambda item: item.detection_id):
        candidates: list[tuple[float, ModuleGalleryEntry]] = []
        for entry in gallery:
            name_score = SequenceMatcher(
                None, _normalized(detection.label_guess), _normalized(entry.name)
            ).ratio()
            manufacturer_score = SequenceMatcher(
                None,
                _normalized(detection.manufacturer_guess),
                _normalized(entry.manufacturer),
            ).ratio()
            score = (name_score * 0.8) + (manufacturer_score * 0.2)
            candidates.append((score, entry))
        candidates.sort(key=lambda item: (-item[0], item[1].module_gallery_id))
        if not candidates or candidates[0][0] < 0.65:
            resolved.append(
                ResolvedModuleRef(
                    detection_id=detection.detection_id,
                    evidence=detection.evidence,
                    confidence=detection.confidence,
                    status=EpistemicStatus.missing,
                )
            )
            continue
        score, entry = candidates[0]
        confirmed = score >= 0.95 and entry.status is EpistemicStatus.confirmed
        resolved.append(
            ResolvedModuleRef(
                detection_id=detection.detection_id,
                module_gallery_id=entry.module_gallery_id,
                module_revision_id=entry.current_revision_id,
                evidence=detection.evidence,
                confidence=min(detection.confidence, score),
                status=EpistemicStatus.confirmed if confirmed else EpistemicStatus.disputed,
            )
        )
    return tuple(resolved)


def ensure_module_specs(
    references: Iterable[ResolvedModuleRef],
    revisions: Mapping[str, ModuleRevision],
) -> tuple[ModuleRevision | None, ...]:
    """Return authoritative specs where present; never synthesize missing facts."""

    return tuple(
        revisions.get(reference.module_revision_id) if reference.module_revision_id else None
        for reference in sorted(references, key=lambda item: item.detection_id)
    )


def build_canonical_rig(
    rig: RigSpec,
    revisions: Mapping[str, ModuleRevision],
) -> CanonicalRig:
    """Build an ordered rig only from explicit module revisions."""

    modules = tuple(sorted(rig.modules, key=lambda item: (item.position, item.instance_id)))
    missing = sorted(
        module.module_revision_id
        for module in modules
        if module.module_revision_id not in revisions
    )
    if missing:
        raise ValueError(f"module revisions are missing: {', '.join(missing)}")
    payload = {"rig_id": rig.rig_id, "modules": modules}
    revision_id = f"rig-rev-{canonical_sha256(payload)[:24]}"
    return CanonicalRig(
        rig_id=rig.rig_id,
        rig_revision_id=revision_id,
        modules=modules,
        canonical_hash=canonical_sha256({**payload, "rig_revision_id": revision_id}),
    )


def map_metrics(
    rig: CanonicalRig,
    revisions: Mapping[str, ModuleRevision],
    *,
    run_id: str,
    seed: int,
    created_at: datetime,
) -> RigMetricsPacket:
    """Map facts while preserving unknown HP as unknown."""

    widths = [revisions[module.module_revision_id].hp for module in rig.modules]
    total_hp = (
        sum(width for width in widths if width is not None)
        if all(width is not None for width in widths)
        else None
    )
    port_count = sum(len(revisions[module.module_revision_id].ports) for module in rig.modules)
    payload = {
        "rig": rig,
        "module_count": len(rig.modules),
        "total_hp": total_hp,
        "ports": port_count,
    }
    artifact_id = f"metrics-{canonical_sha256(payload)[:24]}"
    return RigMetricsPacket(
        artifact_id=artifact_id,
        entity_id=rig.rig_revision_id,
        generator_version="canon-metrics.1.0.0",
        generation_seed=seed,
        source_run_id=run_id,
        source_rig_revision_id=rig.rig_revision_id,
        created_at=created_at,
        module_count=len(rig.modules),
        total_hp=total_hp,
        routing_flex_score=round(port_count / max(len(rig.modules), 1), 6),
        confidence_notes=(
            ("total_hp is missing because one or more module widths are missing",)
            if total_hp is None
            else ()
        ),
    ).seal()


def suggest_layouts(
    rig: CanonicalRig,
    metrics: RigMetricsPacket,
    *,
    run_id: str,
    seed: int,
    created_at: datetime,
) -> tuple[SuggestedLayout, ...]:
    """Place modules deterministically without claiming a fit when HP is unknown."""

    score = metrics.routing_flex_score
    if isinstance(score, str):
        raise ValueError("routing_flex_score is NOT_COMPUTABLE; layouts cannot be scored")
    placements = tuple(
        LayoutPlacement(instance_id=module.instance_id, row=0, start_hp=module.position)
        for module in rig.modules
    )
    layout_id = f"layout-{canonical_sha256(placements)[:24]}"
    layout = SuggestedLayout(
        artifact_id=layout_id,
        entity_id=rig.rig_revision_id,
        generator_version="canon-layout.1.0.0",
        generation_seed=seed,
        source_run_id=run_id,
        source_rig_revision_id=rig.rig_revision_id,
        created_at=created_at,
        layout_id=layout_id,
        label="Stable source order",
        placements=placements,
        score=score,
        confidence=1.0 if metrics.total_hp is not None else 0.5,
        status=(
            EpistemicStatus.confirmed if metrics.total_hp is not None else EpistemicStatus.missing
        ),
    ).seal()
    return (layout,)
