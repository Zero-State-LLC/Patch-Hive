"""Canon export fulfillment worker (KD-12) — closes debit-only queued gap."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from canon.exports import compensate_failed_export
from canon.models import CanonicalExportRecord
from core.config import settings
from core.storage import StorageError, get_file_store
from export.patchbook.design.constraints import (
    StyleResolveError,
    professional_default_resolved,
    revalidate_resolved_recipe,
)
from export.patchbook.design.content_spine import ContentSpineError, load_patch_compilations
from export.patchbook.design.engine import PreflightFailed, compose_design_export_pack
from export.patchbook.design.recipe import (
    DESIGN_ENGINE_VERSION,
    ResolvedStyleRecipe,
    recipe_hash,
)


@dataclass(frozen=True)
class FulfillResult:
    export_id: str
    status: str
    error_code: str | None = None
    pack_manifest_hash: str | None = None
    composition_hash: str | None = None


def export_store_root() -> Path:
    root = Path(settings.export_store_root or settings.export_dir) / "design_packs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def pack_dir_for_export(export_id: str) -> Path:
    return export_store_root() / export_id


def fulfill_export(session: Session, export_id: str) -> FulfillResult:
    """Idempotent fulfill: load spine → compose pack → succeeded or compensate."""

    export = session.get(CanonicalExportRecord, export_id)
    if export is None:
        raise ValueError(f"export not found: {export_id}")

    # Succeeded short-circuit
    if export.status == "succeeded" and getattr(export, "pack_manifest_hash", None):
        pack = pack_dir_for_export(export_id)
        try:
            get_file_store().ensure_local_tree(pack)
        except StorageError:
            pass  # recompose below rather than report a pack that cannot be read
        if pack.exists() and (pack / "PatchBook.pdf").exists():
            return FulfillResult(
                export_id=export_id,
                status="succeeded",
                pack_manifest_hash=export.pack_manifest_hash,
                composition_hash=getattr(export, "composition_hash", None),
            )

    max_attempts = int(settings.export_fulfill_max_attempts)
    attempts = int(getattr(export, "fulfill_attempts", 0) or 0)
    if attempts >= max_attempts and export.status not in {"succeeded"}:
        compensate_failed_export(session, export, occurred_at=datetime.now(timezone.utc))
        export.error_code = export.error_code or "EXPORT_FULFILL_MAX_ATTEMPTS"
        session.flush()
        return FulfillResult(
            export_id=export_id, status=export.status, error_code=export.error_code
        )

    export.status = "running"
    export.fulfill_attempts = attempts + 1
    if hasattr(export, "running_started_at"):
        export.running_started_at = datetime.now(timezone.utc)
    session.flush()

    try:
        recipe = _load_or_default_recipe(export)
        expected_hash = getattr(export, "style_recipe_hash", None) or recipe_hash(recipe)
        revalidate_resolved_recipe(
            recipe,
            expected_hash=expected_hash,
            expected_engine_version=getattr(export, "design_engine_version", None)
            or DESIGN_ENGINE_VERSION,
        )

        library = load_patch_compilations(
            session,
            source_run_id=export.source_run_id,
            source_rig_revision_id=export.source_rig_revision_id,
            artifact_manifest_hash=export.artifact_manifest_hash,
            require_sealed=bool(settings.require_sealed_generated_patches),
        )

        out = pack_dir_for_export(export_id)
        result = compose_design_export_pack(
            library,
            recipe,
            out_dir=out,
            export_id=export_id,
        )
        # A paid pack only counts as delivered once it is durable.
        get_file_store().persist_tree(out)

        export.status = "succeeded"
        if hasattr(export, "library_content_hash"):
            export.library_content_hash = library.library_content_hash
        if hasattr(export, "composition_hash"):
            export.composition_hash = result.composition_hash
        if hasattr(export, "pack_manifest_hash"):
            export.pack_manifest_hash = result.pack_manifest_hash
        if hasattr(export, "artifact_uri"):
            export.artifact_uri = str(out)
        if hasattr(export, "style_recipe_hash") and not export.style_recipe_hash:
            export.style_recipe_hash = recipe_hash(recipe)
        if hasattr(export, "design_engine_version") and not export.design_engine_version:
            export.design_engine_version = DESIGN_ENGINE_VERSION
        export.error_code = None
        session.flush()
        return FulfillResult(
            export_id=export_id,
            status="succeeded",
            pack_manifest_hash=result.pack_manifest_hash,
            composition_hash=result.composition_hash,
        )
    except (ContentSpineError, StyleResolveError, PreflightFailed) as exc:
        code = getattr(exc, "code", "EXPORT_FULFILL_FAILED")
        return _fail(session, export, code)
    except StorageError as exc:
        return _fail(session, export, exc.code)
    except Exception:
        return _fail(session, export, "EXPORT_FULFILL_FAILED")


def _fail(session: Session, export: CanonicalExportRecord, code: str) -> FulfillResult:
    export.error_code = code
    compensate_failed_export(session, export, occurred_at=datetime.now(timezone.utc))
    session.flush()
    return FulfillResult(export_id=export.id, status=export.status, error_code=code)


def _load_or_default_recipe(export: CanonicalExportRecord) -> ResolvedStyleRecipe:
    raw = getattr(export, "resolved_style_recipe_json", None)
    if raw:
        if isinstance(raw, str):
            return ResolvedStyleRecipe.model_validate_json(raw)
        return ResolvedStyleRecipe.model_validate(raw)
    tier = getattr(export, "resolved_tier", None) or "core"
    seed = int(canonical_seed_from_export(export))
    return professional_default_resolved(seed=seed, tier=tier)  # type: ignore[arg-type]


def canonical_seed_from_export(export: CanonicalExportRecord) -> int:
    # Deterministic seed from export id hex
    digits = "".join(ch for ch in export.id if ch.isdigit())
    if digits:
        return int(digits[:9]) % 2_147_483_647
    return 0
