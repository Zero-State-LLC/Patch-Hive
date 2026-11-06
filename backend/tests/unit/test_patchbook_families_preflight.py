"""Template family fingerprints, a11y/preflight, preview rate limit."""

from __future__ import annotations

from export.patchbook.design.a11y import validate_composition_a11y
from export.patchbook.design.families.registry import (
    PATENT_FUTURE_DISCLAIMER,
    STRUCT_MIN_DISTANCE,
    assert_families_structurally_unique,
    get_family,
    list_families,
    pairwise_fingerprint_distances,
)
from export.patchbook.design.layout_ir import LayoutRegion, PageKind, PatchPageLayoutIR
from export.patchbook.design.preflight import run_preflight
from export.patchbook.design.rate_limit import (
    check_preview_rate_limit,
    reset_preview_rate_limits_for_tests,
)
from export.patchbook.design.recipe import (
    PatchBookMode,
    ResolvedStyleRecipe,
    StyleConstraints,
    StyleWeights,
    TemplateFamilyId,
    OutputProfile,
)


def test_all_twelve_families_registered() -> None:
    families = list_families()
    assert len(families) == 12
    assert {f.family_id for f in families} == set(TemplateFamilyId)


def test_structural_fingerprints_unique() -> None:
    assert_families_structurally_unique(STRUCT_MIN_DISTANCE)
    distances = pairwise_fingerprint_distances()
    assert all(d >= STRUCT_MIN_DISTANCE for _, _, d in distances)


def test_family_algorithms_unique() -> None:
    algs = [get_family(f).layout_algorithm_id for f in TemplateFamilyId]
    assert len(algs) == len(set(algs))


def test_patent_disclaimer_constant() -> None:
    fam = get_family(TemplateFamilyId.PATENT_FUTURE)
    assert fam.patent_disclaimer is True
    assert "not a patent" in PATENT_FUTURE_DISCLAIMER.lower()


def test_a11y_requires_execution_footer() -> None:
    recipe = ResolvedStyleRecipe(
        mode=PatchBookMode.PROFESSIONAL,
        template_family=TemplateFamilyId.SIGNAL_MANUAL,
        template_family_version="1.0.0",
        seed=1,
        weights=StyleWeights(),
        constraints=StyleConstraints(),
        output_profile=OutputProfile.PRINT_PDF,
    )
    page = PatchPageLayoutIR(
        page_id="p",
        page_index=0,
        page_kind=PageKind.EXECUTION,
        patch_artifact_id="patch-1",
        page_size="us_letter",
        regions=(
            LayoutRegion(
                region_id="diagram",
                role="diagram",
                required=True,
                bbox_pt=(36.0, 200.0, 500.0, 400.0),
                reading_order=0,
            ),
        ),
        reading_order=("diagram",),
    )
    report = validate_composition_a11y([page], recipe)
    assert report.ok is False
    assert any(i.code == "EXECUTION_FOOTER_MISSING" for i in report.issues)


ROLES = ("identity", "intent", "diagram", "construction", "operation", "footer")


def test_preflight_passes_well_formed_page() -> None:
    recipe = ResolvedStyleRecipe(
        mode=PatchBookMode.PROFESSIONAL,
        template_family=TemplateFamilyId.SIGNAL_MANUAL,
        template_family_version="1.0.0",
        seed=1,
        weights=StyleWeights(),
        constraints=StyleConstraints(),
        output_profile=OutputProfile.PRINT_PDF,
    )
    page = PatchPageLayoutIR(
        page_id="p",
        page_index=0,
        page_kind=PageKind.EXECUTION,
        patch_artifact_id="patch-1",
        page_size="us_letter",
        regions=tuple(
            LayoutRegion(
                region_id=role,
                role=role,
                required=True,
                bbox_pt=(36.0, 36.0 + index * 60.0, 400.0, 50.0),
                reading_order=index,
            )
            for index, role in enumerate(ROLES)
        ),
        reading_order=ROLES,
    )
    report = run_preflight([page], recipe)
    assert report.ok is True


def test_preflight_refuses_a_page_missing_a_semantic_region() -> None:
    """Spec 002 FR-008: a layout can move a region, but can't leave one out."""
    recipe = ResolvedStyleRecipe(
        mode=PatchBookMode.PROFESSIONAL,
        template_family=TemplateFamilyId.SIGNAL_MANUAL,
        template_family_version="1.0.0",
        seed=1,
        weights=StyleWeights(),
        constraints=StyleConstraints(),
        output_profile=OutputProfile.PRINT_PDF,
    )
    kept = tuple(role for role in ROLES if role != "operation")
    page = PatchPageLayoutIR(
        page_id="p",
        page_index=0,
        page_kind=PageKind.EXECUTION,
        patch_artifact_id="a",
        page_size="us_letter",
        regions=tuple(
            LayoutRegion(
                region_id=role,
                role=role,
                required=True,
                bbox_pt=(36.0, 36.0 + index * 60.0, 400.0, 50.0),
                reading_order=index,
            )
            for index, role in enumerate(kept)
        ),
        reading_order=kept,
    )
    report = run_preflight([page], recipe)
    assert report.ok is False
    assert [i.code for i in report.issues if i.severity == "error"] == [
        "PATCH_PAGE_REQUIRED_CONTENT_MISSING"
    ]


def test_preview_rate_limit() -> None:
    reset_preview_rate_limits_for_tests()
    for _ in range(3):
        assert check_preview_rate_limit(99, limit=3).allowed is True
    blocked = check_preview_rate_limit(99, limit=3)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds >= 0
