"""Synthetic Spec 008 artifacts for unit and integration tests.

No real staging walkthrough exists on main; every value here is synthetic test
data. The upstream Spec 007 enablement receipt is built from the 007 synthetic
chain (tests/eval007_helpers.py).
"""

from __future__ import annotations

from core.ops.f5_cutover import (
    CANON_LIST_ROUTE,
    LEGACY_LIST_ROUTE,
    REQUIRED_ALIAS_ROUTES,
    REQUIRED_GATE_ROUTES,
    REQUIRED_PIN_DOCUMENTS,
    REQUIRED_WALKTHROUGH_STEPS,
    DesignEngineFlags,
    HealthSnapshot,
    SeedAccountStatus,
    SeedAuthCheck,
    WalkthroughOutcome,
    WalkthroughStep,
    capture_walkthrough_receipt,
    collect_alias_evidence,
    collect_fe_cutover_evidence,
    pin_readiness_docs,
    start_walkthrough,
)
from intelligence.evaluation_corpus import freeze_corpus
from intelligence.evaluation_enablement import (
    approve_thresholds,
    enable_staging,
    pin_receipt,
    propose_thresholds,
    run_baseline_comparison,
)
from tests.eval007_helpers import (
    APPROVED_AT,
    HARNESS_SHA,
    POLICY,
    admitted_manifest,
    assisted_cases,
    baseline_cases,
    staging_settings,
)
from tests.eval007_helpers import SOURCE_SHA as SOURCE_SHA_007

WALKTHROUGH_SHA = "8" * 40
IDS = (1, 2, 3)


def legacy_twin(route: tuple[str, str]) -> tuple[str, str]:
    method, path = route
    return method, "/api/racks" + path[len("/api/canon/rigs"):]


def full_routes() -> frozenset[tuple[str, str]]:
    """Synthetic route table: canon aliases, their legacy twins, and the gates."""
    routes = set(REQUIRED_ALIAS_ROUTES) | set(REQUIRED_GATE_ROUTES) | {LEGACY_LIST_ROUTE}
    for route in REQUIRED_ALIAS_ROUTES:
        if route[0] != "GET":
            routes.add(legacy_twin(route))
    assert CANON_LIST_ROUTE in routes
    return frozenset(routes)


GOOD_GENERATE = {
    "export_bridge_ready": True,
    "source_run_id": "gen-run-abc",
    "rig_revision_id": "rig-rev-abc",
    "artifact_manifest_hash": "a" * 64,
    "inventory_revision_id": "inv-rev-abc",
}

FE_SOURCES_OK = {
    "frontend/src/pages/Racks.tsx": "const r = await canonApi.listRigs({ limit: 50 });",
    "frontend/src/pages/Modules.tsx": "const r = await canonApi.listRigs({ limit: 50 });",
}


def flags(**overrides) -> DesignEngineFlags:
    values = dict(
        environment="staging",
        enable_patchbook_design_engine=True,
        enable_canon_export_fulfillment=True,
        enable_inline_export_fulfillment=True,
        enable_patchbook_publication_profile=False,
        stripe_test_mode=True,
        allow_production_payments=False,
    )
    values.update(overrides)
    return DesignEngineFlags(**values)


def seed_auth(*, aligned: bool = True) -> SeedAuthCheck:
    statuses = (
        SeedAccountStatus(
            username="golden_demo", expected_role="User", exists=True,
            password_matches=aligned, role_matches=True,
        ),
        SeedAccountStatus(
            username="admin_demo", expected_role="Admin", exists=True,
            password_matches=True, role_matches=True,
        ),
    )
    return SeedAuthCheck(accounts=statuses, aligned=aligned).sealed()


def health(**overrides) -> HealthSnapshot:
    values = dict(http_status=200, status="healthy", database="ok")
    values.update(overrides)
    return HealthSnapshot(**values)


def outcome(*, failed_step: str | None = None, **overrides) -> WalkthroughOutcome:
    steps = tuple(
        WalkthroughStep(name=name, passed=name != failed_step, http_status=200)
        for name in REQUIRED_WALKTHROUGH_STEPS
    )
    values = dict(
        steps=steps,
        export_id="export-synthetic",
        export_status="succeeded",
        pack_manifest_hash="b" * 64,
        composition_hash="c" * 64,
        pack_zip_sha256="d" * 64,
    )
    values.update(overrides)
    return WalkthroughOutcome(**values)


def docs(sha: str = WALKTHROUGH_SHA) -> dict[str, str]:
    return {path: f"# doc\nwalkthrough source sha: {sha}\n" for path in REQUIRED_PIN_DOCUMENTS}


def enablement_receipt():
    manifest = admitted_manifest()
    corpus = freeze_corpus(manifest)
    run = run_baseline_comparison(
        corpus=corpus,
        baseline_cases=baseline_cases(manifest),
        assisted_cases=assisted_cases(manifest),
        policy=POLICY,
        harness_sha=HARNESS_SHA,
        baseline_provider_id="fixture",
        assisted_provider_id="clef",
    )
    proposal = propose_thresholds(run, proposal_version="thresholds-v1")
    approval = approve_thresholds(
        proposal, approved_by="operator-1", approved_at=APPROVED_AT, explicit_sign_off=True
    )
    staging = enable_staging(
        approval=approval, run=run, settings_obj=staging_settings(), target_environment="staging"
    )
    return pin_receipt(
        corpus=corpus, run=run, proposal=proposal, approval=approval, staging=staging,
        source_commit_sha=SOURCE_SHA_007,
    )


def chain(enablement=None) -> dict:
    """Valid, linked artifacts for every transition."""
    alias = collect_alias_evidence(full_routes(), legacy_ids=IDS, canon_ids=IDS)
    fe = collect_fe_cutover_evidence(
        alias, full_routes(), fe_sources=FE_SOURCES_OK, generate_response=GOOD_GENERATE
    )
    start = start_walkthrough(fe, flags())
    receipt = capture_walkthrough_receipt(
        start=start, seed_auth=seed_auth(), health=health(), outcome=outcome(),
        source_commit_sha=WALKTHROUGH_SHA,
    )
    pin = pin_readiness_docs(
        receipt=receipt,
        documents=docs(),
        unresolved_p0=(),
        enablement_receipt=enablement if enablement is not None else enablement_receipt(),
        pinned_by="operator-1",
    )
    return {"alias": alias, "fe": fe, "start": start, "receipt": receipt, "pin": pin}
