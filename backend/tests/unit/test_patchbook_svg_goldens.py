"""Deterministic SVG diagrams + composition_hash goldens across families."""

from __future__ import annotations

from pathlib import Path

from export.patchbook.design.content_spine import (
    LoadedLibrary,
    LoadedLibraryItem,
    ModuleDisplay,
    library_content_hash,
    seal_orm_patch_to_compilation,
)
from export.patchbook.design.diagram_svg import render_patch_diagram_svg
from export.patchbook.design.engine import compose_design_export_pack
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
from patches.models import Patch


def _fixture_library() -> LoadedLibrary:
    patch = Patch(
        id=42,
        rack_id=7,
        run_id=3,
        name="Golden Voice",
        category="Voice",
        description="Fixture for composition goldens",
        connections=[
            {
                "from_module_id": 10,
                "from_port": "Audio Out",
                "to_module_id": 20,
                "to_port": "Audio In",
                "cable_type": "audio",
            },
            {
                "from_module_id": 30,
                "from_port": "CV Out",
                "to_module_id": 10,
                "to_port": "1V/Oct",
                "cable_type": "cv",
            },
            {
                "from_module_id": 40,
                "from_port": "Gate",
                "to_module_id": 20,
                "to_port": "Gate In",
                "cable_type": "gate",
            },
        ],
        generation_seed=384290,
        generation_version="1.0.0",
    )
    compilation = seal_orm_patch_to_compilation(
        patch,
        source_run_id="gen-run-3-deadbeefdeadbeef",
        source_rig_revision_id="rig-rev-" + "c" * 32,
        rig_snapshot={"modules": []},
        position=0,
    )
    item = LoadedLibraryItem(position=0, compilation=compilation, orm_patch_id=42)
    return LoadedLibrary(
        source_run_id="gen-run-3-deadbeefdeadbeef",
        source_rig_revision_id="rig-rev-" + "c" * 32,
        bridge_artifact_manifest_hash="d" * 64,
        library_content_hash=library_content_hash([item]),
        load_path="compile_on_export",
        items=(item,),
        module_display={
            "10": ModuleDisplay("Fixture Oscillator"),
            "20": ModuleDisplay("Fixture Amplifier"),
            "30": ModuleDisplay("Fixture Sequencer"),
            "40": ModuleDisplay("Fixture Clock"),
        },
    )


def _recipe(family: TemplateFamilyId, *, seed: int = 384290) -> ResolvedStyleRecipe:
    return ResolvedStyleRecipe(
        mode=PatchBookMode.PROFESSIONAL,
        template_family=family,
        template_family_version="1.0.0",
        seed=seed,
        weights=StyleWeights(legibility=95, diagram_literalness=96),
        influences={"engineering": 90, "swiss": 70, "cyber_hive": 30},
        constraints=StyleConstraints(book_profile=BookProfile.EXECUTION_PAGE),
        output_profile=OutputProfile.PRINT_PDF,
        resolved_tier="core",
        zero_state_brand_cap=6,
    )


def test_svg_deterministic_and_non_color_encoded() -> None:
    lib = _fixture_library()
    comp = lib.items[0].compilation
    a = render_patch_diagram_svg(comp, layout_algorithm_id="orthogonal_schematic")
    b = render_patch_diagram_svg(comp, layout_algorithm_id="orthogonal_schematic")
    assert a == b
    assert a.startswith("<svg")
    assert "stroke-dasharray" in a
    assert 'data-signal="audio"' in a
    assert 'data-signal="cv"' in a
    assert "non-color: dash+number+label" in a
    # Route numbers present
    assert ">1 Audio In</text>" in a and 'data-route="1"' in a


def test_composition_hash_stable_same_inputs(tmp_path: Path) -> None:
    lib = _fixture_library()
    recipe = _recipe(TemplateFamilyId.SIGNAL_MANUAL)
    r1 = compose_design_export_pack(lib, recipe, out_dir=tmp_path / "a", export_id="exp-a")
    r2 = compose_design_export_pack(lib, recipe, out_dir=tmp_path / "b", export_id="exp-b")
    assert r1.composition_hash == r2.composition_hash
    assert recipe_hash(recipe) == recipe_hash(_recipe(TemplateFamilyId.SIGNAL_MANUAL))
    svg_a = (tmp_path / "a" / "diagrams" / "svg").glob("*.svg")
    assert list(svg_a)
    layout_files = list((tmp_path / "a" / "pages" / "layout_ir").glob("*.json"))
    assert layout_files


def test_composition_hash_differs_by_family(tmp_path: Path) -> None:
    lib = _fixture_library()
    h_manual = compose_design_export_pack(
        lib,
        _recipe(TemplateFamilyId.SIGNAL_MANUAL),
        out_dir=tmp_path / "manual",
        export_id="e1",
    ).composition_hash
    h_field = compose_design_export_pack(
        lib,
        _recipe(TemplateFamilyId.MODULAR_FIELD_NOTES),
        out_dir=tmp_path / "field",
        export_id="e2",
    ).composition_hash
    h_circuit = compose_design_export_pack(
        lib,
        _recipe(TemplateFamilyId.CIRCUIT_ARCHIVE),
        out_dir=tmp_path / "circuit",
        export_id="e3",
    ).composition_hash
    assert h_manual != h_field != h_circuit
    assert h_manual != h_circuit


def test_composition_hash_differs_by_seed(tmp_path: Path) -> None:
    lib = _fixture_library()
    # Seed is in recipe hash which feeds composition_hash
    h1 = compose_design_export_pack(
        lib,
        _recipe(TemplateFamilyId.SIGNAL_MANUAL, seed=1),
        out_dir=tmp_path / "s1",
        export_id="e1",
    ).composition_hash
    h2 = compose_design_export_pack(
        lib,
        _recipe(TemplateFamilyId.SIGNAL_MANUAL, seed=2),
        out_dir=tmp_path / "s2",
        export_id="e2",
    ).composition_hash
    assert h1 != h2
