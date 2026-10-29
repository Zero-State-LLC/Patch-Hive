"""Cover layout: the patent notice never overlaps the metadata block (spec 002 FR-004)."""

from __future__ import annotations

from pathlib import Path

import pytest

from export.patchbook.design import engine
from export.patchbook.design.a11y import body_size_pt
from export.patchbook.design.families.registry import get_family
from export.patchbook.design.recipe import (
    BookProfile,
    OutputProfile,
    PatchBookMode,
    ResolvedStyleRecipe,
    StyleConstraints,
    StyleWeights,
    TemplateFamilyId,
)
from tests.unit.test_patchbook_publication_dual import _minimal_library

LONG_NOTICE = " ".join(
    ["This document is a PatchHive creative template and it is not a patent application,"] * 8
)


class _Recorder:
    """Stands in for the reportlab canvas and records what the cover draws."""

    def __init__(self, *args, **kwargs) -> None:
        self.page = 0
        self.size = 0.0
        self.draws: list[tuple[int, float, float, str]] = []

    def setFont(self, name, size):
        self.size = size

    def drawString(self, x, y, text):
        self.draws.append((self.page, y, self.size, text))

    def showPage(self):
        self.page += 1

    def __getattr__(self, name):
        return lambda *a, **k: None

    def save(self):
        pass


def _recipe(min_body: float = 9.5) -> ResolvedStyleRecipe:
    return ResolvedStyleRecipe(
        mode=PatchBookMode.PROFESSIONAL,
        template_family=TemplateFamilyId.PATENT_FUTURE,
        template_family_version="1.0.0",
        seed=1,
        weights=StyleWeights(legibility=95, diagram_literalness=96),
        constraints=StyleConstraints(
            book_profile=BookProfile.EXECUTION_PAGE, minimum_body_size_pt=min_body
        ),
        output_profile=OutputProfile.PRINT_PDF,
        resolved_tier="core",
        zero_state_brand_cap=6,
    )


@pytest.mark.parametrize("min_body", [9.5, 24.0])
def test_long_disclaimer_wraps_without_touching_the_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, min_body: float
) -> None:
    recorder = _Recorder()
    monkeypatch.setattr(engine.canvas, "Canvas", lambda *a, **k: recorder)
    monkeypatch.setattr(engine, "normalize_pdf_metadata", lambda b: b)
    monkeypatch.setattr(engine, "PATENT_FUTURE_DISCLAIMER", LONG_NOTICE)
    recipe = _recipe(min_body)
    family = get_family(recipe.template_family)
    assert family.patent_disclaimer

    engine._render_execution_pdf(
        _minimal_library(),
        recipe,
        family,
        tmp_path / "out.pdf",
        export_id="export-cover-1",
        composition_hash="a" * 64,
    )

    cover = [d for d in recorder.draws if d[0] == 0]
    meta = [d for d in cover if d[3].startswith(("Export:", "Run:", "Composition:", "Algorithm:"))]
    fixed = {"PatchHive PatchBook", family.cover_subtitle, "A Zero State Product"}
    notice = [d for d in cover if d not in meta and d[3] not in fixed]
    assert len(notice) >= 3
    assert len(meta) == 4
    # Disclaimer is drawn at the body floor, not 8 pt.
    assert all(d[2] == body_size_pt(recipe) for d in notice)
    # Every metadata baseline sits below every notice baseline, by more than a line.
    lowest_notice = min(d[1] for d in notice)
    highest_meta = max(d[1] for d in meta)
    assert highest_meta < lowest_notice
    # No vertical overlap, using ascent 0.72 em and descent 0.25 em.
    size = body_size_pt(recipe)
    assert size == min_body
    subtitle_y = next(d[1] for d in cover if d[3] == family.cover_subtitle)
    highest_notice = max(d[1] for d in notice)
    assert highest_notice + 0.72 * size < subtitle_y - 0.25 * 11
    assert highest_meta + 0.72 * size < lowest_notice - 0.25 * size
    # The cover is one page: its text is drawn before the first showPage.
    assert {d[0] for d in cover} == {0}
