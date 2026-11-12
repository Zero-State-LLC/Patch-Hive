"""Spec 002 T090: composing a book, as built (owner decision 37).

The page and book compile machines aren't built. A book is composed in one pass, and any stage
that stops it fails the whole export and returns the customer's credits. This file holds the
stages table in spec.md, "Composing a book", and what a page has to show (FR-008, FR-011,
FR-013, FR-014, FR-018).
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from canon.compiler import compile_patch, standard_plan_steps
from canon.contracts import ExportRequest, PatchEdge, PatchNode, PatchPort
from canon.exports import credit_balance, request_export
from canon.fulfillment import fulfill_export
from canon.models import StageReceiptRecord
from export.patchbook.design import engine
from export.patchbook.design.content_spine import (
    LoadedLibrary,
    LoadedLibraryItem,
    ModuleDisplay,
    compile_orm_patch,
    library_content_hash,
    orm_patch_nodes_and_edges,
    seal_orm_patch_to_compilation,
)
from export.patchbook.design.diagram_svg import layout_diagram, numbered_edges, render_patch_diagram_svg
from export.patchbook.design.engine import (
    PreflightFailed,
    cable_lines,
    check_semantics,
    compose_design_export_pack,
    operation_lines,
    page_notes,
)
from export.patchbook.design.recipe import (
    BookProfile,
    OutputProfile,
    PatchBookMode,
    ResolvedStyleRecipe,
    StyleConstraints,
    StyleWeights,
    TemplateFamilyId,
)
from patches.models import Patch
from tests.unit.test_patchbook_design_fulfillment import NOW, _seed_user_run_patches

SPEC = Path(__file__).resolve().parents[3] / "specs" / "002-patch-book-publishing" / "spec.md"

# Spec "Composing a book": each stage, in order, and the codes that stop an export there.
STAGES = {
    "load": {"EXPORT_NO_PATCHES", "EXPORT_BRIDGE_HASH_MISMATCH"},
    "check": {
        "PATCH_PAGE_REQUIRED_CONTENT_MISSING",
        "PATCH_BOOK_REFERENCE_UNRESOLVED",
        "PATCH_PAGE_GRAPH_MISMATCH",
    },
    "preflight": {
        "PATCH_PAGE_REQUIRED_CONTENT_MISSING",
        "PATCH_PAGE_NON_COLOR_ENCODING_FAILED",
        "PATCH_PAGE_FONT_BELOW_MINIMUM",
        "CONTRAST_BELOW_AA",
    },
    "draw": {"PATCH_PAGE_TEXT_OVERFLOW", "PATCH_PAGE_DIAGRAM_OVERFLOW"},
    "validate_book": {
        "PATCH_BOOK_PAGE_COUNT_MISMATCH",
        "PATCH_BOOK_REFERENCE_UNRESOLVED",
        "PATCH_BOOK_ASSET_HASH_MISMATCH",
    },
    "emit": {"PATCH_BOOK_ASSET_HASH_MISMATCH", "PACK_FILE_MISSING"},
}
DISPLAY = {
    "1": ModuleDisplay("Mutable Instruments Plaits"),
    "2": ModuleDisplay("Intellijel Polaris", frozenset({"Audio In", "CV In"})),
    "3": ModuleDisplay("Make Noise Maths"),
}
CONNECTIONS = [
    {"from_module_id": 1, "from_port": "Audio Out", "to_module_id": 2, "to_port": "Audio In", "cable_type": "audio"},
    {"from_module_id": 3, "from_port": "Envelope Out", "to_module_id": 2, "to_port": "CV In", "cable_type": "cv"},
]
LOOP = [
    {"from_module_id": 1, "from_port": "Audio Out", "to_module_id": 2, "to_port": "Audio In", "cable_type": "audio"},
    {"from_module_id": 2, "from_port": "Audio Out", "to_module_id": 1, "to_port": "FM In", "cable_type": "audio"},
]


def _patch(connections=None, **fields) -> Patch:
    values = dict(
        id=5, rack_id=1, run_id=1, name="Basalt", category="Voice", description="A voice",
        connections=CONNECTIONS if connections is None else connections,
        generation_seed=7, generation_version="1.1.0",
    )
    values.update(fields)
    return Patch(**values)


def _library(patch: Patch | None = None, display: dict | None = None, *, sealed: bool = True) -> LoadedLibrary:
    patch = patch or _patch()
    run, revision = "gen-run-1-aaaaaaaaaaaaaaaa", "rig-rev-" + "a" * 32
    if sealed:
        compilation = compile_orm_patch(patch, source_run_id=run, source_rig_revision_id=revision)
    else:
        compilation = seal_orm_patch_to_compilation(
            patch, source_run_id=run, source_rig_revision_id=revision, rig_snapshot={"modules": []}
        )
    item = LoadedLibraryItem(position=0, compilation=compilation, orm_patch_id=patch.id)
    return LoadedLibrary(
        source_run_id=run, source_rig_revision_id=revision, bridge_artifact_manifest_hash="b" * 64,
        library_content_hash=library_content_hash([item]), load_path="generated_patches",
        items=(item,), module_display=DISPLAY if display is None else display,
    )


def _recipe(family: TemplateFamilyId = TemplateFamilyId.SIGNAL_MANUAL) -> ResolvedStyleRecipe:
    return ResolvedStyleRecipe(
        mode=PatchBookMode.PROFESSIONAL, template_family=family, template_family_version="1.0.0",
        seed=1, weights=StyleWeights(legibility=95, diagram_literalness=96),
        constraints=StyleConstraints(book_profile=BookProfile.EXECUTION_PAGE),
        output_profile=OutputProfile.PRINT_PDF, resolved_tier="core", zero_state_brand_cap=6,
    )


def _spec_stages() -> dict[str, set[str]]:
    section = SPEC.read_text(encoding="utf-8").split("### Composing a book")[1].split("\n### ")[0]
    rows = re.findall(r"^\| `([a-z_]+)` \| .*? \| (.*?) \|$", section, re.M)
    return {stage: set(re.findall(r"`([A-Z_]+)`", codes)) for stage, codes in rows}


def test_this_file_encodes_the_stages_in_the_spec():
    assert _spec_stages() == STAGES


# --- check: a missing fact is an error, never a placeholder (FR-013, FR-014, D7)


@pytest.mark.parametrize(
    "patch",
    [
        _patch([{"from_module_id": 1, "to_module_id": 2, "cable_type": "audio"}]),  # no jack names
        _patch(description=None),  # no intent
        _patch(name=None),  # no title
        _patch([]),  # no cables
        _patch([{**CONNECTIONS[0], "cable_type": "wobble"}]),  # no signal type
    ],
    ids=["jacks", "intent", "title", "cables", "signal"],
)
def test_a_missing_fact_stops_the_book(patch):
    with pytest.raises(PreflightFailed) as exc:
        check_semantics(_library(patch, sealed=False))
    assert exc.value.code in {"PATCH_PAGE_REQUIRED_CONTENT_MISSING", "PATCH_BOOK_REFERENCE_UNRESOLVED"}
    assert "Remediation" in exc.value.message


def test_a_module_not_on_the_source_rig_stops_the_book():
    display = {key: value for key, value in DISPLAY.items() if key != "3"}
    with pytest.raises(PreflightFailed) as exc:
        check_semantics(_library(display=display))
    assert exc.value.code == "PATCH_BOOK_REFERENCE_UNRESOLVED"
    assert "module 3" in exc.value.message


def test_a_failing_validation_report_stops_the_book():
    library = _library()
    compilation = library.items[0].compilation
    failed = compilation.validation_report.model_copy(update={"valid": False})
    item = replace(library.items[0], compilation=compilation.model_copy(update={"validation_report": failed}))
    with pytest.raises(PreflightFailed) as exc:
        check_semantics(replace(library, items=(item,)))
    assert exc.value.code == "PATCH_PAGE_GRAPH_MISMATCH"


# --- a patch that doesn't fit fails the whole export, and the credits come back (decision 37)


def _request(db: Session, user, bridge, key: str):
    export = request_export(
        db,
        ExportRequest(
            request_id=f"req-{key}", user_id=user.id, source_run_id=bridge.source_run_id,
            source_rig_revision_id=bridge.rig_revision_id, formats=("pdf", "json"),
            license="personal", credit_cost=3, idempotency_key=key, requested_at=NOW,
        ),
        artifact_manifest_hash=bridge.artifact_manifest_hash,
        export_version="1.0.0",
    )
    db.commit()
    return export


@pytest.fixture
def fulfilling(monkeypatch, tmp_path):
    import core.config as config_mod

    monkeypatch.setattr(config_mod.settings, "export_store_root", str(tmp_path))
    monkeypatch.setattr(config_mod.settings, "export_dir", str(tmp_path))
    monkeypatch.setattr(config_mod.settings, "enable_canon_export_fulfillment", True)


def test_one_patch_that_does_not_fit_fails_the_whole_export_and_returns_the_credits(
    db_session: Session, fulfilling
):
    user, run, bridge = _seed_user_run_patches(db_session)
    too_long = db_session.query(Patch).filter(Patch.run_id == run.id).order_by(Patch.id).first()
    too_long.description = "This patch explains itself at far too great a length. " * 200
    db_session.commit()
    export = _request(db_session, user, bridge, "doesnt-fit")
    assert credit_balance(db_session, user.id) == 7

    result = fulfill_export(db_session, export.id)
    db_session.commit()

    assert result.status == "refunded"
    assert result.error_code == "PATCH_PAGE_TEXT_OVERFLOW"
    assert credit_balance(db_session, user.id) == 10


def test_a_failed_compose_keeps_which_patch_stopped_it_and_what_to_do(db_session: Session, fulfilling):
    user, run, bridge = _seed_user_run_patches(db_session)
    patch = db_session.query(Patch).filter(Patch.run_id == run.id).order_by(Patch.id).first()
    patch.connections = [{"to_module_id": patch.connections[0]["to_module_id"], "cable_type": "audio"}]
    db_session.commit()
    export = _request(db_session, user, bridge, "no-source")

    result = fulfill_export(db_session, export.id)
    db_session.commit()

    assert result.status == "refunded"
    receipt = (
        db_session.query(StageReceiptRecord)
        .filter_by(run_id=bridge.source_run_id, stage="export")
        .one()
    )
    assert receipt.operation == "compose_design_export_pack"
    failure = receipt.receipt["failure"]
    assert failure["code"] == result.error_code
    assert "Remediation" in failure["detail"]


# --- the page (FR-008, FR-011, FR-013, FR-014)


def test_cables_are_numbered_by_name_and_match_the_routes():
    compilation = _library().items[0].compilation
    labels = {key: value.label for key, value in DISPLAY.items()}
    cables = cable_lines(compilation.patch_graph, labels)
    assert cables == [
        "1. Mutable Instruments Plaits Audio Out -> Intellijel Polaris Audio In [audio]",
        "2. Make Noise Maths Envelope Out -> Intellijel Polaris CV In [cv]",
    ]
    layout = layout_diagram(compilation, module_labels=labels)
    assert [route.number for route in layout.routes] == [1, 2]
    jacks = {(jack.number, jack.side) for box in layout.boxes for jack in box.jacks}
    assert jacks == {(1, "out"), (1, "in"), (2, "out"), (2, "in")}


def test_cable_ten_comes_after_cable_two():
    edges = [SimpleNamespace(edge_id=f"edge-{n}") for n in (10, 2, 1)]
    assert [edge.edge_id for _, edge in numbered_edges(edges)] == ["edge-1", "edge-2", "edge-10"]


def test_the_svg_shows_names_and_labeled_jacks_not_database_ids():
    compilation = _library().items[0].compilation
    labels = {key: value.label for key, value in DISPLAY.items()}
    svg = render_patch_diagram_svg(compilation, module_labels=labels)
    assert ">Mutable Instruments Plaits<" in svg
    assert ">1 Audio Out<" in svg and ">1 Audio In<" in svg
    assert "Module 1" not in svg


def test_a_hostile_name_is_escaped_in_the_svg():
    compilation = _library().items[0].compilation
    svg = render_patch_diagram_svg(compilation, module_labels={"1": "<script>x</script>"})
    assert "<script>" not in svg and "&lt;script&gt;" in svg


def test_a_loop_is_declared_marked_and_warned_about():
    patch = _patch(LOOP)
    nodes, edges = orm_patch_nodes_and_edges(LOOP)
    assert all(edge.feedback_cycle_id for edge in edges)

    library = _library(patch)
    compilation = library.items[0].compilation
    assert compilation.validation_report.valid  # it used to be UNDECLARED_FEEDBACK_CYCLE

    notes = page_notes(compilation, library)
    assert notes[0].startswith("Feedback: cables 1, 2 form a loop.")

    layout = layout_diagram(compilation)
    assert all(route.feedback for route in layout.routes)
    labels = [line for box in layout.boxes for jack in box.jacks for line in jack.lines]
    assert all(" FB " in line for line in labels)
    assert 'data-feedback="true"' in render_patch_diagram_svg(compilation)


def test_a_module_patched_into_itself_is_drawn_and_marked():
    self_patch = [{"from_module_id": 1, "from_port": "Out", "to_module_id": 1, "to_port": "In", "cable_type": "cv"}]
    library = _library(_patch(self_patch))
    layout = layout_diagram(library.items[0].compilation)
    assert len(layout.boxes) == 1 and layout.routes[0].feedback


def _busy_patch() -> Patch:
    """Seven modules in three rows, with forward, backward, long and looping cables."""
    pairs = [(1, 2), (2, 3), (3, 1), (4, 3), (5, 2), (6, 5), (3, 7), (1, 7), (7, 4), (1, 1)]
    return _patch(
        [
            {"from_module_id": a, "from_port": f"Out {i}", "to_module_id": b, "to_port": f"In {i}", "cable_type": "cv"}
            for i, (a, b) in enumerate(pairs)
        ]
    )


def test_no_route_runs_behind_a_box_or_off_the_diagram():
    """A line that disappears behind a box reads as ending there."""
    display = {str(n): ModuleDisplay(f"Module number {n}") for n in range(1, 8)}
    layout = layout_diagram(_library(_busy_patch(), display).items[0].compilation)
    assert len(layout.boxes) == 7 and len(layout.routes) == 10
    for route in layout.routes:
        for x, y in route.points:
            assert 0 <= x <= layout.width and 0 <= y <= layout.height
        for (x1, y1), (x2, y2) in zip(route.points, route.points[1:]):
            for box in layout.boxes:
                inside_x = max(x1, x2) > box.x and min(x1, x2) < box.x + box.width
                inside_y = max(y1, y2) > box.y and min(y1, y2) < box.y + box.height
                assert not (inside_x and inside_y), (route.number, box.node_id)


def test_every_report_issue_reaches_the_page():
    nodes = (
        PatchNode(node_id="a", module_instance_id="1", label="A", ports=(
            PatchPort(port_id="a:o", module_instance_id="1", module_port_id="o", label="Out", direction="output", signal_type="cv"),
        )),
        PatchNode(node_id="b", module_instance_id="2", label="B", ports=(
            PatchPort(port_id="b:i", module_instance_id="2", module_port_id="i", label="In", direction="input", signal_type="cv"),
        )),
    )
    edges = (PatchEdge(edge_id="e", source_port_id="a:o", target_port_id="b:i", signal_type="cv", breaks_normal=True),)
    compilation = compile_patch(
        run_id="gen-run-1-aaaaaaaaaaaaaaaa", rig_revision_id="rig-rev-" + "a" * 32, seed=1, intent="x",
        nodes=nodes, edges=edges, created_at=datetime(1970, 1, 1, tzinfo=timezone.utc), title="T",
    )
    notes = page_notes(compilation, _library())
    assert "Inserting this cable breaks a normalled connection." in notes


def test_generic_jack_names_are_named_as_generic():
    """FR-014: spec 001 OQ-04 keeps a generic role name when a jack isn't on file. The page says
    so, and names only the modules it applies to."""
    library = _library()
    notes = page_notes(library.items[0].compilation, library)
    assert notes[-1].startswith("Jack names are generic for Make Noise Maths, Mutable Instruments Plaits")
    assert "Polaris" not in notes[-1]
    polaris_too = {**DISPLAY, "2": ModuleDisplay("Intellijel Polaris", frozenset({"Audio In"}))}
    library = replace(library, module_display=polaris_too)
    assert "Intellijel Polaris" in page_notes(library.items[0].compilation, library)[-1]


class _Recorder:
    """Stands in for the reportlab canvas and records what the pages draw."""

    def __init__(self) -> None:
        self.page = 0
        self.font = ("", 0.0)
        self.texts: list[tuple[int, str, float, str]] = []
        self.boxes: list[int] = []
        self.paths: list[int] = []

    def setFont(self, name, size):
        self.font = (name, size)

    def drawString(self, x, y, text):
        self.texts.append((self.page, self.font[0], self.font[1], text))

    drawRightString = drawString

    def roundRect(self, *args, **kwargs):
        self.boxes.append(self.page)

    def drawPath(self, *args, **kwargs):
        self.paths.append(self.page)

    def beginPath(self):
        return _Recorder()

    def showPage(self):
        self.page += 1

    def __getattr__(self, name):
        return lambda *a, **k: None


def _draw(monkeypatch, tmp_path, library, family=TemplateFamilyId.SIGNAL_MANUAL) -> _Recorder:
    recorder = _Recorder()
    monkeypatch.setattr(engine.canvas, "Canvas", lambda *a, **k: recorder)
    monkeypatch.setattr(engine, "normalize_pdf_metadata", lambda b: b)
    compose_design_export_pack(library, _recipe(family), out_dir=tmp_path, export_id="e")
    return recorder


def test_the_colophon_says_how_many_modules_have_jack_names(monkeypatch, tmp_path):
    recorder = _draw(monkeypatch, tmp_path, _library())
    last = max(p for p, _, _, _ in recorder.texts)
    colophon = " ".join(t for p, _, _, t in recorder.texts if p == last)
    assert "Jack names on file for 1 of 3 Modules in this book." in colophon


def test_the_pdf_page_draws_the_diagram_names_and_warnings(monkeypatch, tmp_path):
    recorder = _draw(monkeypatch, tmp_path, _library())
    page = 1  # after the cover
    assert recorder.boxes.count(page) == 3  # one box per module
    assert recorder.paths.count(page) >= 2  # a route and its arrow, per cable
    text = " ".join(t for p, _, _, t in recorder.texts if p == page)
    for required in (
        "Basalt", "Intent: A voice", "Mutable Instruments Plaits", "Construction", "Operation",
        "Warnings", "Jack names are generic",
    ):
        assert required in text
    assert "1:Audio Out" not in text
    library = _library()
    for step in operation_lines(library.items[0].compilation, library):
        assert step in text
    assert "[prep]" not in text


def _operation(connections, *, sealed: bool = True) -> list[str]:
    library = _library(_patch(connections), sealed=sealed)
    return operation_lines(library.items[0].compilation, library)


def _cable(source: int, target: int, kind: str, jack: str = "") -> dict:
    return {
        "from_module_id": source, "from_port": f"{kind} Out{jack}",
        "to_module_id": target, "to_port": f"{kind} In{jack}", "cable_type": kind,
    }


@pytest.mark.parametrize("sealed", [True, False])
def test_operation_is_worked_out_from_the_patchs_own_cables(sealed):
    """FR-008, T091. A run with sealed rows and one without print the same steps."""
    assert _operation(CONNECTIONS, sealed=sealed) == [
        "Power down, set levels low, and verify every destination range.",
        "Patch cables 1 to 2 in order, then power up.",
        "Take your output from Intellijel Polaris, and raise the level slowly.",
        "Bring in the CV from Make Noise Maths slowly while monitoring the output.",
        "Reduce the CV, then the output level.",
        "Return levels low, then power down if rewiring.",
    ]


def test_operation_takes_the_output_from_where_the_audio_ends():
    chain = _operation([_cable(1, 2, "audio"), _cable(2, 3, "audio")])
    assert "Take your output from Make Noise Maths, and raise the level slowly." in chain
    forked = _operation([_cable(1, 2, "audio"), _cable(1, 3, "audio", " 2")])
    assert (
        "Take your output from Intellijel Polaris and Make Noise Maths, and raise the level slowly."
        in forked
    )


def test_operation_names_what_sends_the_timing():
    one = _operation([_cable(1, 2, "audio"), _cable(3, 1, "gate")])
    assert "Check that Make Noise Maths is running: it sends this patch's timing." in one
    two = _operation([_cable(3, 1, "clock"), _cable(2, 1, "trigger", " 2")])
    assert (
        "Check that Intellijel Polaris and Make Noise Maths are running: they send this patch's timing."
        in two
    )
    assert not any("timing" in step for step in _operation(CONNECTIONS))


def test_operation_without_a_cv_cable_only_mentions_the_level():
    steps = _operation([_cable(1, 2, "audio")])
    assert "Patch cable 1, then power up." in steps
    assert "Reduce the output level." in steps
    assert not any("CV" in step for step in steps)


def test_operation_without_an_audio_cable_names_no_output():
    steps = _operation([_cable(3, 1, "cv")])
    assert "Connect the module you want to hear to your output, and raise its level slowly." in steps
    assert not any("Take your output" in step for step in steps)


def test_operation_names_a_loops_cables_and_only_a_loop_gets_that_step():
    steps = _operation(LOOP)
    assert steps[-1] == "Return levels low, remove cables 1 and 2, then power down if rewiring."
    # Every module in a loop passes the audio on, so no module is the end of the path.
    assert not any("Take your output" in step for step in steps)
    assert not any("remove" in step for step in _operation(CONNECTIONS))


def test_a_run_with_no_sealed_rows_has_no_padding_and_no_module_ids():
    """T091. This plan used to repeat the cables, pad to five steps with "verify prior
    connection", and print a module id from the sixth cable on."""
    six = [_cable(1, 2, "audio", f" {n}") for n in range(1, 7)]
    library = _library(_patch(six), sealed=False)
    compilation = library.items[0].compilation
    assert compilation.patch_plan.steps == standard_plan_steps()
    steps = operation_lines(compilation, library)
    assert "Patch cables 1 to 6 in order, then power up." in steps
    assert not any(re.search(r"\b\d+ (audio|Out)", step) for step in steps)
    assert not any("verify prior connection" in step for step in steps)


def test_the_companion_prints_the_same_steps_in_page_order(tmp_path):
    library = _library()
    compose_design_export_pack(library, _recipe(), out_dir=tmp_path, export_id="e")
    companion = (tmp_path / "technical" / "companion.txt").read_text(encoding="utf-8")
    for number, step in enumerate(operation_lines(library.items[0].compilation, library), start=1):
        assert f"  STEP {number}. {step}" in companion
    assert "[prep]" not in companion
    assert companion.index("  CABLE ") < companion.index("  STEP ") < companion.index("  NOTE ")


def test_the_colophon_notice_is_drawn_at_the_body_floor(monkeypatch, tmp_path):
    """FR-004. Only the Patent Future family carries the notice."""
    recorder = _draw(monkeypatch, tmp_path, _library(), TemplateFamilyId.PATENT_FUTURE)
    colophon = recorder.page - 1
    sizes = {size for p, _, size, text in recorder.texts if p == colophon and "patent" in text.lower()}
    assert sizes and min(sizes) >= 9.5


def test_the_pack_has_a_readme_with_a_checksum(tmp_path):
    """FR-018."""
    compose_design_export_pack(_library(), _recipe(), out_dir=tmp_path, export_id="e")
    assert (tmp_path / "README.txt").read_text().startswith("PatchHive PatchBook")
    files = json.loads((tmp_path / "manifest" / "checksums.json").read_text())["files"]
    assert "README.txt" in files


def test_renaming_a_module_changes_the_composition_hash(tmp_path):
    """FR-006: what a page prints counts toward the hash, so a replay can't pass over a change."""
    library = _library()
    first = compose_design_export_pack(library, _recipe(), out_dir=tmp_path / "a", export_id="e")
    again = compose_design_export_pack(library, _recipe(), out_dir=tmp_path / "b", export_id="e")
    assert first.composition_hash == again.composition_hash

    renamed = replace(library, module_display={**DISPLAY, "1": ModuleDisplay("Renamed Plaits")})
    other = compose_design_export_pack(renamed, _recipe(), out_dir=tmp_path / "c", export_id="e")
    assert other.composition_hash != first.composition_hash


@pytest.mark.parametrize("family", list(TemplateFamilyId))
def test_every_family_composes_a_page_with_every_semantic_region(tmp_path, family):
    """FR-008 and FR-009: each family may move a region, and none leaves one out."""
    result = compose_design_export_pack(_library(), _recipe(family), out_dir=tmp_path, export_id="e")
    execution = [ir for ir in result.layout_irs if ir.patch_artifact_id]
    assert execution
    roles = {region.role for region in execution[0].regions}
    assert {"identity", "diagram", "intent", "construction", "operation", "footer"} <= roles
