"""Accessibility validation for Design Engine compositions."""

from __future__ import annotations

from dataclasses import dataclass

from export.patchbook.design.layout_ir import PageKind, PatchPageLayoutIR
from export.patchbook.design.recipe import ResolvedStyleRecipe

MIN_BODY_PT_PRINT = 9.5
# 14 px at 96 dpi, the digital body-text floor (spec 002 FR-004).
MIN_BODY_PT_DIGITAL = 10.5
MIN_CONTRAST = 4.5


def body_floor_pt(output_profile: str) -> float:
    """The smallest body text a profile allows: print profiles 9.5 pt, digital 14 px."""
    return MIN_BODY_PT_PRINT if output_profile.startswith("print") else MIN_BODY_PT_DIGITAL


def body_size_pt(recipe: ResolvedStyleRecipe) -> float:
    """The size body text is drawn at: the recipe's minimum, never below the floor."""
    return max(recipe.constraints.minimum_body_size_pt, body_floor_pt(recipe.output_profile.value))


@dataclass(frozen=True)
class A11yIssue:
    code: str
    severity: str
    message: str
    page_id: str | None = None


@dataclass(frozen=True)
class A11yReport:
    ok: bool
    issues: tuple[A11yIssue, ...]


def validate_composition_a11y(
    pages: list[PatchPageLayoutIR] | tuple[PatchPageLayoutIR, ...],
    recipe: ResolvedStyleRecipe,
) -> A11yReport:
    issues: list[A11yIssue] = []
    min_body = recipe.constraints.minimum_body_size_pt
    floor = body_floor_pt(recipe.output_profile.value)
    if min_body < floor:
        # The renderer draws body text at body_size_pt(), never below the floor, so a
        # recipe asking for less is raised, not rejected. Text runs below the floor are
        # still errors (TEXT_RUN_BELOW_MINIMUM, below).
        issues.append(
            A11yIssue(
                code="BODY_SIZE_RAISED_TO_FLOOR",
                severity="warning",
                message=(
                    f"minimum_body_size_pt {min_body} is below {floor} for "
                    f"{recipe.output_profile.value}; body text is drawn at {floor}"
                ),
            )
        )

    if recipe.constraints.minimum_contrast_ratio < MIN_CONTRAST:
        issues.append(
            A11yIssue(
                code="CONTRAST_BELOW_AA",
                severity="error",
                message=f"minimum_contrast_ratio {recipe.constraints.minimum_contrast_ratio} < {MIN_CONTRAST}",
            )
        )

    if not recipe.constraints.color_independent_diagrams:
        issues.append(
            A11yIssue(
                code="COLOR_ONLY_DIAGRAMS",
                severity="error",
                message="color_independent_diagrams must be true for production export",
            )
        )

    for page in pages:
        if page.page_kind in (PageKind.EXECUTION, PageKind.APPENDIX_EXECUTION):
            roles = {r.role for r in page.regions}
            if "footer" not in roles:
                issues.append(
                    A11yIssue(
                        code="EXECUTION_FOOTER_MISSING",
                        severity="error",
                        message="execution pages require footer band",
                        page_id=page.page_id,
                    )
                )
            if "diagram" not in roles and page.diagram_literal:
                # non-literal plates may omit; literal execution needs diagram region
                issues.append(
                    A11yIssue(
                        code="DIAGRAM_REGION_MISSING",
                        severity="warning",
                        message="literal execution page missing diagram region",
                        page_id=page.page_id,
                    )
                )
            if not page.reading_order:
                issues.append(
                    A11yIssue(
                        code="READING_ORDER_EMPTY",
                        severity="error",
                        message="reading_order required",
                        page_id=page.page_id,
                    )
                )
        for run in page.text_runs:
            if run.style_role in {"body", "warning"} and run.font_size_pt < max(min_body, floor):
                issues.append(
                    A11yIssue(
                        code="TEXT_RUN_BELOW_MINIMUM",
                        severity="error",
                        message=f"run {run.run_id} font_size_pt {run.font_size_pt} < {max(min_body, floor)}",
                        page_id=page.page_id,
                    )
                )

    blocking = [i for i in issues if i.severity == "error"]
    return A11yReport(ok=not blocking, issues=tuple(issues))
