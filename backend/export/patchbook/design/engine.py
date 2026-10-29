"""Minimal Design Engine orchestrator: compose pack from sealed compilations + recipe."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from canon.contracts import canonical_json, canonical_sha256
from export.patchbook.design.brand_policy import (
    PDF_CREATOR_PATTERN,
    scan_forbidden_strings,
)
from export.patchbook.design.content_spine import LoadedLibrary
from export.patchbook.design.a11y import body_size_pt
from export.patchbook.design.diagram_svg import render_patch_diagram_svg
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


def compose_design_export_pack(
    library: LoadedLibrary,
    recipe: ResolvedStyleRecipe,
    *,
    out_dir: str | Path,
    export_id: str,
) -> ComposeResult:
    """Write design_export_pack.v1 directory; presentation only."""
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
    for item in library.items:
        # Deterministic technical SVG per patch (color + dash + number)
        svg = render_patch_diagram_svg(
            item.compilation, layout_algorithm_id=family.layout_algorithm_id
        )
        svg_rel = f"diagrams/svg/{item.compilation.patch_graph.artifact_id}.svg"
        (root / svg_rel).write_text(svg, encoding="utf-8")
        diagram_paths.append(svg_rel)

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
            app_ir = _execution_page(page_index, item.compilation, recipe, family)
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
            ir = _execution_page(page_index, item.compilation, recipe, family)
            layout_irs.append(ir)
            page_payload = {
                "page_index": page_index,
                "page_kind": "execution",
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
    # Warnings do not block the pack, but they are never dropped (spec 002 OQ-7, FR-019).
    preflight_warnings = sorted({i.code for i in gate.issues if i.severity == "warning"})

    comp_hash = composition_hash(
        library_content_hash=library.library_content_hash,
        bridge_artifact_manifest_hash=library.bridge_artifact_manifest_hash,
        resolved_recipe_hash=resolved_hash,
        layout_irs=layout_irs,
        design_engine_version=DESIGN_ENGINE_VERSION,
    )

    pdf_path = root / "PatchBook.pdf"
    _render_execution_pdf(
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
        for step in item.compilation.patch_plan.steps:
            companion_lines.append(f"  [{step.phase}] {step.instruction}")
        for edge in item.compilation.patch_graph.edges:
            companion_lines.append(
                f"  CABLE {edge.edge_id}: {edge.source_port_id} -> {edge.target_port_id} ({edge.signal_type})"
            )
        companion_lines.append("")
    (root / "technical" / "companion.txt").write_text("\n".join(companion_lines), encoding="utf-8")

    if recipe.constraints.canonical_appendix_required:
        # Dual-artifact: copy execution pdf as technical appendix
        appendix = root / "technical" / "PatchBook-execution.pdf"
        appendix.write_bytes(pdf_path.read_bytes())

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
        "resolved_tier": recipe.resolved_tier,
        "warnings": preflight_warnings,
        "paths": {
            "pdf": "PatchBook.pdf",
            "companion": "technical/companion.txt",
            "library_index": "source/library_index.json",
            "resolved_recipe": "style/resolved_recipe.json",
            "family": "style/family.json",
            "diagrams": diagram_paths,
            "layout_ir_dir": "pages/layout_ir",
        },
    }
    body_hash = canonical_sha256({k: v for k, v in manifest.items() if k != "pack_manifest_hash"})
    manifest["pack_manifest_hash"] = body_hash
    (root / "manifest" / "patch-book.json").write_text(canonical_json(manifest), encoding="utf-8")
    (root / "manifest" / "checksums.json").write_text(
        canonical_json({"composition_hash": comp_hash, "pack_manifest_hash": body_hash}),
        encoding="utf-8",
    )
    license_lines = ["PatchHive export. Designed and Engineered by Zero State.\n"]
    if family.patent_disclaimer:
        license_lines.append(PATENT_FUTURE_DISCLAIMER + "\n")
    (root / "LICENSE.txt").write_text("".join(license_lines), encoding="utf-8")

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


def _execution_page(
    index: int, compilation, recipe: ResolvedStyleRecipe, family: FamilySpec
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
) -> None:
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

    # Cover
    c.setFont("Helvetica-Bold", 22)
    c.drawString(inch, height - inch, "PatchHive PatchBook")
    c.setFont(body_font, 11)
    c.setFillColorRGB(*accent)
    c.drawString(inch, height - 1.35 * inch, family.cover_subtitle)
    c.setFillColorRGB(0, 0, 0)
    y_meta = height - 1.7 * inch
    if family.patent_disclaimer:
        # The notice is drawn at the body floor (FR-004). The metadata block starts
        # below its last wrapped line, so a long notice cannot overlap it.
        y_meta = _draw_wrapped(
            c,
            [PATENT_FUTURE_DISCLAIMER],
            "Helvetica",
            body_size,
            height - 1.55 * inch,
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

    recipe_h = recipe_hash(recipe)
    for item in library.items:
        plan = item.compilation.patch_plan
        graph = item.compilation.patch_graph
        # Lay the page out first: everything wraps, nothing is cut, and a page that
        # cannot hold its required content fails instead of dropping it (spec 002
        # FR-001, FR-003, FR-010, FR-021).
        page = layout_patch_page(
            plan,
            graph,
            family,
            body_font=body_font,
            mono=mono,
            width=width,
            height=height,
            body_size=body_size,
        )
        for line in page:
            if line.rule:
                c.setStrokeColorRGB(*accent)
                c.line(inch, line.y, width - inch, line.y)
                c.setStrokeColorRGB(0, 0, 0)
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
        _draw_wrapped(c, [PATENT_FUTURE_DISCLAIMER], "Helvetica", 8, y_after - 10, width - 2 * inch)
    c.showPage()

    c.setAuthor("PatchHive")
    c.setCreator(PDF_CREATOR_PATTERN)
    c.setTitle("PatchHive PatchBook")
    c.setSubject(f"PatchHive PatchBook eng={DESIGN_ENGINE_VERSION} {composition_hash[:16]}")
    c.save()
    path.write_bytes(normalize_pdf_metadata(buf.getvalue()))


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


def _wrap_to_width(
    text: str, font: str, size: float, max_width: float, rest_width: float | None = None
) -> list[str]:
    """Wrap by measured width; continuation lines may be narrower (``rest_width``). A
    single word wider than its line is split across lines, never cut and never given
    extra spaces."""
    lines: list[str] = []
    cur = ""

    def limit() -> float:
        return max_width if not lines or rest_width is None else rest_width

    for word in text.split():
        trial = f"{cur} {word}" if cur else word
        if stringWidth(trial, font, size) <= limit():
            cur = trial
            continue
        if cur:
            lines.append(cur)
            cur = ""
        while stringWidth(word, font, size) > limit():
            cut = len(word)
            while cut > 1 and stringWidth(word[:cut], font, size) > limit():
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


def layout_patch_page(
    plan: Any,
    graph: Any,
    family: FamilySpec,
    *,
    body_font: str,
    mono: str,
    width: float,
    height: float,
    body_size: float = 9.5,
) -> list[PageLine]:
    """Every line of one patch page, fully wrapped. Optional decoration (the title
    block) goes first if the page is full; if required content still does not fit,
    PATCH_PAGE_TEXT_OVERFLOW, never a truncated or dropped line."""
    for with_title_block in ((True, False) if family.show_title_block else (False,)):
        page = _lay_out(
            plan, graph, family, body_font, mono, width, height, with_title_block, body_size
        )
        if all(line.y >= CONTENT_FLOOR for line in page):
            return page
    raise PreflightFailed(
        "PATCH_PAGE_TEXT_OVERFLOW",
        f"Patch {graph.artifact_id} needs more than one page for its required content "
        f"({len(plan.steps)} steps, {len(graph.edges)} cables). Remediation: split the "
        "patch into smaller patches, or choose a book profile with a denser layout.",
    )


def _lay_out(
    plan: Any,
    graph: Any,
    family: FamilySpec,
    body_font: str,
    mono: str,
    width: float,
    height: float,
    with_title_block: bool,
    body_size: float,
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

    add(plan.title, "Helvetica-Bold", 16, 18)
    add(f"Intent: {plan.intent}", body_font, body_size, leading)
    y -= 4
    lines.append(PageLine("", body_font, 9, y, rule=True))
    y -= 20
    if with_title_block:
        add(f"TITLE BLOCK · {family.display_name} · rev eng={DESIGN_ENGINE_VERSION}", "Helvetica", 7, 14)
    add("Checklist" if family.show_checklist else "Construction", "Helvetica-Bold", 11, 14)
    for step in plan.steps:
        prefix = "[ ] " if family.show_checklist else f"{step.position}. "
        add(f"{prefix}[{step.phase}] {step.instruction}", body_font, body_size, leading)
    y -= 8
    add("Cables", "Helvetica-Bold", 11, 14)
    for edge in graph.edges:
        text = f"{edge.edge_id}: {edge.source_port_id} -> {edge.target_port_id} [{edge.signal_type}]"
        # Cables are required content: body size, not a smaller caption size. One pass
        # over the original text; continuation lines indent (and are narrower) so one
        # cable never reads as two.
        for i, chunk in enumerate(_wrap_to_width(text, mono, body_size, usable, usable - 12)):
            lines.append(PageLine(chunk, mono, body_size, y, indent=12 if i else 0))
            y -= leading
    return lines
