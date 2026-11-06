"""Minimal Design Engine orchestrator: compose pack from sealed compilations + recipe."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from canon.compiler import STARTUP_CHECK
from canon.contracts import canonical_json, canonical_sha256
from export.patchbook.design.brand_policy import (
    PDF_CREATOR_PATTERN,
    scan_forbidden_strings,
)
from export.patchbook.design.content_spine import LoadedLibrary
from export.patchbook.design.a11y import body_size_pt
from export.patchbook.design.diagram_svg import (
    DiagramLayout,
    draw_diagram_on_canvas,
    feedback_edge_ids,
    layout_diagram,
    numbered_edges,
    render_patch_diagram_svg,
)
from export.patchbook.design.diagram_svg import wrap_to_width as _wrap_to_width
from export.patchbook.design.families.registry import (
    PATENT_FUTURE_DISCLAIMER,
    FamilySpec,
    get_family,
)
from export.patchbook.design.layout_ir import (
    LayoutRegion,
    PageKind,
    PatchPageLayoutIR,
    composition_hash,
)
from export.patchbook.design.preflight import run_preflight
from export.patchbook.design.recipe import (
    DESIGN_ENGINE_VERSION,
    ResolvedStyleRecipe,
    recipe_hash,
)
from export.patchbook.pdf_meta import normalize_pdf_metadata


class PreflightFailed(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ComposeResult:
    composition_hash: str
    pack_manifest_hash: str
    page_count: int
    layout_irs: tuple[PatchPageLayoutIR, ...]
    family_algorithm: str


# --- Book validation (spec 002 FR-006, FR-016, FR-017, FR-019) ----------------------

BOOK_VALIDATION_RECEIPT_PATH = "validation/book.json"
BOOK_VALIDATION_OPERATION_VERSION = "1.0.0"
CHECKSUMS_PATH = "manifest/checksums.json"

# Section 15 book codes, each with its remediation (FR-019).
BOOK_REMEDIATION = {
    "PATCH_BOOK_PAGE_COUNT_MISMATCH": (
        "Draw every page the manifest lists, or remove it from the layout. Plate mode "
        "fails until plates are drawn; use the execution_page profile."
    ),
    "PATCH_BOOK_REFERENCE_UNRESOLVED": (
        "Re-run the export from the same sealed library so every page, patch and "
        "bundle path resolves."
    ),
    "PATCH_BOOK_ASSET_HASH_MISMATCH": (
        "Re-run the export; a bundle file changed after it was written or the layout "
        "IR no longer replays the composition hash."
    ),
}

_PATCH_PAGE_KINDS = (PageKind.EXECUTION, PageKind.APPENDIX_EXECUTION)


class BookValidationFailed(PreflightFailed):
    """A `validate_book` check failed; the receipt stays in the pack."""


@dataclass(frozen=True)
class BookValidation:
    pages: tuple[dict[str, Any], ...]
    pdf_page_count: int
    manifest_page_count: int
    patch_count: int
    patch_page_count: int
    replay_composition_hash: str | None
    error_code: str | None = None
    message: str | None = None

    @property
    def status(self) -> str:
        return "fail" if self.error_code else "pass"


def validate_book(
    root: Path,
    layout_irs: list[PatchPageLayoutIR],
    library: LoadedLibrary,
    *,
    pages_drawn: int,
    svg_hashes: dict[str, str],
    paths: dict[str, Any],
    expected_composition_hash: str,
    resolved_recipe_hash: str,
) -> BookValidation:
    """Check the rendered pack against its layout and return one entry per page.

    The checks run in order and the first failure sets the error code: page counts
    and order, then references, then asset hashes and replay.
    """
    library_ids = {item.compilation.patch_graph.artifact_id for item in library.items}
    errors: list[tuple[str, str]] = []
    page_failures: set[int] = set()

    # Page count: the PDF is the authority. Patches and patch pages match one to one.
    patch_pages = [ir for ir in layout_irs if ir.page_kind in _PATCH_PAGE_KINDS]
    if pages_drawn != len(layout_irs):
        errors.append(
            (
                "PATCH_BOOK_PAGE_COUNT_MISMATCH",
                f"PatchBook.pdf has {pages_drawn} pages; the manifest lists {len(layout_irs)}",
            )
        )
    if len(patch_pages) != len(library.items):
        errors.append(
            (
                "PATCH_BOOK_PAGE_COUNT_MISMATCH",
                f"{len(library.items)} patches but {len(patch_pages)} patch pages",
            )
        )
    if [ir.page_index for ir in layout_irs] != list(range(len(layout_irs))):
        errors.append(("PATCH_BOOK_PAGE_COUNT_MISMATCH", "page order is not 0..n-1"))

    # References: every patch page names a library patch with a diagram, every patch
    # has a page, and every bundle path the manifest will list exists.
    for ir in layout_irs:
        if ir.patch_artifact_id is None:
            continue
        if ir.patch_artifact_id not in library_ids:
            page_failures.add(ir.page_index)
            errors.append(
                (
                    "PATCH_BOOK_REFERENCE_UNRESOLVED",
                    f"page {ir.page_index} names unknown patch {ir.patch_artifact_id}",
                )
            )
        elif not (root / _diagram_path(ir.patch_artifact_id)).is_file():
            page_failures.add(ir.page_index)
            errors.append(
                (
                    "PATCH_BOOK_REFERENCE_UNRESOLVED",
                    f"page {ir.page_index} diagram {_diagram_path(ir.patch_artifact_id)} is missing",
                )
            )
    paged_ids = {ir.patch_artifact_id for ir in patch_pages}
    for artifact_id in sorted(library_ids - paged_ids):
        errors.append(("PATCH_BOOK_REFERENCE_UNRESOLVED", f"patch {artifact_id} has no page"))
    for key, value in sorted(paths.items()):
        if key in {"layout_ir_dir", "book_validation"}:
            continue  # a directory, and the receipt this stage is about to write
        for rel in value if isinstance(value, list) else [value]:
            if not (root / rel).is_file():
                errors.append(("PATCH_BOOK_REFERENCE_UNRESOLVED", f"{key} path {rel} is missing"))

    # Asset hashes: each diagram on disk matches the SVG drawn, and the layout IR on
    # disk replays composition_hash (deterministic replay, FR-006).
    on_disk_svg: dict[str, str] = {}
    for artifact_id, expected in sorted(svg_hashes.items()):
        target = root / _diagram_path(artifact_id)
        if not target.is_file():
            continue  # already reported as unresolved
        on_disk_svg[artifact_id] = _sha256_file(target)
        if on_disk_svg[artifact_id] != expected:
            page_failures.update(
                ir.page_index for ir in layout_irs if ir.patch_artifact_id == artifact_id
            )
            errors.append(
                (
                    "PATCH_BOOK_ASSET_HASH_MISMATCH",
                    f"{_diagram_path(artifact_id)} does not match the diagram drawn",
                )
            )
    replay_hash: str | None = None
    try:
        replayed = [
            PatchPageLayoutIR.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted((root / "pages" / "layout_ir").glob("*.json"))
        ]
        replay_hash = composition_hash(
            library_content_hash=library.library_content_hash,
            bridge_artifact_manifest_hash=library.bridge_artifact_manifest_hash,
            resolved_recipe_hash=resolved_recipe_hash,
            layout_irs=replayed,
            design_engine_version=DESIGN_ENGINE_VERSION,
        )
    except ValueError as exc:  # pydantic ValidationError is a ValueError
        errors.append(("PATCH_BOOK_ASSET_HASH_MISMATCH", f"layout IR does not load: {exc}"))
    if replay_hash is not None and replay_hash != expected_composition_hash:
        errors.append(
            ("PATCH_BOOK_ASSET_HASH_MISMATCH", "layout IR on disk does not replay composition_hash")
        )

    pages = tuple(
        {
            "index": ir.page_index,
            "kind": ir.page_kind.value,
            "page_id": ir.page_id,
            "patch_artifact_id": ir.patch_artifact_id,
            "page_hash": canonical_sha256(ir.model_dump(mode="json")),
            "svg_hash": on_disk_svg.get(ir.patch_artifact_id) if ir.patch_artifact_id else None,
            "status": "fail" if ir.page_index in page_failures else "pass",
        }
        for ir in layout_irs
    )
    first = errors[0] if errors else (None, None)
    return BookValidation(
        pages=pages,
        pdf_page_count=pages_drawn,
        manifest_page_count=len(layout_irs),
        patch_count=len(library.items),
        patch_page_count=len(patch_pages),
        replay_composition_hash=replay_hash,
        error_code=first[0],
        message="; ".join(msg for _, msg in errors) if errors else None,
    )


def _book_validation_receipt(
    validation: BookValidation,
    *,
    export_id: str,
    composition_hash_value: str,
    warning_issues: list[tuple[str, str, str]],
) -> dict[str, Any]:
    """The `validate_book` stage receipt. No timestamps, so a replay writes the same bytes."""
    return {
        "stage": "validate_book",
        "operation": "compose_design_export_pack.validate_book",
        "operation_version": BOOK_VALIDATION_OPERATION_VERSION,
        "determinism_class": "deterministic",
        "design_engine_version": DESIGN_ENGINE_VERSION,
        "export_id": export_id,
        "input_hash": composition_hash_value,
        "output_hash": canonical_sha256(list(validation.pages)),
        "status": validation.status,
        "error_code": validation.error_code,
        "message": validation.message,
        "remediation": BOOK_REMEDIATION.get(validation.error_code or ""),
        "pdf_page_count": validation.pdf_page_count,
        "manifest_page_count": validation.manifest_page_count,
        "patch_count": validation.patch_count,
        "patch_page_count": validation.patch_page_count,
        "replay_composition_hash": validation.replay_composition_hash,
        "pages": list(validation.pages),
        # Every preflight warning, never dropped (spec 002 FR-019, OQ-7).
        "warnings": [
            {"code": code, "severity": severity, "message": message}
            for code, severity, message in warning_issues
        ],
    }


def _diagram_path(artifact_id: str) -> str:
    return f"diagrams/svg/{artifact_id}.svg"


def _bundle_files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# What a seal writes when a fact was missing. None of these may reach a page (spec 002 FR-014).
PLACEHOLDERS = {"", "UNKNOWN", "NOT_COMPUTABLE"}


def check_semantics(library: LoadedLibrary) -> None:
    """Refuse a patch before anything is drawn (spec 002 FR-013, FR-014): a missing fact is an
    error, never a placeholder, and every module has to be on the source rig revision. One
    patch that fails stops the whole export, and the customer's credits come back (decision 37)."""
    for item in library.items:
        plan = item.compilation.patch_plan
        graph = item.compilation.patch_graph
        report = item.compilation.validation_report
        artifact = graph.artifact_id

        def missing(what: str) -> PreflightFailed:
            return PreflightFailed(
                "PATCH_PAGE_REQUIRED_CONTENT_MISSING",
                f"Patch {artifact} has no {what}. Remediation: generate the patch again from the "
                "confirmed rig.",
            )

        if str(plan.title).strip() in PLACEHOLDERS:
            raise missing("title")
        if str(plan.intent).strip() in PLACEHOLDERS:
            raise missing("intent")
        if not plan.steps:
            raise missing("operation steps")
        if not graph.edges:
            raise missing("cables")
        for node in graph.nodes:
            if node.module_instance_id not in library.module_display:
                raise PreflightFailed(
                    "PATCH_BOOK_REFERENCE_UNRESOLVED",
                    f"Patch {artifact} uses module {node.module_instance_id}, which isn't on "
                    "the source rig revision. Remediation: generate the patch again from the "
                    "current rig.",
                )
            for port in node.ports:
                if str(port.label).strip() in PLACEHOLDERS:
                    raise missing(f"jack name on module {node.module_instance_id}")
        for edge in graph.edges:
            if edge.signal_type == "unknown":
                raise missing(f"signal type on cable {edge.edge_id}")
        if not report.valid:
            codes = ", ".join(sorted({i.code for i in report.issues if i.severity in {"error", "critical"}}))
            raise PreflightFailed(
                "PATCH_PAGE_GRAPH_MISMATCH",
                f"Patch {artifact} did not pass validation ({codes}). Remediation: generate the "
                "patch again from the confirmed rig.",
            )


def compose_design_export_pack(
    library: LoadedLibrary,
    recipe: ResolvedStyleRecipe,
    *,
    out_dir: str | Path,
    export_id: str,
) -> ComposeResult:
    """Write design_export_pack.v1 directory; presentation only."""
    check_semantics(library)
    family = get_family(recipe.template_family)
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "style").mkdir(exist_ok=True)
    (root / "source").mkdir(exist_ok=True)
    (root / "pages" / "json").mkdir(parents=True, exist_ok=True)
    (root / "pages" / "layout_ir").mkdir(parents=True, exist_ok=True)
    (root / "diagrams" / "svg").mkdir(parents=True, exist_ok=True)
    (root / "manifest").mkdir(exist_ok=True)
    (root / "technical").mkdir(exist_ok=True)

    resolved_hash = recipe_hash(recipe)
    (root / "style" / "family.json").write_text(
        canonical_json(
            {
                "family_id": family.family_id.value,
                "layout_algorithm_id": family.layout_algorithm_id,
                "fingerprint": family.fingerprint.as_dict(),
            }
        ),
        encoding="utf-8",
    )
    (root / "style" / "resolved_recipe.json").write_text(
        canonical_json(recipe.model_dump(mode="json")), encoding="utf-8"
    )
    (root / "style" / "resolved_recipe.sha256").write_text(resolved_hash + "\n", encoding="utf-8")

    library_index = {
        "source_run_id": library.source_run_id,
        "source_rig_revision_id": library.source_rig_revision_id,
        "bridge_artifact_manifest_hash": library.bridge_artifact_manifest_hash,
        "library_content_hash": library.library_content_hash,
        "load_path": library.load_path,
        "patches": [
            {
                "position": item.position,
                "title": item.compilation.patch_plan.title,
                "graph_artifact_id": item.compilation.patch_graph.artifact_id,
                "canonical_hash": item.compilation.canonical_hash_value(),
                "edge_count": len(item.compilation.patch_graph.edges),
            }
            for item in library.items
        ],
    }
    (root / "source" / "library_index.json").write_text(
        canonical_json(library_index), encoding="utf-8"
    )

    publication = recipe.constraints.book_profile.value == "publication"
    plate_primary = publication and "plate" in family.fingerprint.default_page_kinds

    layout_irs: list[PatchPageLayoutIR] = []
    # Cover
    layout_irs.append(_front_matter_page(0, "cover", recipe, family))
    page_index = 1
    diagram_paths: list[str] = []
    svg_hashes: dict[str, str] = {}
    for item in library.items:
        # Deterministic technical SVG per patch (color + dash + number)
        svg = render_patch_diagram_svg(
            item.compilation,
            layout_algorithm_id=family.layout_algorithm_id,
            module_labels=_module_labels(library),
        )
        svg_rel = _diagram_path(item.compilation.patch_graph.artifact_id)
        (root / svg_rel).write_text(svg, encoding="utf-8")
        diagram_paths.append(svg_rel)
        svg_hashes[item.compilation.patch_graph.artifact_id] = hashlib.sha256(
            svg.encode("utf-8")
        ).hexdigest()

        if plate_primary:
            # Artistic/publication primary: non-executable plate (appendix holds execution)
            plate_ir = _plate_page(page_index, item.compilation, recipe, family)
            layout_irs.append(plate_ir)
            page_payload = {
                "page_index": page_index,
                "page_kind": "plate",
                "title": item.compilation.patch_plan.title,
                "intent": item.compilation.patch_plan.intent,
                "graph_artifact_id": item.compilation.patch_graph.artifact_id,
                "note": "Visual plate — technical execution is in the appendix",
            }
            (root / "pages" / "json" / f"page-{page_index:04d}-plate.json").write_text(
                canonical_json(page_payload), encoding="utf-8"
            )
            page_index += 1
            # Dual-artifact: appendix_execution page IR for preflight completeness
            app_ir = _execution_page(page_index, item.compilation, recipe, family, library)
            app_ir = app_ir.model_copy(
                update={
                    "page_kind": PageKind.APPENDIX_EXECUTION,
                    "page_id": f"appendix-{item.compilation.patch_graph.artifact_id}",
                    "page_index": page_index,
                }
            )
            layout_irs.append(app_ir)
            page_payload_ex = {
                "page_index": page_index,
                "page_kind": "appendix_execution",
                "modules": _page_modules(item.compilation, library),
                "plan": item.compilation.patch_plan.canonical_dict(),
                "graph": {
                    "artifact_id": item.compilation.patch_graph.artifact_id,
                    "nodes": len(item.compilation.patch_graph.nodes),
                    "edges": [
                        {
                            "edge_id": e.edge_id,
                            "source_port_id": e.source_port_id,
                            "target_port_id": e.target_port_id,
                            "signal_type": e.signal_type,
                        }
                        for e in item.compilation.patch_graph.edges
                    ],
                },
                "validation": item.compilation.validation_report.canonical_dict(),
            }
            (root / "pages" / "json" / f"page-{page_index:04d}-appendix.json").write_text(
                canonical_json(page_payload_ex), encoding="utf-8"
            )
            page_index += 1
        else:
            ir = _execution_page(page_index, item.compilation, recipe, family, library)
            layout_irs.append(ir)
            page_payload = {
                "page_index": page_index,
                "page_kind": "execution",
                "modules": _page_modules(item.compilation, library),
                "plan": item.compilation.patch_plan.canonical_dict(),
                "graph": {
                    "artifact_id": item.compilation.patch_graph.artifact_id,
                    "nodes": len(item.compilation.patch_graph.nodes),
                    "edges": [
                        {
                            "edge_id": e.edge_id,
                            "source_port_id": e.source_port_id,
                            "target_port_id": e.target_port_id,
                            "signal_type": e.signal_type,
                        }
                        for e in item.compilation.patch_graph.edges
                    ],
                },
                "validation": item.compilation.validation_report.canonical_dict(),
            }
            (root / "pages" / "json" / f"page-{page_index:04d}.json").write_text(
                canonical_json(page_payload), encoding="utf-8"
            )
            page_index += 1

    # Colophon
    layout_irs.append(_front_matter_page(page_index, "colophon", recipe, family))

    # Persist layout IR pages for golden / adapter reuse
    for ir in layout_irs:
        (root / "pages" / "layout_ir" / f"{ir.page_index:04d}-{ir.page_id}.json").write_text(
            canonical_json(ir.model_dump(mode="json")),
            encoding="utf-8",
        )

    # Brand text scan
    brand_scan = scan_forbidden_strings(
        [recipe.notes, PDF_CREATOR_PATTERN, "PatchHive", "A Zero State Product"]
    )
    if not brand_scan.ok:
        raise PreflightFailed("BRAND_POLICY_VIOLATION", ",".join(brand_scan.violations))

    # Pre-render a11y/layout gates
    gate = run_preflight(layout_irs, recipe, pack_dir=None)
    if not gate.ok:
        first = next((i for i in gate.issues if i.severity == "error"), None)
        code = first.code if first else "PREFLIGHT_FAILED"
        raise PreflightFailed(code, first.message if first else "preflight failed")
    # Warnings do not block the pack, but they are never dropped (spec 002 OQ-7, FR-019):
    # the manifest lists their codes and the book validation receipt lists each one.
    warning_issues = sorted(
        {(i.code, i.severity, i.message) for i in gate.issues if i.severity == "warning"}
    )
    preflight_warnings = sorted({code for code, _, _ in warning_issues})

    comp_hash = composition_hash(
        library_content_hash=library.library_content_hash,
        bridge_artifact_manifest_hash=library.bridge_artifact_manifest_hash,
        resolved_recipe_hash=resolved_hash,
        layout_irs=layout_irs,
        design_engine_version=DESIGN_ENGINE_VERSION,
    )

    pdf_path = root / "PatchBook.pdf"
    pages_drawn = _render_execution_pdf(
        library,
        recipe,
        family,
        pdf_path,
        export_id=export_id,
        composition_hash=comp_hash,
    )

    # Technical companion (text-first)
    companion_lines = [
        "PatchHive Technical Companion",
        f"export_id={export_id}",
        f"composition_hash={comp_hash}",
        f"library_content_hash={library.library_content_hash}",
        f"style_recipe_hash={resolved_hash}",
        f"design_engine_version={DESIGN_ENGINE_VERSION}",
        f"mode={recipe.mode.value}",
        f"template_family={recipe.template_family.value}",
        "",
    ]
    for item in library.items:
        companion_lines.append(f"## {item.compilation.patch_plan.title}")
        companion_lines.append(item.compilation.patch_plan.intent)
        for cable in cable_lines(item.compilation.patch_graph, _module_labels(library)):
            companion_lines.append(f"  CABLE {cable}")
        for number, step in enumerate(operation_lines(item.compilation, library), start=1):
            companion_lines.append(f"  STEP {number}. {step}")
        for note in page_notes(item.compilation, library):
            companion_lines.append(f"  NOTE {note}")
        companion_lines.append("")
    (root / "technical" / "companion.txt").write_text("\n".join(companion_lines), encoding="utf-8")

    if recipe.constraints.canonical_appendix_required:
        # Dual-artifact: copy execution pdf as technical appendix
        appendix = root / "technical" / "PatchBook-execution.pdf"
        appendix.write_bytes(pdf_path.read_bytes())

    license_lines = ["PatchHive export. Designed and Engineered by Zero State.\n"]
    if family.patent_disclaimer:
        license_lines.append(PATENT_FUTURE_DISCLAIMER + "\n")
    (root / "LICENSE.txt").write_text("".join(license_lines), encoding="utf-8")
    (root / "README.txt").write_text(_pack_readme(library, comp_hash), encoding="utf-8")

    paths: dict[str, Any] = {
        "pdf": "PatchBook.pdf",
        "companion": "technical/companion.txt",
        "library_index": "source/library_index.json",
        "resolved_recipe": "style/resolved_recipe.json",
        "family": "style/family.json",
        "diagrams": diagram_paths,
        "layout_ir_dir": "pages/layout_ir",
        "book_validation": BOOK_VALIDATION_RECEIPT_PATH,
        "readme": "README.txt",
    }

    # validate_book: the PDF is the page-count authority, every reference resolves,
    # every asset is hash-valid, and the IR on disk replays composition_hash (spec 002
    # FR-006, FR-016, FR-017). A failure keeps its receipt in the pack (FR-007).
    validation = validate_book(
        root,
        layout_irs,
        library,
        pages_drawn=pages_drawn,
        svg_hashes=svg_hashes,
        paths=paths,
        expected_composition_hash=comp_hash,
        resolved_recipe_hash=resolved_hash,
    )
    receipt = _book_validation_receipt(
        validation,
        export_id=export_id,
        composition_hash_value=comp_hash,
        warning_issues=warning_issues,
    )
    (root / BOOK_VALIDATION_RECEIPT_PATH).parent.mkdir(parents=True, exist_ok=True)
    (root / BOOK_VALIDATION_RECEIPT_PATH).write_text(canonical_json(receipt), encoding="utf-8")
    if validation.error_code is not None:
        raise BookValidationFailed(validation.error_code, validation.message or "")

    manifest: dict[str, Any] = {
        "schema_version": "patchhive.design_export_pack.v1",
        "export_id": export_id,
        "design_engine_version": DESIGN_ENGINE_VERSION,
        "composition_hash": comp_hash,
        "library_content_hash": library.library_content_hash,
        "bridge_artifact_manifest_hash": library.bridge_artifact_manifest_hash,
        "style_recipe_hash": resolved_hash,
        "mode": recipe.mode.value,
        "template_family": recipe.template_family.value,
        "layout_algorithm_id": family.layout_algorithm_id,
        "page_count": len(layout_irs),
        "pages": list(validation.pages),
        "validation_status": "pass",
        "resolved_tier": recipe.resolved_tier,
        "warnings": preflight_warnings,
        "paths": paths,
    }
    body_hash = canonical_sha256({k: v for k, v in manifest.items() if k != "pack_manifest_hash"})
    manifest["pack_manifest_hash"] = body_hash
    (root / "manifest" / "patch-book.json").write_text(canonical_json(manifest), encoding="utf-8")

    # Emit: one SHA-256 per bundle file, then read every file back against it.
    file_hashes = {
        rel: _sha256_file(root / rel) for rel in _bundle_files(root) if rel != CHECKSUMS_PATH
    }
    (root / CHECKSUMS_PATH).write_text(
        canonical_json(
            {
                "composition_hash": comp_hash,
                "pack_manifest_hash": body_hash,
                "files": file_hashes,
            }
        ),
        encoding="utf-8",
    )
    recorded = json.loads((root / CHECKSUMS_PATH).read_text(encoding="utf-8"))["files"]
    for rel, digest in sorted(recorded.items()):
        target = root / rel
        if not target.is_file() or _sha256_file(target) != digest:
            raise BookValidationFailed(
                "PATCH_BOOK_ASSET_HASH_MISMATCH", f"{rel} does not match manifest/checksums.json"
            )

    # Post-pack preflight (files present)
    post = run_preflight(layout_irs, recipe, pack_dir=root)
    if not post.ok:
        first = next((i for i in post.issues if i.severity == "error"), None)
        code = first.code if first else "PREFLIGHT_FAILED"
        raise PreflightFailed(code, first.message if first else "post-pack preflight failed")

    return ComposeResult(
        composition_hash=comp_hash,
        pack_manifest_hash=body_hash,
        page_count=len(layout_irs),
        layout_irs=tuple(layout_irs),
        family_algorithm=family.layout_algorithm_id,
    )


def _pack_readme(library: LoadedLibrary, composition_hash_value: str) -> str:
    """What's in the pack (spec 002 FR-018)."""
    return "\n".join(
        [
            "PatchHive PatchBook",
            "",
            f"Patches: {len(library.items)}",
            f"Source run: {library.source_run_id}",
            f"Composition hash: {composition_hash_value}",
            "",
            "PatchBook.pdf                One page per patch, ready to print.",
            "technical/companion.txt      The same patches as plain text.",
            "diagrams/svg/                Each patch's diagram.",
            "pages/json/                  Each page's data.",
            "manifest/patch-book.json     The pages and hashes of this book.",
            "manifest/checksums.json      A SHA-256 for every file in this pack.",
            "validation/book.json         What was checked before this pack was written.",
            "",
            "The PDF is for reading. The JSON files and hashes are what reproduce the book.",
            "",
        ]
    )


def _module_labels(library: LoadedLibrary) -> dict[str, str]:
    return {module_id: module.label for module_id, module in library.module_display.items()}


def _page_modules(compilation: Any, library: LoadedLibrary) -> dict[str, str]:
    """The names this patch's page prints. They go in the page data and the layout IR, so they
    count toward the composition hash."""
    return {
        node.module_instance_id: library.module_display[node.module_instance_id].label
        for node in compilation.patch_graph.nodes
    }


def cable_lines(graph: Any, labels: dict[str, str]) -> list[str]:
    """The ordered connection list. Each number matches a route on the diagram (FR-011)."""
    ports = {port.port_id: (node, port) for node in graph.nodes for port in node.ports}

    def end(port_id: str) -> str:
        node, port = ports[port_id]
        return f"{labels.get(node.module_instance_id, node.label)} {port.label}"

    return [
        f"{number}. {end(edge.source_port_id)} -> {end(edge.target_port_id)} [{edge.signal_type}]"
        for number, edge in numbered_edges(graph.edges)
    ]


def _names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def operation_lines(compilation: Any, library: LoadedLibrary) -> list[str]:
    """How to run this patch, worked out from its own cables (FR-008). The catalog holds no
    knob or mode data, so the steps say where to listen and what to bring in, never a setting."""
    graph = compilation.patch_graph
    labels = _module_labels(library)
    nodes = {port.port_id: node for node in graph.nodes for port in node.ports}
    cables = numbered_edges(graph.edges)

    def name(port_id: str) -> str:
        node = nodes[port_id]
        return labels.get(node.module_instance_id, node.label)

    def sources(*kinds: str) -> list[str]:
        return list(
            dict.fromkeys(name(e.source_port_id) for _, e in cables if e.signal_type in kinds)
        )

    audio = [e for _, e in cables if e.signal_type == "audio"]
    passes_on = {
        nodes[e.source_port_id].node_id
        for e in audio
        if nodes[e.source_port_id].node_id != nodes[e.target_port_id].node_id
    }
    ends = list(
        dict.fromkeys(
            name(e.target_port_id)
            for e in audio
            if nodes[e.target_port_id].node_id not in passes_on
        )
    )
    timing = sources("gate", "trigger", "clock")
    cv = sources("cv")
    looped_ids = feedback_edge_ids(graph)
    looped = [str(n) for n, e in cables if e.edge_id in looped_ids]

    steps = [
        STARTUP_CHECK,
        (
            "Patch cable 1, then power up."
            if len(cables) == 1
            else f"Patch cables 1 to {len(cables)} in order, then power up."
        ),
    ]
    if timing:
        steps.append(
            f"Check that {_names(timing)} "
            + ("is running: it sends" if len(timing) == 1 else "are running: they send")
            + " this patch's timing."
        )
    steps.append(
        f"Take your output from {_names(ends)}, and raise the level slowly."
        if ends
        else "Connect the module you want to hear to your output, and raise its level slowly."
    )
    if cv:
        steps.append(f"Bring in the CV from {_names(cv)} slowly while monitoring the output.")
    steps.append("Reduce the CV, then the output level." if cv else "Reduce the output level.")
    if looped:
        cable_word = "cable" if len(looped) == 1 else "cables"
        steps.append(
            f"Return levels low, remove {cable_word} {_names(looped)}, then power down if rewiring."
        )
    else:
        steps.append("Return levels low, then power down if rewiring.")
    return steps


def page_notes(compilation: Any, library: LoadedLibrary) -> list[str]:
    """What the page must warn about (FR-011, FR-013, FR-014): a feedback loop, each issue in
    the validation report, and the modules whose jack names are generic roles."""
    graph = compilation.patch_graph
    notes: list[str] = []
    looped = feedback_edge_ids(graph)
    if looped:
        numbers = [str(n) for n, edge in numbered_edges(graph.edges) if edge.edge_id in looped]
        notes.append(
            f"Feedback: cables {', '.join(numbers)} form a loop. Start with levels low, and "
            "raise them slowly."
        )
    for issue in compilation.validation_report.issues:
        if issue.message not in notes:
            notes.append(issue.message)
    generic = sorted(
        library.module_display[node.module_instance_id].label
        for node in graph.nodes
        if any(
            port.label not in library.module_display[node.module_instance_id].declared_jacks
            for port in node.ports
        )
    )
    if generic:
        notes.append(
            f"Jack names are generic for {', '.join(generic)}: the real names aren't on file, "
            "so check each panel."
        )
    return notes


def _front_matter_page(
    index: int, role: str, recipe: ResolvedStyleRecipe, family: FamilySpec
) -> PatchPageLayoutIR:
    from export.patchbook.design.layout_ir import BrandMarkRef

    region = LayoutRegion(
        region_id="identity",
        role="identity",
        required=True,
        bbox_pt=(36.0, 700.0, 540.0, 60.0),
        reading_order=0,
    )
    marks = ()
    if role in {"cover", "colophon"}:
        marks = (
            BrandMarkRef(
                mark_id="patchhive" if role == "cover" else "zero_state",
                page_role="cover" if role == "cover" else "colophon",
                bbox_pt=(36.0, 40.0, 100.0, 12.0),
                opacity=0.7,
            ),
        )
    return PatchPageLayoutIR(
        page_id=f"fm-{role}-{index}",
        page_index=index,
        page_kind=PageKind.FRONT_MATTER if role == "cover" else PageKind.BACK_MATTER,
        page_size="us_letter",
        regions=(region,),
        reading_order=("identity",),
        brand_marks=marks,
        layout_algorithm_id=family.layout_algorithm_id,
        fit={"role": role, "mode": recipe.mode.value, "family": family.family_id.value},
    )


def _plate_page(
    index: int, compilation, recipe: ResolvedStyleRecipe, family: FamilySpec
) -> PatchPageLayoutIR:
    """Non-executable visual plate for publication/artistic primary artifact."""
    regions = (
        LayoutRegion(
            region_id="identity",
            role="identity",
            required=True,
            bbox_pt=(48.0, 700.0, 500.0, 50.0),
            reading_order=0,
        ),
        LayoutRegion(
            region_id="plate",
            role="caption",
            required=True,
            bbox_pt=(48.0, 200.0, 500.0, 460.0),
            reading_order=1,
        ),
        LayoutRegion(
            region_id="footer",
            role="footer",
            required=True,
            bbox_pt=(48.0, 40.0, 500.0, 36.0),
            reading_order=2,
        ),
    )
    return PatchPageLayoutIR(
        page_id=f"plate-{compilation.patch_graph.artifact_id}",
        page_index=index,
        page_kind=PageKind.PLATE,
        patch_artifact_id=compilation.patch_graph.artifact_id,
        page_size="us_letter",
        regions=regions,
        reading_order=tuple(r.region_id for r in regions),
        diagram_literal=False,
        layout_algorithm_id=family.layout_algorithm_id,
        fit={
            "page_kind": "plate",
            "title": compilation.patch_plan.title,
            "rhythm": family.fingerprint.rhythm_signature,
        },
    )


def _with_every_semantic_region(regions: tuple[LayoutRegion, ...]) -> tuple[LayoutRegion, ...]:
    """Intent shares the identity band and operation shares the construction block, so each
    family's geometry keeps its overall shape (spec 002 FR-008)."""
    split: list[LayoutRegion] = []
    for region in regions:
        x, y, w, h = region.bbox_pt
        if region.role == "identity":
            parts = (("identity", (x, y + h / 2, w, h / 2)), ("intent", (x, y, w, h / 2)))
        elif region.role == "construction":
            parts = (("construction", (x, y + h / 2, w, h / 2)), ("operation", (x, y, w, h / 2)))
        else:
            parts = ((region.role, region.bbox_pt),)
        for role, bbox in parts:
            split.append(
                region.model_copy(
                    update={"region_id": role, "role": role, "bbox_pt": bbox, "reading_order": len(split)}
                )
            )
    return tuple(split)


def _execution_page(
    index: int, compilation, recipe: ResolvedStyleRecipe, family: FamilySpec, library: LoadedLibrary
) -> PatchPageLayoutIR:
    # Family-specific region geometry (structural uniqueness, not palette)
    if family.layout_algorithm_id == "notebook_checklist":
        regions = (
            LayoutRegion(
                region_id="identity",
                role="identity",
                required=True,
                bbox_pt=(36.0, 720.0, 540.0, 36.0),
                reading_order=0,
            ),
            LayoutRegion(
                region_id="construction",
                role="construction",
                required=True,
                bbox_pt=(36.0, 360.0, 540.0, 340.0),
                reading_order=1,
            ),
            LayoutRegion(
                region_id="diagram",
                role="diagram",
                required=True,
                bbox_pt=(36.0, 120.0, 540.0, 220.0),
                reading_order=2,
            ),
            LayoutRegion(
                region_id="footer",
                role="footer",
                required=True,
                bbox_pt=(36.0, 36.0, 540.0, 40.0),
                reading_order=3,
            ),
        )
    elif family.layout_algorithm_id == "title_block_engineering":
        regions = (
            LayoutRegion(
                region_id="identity",
                role="identity",
                required=True,
                bbox_pt=(36.0, 740.0, 400.0, 28.0),
                reading_order=0,
            ),
            LayoutRegion(
                region_id="diagram",
                role="diagram",
                required=True,
                bbox_pt=(36.0, 280.0, 540.0, 440.0),
                reading_order=1,
            ),
            LayoutRegion(
                region_id="construction",
                role="construction",
                required=True,
                bbox_pt=(36.0, 100.0, 540.0, 160.0),
                reading_order=2,
            ),
            LayoutRegion(
                region_id="footer",
                role="footer",
                required=True,
                bbox_pt=(36.0, 36.0, 540.0, 40.0),
                reading_order=3,
            ),
        )
    elif family.layout_algorithm_id == "open_asymmetric_sparse":
        regions = (
            LayoutRegion(
                region_id="identity",
                role="identity",
                required=True,
                bbox_pt=(72.0, 700.0, 400.0, 48.0),
                reading_order=0,
            ),
            LayoutRegion(
                region_id="diagram",
                role="diagram",
                required=True,
                bbox_pt=(72.0, 380.0, 400.0, 280.0),
                reading_order=1,
            ),
            LayoutRegion(
                region_id="construction",
                role="construction",
                required=True,
                bbox_pt=(72.0, 140.0, 400.0, 200.0),
                reading_order=2,
            ),
            LayoutRegion(
                region_id="footer",
                role="footer",
                required=True,
                bbox_pt=(72.0, 48.0, 400.0, 40.0),
                reading_order=3,
            ),
        )
    else:
        regions = (
            LayoutRegion(
                region_id="identity",
                role="identity",
                required=True,
                bbox_pt=(36.0, 720.0, 540.0, 40.0),
                reading_order=0,
            ),
            LayoutRegion(
                region_id="diagram",
                role="diagram",
                required=True,
                bbox_pt=(36.0, 400.0, 540.0, 280.0),
                reading_order=1,
            ),
            LayoutRegion(
                region_id="construction",
                role="construction",
                required=True,
                bbox_pt=(36.0, 120.0, 540.0, 260.0),
                reading_order=2,
            ),
            LayoutRegion(
                region_id="footer",
                role="footer",
                required=True,
                bbox_pt=(36.0, 36.0, 540.0, 40.0),
                reading_order=3,
            ),
        )
    regions = _with_every_semantic_region(regions)
    return PatchPageLayoutIR(
        page_id=f"exec-{compilation.patch_graph.artifact_id}",
        page_index=index,
        page_kind=PageKind.EXECUTION,
        patch_artifact_id=compilation.patch_graph.artifact_id,
        page_size="us_letter",
        regions=regions,
        reading_order=tuple(r.region_id for r in regions),
        diagram_literal=recipe.weights.diagram_literalness >= 50,
        layout_algorithm_id=family.layout_algorithm_id,
        fit={
            "edge_count": len(compilation.patch_graph.edges),
            # What the page prints beyond its sealed patch: part of the composition hash.
            "printed_hash": canonical_sha256(
                {
                    "modules": _page_modules(compilation, library),
                    "notes": page_notes(compilation, library),
                    "operation": operation_lines(compilation, library),
                }
            ),
            "layout_class": family.default_layout_class,
            "rhythm": family.fingerprint.rhythm_signature,
        },
    )


def _hex_rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (0.96, 0.65, 0.14)
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def _render_execution_pdf(
    library: LoadedLibrary,
    recipe: ResolvedStyleRecipe,
    family: FamilySpec,
    path: Path,
    *,
    export_id: str,
    composition_hash: str,
) -> int:
    """Draw the PDF and return the number of pages drawn (one ``showPage`` each)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    accent = _hex_rgb(family.accent_hex)
    body_font = (
        family.body_font
        if family.body_font
        in {
            "Helvetica",
            "Helvetica-Bold",
            "Times-Roman",
            "Courier",
        }
        else "Helvetica"
    )
    mono = family.mono_font if family.mono_font in {"Courier", "Helvetica"} else "Courier"
    # Body text, steps and cables never go below the profile's floor (spec 002 FR-004).
    body_size = body_size_pt(recipe)

    drawn = 0
    # Cover
    c.setFont("Helvetica-Bold", 22)
    c.drawString(inch, height - inch, "PatchHive PatchBook")
    c.setFont(body_font, 11)
    c.setFillColorRGB(*accent)
    subtitle_y = height - 1.35 * inch
    c.drawString(inch, subtitle_y, family.cover_subtitle)
    c.setFillColorRGB(0, 0, 0)
    y_meta = height - 1.7 * inch
    if family.patent_disclaimer:
        # The notice is drawn at the body floor (FR-004). The metadata block starts
        # below its last wrapped line, so a long notice cannot overlap it. Its first
        # baseline sits one leading plus the subtitle's descent under the subtitle,
        # so large body sizes clear the subtitle too.
        notice_leading = max(18.0, body_size * 1.5) if body_size >= 9 else body_size * 1.5
        y_meta = _draw_wrapped(
            c,
            [PATENT_FUTURE_DISCLAIMER],
            "Helvetica",
            body_size,
            subtitle_y - 11 * 0.25 - notice_leading,
            width - 2 * inch,
        )
    _draw_wrapped(
        c,
        [
            f"Export: {export_id}",
            f"Run: {library.source_run_id}",
            f"Composition: {composition_hash[:16]}…",
            f"Algorithm: {family.layout_algorithm_id}",
        ],
        body_font,
        body_size,
        y_meta,
        width - 2 * inch,
    )
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(inch, 0.75 * inch, "A Zero State Product")
    c.setFillColorRGB(0, 0, 0)
    c.showPage()
    drawn += 1

    recipe_h = recipe_hash(recipe)
    for item in library.items:
        plan = item.compilation.patch_plan
        graph = item.compilation.patch_graph
        # Lay the page out first: everything wraps, nothing is cut, and a page that
        # cannot hold its required content fails instead of dropping it (spec 002
        # FR-001, FR-003, FR-010, FR-021).
        labels = _module_labels(library)
        diagram = layout_diagram(item.compilation, module_labels=labels)
        page = layout_patch_page(
            plan,
            graph,
            family,
            body_font=body_font,
            mono=mono,
            width=width,
            height=height,
            body_size=body_size,
            cables=cable_lines(graph, labels),
            operation=operation_lines(item.compilation, library),
            notes=page_notes(item.compilation, library),
            diagram=diagram,
        )
        for line in page:
            if line.rule:
                c.setStrokeColorRGB(*accent)
                c.line(inch, line.y, width - inch, line.y)
                c.setStrokeColorRGB(0, 0, 0)
                continue
            if line.diagram:
                draw_diagram_on_canvas(
                    c,
                    diagram,
                    x=inch,
                    top=line.y + diagram.height,
                    layout_algorithm_id=family.layout_algorithm_id,
                )
                continue
            c.setFont(line.font, line.size)
            c.drawString(inch + line.indent, line.y, line.text)
        # Execution footer
        c.setFont("Helvetica", 7)
        c.drawString(
            inch,
            0.55 * inch,
            f"{graph.artifact_id} | execution | {composition_hash[:16]} | "
            f"recipe:{recipe_h[:8]} | eng:{DESIGN_ENGINE_VERSION}",
        )
        c.drawRightString(width - inch, 0.55 * inch, f"legibility={recipe.weights.legibility}")
        c.showPage()
        drawn += 1

    # Colophon
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, height - inch, "Colophon")
    y_after = _draw_wrapped(
        c,
        [
            "Designed and Engineered by Zero State",
            "PatchHive — a Zero State product",
            f"Template family: {family.display_name}",
            f"Mode: {recipe.mode.value}",
            f"Layout algorithm: {family.layout_algorithm_id}",
        ],
        body_font,
        body_size,
        height - 1.4 * inch,
        width - 2 * inch,
    )
    if family.patent_disclaimer:
        # The same floor as the cover's notice (FR-004).
        _draw_wrapped(
            c, [PATENT_FUTURE_DISCLAIMER], "Helvetica", body_size, y_after - 10, width - 2 * inch
        )
    c.showPage()
    drawn += 1

    c.setAuthor("PatchHive")
    c.setCreator(PDF_CREATOR_PATTERN)
    c.setTitle("PatchHive PatchBook")
    c.setSubject(f"PatchHive PatchBook eng={DESIGN_ENGINE_VERSION} {composition_hash[:16]}")
    c.save()
    path.write_bytes(normalize_pdf_metadata(buf.getvalue()))
    return drawn


# --- Page layout (spec 002 FR-001/003/010/021) -------------------------------------

# Lowest baseline for page content: the execution footer sits at 0.55 in.
CONTENT_FLOOR = inch + 12


@dataclass(frozen=True)
class PageLine:
    text: str
    font: str
    size: float
    y: float
    indent: float = 0.0
    rule: bool = False
    # The block's bottom edge is ``y``, so the page-fit check holds the whole block.
    diagram: bool = False


def _draw_wrapped(
    c: Any, lines: list[str], font: str, size: float, y: float, max_width: float
) -> float:
    """Draw front or back matter: each line wraps to the page width and the spacing
    grows with the font size, so a large body size never runs off the page or
    overlaps. Returns the baseline below the last line."""
    leading = max(18.0, size * 1.5) if size >= 9 else size * 1.5
    c.setFont(font, size)
    for line in lines:
        for chunk in _wrap_to_width(line, font, size, max_width):
            c.drawString(inch, y, chunk)
            y -= leading
    return y


def layout_patch_page(
    plan: Any,
    graph: Any,
    family: FamilySpec,
    *,
    body_font: str,
    mono: str,
    width: float,
    height: float,
    cables: list[str],
    operation: list[str],
    notes: list[str] | None = None,
    diagram: DiagramLayout | None = None,
    body_size: float = 9.5,
) -> list[PageLine]:
    """Every line of one patch page, fully wrapped. Optional decoration (the title
    block) goes first if the page is full; if required content still does not fit,
    the export fails with a code, never a truncated or dropped line."""
    for with_title_block in ((True, False) if family.show_title_block else (False,)):
        page = _lay_out(
            plan,
            family,
            body_font,
            mono,
            width,
            height,
            with_title_block,
            body_size,
            cables,
            operation,
            notes or [],
            diagram.height if diagram is not None else 0.0,
        )
        if all(line.y >= CONTENT_FLOOR for line in page):
            return page
    if diagram is not None and diagram.height >= (height - inch - CONTENT_FLOOR) / 2:
        raise PreflightFailed(
            "PATCH_PAGE_DIAGRAM_OVERFLOW",
            f"Patch {graph.artifact_id} has a diagram too tall to share a page with its required "
            f"content ({len(diagram.boxes)} modules, {len(cables)} cables). Remediation: split "
            "the patch into smaller patches.",
        )
    raise PreflightFailed(
        "PATCH_PAGE_TEXT_OVERFLOW",
        f"Patch {graph.artifact_id} needs more than one page for its required content "
        f"({len(operation)} steps, {len(cables)} cables). Remediation: split the "
        "patch into smaller patches, or choose a book profile with a denser layout.",
    )


def _lay_out(
    plan: Any,
    family: FamilySpec,
    body_font: str,
    mono: str,
    width: float,
    height: float,
    with_title_block: bool,
    body_size: float,
    cables: list[str],
    operation: list[str],
    notes: list[str],
    diagram_height: float,
) -> list[PageLine]:
    usable = width - 2 * inch
    leading = round(body_size * 1.3, 2)
    lines: list[PageLine] = []
    y = height - inch

    def add(text: str, font: str, size: float, step: float, indent: float = 0.0) -> None:
        nonlocal y
        for chunk in _wrap_to_width(text, font, size, usable - indent):
            lines.append(PageLine(chunk, font, size, y, indent))
            y -= step

    def add_diagram() -> None:
        nonlocal y
        if diagram_height:
            lines.append(PageLine("", body_font, 9, y - diagram_height, diagram=True))
            y -= diagram_height + 16

    add(plan.title, "Helvetica-Bold", 16, 18)
    add(f"Intent: {plan.intent}", body_font, body_size, leading)
    y -= 4
    lines.append(PageLine("", body_font, 9, y, rule=True))
    y -= 20
    if with_title_block:
        add(f"TITLE BLOCK · {family.display_name} · rev eng={DESIGN_ENGINE_VERSION}", "Helvetica", 7, 14)
    if family.default_layout_class != "instruction_first":
        add_diagram()
    add("Construction", "Helvetica-Bold", 11, 14)
    for cable in cables:
        # Cables are required content: body size, not a smaller caption size. One pass
        # over the original text; continuation lines indent (and are narrower) so one
        # cable never reads as two.
        for i, chunk in enumerate(_wrap_to_width(cable, mono, body_size, usable, usable - 12)):
            lines.append(PageLine(chunk, mono, body_size, y, indent=12 if i else 0))
            y -= leading
    y -= 8
    add("Checklist" if family.show_checklist else "Operation", "Helvetica-Bold", 11, 14)
    for number, step in enumerate(operation, start=1):
        prefix = "[ ] " if family.show_checklist else f"{number}. "
        add(f"{prefix}{step}", body_font, body_size, leading)
    if notes:
        y -= 8
        add("Warnings", "Helvetica-Bold", 11, 14)
        for note in notes:
            add(note, body_font, body_size, leading)
    if family.default_layout_class == "instruction_first":
        y -= 8
        add_diagram()
    return lines
