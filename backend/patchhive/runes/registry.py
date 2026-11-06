from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Iterable, List, Set

from patchhive.runes.schema import RuneManifest, parse_manifest

CORE_HANDLERS: List[str] = [
    "patches.engine:build_rack_state_ir",
    "patches.engine:generate_patches_for_rack",
    "patches.engine:generate_patches_with_ir",
    "patchhive.ops.build_canonical_rig:build_canonical_rig",
    "patchhive.gallery.revisions:append_revision",
    "export.pdf:generate_patch_pdf",
    "export.pdf:generate_rack_pdf",
    "export.visualization:generate_patch_diagram_svg",
    "export.visualization:generate_rack_layout_svg",
    "export.waveform:generate_waveform_svg",
]

CORE_OPERATIONS = {
    "RUNE.PATCHHIVE.DETECT_MODULES",
    "RUNE.PATCHHIVE.RESOLVE_MODULES",
    "RUNE.PATCHHIVE.ENSURE_MODULE_SPECS",
    "RUNE.PATCHHIVE.BUILD_CANONICAL_RIG",
    "RUNE.PATCHHIVE.MAP_METRICS",
    "RUNE.PATCHHIVE.SUGGEST_LAYOUTS",
    "RUNE.PATCHHIVE.GENERATE_PATCH",
    "RUNE.PATCHHIVE.VALIDATE_PATCH",
}


def rune_id_for(*, maps_to: str, name: str) -> str:
    payload = f"patchhive:{maps_to}:{name}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def manifest_path() -> Path:
    return Path(__file__).resolve().parent / "manifest.json"


def assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets"


def load_manifest() -> RuneManifest:
    data = json.loads(manifest_path().read_text(encoding="utf-8"))
    return parse_manifest(data)


def resolve_callable(path: str):
    if ":" not in path:
        raise ValueError(f"Rune maps_to must include module:callable, got {path}")
    module_path, attr_path = path.split(":", 1)
    module = importlib.import_module(module_path)
    target = module
    for attr in attr_path.split("."):
        target = getattr(target, attr)
    if not callable(target):
        raise TypeError(f"Resolved rune target is not callable: {path}")
    return target


def validate_manifest(manifest: RuneManifest | None = None) -> List[str]:
    if manifest is None:
        manifest = load_manifest()

    errors: List[str] = []
    rune_ids: Set[str] = set()
    referenced_assets: Set[str] = set()
    mapped_handlers = {r.maps_to for r in manifest.runes}

    for rune in manifest.runes:
        expected_id = rune_id_for(maps_to=rune.maps_to, name=rune.name)
        if rune.rune_id != expected_id:
            errors.append(
                f"Rune {rune.name} has non-deterministic id: {rune.rune_id} != {expected_id}"
            )
        if rune.rune_id in rune_ids:
            errors.append(f"Duplicate rune_id: {rune.rune_id}")
        rune_ids.add(rune.rune_id)

        try:
            resolve_callable(rune.maps_to)
        except Exception as exc:  # pragma: no cover - captured for report
            errors.append(f"maps_to not importable ({rune.maps_to}): {exc}")

        for asset in rune.assets:
            asset_path = Path(__file__).resolve().parent / asset
            if not asset_path.exists():
                errors.append(f"Missing asset for rune {rune.name}: {asset}")
            referenced_assets.add(asset)

    existing_assets = {
        str(p.relative_to(Path(__file__).resolve().parent)) for p in assets_dir().glob("*.svg")
    }
    orphans = existing_assets - referenced_assets
    if orphans:
        errors.append(f"Orphan rune assets: {sorted(orphans)}")

    missing_handlers = [h for h in CORE_HANDLERS if h not in mapped_handlers]
    if missing_handlers:
        errors.append(f"Core handlers without rune mapping: {missing_handlers}")

    operation_names = {operation.name for operation in manifest.operations}
    missing_operations = CORE_OPERATIONS - operation_names
    if missing_operations:
        errors.append(f"Missing canonical rune operations: {sorted(missing_operations)}")
    if len(operation_names) != len(manifest.operations):
        errors.append("Duplicate canonical rune operation name")
    for operation in manifest.operations:
        expected_id = rune_id_for(maps_to=operation.maps_to, name=operation.name)
        if operation.rune_id != expected_id:
            errors.append(
                f"Rune operation {operation.name} has non-deterministic id: "
                f"{operation.rune_id} != {expected_id}"
            )
        if operation.determinism_class not in {"deterministic", "evidence_acquisition"}:
            errors.append(f"Invalid determinism class for {operation.name}")
        if not operation.failure_taxonomy or not operation.test_vectors:
            errors.append(f"Incomplete failure taxonomy or test vectors for {operation.name}")
        try:
            resolve_callable(operation.maps_to)
        except Exception as exc:  # pragma: no cover - captured for report
            errors.append(f"maps_to not importable ({operation.maps_to}): {exc}")

    return errors


def iter_core_handlers() -> Iterable[str]:
    return list(CORE_HANDLERS)
