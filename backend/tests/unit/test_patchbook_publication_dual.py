"""Publication / artistic dual-artifact compose tests."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from export.patchbook.design.content_spine import LoadedLibrary, LoadedLibraryItem
from export.patchbook.design.engine import compose_design_export_pack
from export.patchbook.design.layout_ir import PageKind
from export.patchbook.design.recipe import (
    BookProfile,
    OutputProfile,
    PatchBookMode,
    ResolvedStyleRecipe,
    StyleConstraints,
    StyleWeights,
    TemplateFamilyId,
)
from export.patchbook.design.content_spine import seal_orm_patch_to_compilation
from patches.models import Patch


def _minimal_library() -> LoadedLibrary:
    patch = Patch(
        id=1,
        rack_id=1,
        run_id=1,
        name="Plate Patch",
        category="Voice",
        description="Artistic dual-artifact fixture",
        connections=[
            {
                "from_module_id": 1,
                "from_port": "Out",
                "to_module_id": 2,
                "to_port": "In",
                "cable_type": "audio",
            }
        ],
        generation_seed=9,
        generation_version="1.0.0",
    )
    compilation = seal_orm_patch_to_compilation(
        patch,
        source_run_id="gen-run-1-aaaaaaaaaaaaaaaa",
        source_rig_revision_id="rig-rev-" + "a" * 32,
        rig_snapshot={"modules": []},
        position=0,
    )
    item = LoadedLibraryItem(position=0, compilation=compilation, orm_patch_id=1)
    from export.patchbook.design.content_spine import library_content_hash

    return LoadedLibrary(
        source_run_id="gen-run-1-aaaaaaaaaaaaaaaa",
        source_rig_revision_id="rig-rev-" + "a" * 32,
        bridge_artifact_manifest_hash="b" * 64,
        library_content_hash=library_content_hash([item]),
        load_path="compile_on_export",
        items=(item,),
    )


def test_preflight_warnings_are_recorded_in_the_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A warning never blocks the pack, and never vanishes (spec 002 OQ-7, FR-019)."""
    import json

    from export.patchbook.design import engine
    from export.patchbook.design.preflight import PreflightIssue

    real = engine.run_preflight

    def with_warnings(*args, **kwargs):
        report = real(*args, **kwargs)
        if kwargs.get("pack_dir") is not None:
            return report
        extra = (
            PreflightIssue(code="INK_COVERAGE_HIGH", severity="warning", message="x"),
            PreflightIssue(code="BODY_SIZE_RAISED_TO_FLOOR", severity="warning", message="y"),
        )
        return dataclasses.replace(report, issues=report.issues + extra)

    recipe = ResolvedStyleRecipe(
        mode=PatchBookMode.PROFESSIONAL,
        template_family=TemplateFamilyId.SIGNAL_MANUAL,
        template_family_version="1.0.0",
        seed=1,
        weights=StyleWeights(legibility=95, diagram_literalness=96),
        constraints=StyleConstraints(book_profile=BookProfile.EXECUTION_PAGE),
        output_profile=OutputProfile.PRINT_PDF,
        resolved_tier="core",
        zero_state_brand_cap=6,
    )
    monkeypatch.setattr(engine, "run_preflight", with_warnings)
    compose_design_export_pack(
        _minimal_library(), recipe, out_dir=tmp_path / "pack", export_id="export-warn-1"
    )
    manifest = json.loads((tmp_path / "pack" / "manifest" / "patch-book.json").read_text())
    assert "INK_COVERAGE_HIGH" in manifest["warnings"]
    assert "BODY_SIZE_RAISED_TO_FLOOR" in manifest["warnings"]
    assert manifest["warnings"] == sorted(set(manifest["warnings"]))
    # The stage receipt keeps each warning with its message (T036).
    receipt = json.loads((tmp_path / "pack" / "validation" / "book.json").read_text())
    assert receipt["stage"] == "validate_book" and receipt["status"] == "pass"
    assert {"code": "INK_COVERAGE_HIGH", "severity": "warning", "message": "x"} in receipt["warnings"]
    assert {
        "code": "BODY_SIZE_RAISED_TO_FLOOR",
        "severity": "warning",
        "message": "y",
    } in receipt["warnings"]
    assert {w["code"] for w in receipt["warnings"]} == set(manifest["warnings"])


def test_plate_family_publication_fails_page_count_until_plates_are_drawn(
    tmp_path: Path,
) -> None:
    """Plate mode lays out 2N+2 pages but draws N+2, so validate_book refuses it
    (spec 002 FR-016, research R1, T031). The pages written before validation and the
    failed receipt stay in the pack."""
    import json

    from export.patchbook.design.engine import BookValidationFailed

    recipe = ResolvedStyleRecipe(
        mode=PatchBookMode.GALLERY,
        template_family=TemplateFamilyId.IMPOSSIBLE_INSTRUMENT,
        template_family_version="1.0.0",
        seed=1,
        weights=StyleWeights(legibility=15, diagram_literalness=10),
        constraints=StyleConstraints(
            book_profile=BookProfile.PUBLICATION,
            canonical_appendix_required=True,
            artistic_disclosure_acknowledged=True,
        ),
        output_profile=OutputProfile.PRINT_PDF,
        resolved_tier="studio",
        zero_state_brand_cap=6,
    )
    library = _minimal_library()
    pack = tmp_path / "pack"
    with pytest.raises(BookValidationFailed) as exc:
        compose_design_export_pack(library, recipe, out_dir=pack, export_id="export-art-1")
    assert exc.value.code == "PATCH_BOOK_PAGE_COUNT_MISMATCH"

    n = len(library.items)
    receipt = json.loads((pack / "validation" / "book.json").read_text())
    assert receipt["status"] == "fail"
    assert receipt["error_code"] == "PATCH_BOOK_PAGE_COUNT_MISMATCH"
    assert receipt["remediation"]
    assert receipt["manifest_page_count"] == 2 * n + 2
    assert receipt["pdf_page_count"] == n + 2
    kinds = [page["kind"] for page in receipt["pages"]]
    assert PageKind.PLATE.value in kinds
    assert PageKind.APPENDIX_EXECUTION.value in kinds
    # A failed book never gets a manifest or checksums.
    assert not (pack / "manifest" / "patch-book.json").exists()
    assert not (pack / "manifest" / "checksums.json").exists()
    assert (pack / "PatchBook.pdf").exists()
    assert (pack / "technical" / "PatchBook-execution.pdf").exists()
    assert any((pack / "pages" / "json").glob("*-plate.json"))
    assert any((pack / "pages" / "json").glob("*-appendix.json"))
