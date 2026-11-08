"""Spec 008 T010-T050 unit tests for core.ops.f5_cutover (synthetic data only)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from core.ops.f5_cutover import (
    REQUIRED_PIN_DOCUMENTS,
    RUNTIME_FLAGS_SCHEMA,
    alias_evidence_failures,
    flags_from_server_payload,
    runtime_flags_payload,
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
from tests.f5008_helpers import f5008_approver_allowlist  # noqa: F401  (autouse)
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
    pin_signing,
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


def test_fe_scan_finds_calls_split_over_lines() -> None:
    # A formatter puts `rackApi` and `.list(` on separate lines; the builder's legacy
    # read hid this way from the one-line pattern (a false "no legacy callers").
    legacy, canon = scan_fe_list_callers(
        {
            "builder.tsx": "    rackApi\n      .list({ limit: 50 })\n      .then(() => {})",
            "racks.tsx": "    canonApi\n      .listRigs({ limit: 50 })",
        }
    )
    assert legacy == ("builder.tsx",)
    assert canon == ("racks.tsx",)


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
        ({"environment": "development"}, "SERVER_ENVIRONMENT_NOT_STAGING"),
        ({"environment": "Staging"}, "SERVER_ENVIRONMENT_NOT_STAGING"),
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
        **pin_signing(enablement),
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
        # A required list page that doesn't read the canon alias (only Racks.tsx is required
        # since the rig builder's evidence picker left, decision 63).
        ({"frontend/src/pages/Racks.tsx": "const rigs = await loadRigs();"}, GOOD_GENERATE, "FE_LIST_PAGE_NOT_CUT_OVER"),
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


# --- Codex review: shared alias checks, strict server flag parsing -------------


def test_alias_evidence_failures_matches_guard_codes() -> None:
    art = chain()
    assert alias_evidence_failures(art["alias"]) == ()
    assert alias_evidence_failures(None) == ("ALIAS_EVIDENCE_MISSING",)
    drift = art["alias"].model_copy(update={"same_set": False, "new_write_surface": ("POST /x",)})
    assert alias_evidence_failures(drift) == (
        "ALIAS_EVIDENCE_TAMPERED",
        "ALIAS_SET_DIFFERS_FROM_LEGACY",
        "NEW_WRITE_SURFACE",
    )


def test_runtime_flags_payload_round_trips_and_has_no_extra_fields() -> None:
    class S:
        environment = "staging"
        enable_patchbook_design_engine = True
        enable_canon_export_fulfillment = True
        enable_inline_export_fulfillment = False
        enable_patchbook_publication_profile = False
        stripe_test_mode = True
        allow_production_payments = False
        download_token_secret = "y" * 40
        database_url = "sqlite:///example.invalid.db"

    payload = runtime_flags_payload(S())
    assert payload["schema_version"] == RUNTIME_FLAGS_SCHEMA
    assert flags_from_server_payload(payload) == DesignEngineFlags.from_settings(S())
    text = json.dumps(payload)
    assert "y" * 40 not in text and "example.invalid" not in text


def test_runtime_flags_payload_defaults_missing_production_switch_to_unsafe() -> None:
    class Bare:
        environment = "staging"

    flags = flags_from_server_payload(runtime_flags_payload(Bare()))
    assert flags.allow_production_payments is True
    assert "PRODUCTION_PAYMENTS_ENABLED" in flags_test_mode_failures(flags)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("allow_production_payments"),
        lambda p: p.pop("schema_version"),
        lambda p: p.update(allow_production_payments="false"),
        lambda p: p.update(allow_production_payments=0),
        lambda p: p.update(stripe_test_mode=None),
        lambda p: p.update(environment=" "),
        lambda p: p.update(environment=None),
        lambda p: p.update(extra_flag=True),
    ],
)
def test_flags_from_server_payload_fails_closed_on_ambiguity(mutate) -> None:
    payload = {"schema_version": RUNTIME_FLAGS_SCHEMA, **flags().model_dump(mode="json")}
    assert flags_from_server_payload(dict(payload)) == flags()
    mutate(payload)
    with pytest.raises(CutoverError) as exc:
        flags_from_server_payload(payload)
    assert exc.value.code == "SERVER_FLAGS_UNVERIFIABLE"


@pytest.mark.parametrize("payload", [None, [], "flags", 1])
def test_flags_from_server_payload_rejects_non_objects(payload) -> None:
    with pytest.raises(CutoverError) as exc:
        flags_from_server_payload(payload)
    assert exc.value.code == "SERVER_FLAGS_UNVERIFIABLE"


# --- T071: signed 007 receipt and signed pin (research R1) ------------------------


def test_pin_is_signed_by_the_approver_key_it_names(art) -> None:
    from core.ops.f5_cutover import readiness_pin_signature_failures
    from tests.f5008_helpers import APPROVER_ID

    pin = art["pin"]
    assert pin.pinned_by == APPROVER_ID
    assert pin.pin_signature is not None and pin.pin_signature.key_id == APPROVER_ID
    assert pin.pin_signature.receipt_sha256 == pin.record_sha256
    assert pin.intact()
    assert readiness_pin_signature_failures(pin) == ()


def test_pin_refuses_an_unsigned_or_wrongly_signed_007_receipt(art, enablement) -> None:
    from intelligence.receipt_signing import sign_receipt_sha256
    from tests.eval007_helpers import throwaway_approver

    with pytest.raises(CutoverError) as exc:
        _pin(art, enablement, enablement_signature=None)
    assert exc.value.code == "ENABLEMENT_RECEIPT_INVALID"
    assert "RECEIPT_SIGNATURE_MISSING" in exc.value.detail

    stranger, _ = throwaway_approver("operator-1")
    forged = sign_receipt_sha256(stranger, key_id="operator-1", receipt_sha256=enablement.receipt_sha256)
    with pytest.raises(CutoverError) as exc:
        _pin(art, enablement, enablement_signature=forged)
    assert exc.value.code == "ENABLEMENT_RECEIPT_INVALID"
    assert "SIGNATURE_INVALID" in exc.value.detail


def test_pin_refuses_a_signer_who_is_not_the_named_key(art, enablement) -> None:
    from tests.eval007_helpers import throwaway_approver

    stranger, _ = throwaway_approver("operator-1")
    with pytest.raises(CutoverError) as exc:
        _pin(art, enablement, signing_key=stranger)
    assert exc.value.code == "PIN_SIGNATURE_INVALID"
    with pytest.raises(CutoverError) as exc:
        _pin(art, enablement, pinned_by="operator-9")
    assert exc.value.code == "PIN_SIGNATURE_INVALID"
    assert "PIN_APPROVER_KEY_UNKNOWN" in exc.value.detail


def test_a_pin_signature_is_not_a_receipt_signature(art) -> None:
    """Domain separation: the pin's signature over its SHA does not verify as a
    receipt approval of the same SHA, and a receipt-domain signature does not
    verify as a pin."""
    from core.ops.f5_cutover import readiness_pin_signature_failures
    from intelligence.receipt_signing import sign_receipt_sha256, signature_failures, load_approver_allowlist
    from tests.f5008_helpers import APPROVER_ID, APPROVER_KEY

    pin = art["pin"]
    allowlist = load_approver_allowlist()
    as_receipt = signature_failures(
        pin.pin_signature, receipt_sha256=pin.record_sha256, approved_by=APPROVER_ID,
        approved_at=pin.pinned_at, allowlist=allowlist,
    )
    assert "SIGNATURE_INVALID" in as_receipt
    receipt_domain = sign_receipt_sha256(APPROVER_KEY, key_id=APPROVER_ID, receipt_sha256=pin.record_sha256)
    swapped = pin.model_copy(update={"pin_signature": receipt_domain})
    assert "PIN_SIGNATURE_INVALID" in readiness_pin_signature_failures(swapped)


def test_the_pin_guard_refuses_a_missing_or_stale_pin_signature(art) -> None:
    from core.ops.f5_cutover import CutoverEvent, CutoverEventType as E, CutoverState, replay

    events = [
        CutoverEvent(E.EXPOSE_CANON_ALIAS, alias=art["alias"]),
        CutoverEvent(E.SWITCH_FE_LIST, fe_cutover=art["fe"]),
        CutoverEvent(E.RUN_WALKTHROUGH, start=art["start"]),
        CutoverEvent(E.CAPTURE_RECEIPT, receipt=art["receipt"]),
    ]
    unsigned = art["pin"].model_copy(update={"pin_signature": None})
    machine = replay(events + [CutoverEvent(E.OPERATOR_PIN, pin=unsigned)])
    assert machine.state is CutoverState.RECEIPT_CAPTURED
    assert "PIN_SIGNATURE_INVALID" in machine.history[-1].reasons
    # Re-sealed after an edit: the seal is intact, the signature covers the old SHA.
    edited = art["pin"].model_copy(update={"pinned_at": "2026-12-01T00:00:00Z"}).sealed()
    assert edited.intact()
    machine = replay(events + [CutoverEvent(E.OPERATOR_PIN, pin=edited)])
    assert machine.state is CutoverState.RECEIPT_CAPTURED
    assert "PIN_SIGNATURE_INVALID" in machine.history[-1].reasons
