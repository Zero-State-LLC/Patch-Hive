"""validate_book stage of compose_design_export_pack (spec 002 FR-006, FR-016, FR-017, T030)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from export.patchbook.design import engine
from export.patchbook.design.engine import (
    BookValidationFailed,
    compose_design_export_pack,
    validate_book,
)
from export.patchbook.design.recipe import (
    BookProfile,
    OutputProfile,
    PatchBookMode,
    ResolvedStyleRecipe,
    StyleConstraints,
    StyleWeights,
    TemplateFamilyId,
    recipe_hash,
)
from tests.unit.test_patchbook_publication_dual import _minimal_library


def _recipe() -> ResolvedStyleRecipe:
    return ResolvedStyleRecipe(
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_valid_book_has_one_manifest_entry_per_page_and_a_hash_per_file(
    tmp_path: Path,
) -> None:
    library = _minimal_library()
    pack = tmp_path / "pack"
    result = compose_design_export_pack(library, _recipe(), out_dir=pack, export_id="exp-vb-1")

    manifest = json.loads((pack / "manifest" / "patch-book.json").read_text())
    assert manifest["validation_status"] == "pass"
    assert manifest["page_count"] == result.page_count == len(manifest["pages"])
    assert [p["index"] for p in manifest["pages"]] == list(range(result.page_count))
    assert [p["kind"] for p in manifest["pages"]] == ["front_matter", "execution", "back_matter"]
    artifact_id = library.items[0].compilation.patch_graph.artifact_id
    patch_page = manifest["pages"][1]
    assert patch_page["patch_artifact_id"] == artifact_id
    assert patch_page["svg_hash"] == _sha(pack / "diagrams" / "svg" / f"{artifact_id}.svg")
    assert patch_page["page_hash"] and patch_page["status"] == "pass"
    assert manifest["pages"][0]["patch_artifact_id"] is None
    assert manifest["pages"][0]["svg_hash"] is None

    checksums = json.loads((pack / "manifest" / "checksums.json").read_text())
    assert checksums["composition_hash"] == result.composition_hash
    assert checksums["pack_manifest_hash"] == result.pack_manifest_hash
    files = sorted(
        p.relative_to(pack).as_posix()
        for p in pack.rglob("*")
        if p.is_file() and p.name != "checksums.json"
    )
    assert sorted(checksums["files"]) == files
    for rel, digest in checksums["files"].items():
        assert _sha(pack / rel) == digest, rel

    receipt = json.loads((pack / "validation" / "book.json").read_text())
    assert receipt["status"] == "pass" and receipt["error_code"] is None
    assert receipt["pdf_page_count"] == receipt["manifest_page_count"] == 3
    assert receipt["patch_count"] == receipt["patch_page_count"] == 1
    assert receipt["replay_composition_hash"] == result.composition_hash
    assert receipt["pages"] == manifest["pages"]


def test_the_receipt_is_deterministic(tmp_path: Path) -> None:
    library = _minimal_library()
    for name in ("a", "b"):
        compose_design_export_pack(library, _recipe(), out_dir=tmp_path / name, export_id="exp-d")
    a = (tmp_path / "a" / "validation" / "book.json").read_bytes()
    b = (tmp_path / "b" / "validation" / "book.json").read_bytes()
    assert a == b


def test_fewer_pages_drawn_than_listed_fails_page_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = engine._render_execution_pdf

    def drops_a_page(*args, **kwargs):
        return real(*args, **kwargs) - 1

    monkeypatch.setattr(engine, "_render_execution_pdf", drops_a_page)
    pack = tmp_path / "pack"
    with pytest.raises(BookValidationFailed) as exc:
        compose_design_export_pack(_minimal_library(), _recipe(), out_dir=pack, export_id="e")
    assert exc.value.code == "PATCH_BOOK_PAGE_COUNT_MISMATCH"
    receipt = json.loads((pack / "validation" / "book.json").read_text())
    assert receipt["status"] == "fail" and receipt["remediation"]


def _composed(tmp_path: Path):
    """Compose a valid pack, then return what validate_book needs to re-run on it."""
    library = _minimal_library()
    recipe = _recipe()
    pack = tmp_path / "pack"
    result = compose_design_export_pack(library, recipe, out_dir=pack, export_id="exp-t")
    manifest = json.loads((pack / "manifest" / "patch-book.json").read_text())
    svg_hashes = {
        p["patch_artifact_id"]: p["svg_hash"] for p in manifest["pages"] if p["svg_hash"]
    }
    kwargs = dict(
        pages_drawn=result.page_count,
        svg_hashes=svg_hashes,
        paths=manifest["paths"],
        expected_composition_hash=result.composition_hash,
        resolved_recipe_hash=recipe_hash(recipe),
    )
    return pack, list(result.layout_irs), library, kwargs


def test_validate_book_passes_on_an_untouched_pack(tmp_path: Path) -> None:
    pack, irs, library, kwargs = _composed(tmp_path)
    assert validate_book(pack, irs, library, **kwargs).error_code is None


def test_a_changed_diagram_fails_asset_hash(tmp_path: Path) -> None:
    pack, irs, library, kwargs = _composed(tmp_path)
    svg = next((pack / "diagrams" / "svg").glob("*.svg"))
    svg.write_text(svg.read_text() + "<!-- edited -->", encoding="utf-8")
    report = validate_book(pack, irs, library, **kwargs)
    assert report.error_code == "PATCH_BOOK_ASSET_HASH_MISMATCH"
    assert [p["status"] for p in report.pages] == ["pass", "fail", "pass"]


def test_a_changed_layout_ir_fails_replay(tmp_path: Path) -> None:
    pack, irs, library, kwargs = _composed(tmp_path)
    ir_path = sorted((pack / "pages" / "layout_ir").glob("*.json"))[1]
    data = json.loads(ir_path.read_text())
    data["layout_algorithm_id"] = "tampered"
    ir_path.write_text(json.dumps(data), encoding="utf-8")
    report = validate_book(pack, irs, library, **kwargs)
    assert report.error_code == "PATCH_BOOK_ASSET_HASH_MISMATCH"
    assert report.replay_composition_hash != kwargs["expected_composition_hash"]


def test_a_missing_diagram_or_bundle_file_fails_reference(tmp_path: Path) -> None:
    pack, irs, library, kwargs = _composed(tmp_path)
    next((pack / "diagrams" / "svg").glob("*.svg")).unlink()
    assert validate_book(pack, irs, library, **kwargs).error_code == (
        "PATCH_BOOK_REFERENCE_UNRESOLVED"
    )

    pack, irs, library, kwargs = _composed(tmp_path / "again")
    (pack / "technical" / "companion.txt").unlink()
    assert validate_book(pack, irs, library, **kwargs).error_code == (
        "PATCH_BOOK_REFERENCE_UNRESOLVED"
    )


def test_a_page_for_an_unknown_patch_fails_reference(tmp_path: Path) -> None:
    pack, irs, library, kwargs = _composed(tmp_path)
    irs[1] = irs[1].model_copy(update={"patch_artifact_id": "not-in-library"})
    report = validate_book(pack, irs, library, **kwargs)
    assert report.error_code == "PATCH_BOOK_REFERENCE_UNRESOLVED"
