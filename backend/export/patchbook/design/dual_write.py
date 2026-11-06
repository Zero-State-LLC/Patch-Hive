"""Path A producer: dual-write sealed GeneratedPatchRecord rows at generate time.

Each patch that passed validation goes through ``canon.compiler.compile_patch`` (spec 001
FR-004, T030). The compiler's graph, plan and report are stored on the row and its stage
receipts in ``stage_receipts``. The older adapter stays as the Path B fallback.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from canon.models import (
    ArtifactManifestRecord,
    GeneratedPatchRecord,
    GenerationRunRecord,
    PatchLibraryRecord,
    StageReceiptRecord,
)
from export.patchbook.design.content_spine import (
    library_content_hash,
    compile_orm_patch,
    LoadedLibraryItem,
)
from patches.models import Patch
from runs.bridge import LegacyRunExportBridge


def dual_write_generated_patches(
    session: Session,
    *,
    bridge: LegacyRunExportBridge,
    patches: list[Patch],
) -> str | None:
    """Seal ORM patches into GeneratedPatchRecord ordered by list position.

    Idempotent for empty library: skips if rows already exist for the library.
    Returns library_content_hash or None if bridge not ready / no patches.
    """
    if not bridge.export_bridge_ready:
        return None

    library_id = f"library-{bridge.source_run_id}"
    library = session.get(PatchLibraryRecord, library_id)
    if library is None:
        return None
    if not patches:
        _seal_run_manifest(session, bridge=bridge, library_id=library_id, items=[])
        return None

    existing = (
        session.query(GeneratedPatchRecord)
        .filter(GeneratedPatchRecord.patch_library_id == library_id)
        .count()
    )
    if existing > 0:
        # Already sealed — recompute hash from existing for return value
        rows = (
            session.query(GeneratedPatchRecord)
            .filter(GeneratedPatchRecord.patch_library_id == library_id)
            .order_by(GeneratedPatchRecord.position.asc())
            .all()
        )
        return _hash_from_generated_rows(rows)

    items: list[LoadedLibraryItem] = []
    seen_hashes: set[str] = set()
    for position, patch in enumerate(patches):
        compilation = compile_orm_patch(
            patch,
            source_run_id=bridge.source_run_id,
            source_rig_revision_id=bridge.rig_revision_id,
        )
        if compilation.canonical_hash_value() in seen_hashes:
            # Same cables and description as an earlier patch in this run.
            compilation = compile_orm_patch(
                patch,
                source_run_id=bridge.source_run_id,
                source_rig_revision_id=bridge.rig_revision_id,
                intent_suffix=f" (patch {position})",
            )
        seen_hashes.add(compilation.canonical_hash_value())
        row_id = f"gen-patch-{bridge.source_run_id}-{position}"
        session.add(
            GeneratedPatchRecord(
                id=row_id,
                patch_library_id=library_id,
                position=position,
                name=str(patch.name or f"Patch {position}"),
                patch_graph=compilation.patch_graph.canonical_dict(),
                patch_plan=compilation.patch_plan.canonical_dict(),
                validation_report=compilation.validation_report.canonical_dict(),
                variations=[v.canonical_dict() for v in compilation.variations],
                canonical_hash=compilation.canonical_hash_value(),
            )
        )
        for receipt in compilation.stage_receipts:
            session.add(
                StageReceiptRecord(
                    id=receipt.artifact_id,
                    run_id=bridge.source_run_id,
                    stage=receipt.stage,
                    operation=receipt.operation,
                    operation_version=receipt.operation_version,
                    determinism_class=receipt.determinism_class,
                    input_hash=receipt.input_hash,
                    output_hash=receipt.output_hash,
                    receipt=receipt.canonical_dict(),
                )
            )
        items.append(
            LoadedLibraryItem(
                position=position,
                compilation=compilation,
                orm_patch_id=int(patch.id) if patch.id is not None else None,
                generated_patch_id=row_id,
            )
        )

    content_hash = library_content_hash(items)
    _seal_run_manifest(session, bridge=bridge, library_id=library_id, items=items)
    # PatchLibraryRecord is append-only — do not mutate library.canonical_hash.
    # Integrity lives on GeneratedPatchRecord.canonical_hash + library_content_hash
    # returned to callers / export seal (KD-19).
    session.flush()
    return content_hash


def _seal_run_manifest(
    session: Session,
    *,
    bridge: LegacyRunExportBridge,
    library_id: str,
    items: list[LoadedLibraryItem],
) -> None:
    """Store what a succeeded run sealed: one manifest per run, holding each patch's (spec 001 D6)."""
    from canon.contracts import canonical_sha256

    manifest = {
        "library_id": library_id,
        "patches": [
            {"artifact_manifest": item.compilation.artifact_manifest.canonical_dict(), "position": item.position}
            for item in items
        ],
        "rig_revision_id": bridge.rig_revision_id,
        "run_id": bridge.source_run_id,
    }
    canonical_hash = canonical_sha256(manifest)
    session.add(
        ArtifactManifestRecord(
            id=f"manifest-{canonical_hash[:48]}",
            run_id=bridge.source_run_id,
            manifest=manifest,
            canonical_hash=canonical_hash,
        )
    )


def write_run_outcome_receipt(
    session: Session,
    *,
    bridge: LegacyRunExportBridge,
    seed: int,
    status: str,
    detail: object,
) -> None:
    """Keep a receipt for a run that sealed no patch (spec 001 D5). A run stopped before its
    canonical record was committed has nothing to hang one on, so it keeps only its reason."""
    from datetime import datetime, timezone

    from canon.compiler import run_outcome_receipt

    if session.get(GenerationRunRecord, bridge.source_run_id) is None:
        return
    receipt = run_outcome_receipt(
        run_id=bridge.source_run_id,
        rig_revision_id=bridge.rig_revision_id,
        seed=seed,
        status=status,
        detail=detail,
        created_at=datetime.now(timezone.utc),
    )
    session.add(
        StageReceiptRecord(
            id=receipt.artifact_id,
            run_id=bridge.source_run_id,
            stage=receipt.stage,
            operation=receipt.operation,
            operation_version=receipt.operation_version,
            determinism_class=receipt.determinism_class,
            input_hash=receipt.input_hash,
            output_hash=receipt.output_hash,
            receipt=receipt.canonical_dict(),
        )
    )


def _hash_from_generated_rows(rows: list[GeneratedPatchRecord]) -> str:
    from canon.contracts import canonical_sha256

    payload = [{"position": int(r.position), "canonical_hash": str(r.canonical_hash)} for r in rows]
    return canonical_sha256(payload)
