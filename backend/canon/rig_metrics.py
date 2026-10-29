"""RigMetricsPacket for a rig revision from the facts the rack holds (spec 001 FR-027, T031).

Only counts are computed. The six scores have no formula yet (OQ-11), so they are
``NOT_COMPUTABLE`` and no number is invented.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from canon.contracts import NOT_COMPUTABLE, RigMetricsPacket
from canon.models import RigMetricsPacketRecord, RigRevisionRecord
from modules.models import Module

METRICS_GENERATOR_VERSION = "canon-metrics.1.1.0"
UNCATEGORIZED = "UNKNOWN"


def build_rig_metrics_packet(
    db: Session, revision: RigRevisionRecord, *, source_run_id: str
) -> RigMetricsPacket:
    """Count the modules in a rig revision snapshot, by module type."""
    snapshot = revision.canonical_rig if isinstance(revision.canonical_rig, dict) else {}
    placed = [m for m in (snapshot.get("modules") or []) if isinstance(m, dict)]
    module_ids = {int(m["module_id"]) for m in placed if m.get("module_id") is not None}
    rows = (
        {
            int(m.id): m
            for m in db.query(Module).filter(Module.id.in_(module_ids)).all()
        }
        if module_ids
        else {}
    )
    counts: Counter[str] = Counter()
    widths: list[int | None] = []
    for entry in placed:
        module = rows.get(int(entry["module_id"])) if entry.get("module_id") is not None else None
        counts[str(module.module_type) if module and module.module_type else UNCATEGORIZED] += 1
        widths.append(int(module.hp) if module and module.hp is not None else None)
    total_hp = sum(w for w in widths if w is not None) if all(w is not None for w in widths) else None
    notes = ["The six scores are NOT_COMPUTABLE until OQ-11 defines their formulas."]
    if total_hp is None:
        notes.append("total_hp is missing because one or more module widths are missing")
    packet = RigMetricsPacket(
        artifact_id=f"metrics-{revision.id}",
        entity_id=str(revision.id),
        generator_version=METRICS_GENERATOR_VERSION,
        generation_seed=0,
        source_run_id=source_run_id,
        source_rig_revision_id=str(revision.id),
        created_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
        rig_id=str(revision.rig_id),
        module_count=len(placed),
        category_counts=dict(sorted(counts.items())),
        total_hp=total_hp,
        modulation_budget=NOT_COMPUTABLE,
        routing_flex_score=NOT_COMPUTABLE,
        clock_coherence_score=NOT_COMPUTABLE,
        chaos_headroom=NOT_COMPUTABLE,
        learning_gradient_index=NOT_COMPUTABLE,
        performance_density_index=NOT_COMPUTABLE,
        confidence_notes=tuple(notes),
    )
    return packet.seal()


def ensure_rig_metrics_packet(
    db: Session, *, rig_revision_id: str, source_run_id: str
) -> RigMetricsPacket | None:
    """Store the revision's packet once. A later run on the same revision reuses it.

    Revisions are immutable, so the packet is too; ``source_run_id`` is the run that first
    emitted it.
    """
    revision = db.get(RigRevisionRecord, rig_revision_id)
    if revision is None:
        return None
    existing = (
        db.query(RigMetricsPacketRecord)
        .filter(RigMetricsPacketRecord.rig_revision_id == rig_revision_id)
        .first()
    )
    if existing is not None:
        return RigMetricsPacket.model_validate(existing.packet)
    packet = build_rig_metrics_packet(db, revision, source_run_id=source_run_id)
    db.add(
        RigMetricsPacketRecord(
            id=packet.artifact_id,
            rig_revision_id=rig_revision_id,
            packet=packet.canonical_dict(),
            canonical_hash=packet.canonical_hash or "",
        )
    )
    db.flush()
    return packet
