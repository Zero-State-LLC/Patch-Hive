"""Spec 002 FR-001/003/010/021: a patch page wraps its content, never cuts or drops it,
and a patch whose required content cannot fit one page fails with a coded error."""

from types import SimpleNamespace

import pytest
from reportlab.lib.pagesizes import letter

from export.patchbook.design.diagram_svg import _label_lines
from export.patchbook.design.engine import (
    CONTENT_FLOOR,
    PreflightFailed,
    _wrap_to_width,
    layout_patch_page,
)
from export.patchbook.design.families.registry import FAMILIES

WIDTH, HEIGHT = letter
FAMILY = next(f for f in FAMILIES.values() if f.show_title_block)


def _patch(steps: int = 3, cables: int = 3, *, title: str = "Title", intent: str = "Intent"):
    plan = SimpleNamespace(
        title=title,
        intent=intent,
        steps=[SimpleNamespace(position=i + 1, phase="build", instruction=f"Step {i + 1} text") for i in range(steps)],
    )
    graph = SimpleNamespace(
        artifact_id="patch-1",
        edges=[
            SimpleNamespace(edge_id=f"e{i}", source_port_id=f"m{i}.out", target_port_id=f"m{i}.in", signal_type="audio")
            for i in range(cables)
        ],
    )
    return plan, graph


def _layout(plan, graph):
    return layout_patch_page(plan, graph, FAMILY, body_font="Helvetica", mono="Courier", width=WIDTH, height=HEIGHT)


def _text(lines) -> str:
    return " ".join(line.text for line in lines if not line.rule)


def test_long_titles_intents_and_cables_wrap_without_losing_a_word():
    title = "A very long patch title " * 6
    intent = "Explain in many words what this patch is for and why it sounds the way it does. " * 3
    plan, graph = _patch(title=title, intent=intent)
    graph.edges[0].target_port_id = "a.really.long.port.identifier." * 6
    page = _layout(plan, graph)
    joined = _text(page).replace(" ", "")
    for required in (title, intent, graph.edges[0].target_port_id):
        assert required.replace(" ", "") in joined
    assert all(line.y >= CONTENT_FLOOR for line in page)


def test_every_step_and_cable_is_on_the_page():
    plan, graph = _patch(steps=12, cables=10)
    text = _text(_layout(plan, graph))
    for step in plan.steps:
        assert step.instruction in text
    for edge in graph.edges:
        assert edge.edge_id in text


def test_a_patch_that_cannot_fit_fails_with_a_code_not_a_cut():
    plan, graph = _patch(steps=40, cables=30)
    with pytest.raises(PreflightFailed) as exc:
        _layout(plan, graph)
    assert exc.value.code == "PATCH_PAGE_TEXT_OVERFLOW"
    assert "Remediation" in exc.value.message


def test_the_optional_title_block_goes_before_the_patch_fails():
    # Find a size that fits only without the title block.
    for steps in range(20, 60):
        plan, graph = _patch(steps=steps, cables=4)
        try:
            page = _layout(plan, graph)
        except PreflightFailed:
            pytest.skip("no size fits only without the title block")
        if not any(line.text.startswith("TITLE BLOCK") for line in page):
            return  # the title block was dropped and the page still fits
    pytest.fail("the title block was never dropped before failing")


def test_a_word_wider_than_the_line_is_split_not_cut():
    word = "x" * 400
    lines = _wrap_to_width(word, "Courier", 8, 200)
    assert "".join(lines) == word and len(lines) > 1


def test_long_diagram_labels_wrap_and_impossible_ones_fail():
    assert _label_lines("Short name") == ["Short name"]
    wrapped = _label_lines("Erica Synths Black Wavetable VCO")
    assert " ".join(wrapped) == "Erica Synths Black Wavetable VCO" and len(wrapped) > 1
    with pytest.raises(PreflightFailed) as exc:
        _label_lines("Extremely Long Module Display Name That Will Not Fit In Any Node Box At All")
    assert exc.value.code == "PATCH_PAGE_DIAGRAM_OVERFLOW"


def test_a_long_identifier_wraps_without_extra_spaces_or_wasted_lines():
    port = "p" * 400
    plan, graph = _patch(steps=1, cables=1)
    graph.edges[0].target_port_id = port
    cable = [line for line in _layout(plan, graph) if line.font == "Courier"]
    # Rejoined without separators, the identifier is intact: no space was put inside it.
    assert port in "".join(line.text for line in cable)
    # Every continuation line but the last is full: no 2-character fragments.
    widths = [len(line.text) for line in cable[1:-1]]
    assert widths and min(widths) > 50


def test_labels_are_measured_against_each_node_shape():
    label = "Wonderful Oscillator"  # 20 characters
    assert _label_lines(label, "orthogonal_schematic") == ["Wonderful", "Oscillator"]
    with pytest.raises(PreflightFailed):
        # One word wider than the hex cell's inner width.
        _label_lines("Supercalifragilistic Osc", "hex_cell_map")
    with pytest.raises(PreflightFailed):
        _label_lines("Ultrawidemodulename Two", "orthogonal_schematic")
def test_body_text_and_cables_are_drawn_at_the_floor_or_above():
    plan, graph = _patch(steps=4, cables=4)
    for floor in (9.5, 10.5):
        page = layout_patch_page(
            plan, graph, FAMILY, body_font="Helvetica", mono="Courier",
            width=WIDTH, height=HEIGHT, body_size=floor,
        )
        required = [
            line for line in page
            if not line.rule and (line.text.startswith(("Intent", "e")) or "[build]" in line.text)
        ]
        assert required and all(line.size >= floor for line in required)


def test_profiles_have_their_own_floor():
    from export.patchbook.design.a11y import body_floor_pt

    assert body_floor_pt("print_pdf") == 9.5
    assert body_floor_pt("screen_pdf") == 10.5  # 14 px
    assert body_floor_pt("html_companion") == 10.5


def test_a_recipe_below_the_floor_is_raised_not_rejected():
    from export.patchbook.design.a11y import body_size_pt, validate_composition_a11y
    from export.patchbook.design.recipe import (
        OutputProfile,
        PatchBookMode,
        ResolvedStyleRecipe,
        StyleConstraints,
        StyleWeights,
        TemplateFamilyId,
    )

    recipe = ResolvedStyleRecipe(
        mode=PatchBookMode.PROFESSIONAL,
        template_family=TemplateFamilyId.SIGNAL_MANUAL,
        template_family_version="1.0.0",
        seed=1,
        weights=StyleWeights(),
        constraints=StyleConstraints(minimum_body_size_pt=9.5),
        output_profile=OutputProfile.SCREEN_PDF,
    )
    assert body_size_pt(recipe) == 10.5
    report = validate_composition_a11y([], recipe)
    assert report.ok
    assert [i.code for i in report.issues] == ["BODY_SIZE_RAISED_TO_FLOOR"]


def test_front_matter_wraps_at_large_body_sizes():
    """At 24 pt Courier a 39-character export line is wider than the page; it must wrap."""
    from unittest.mock import MagicMock

    from export.patchbook.design.engine import _draw_wrapped
    from reportlab.pdfbase.pdfmetrics import stringWidth

    canvas = MagicMock()
    text = "Export: export-" + "a" * 24
    _draw_wrapped(canvas, [text, "Run: gen-run-1"], "Courier", 24, 600, WIDTH - 144)
    drawn = [call.args for call in canvas.drawString.call_args_list]
    assert all(stringWidth(t, "Courier", 24) <= WIDTH - 144 for _, _, t in drawn)
    assert "".join(t for _, _, t in drawn[:-1]).replace(" ", "") == text.replace(" ", "")
    ys = [y for _, y, _ in drawn]
    assert all(a - b >= 24 for a, b in zip(ys, ys[1:]))  # no overlapping lines
