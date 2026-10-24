"""Spec 008 T010-T050 unit tests for core.ops.f5_cutover (synthetic data only)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from core.ops.f5_cutover import (
    REQUIRED_PIN_DOCUMENTS,
    CutoverError,
    DesignEngineFlags,
    SeedAccount,
    WalkthroughReceipt,
    audit_generate_dual_write,
    capture_walkthrough_receipt,
    collect_alias_evidence,
    collect_fe_cutover_evidence,
    flags_test_mode_failures,
    pin_readiness_docs,
    route_table,
    scan_fe_list_callers,
    start_walkthrough,
)
from tests.f5008_helpers import (
    FE_SOURCES_OK,
    GOOD_GENERATE,
    IDS,
    WALKTHROUGH_SHA,
    chain,
    docs,
    enablement_receipt,
    flags,
    full_routes,
    health,
    outcome,
    seed_auth,
)


@pytest.fixture(scope="module")
def enablement():
    return enablement_receipt()


@pytest.fixture(scope="module")
def art(enablement):
    return chain(enablement)


# --- shared -----------------------------------------------------------------


def test_route_table_reads_openapi_paths() -> None:
    spec = {"paths": {"/a": {"get": {}, "post": {}, "parameters": []}, "/b/{x}": {"delete": {}}}}
    assert route_table(spec) == frozenset({("GET", "/a"), ("POST", "/a"), ("DELETE", "/b/{x}")})
    assert route_table({}) == frozenset()


# --- T010 -------------------------------------------------------------------


def test_alias_evidence_happy_path() -> None:
    ev = collect_alias_evidence(full_routes(), legacy_ids=IDS, canon_ids=reversed(IDS))
    assert ev.intact()
    assert ev.missing_alias_routes == ()
    assert ev.same_set is True
    assert ev.rig_count == 3
    assert ev.legacy_ids_sha256 == ev.canon_ids_sha256
    assert ev.new_write_surface == ()
    assert "POST /api/canon/rigs/{rack_id}/evidence/confirmations" in ev.canon_write_routes


def test_alias_evidence_flags_missing_routes_and_set_drift() -> None:
    routes = full_routes() - {("GET", "/api/canon/rigs")}
    ev = collect_alias_evidence(routes, legacy_ids=(1, 2, 3), canon_ids=(1, 2))
    assert ev.missing_alias_routes == ("GET /api/canon/rigs",)
    assert ev.same_set is False
    assert ev.legacy_ids_sha256 != ev.canon_ids_sha256


def test_alias_evidence_detects_new_canon_write_surface() -> None:
    routes = full_routes() | {("PUT", "/api/canon/rigs/{rig_id}")}
    ev = collect_alias_evidence(routes, legacy_ids=IDS, canon_ids=IDS)
    assert ev.new_write_surface == ("PUT /api/canon/rigs/{rig_id}",)
    # A canon write that has a legacy twin is a dual-mount, not new surface.
    routes = routes | {("PUT", "/api/racks/{rig_id}")}
    assert collect_alias_evidence(routes, legacy_ids=IDS, canon_ids=IDS).new_write_surface == ()


def test_alias_evidence_is_tamper_evident() -> None:
    ev = collect_alias_evidence(full_routes(), legacy_ids=IDS, canon_ids=IDS)
    forged = ev.model_copy(update={"same_set": False})
    assert not forged.intact()
    with pytest.raises(ValidationError):
        ev.same_set = False  # type: ignore[misc]


# --- T020 -------------------------------------------------------------------


def test_dual_write_audit_passes_native_ids() -> None:
    audit = audit_generate_dual_write(GOOD_GENERATE)
    assert audit.passed and audit.failures == ()


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        ({"export_bridge_ready": False}, "EXPORT_BRIDGE_NOT_READY"),
        ({"source_run_id": "run-1"}, "SOURCE_RUN_NOT_NATIVE"),
        ({"rig_revision_id": None}, "RIG_REVISION_NOT_NATIVE"),
        ({"artifact_manifest_hash": "A" * 64}, "MANIFEST_HASH_INVALID"),
        ({"inventory_revision_id": ""}, "INVENTORY_REVISION_MISSING"),
        ({"source_run_id": "legacy-run-1"}, "LEGACY_ID_INVENTED:source_run_id"),
    ],
)
def test_dual_write_audit_flags_regressions(patch, code) -> None:
    audit = audit_generate_dual_write({**GOOD_GENERATE, **patch})
    assert not audit.passed
    assert code in audit.failures


def test_fe_scan_separates_legacy_and_canon_callers() -> None:
    legacy, canon = scan_fe_list_callers(
        {
            "a.tsx": "await rackApi.list({ limit: 50 })",
            "b.tsx": "await canonApi.listRigs({ limit: 50 })",
            "c.tsx": "rackApi.listing(); rackApi.get(1)",
        }
    )
    assert legacy == ("a.tsx",)
    assert canon == ("b.tsx",)


def test_fe_cutover_evidence_links_alias(art) -> None:
    fe = art["fe"]
    assert fe.intact()
    assert fe.alias_evidence_sha256 == art["alias"].record_sha256
    assert fe.legacy_list_callers == ()
    assert fe.canon_list_callers == tuple(sorted(FE_SOURCES_OK))
    assert fe.missing_gate_routes == ()
    assert fe.dual_write.passed


def test_fe_cutover_rejects_tampered_alias(art) -> None:
    forged = art["alias"].model_copy(update={"rig_count": 99})
    with pytest.raises(CutoverError) as exc:
        collect_fe_cutover_evidence(forged, full_routes(), fe_sources=FE_SOURCES_OK, generate_response=GOOD_GENERATE)
    assert exc.value.code == "ALIAS_EVIDENCE_TAMPERED"


def test_fe_cutover_records_missing_gates(art) -> None:
    routes = full_routes() - {("POST", "/api/patches/generate/{rack_id}")}
    fe = collect_fe_cutover_evidence(art["alias"], routes, fe_sources=FE_SOURCES_OK, generate_response=GOOD_GENERATE)
    assert fe.missing_gate_routes == ("POST /api/patches/generate/{rack_id}",)


# --- T030 -------------------------------------------------------------------


def test_seed_account_repr_hides_password() -> None:
    account = SeedAccount("golden_demo", "demo-pass", "User")
    assert "demo-pass" not in repr(account)


def test_seed_auth_record_carries_no_password() -> None:
    record = seed_auth()
    assert record.intact() and record.aligned
    assert "password_hash" not in record.model_dump_json()


# --- T040 -------------------------------------------------------------------


def test_flags_from_settings_defaults_fail_closed() -> None:
    class Bare:
        pass

    snap = DesignEngineFlags.from_settings(Bare())
    assert snap.allow_production_payments is True  # missing attribute is treated as unsafe
    failures = flags_test_mode_failures(snap)
    assert "PRODUCTION_PAYMENTS_ENABLED" in failures
    assert "DESIGN_ENGINE_FLAG_OFF" in failures


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"enable_patchbook_design_engine": False}, "DESIGN_ENGINE_FLAG_OFF"),
        ({"enable_canon_export_fulfillment": False}, "EXPORT_FULFILLMENT_FLAG_OFF"),
        ({"stripe_test_mode": False}, "PAYMENTS_NOT_TEST_MODE"),
        ({"allow_production_payments": True}, "PRODUCTION_PAYMENTS_ENABLED"),
        ({"environment": "Production"}, "PRODUCTION_ENVIRONMENT"),
    ],
)
def test_start_walkthrough_requires_test_mode_flags(art, overrides, code) -> None:
    assert flags_test_mode_failures(flags()) == ()
    with pytest.raises(CutoverError) as exc:
        start_walkthrough(art["fe"], flags(**overrides))
    assert exc.value.code == "FLAGS_NOT_TEST_MODE"
    assert code in exc.value.detail


def test_start_walkthrough_rejects_tampered_fe(art) -> None:
    with pytest.raises(CutoverError) as exc:
        start_walkthrough(art["fe"].model_copy(update={"scanned_files": ("x",)}), flags())
    assert exc.value.code == "FE_CUTOVER_TAMPERED"


def test_receipt_captures_sha_links(art) -> None:
    receipt = art["receipt"]
    assert receipt.intact()
    assert receipt.source_commit_sha == WALKTHROUGH_SHA
    assert receipt.walkthrough_start_sha256 == art["start"].record_sha256
    assert receipt.fe_cutover_sha256 == art["fe"].record_sha256
    assert receipt.production_payments_enabled is False
    assert receipt.outcome_passed and receipt.seed_auth_aligned


def _capture(art, **overrides):
    kwargs = dict(
        start=art["start"], seed_auth=seed_auth(), health=health(), outcome=outcome(),
        source_commit_sha=WALKTHROUGH_SHA,
    )
    kwargs.update(overrides)
    return capture_walkthrough_receipt(**kwargs)


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"start": None}, "WALKTHROUGH_NOT_STARTED"),
        ({"seed_auth": None}, "SEED_AUTH_MISSING_OR_TAMPERED"),
        ({"seed_auth": seed_auth(aligned=False)}, "SEED_AUTH_NOT_ALIGNED"),
        ({"health": None}, "HEALTH_NOT_OK"),
        ({"health": health(database="error")}, "HEALTH_NOT_OK"),
        ({"health": health(http_status=503)}, "HEALTH_NOT_OK"),
        ({"outcome": None}, "WALKTHROUGH_FAILED"),
        ({"outcome": outcome(failed_step="download_pack")}, "WALKTHROUGH_FAILED"),
        ({"outcome": outcome(export_status="failed")}, "WALKTHROUGH_FAILED"),
        ({"outcome": outcome(pack_zip_sha256=None)}, "WALKTHROUGH_FAILED"),
        ({"source_commit_sha": "main"}, "SOURCE_SHA_NOT_PINNED"),
        ({"source_commit_sha": ""}, "SOURCE_SHA_NOT_PINNED"),
    ],
)
def test_receipt_capture_fails_closed(art, overrides, code) -> None:
    with pytest.raises(CutoverError) as exc:
        _capture(art, **overrides)
    assert exc.value.code == code


def test_receipt_capture_rejects_tampered_seed_auth(art) -> None:
    forged = seed_auth(aligned=False).model_copy(update={"aligned": True})
    with pytest.raises(CutoverError) as exc:
        _capture(art, seed_auth=forged)
    assert exc.value.code == "SEED_AUTH_MISSING_OR_TAMPERED"


def test_outcome_missing_step_is_not_passed() -> None:
    full = outcome()
    assert full.passed
    partial = full.model_copy(update={"steps": full.steps[:-1]})
    assert not partial.passed


def test_receipt_cannot_record_production_payments(art) -> None:
    payload = art["receipt"].model_dump()
    payload["production_payments_enabled"] = True
    with pytest.raises(ValidationError):
        WalkthroughReceipt(**payload)


def test_receipt_contains_hashes_not_secrets(art) -> None:
    text = json.dumps(art["receipt"].model_dump(mode="json"))
    for forbidden in ("demo-pass", "admin-pass", "access_token", "Bearer", "postgresql://"):
        assert forbidden not in text


# --- T050 -------------------------------------------------------------------


def _pin(art, enablement, **overrides):
    kwargs = dict(
        receipt=art["receipt"], documents=docs(), unresolved_p0=(), enablement_receipt=enablement,
        pinned_by="operator-1",
    )
    kwargs.update(overrides)
    return pin_readiness_docs(**kwargs)


def test_pin_binds_documents_to_receipt_sha(art, enablement) -> None:
    pin = _pin(art, enablement)
    assert pin.intact()
    assert pin.source_commit_sha == WALKTHROUGH_SHA
    assert pin.walkthrough_receipt_sha256 == art["receipt"].record_sha256
    assert {d.path for d in pin.documents} == set(REQUIRED_PIN_DOCUMENTS)
    assert all(d.references_source_sha for d in pin.documents)
    assert pin.unresolved_p0 == ()


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"receipt": None}, "WALKTHROUGH_RECEIPT_MISSING_OR_TAMPERED"),
        ({"enablement_receipt": None}, "ENABLEMENT_RECEIPT_INVALID"),
        ({"documents": {REQUIRED_PIN_DOCUMENTS[0]: "x"}}, "PIN_DOCUMENT_MISSING"),
        ({"documents": docs("9" * 40)}, "DOCUMENT_NOT_PINNED_TO_SHA"),
        ({"unresolved_p0": ("P0-17 export double debit",)}, "UNRESOLVED_P0"),
        ({"pinned_by": "  "}, "OPERATOR_MISSING"),
    ],
)
def test_pin_fails_closed(art, enablement, overrides, code) -> None:
    with pytest.raises(CutoverError) as exc:
        _pin(art, enablement, **overrides)
    assert exc.value.code == code


def test_pin_rejects_tampered_receipt_and_forged_enablement(art, enablement) -> None:
    with pytest.raises(CutoverError) as exc:
        _pin(art, enablement, receipt=art["receipt"].model_copy(update={"source_commit_sha": "9" * 40}))
    assert exc.value.code == "WALKTHROUGH_RECEIPT_MISSING_OR_TAMPERED"
    forged = enablement.model_copy(update={"source_commit_sha": "9" * 40})
    with pytest.raises(CutoverError) as exc:
        _pin(art, enablement, enablement_receipt=forged)
    assert exc.value.code == "ENABLEMENT_RECEIPT_INVALID"


def test_blank_p0_entries_are_ignored(art, enablement) -> None:
    assert _pin(art, enablement, unresolved_p0=("", "  ")).unresolved_p0 == ()


# --- review hardening -----------------------------------------------------------


@pytest.mark.parametrize(
    ("fe_sources", "generate", "code"),
    [
        ({"frontend/src/pages/Racks.tsx": "canonApi.listRigs("}, GOOD_GENERATE, "FE_LIST_PAGE_NOT_CUT_OVER"),
        ({**FE_SOURCES_OK, "frontend/src/pages/Other.tsx": "rackApi.list("}, GOOD_GENERATE, "FE_LIST_NOT_ON_CANON_ALIAS"),
        (FE_SOURCES_OK, {**GOOD_GENERATE, "export_bridge_ready": False}, "DUAL_WRITE_REGRESSION"),
    ],
)
def test_start_walkthrough_refuses_incomplete_fe_cutover(art, fe_sources, generate, code) -> None:
    fe = collect_fe_cutover_evidence(art["alias"], full_routes(), fe_sources=fe_sources, generate_response=generate)
    with pytest.raises(CutoverError) as exc:
        start_walkthrough(fe, flags())
    assert exc.value.code == "FE_CUTOVER_INCOMPLETE"
    assert code in exc.value.detail


def test_start_walkthrough_refuses_missing_gate(art) -> None:
    routes = full_routes() - {("POST", "/api/racks/{rack_id}/evidence/confirmations")}
    fe = collect_fe_cutover_evidence(art["alias"], routes, fe_sources=FE_SOURCES_OK, generate_response=GOOD_GENERATE)
    with pytest.raises(CutoverError) as exc:
        start_walkthrough(fe, flags())
    assert "GENERATE_OR_CONFIRMATION_GATE_CHANGED" in exc.value.detail


def test_receipt_embeds_sealed_seed_auth(art) -> None:
    receipt = art["receipt"]
    assert receipt.seed_auth.intact()
    assert receipt.seed_auth.aligned
    assert receipt.seed_auth_sha256 == receipt.seed_auth.record_sha256
