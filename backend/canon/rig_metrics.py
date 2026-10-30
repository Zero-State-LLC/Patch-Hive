"""RigMetricsPacket for a rig revision from the facts the rack holds (spec 001 FR-027, T031).

Counts are computed, plus ``routing_flex_score`` and ``performance_density_index`` (OQ-11
option 2, see ``canon.rig_scores``). The other four scores stay ``NOT_COMPUTABLE``.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from canon.contracts import NOT_COMPUTABLE, RigMetricsPacket
from canon.models import RigMetricsPacketRecord, RigRevisionRecord
from canon.rig_scores import METRICS_GENERATOR_VERSION, compute_rig_scores
from modules.models import Module

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
    port_counts: list[int | None] = []
    for entry in placed:
        module = rows.get(int(entry["module_id"])) if entry.get("module_id") is not None else None
        counts[str(module.module_type) if module and module.module_type else UNCATEGORIZED] += 1
        widths.append(int(module.hp) if module and module.hp is not None else None)
        ports = module.io_ports if module is not None else None
        port_counts.append(len(ports) if isinstance(ports, list) else None)
    total_hp = sum(w for w in widths if w is not None) if all(w is not None for w in widths) else None
    flex, density, score_notes = compute_rig_scores(port_counts, widths)
    notes = list(score_notes)
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
        routing_flex_score=flex,
        clock_coherence_score=NOT_COMPUTABLE,
        chaos_headroom=NOT_COMPUTABLE,
        learning_gradient_index=NOT_COMPUTABLE,
        performance_density_index=density,
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
    # A concurrent run on the same revision may insert first. The insert runs in a
    # savepoint so that losing the race rolls back only the insert, not the generation run.
    try:
        with db.begin_nested():
            db.add(
                RigMetricsPacketRecord(
                    id=packet.artifact_id,
                    rig_revision_id=rig_revision_id,
                    packet=packet.canonical_dict(),
                    canonical_hash=packet.canonical_hash or "",
                )
            )
    except IntegrityError:
        winner = (
            db.query(RigMetricsPacketRecord)
            .filter(RigMetricsPacketRecord.rig_revision_id == rig_revision_id)
            .first()
        )
        if winner is None:
            raise
        return RigMetricsPacket.model_validate(winner.packet)
    return packet
