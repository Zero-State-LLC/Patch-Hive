"""Run → canonical export bridge.

MVP UI still lists integer ``runs`` rows. Canonical exports require
``generation_runs`` + ``rig_revisions`` FK targets and a 64-char manifest hash.

Native bridge identifiers (post-PR #66 continuation):
- ``rig-rev-{content_hash[:32]}`` — immutable per rack layout snapshot
- ``gen-run-{run_id}-{content_hash[:16]}`` — generation run bound to that snapshot

Legacy ``legacy-rack-*`` / ``legacy-run-*`` helpers remain only for migration
parity tests and are not used by ``ensure_legacy_run_export_bridge``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from canon.models import GenerationRunRecord, PatchLibraryRecord, RigRevisionRecord
from core.config import settings
from racks.models import Rack, RackModule
from runs.models import Run

RACK_SNAPSHOT_SCHEMA = "patchhive.rack-snapshot.v1"
BRIDGE_NAMESPACE = "native"


def legacy_rig_revision_id(rack_id: int) -> str:
    """Historical id form (deprecated; not written by ensure_*)."""
    return f"legacy-rack-{int(rack_id)}"


def legacy_source_run_id(run_id: int) -> str:
    """Historical id form (deprecated; not written by ensure_*)."""
    return f"legacy-run-{int(run_id)}"


def native_rig_revision_id(content_hash: str) -> str:
    """Immutable revision id derived from content hash (never mutates in place)."""
    digest = content_hash.lower()
    if len(digest) < 32:
        raise ValueError("content_hash must be a full sha256 hex digest")
    return f"rig-rev-{digest[:32]}"


def native_source_run_id(run_id: int, content_hash: str) -> str:
    digest = content_hash.lower()
    return f"gen-run-{int(run_id)}-{digest[:16]}"


def _sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stable_hash(label: str) -> str:
    return _sha256_hex(label)


def build_rack_content_snapshot(db: Session, rack: Rack) -> dict[str, Any]:
    """Deterministic layout snapshot for RigRevision.canonical_rig."""
    rack_id = int(rack.id)  # type: ignore[arg-type]
    case_id = int(rack.case_id)  # type: ignore[arg-type]
    rows = (
        db.query(RackModule)
        .filter(RackModule.rack_id == rack_id)
        .order_by(RackModule.row_index.asc(), RackModule.start_hp.asc(), RackModule.module_id.asc())
        .all()
    )
    modules = [
        {
            "module_id": int(rm.module_id),  # type: ignore[arg-type]
            "row_index": int(rm.row_index),  # type: ignore[arg-type]
            "start_hp": int(rm.start_hp),  # type: ignore[arg-type]
        }
        for rm in rows
    ]
    return {
        "schema": RACK_SNAPSHOT_SCHEMA,
        "bridge": BRIDGE_NAMESPACE,
        "rack_id": rack_id,
        "case_id": case_id,
        "modules": modules,
    }


def rack_content_hash(snapshot: dict[str, Any]) -> str:
    """SHA-256 over canonical JSON of the rack snapshot (includes rack_id → unique)."""
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return _sha256_hex(encoded)


def legacy_artifact_manifest_hash(
    run_id: int, rack_id: int, content_hash: str | None = None
) -> str:
    """Historical manifest formula (kept for regression comparison)."""
    if content_hash:
        payload = f"patchhive:legacy-run:{int(run_id)}:rig:{int(rack_id)}:content:{content_hash}"
    else:
        payload = f"patchhive:legacy-run:{int(run_id)}:rig:{int(rack_id)}"
    return _sha256_hex(payload)


def native_artifact_manifest_hash(run_id: int, rack_id: int, content_hash: str) -> str:
    payload = f"patchhive:gen-run:{int(run_id)}:rig:{int(rack_id)}:content:{content_hash}"
    return _sha256_hex(payload)


# Alias used by older call sites.
artifact_manifest_hash = native_artifact_manifest_hash


@dataclass(frozen=True)
class LegacyRunExportBridge:
    """Bridge DTO name retained for API stability; IDs are native namespace."""

    run_id: int
    rack_id: int
    rig_revision_id: str
    source_run_id: str
    artifact_manifest_hash: str
    export_bridge_ready: bool
    content_hash: str | None = None

    def as_export_body_fields(self) -> dict[str, str]:
        return {
            "source_run_id": self.source_run_id,
            "source_rig_revision_id": self.rig_revision_id,
            "artifact_manifest_hash": self.artifact_manifest_hash,
        }


def bridge_for_run(run: Run, content_hash: str | None = None) -> LegacyRunExportBridge:
    run_id = int(run.id)  # type: ignore[arg-type]
    rack_id = int(run.rack_id)  # type: ignore[arg-type]
    if not content_hash:
        # Without a snapshot we cannot form native content-bound IDs.
        return LegacyRunExportBridge(
            run_id=run_id,
            rack_id=rack_id,
            rig_revision_id=legacy_rig_revision_id(rack_id),
            source_run_id=legacy_source_run_id(run_id),
            artifact_manifest_hash=legacy_artifact_manifest_hash(run_id, rack_id),
            export_bridge_ready=False,
            content_hash=None,
        )
    return LegacyRunExportBridge(
        run_id=run_id,
        rack_id=rack_id,
        rig_revision_id=native_rig_revision_id(content_hash),
        source_run_id=native_source_run_id(run_id, content_hash),
        artifact_manifest_hash=native_artifact_manifest_hash(run_id, rack_id, content_hash),
        export_bridge_ready=False,
        content_hash=content_hash,
    )


def recorded_run_bridge(db: Session, run: Run) -> LegacyRunExportBridge:
    """The canonical ids recorded for a run when it was generated. Read-only.

    Runs are append-only (spec 001 FR-020): reading one never mints rows, and a
    later layout change never re-binds an old run to a new rig revision. A run with
    no recorded generation (from before generate wrote the bridge) reports
    ``export_bridge_ready=False``.
    """
    record = (
        db.query(GenerationRunRecord)
        .filter(GenerationRunRecord.id.like(f"gen-run-{int(run.id)}-%"))  # type: ignore[arg-type]
        .order_by(GenerationRunRecord.created_at.asc())
        .first()
    )
    library = (
        db.query(PatchLibraryRecord).filter(PatchLibraryRecord.run_id == record.id).first()
        if record is not None
        else None
    )
    if record is None or library is None:
        return bridge_for_run(run)
    return LegacyRunExportBridge(
        run_id=int(run.id),  # type: ignore[arg-type]
        rack_id=int(run.rack_id),  # type: ignore[arg-type]
        rig_revision_id=str(record.rig_revision_id),
        source_run_id=str(record.id),
        artifact_manifest_hash=str(library.artifact_manifest_hash),
        export_bridge_ready=True,
    )


def ensure_legacy_run_export_bridge(
    db: Session,
    run: Run,
    *,
    generation_seed: int | None = None,
    generator_version: str | None = None,
) -> LegacyRunExportBridge:
    """Idempotently create canon hierarchy rows required for /api/canon/exports.

    Function name retained for call-site stability; identifiers are native.
    Rig revisions are append-only: layout changes mint a new ``rig-rev-*`` id.

    Generation passes the request's seed and the engine version so the canonical
    run records the real provenance (spec 001 FR-024/FR-026). Runs bridged later
    from a read never recorded their seed; for those the run id stands in, as before.
    """
    rack = db.get(Rack, run.rack_id)
    if rack is None:
        return bridge_for_run(run)

    snapshot = build_rack_content_snapshot(db, rack)
    content_hash = rack_content_hash(snapshot)
    bridge = bridge_for_run(run, content_hash=content_hash)

    user_id = int(rack.user_id)  # type: ignore[arg-type]
    revision_id = bridge.rig_revision_id
    source_run_id = bridge.source_run_id
    library_id = f"library-{source_run_id}"
    manifest_hash = bridge.artifact_manifest_hash

    existing_rev = db.get(RigRevisionRecord, revision_id)
    if existing_rev is None:
        db.add(
            RigRevisionRecord(
                id=revision_id,
                rig_id=bridge.rack_id,
                schema_version="patchhive.canon.v1",
                canonical_rig=snapshot,
                canonical_hash=content_hash,
            )
        )
        db.flush()
    # else: immutable — same content_hash means same revision id; do not mutate

    if db.get(GenerationRunRecord, source_run_id) is None:
        db.add(
            GenerationRunRecord(
                id=source_run_id,
                user_id=user_id,
                rig_revision_id=revision_id,
                schema_version="patchhive.canon.v1",
                generator_version=generator_version or settings.patch_engine_version,
                generation_seed=bridge.run_id if generation_seed is None else int(generation_seed),
                normalized_input_hash=_stable_hash(
                    f"generation-run:{source_run_id}:content:{content_hash}"
                ),
            )
        )
        db.flush()

    if db.get(PatchLibraryRecord, library_id) is None:
        db.add(
            PatchLibraryRecord(
                id=library_id,
                run_id=source_run_id,
                artifact_manifest_hash=manifest_hash,
                canonical_hash=_stable_hash(f"patch-library:{library_id}:{manifest_hash}"),
            )
        )
        db.flush()

    return LegacyRunExportBridge(
        run_id=bridge.run_id,
        rack_id=bridge.rack_id,
        rig_revision_id=revision_id,
        source_run_id=source_run_id,
        artifact_manifest_hash=manifest_hash,
        export_bridge_ready=True,
        content_hash=content_hash,
    )
