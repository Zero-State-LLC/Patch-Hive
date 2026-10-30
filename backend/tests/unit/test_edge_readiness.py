"""Unit tests for edge readiness state machine and config gates (Spec 006, T070)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.config import Settings
from core.ops.edge_readiness import (
    READINESS_ORDER,
    ReadinessEvent,
    ReadinessEvidence,
    ReadinessState,
    config_gate_checks,
    d1_permitted,
    live_payments_permitted,
    production_claims_permitted,
    readiness_transition,
    replay_readiness,
    summarize,
)
from intelligence.receipt_signing import sign_receipt_sha256
from tests.eval007_helpers import build_receipt_chain, install_allowlist, throwaway_approver

# gates_pass verifies the signed 007 receipt (006 T100). The receipt is the
# synthetic 007 chain; the approver key is a throwaway generated in memory.
_CHAIN = build_receipt_chain()
_RECEIPT = _CHAIN["receipt"]
_APPROVER_KEY, _APPROVER_ENTRY = throwaway_approver("operator-1")
_SIGNATURE = sign_receipt_sha256(
    _APPROVER_KEY, key_id="operator-1", receipt_sha256=_RECEIPT.receipt_sha256
)
_FIXED_RECEIPT_SHA = _RECEIPT.receipt_sha256

_VALID_PAIRS = {
    (ReadinessState.UNCONFIGURED, ReadinessEvent.FRONTEND_DEPLOYED),
    (ReadinessState.FRONTEND_ATTACHED, ReadinessEvent.API_PUBLISHED),
    (ReadinessState.API_HOSTNAME_LIVE, ReadinessEvent.DATABASE_BOUND),
    (ReadinessState.DATABASE_BOUND, ReadinessEvent.CLEF_ADAPTER_WIRED),
    (ReadinessState.CLEF_FLAGGED, ReadinessEvent.GATES_PASS),
    (ReadinessState.GATES_PASSED, ReadinessEvent.OPERATOR_APPROVE),
}


@pytest.fixture(autouse=True)
def approver_allowlist(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Allowlist holding only the throwaway approver key."""
    install_allowlist(monkeypatch, tmp_path, _APPROVER_ENTRY)


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove settings-relevant env vars before constructing Settings."""
    for name in ("ENABLE_CLEF_PROVIDER", "CORS_ORIGINS", "ALLOW_PRODUCTION_PAYMENTS"):
        monkeypatch.delenv(name, raising=False)


def _valid_evidence(**overrides: object) -> ReadinessEvidence:
    fields: dict[str, object] = {
        "frontend_build_output_present": True,
        "frontend_custom_domain_attached": True,
        "api_environment_staging": True,
        "api_cors_exact_origin": True,
        "api_health_ok": True,
        "payments_live_disabled": True,
        "database_neon_staging_pooled": True,
        "d1_absent": True,
        "clef_flag_default_off": True,
        "staging_host_plan_passed": True,
        "evaluation_receipt_sha256": _FIXED_RECEIPT_SHA,
        "evaluation_receipt": _RECEIPT,
        "evaluation_receipt_signature": _SIGNATURE,
        "operator_approved": True,
        "checklist_receipts": ("receipt-1",),
    }
    fields.update(overrides)
    return ReadinessEvidence(**fields)  # type: ignore[arg-type]


def _happy_path_events() -> list[tuple[ReadinessEvent, ReadinessEvidence]]:
    return [
        (ReadinessEvent.FRONTEND_DEPLOYED, _valid_evidence()),
        (ReadinessEvent.API_PUBLISHED, _valid_evidence()),
        (ReadinessEvent.DATABASE_BOUND, _valid_evidence()),
        (ReadinessEvent.CLEF_ADAPTER_WIRED, _valid_evidence()),
        (ReadinessEvent.GATES_PASS, _valid_evidence()),
        (ReadinessEvent.OPERATOR_APPROVE, _valid_evidence()),
    ]


def test_full_happy_path_reaches_beta_ready() -> None:
    state, results = replay_readiness(_happy_path_events())
    assert state is ReadinessState.BETA_READY
    assert len(results) == 6
    assert all(result.accepted for result in results)
    assert [result.to_state for result in results] == [
        ReadinessState.FRONTEND_ATTACHED,
        ReadinessState.API_HOSTNAME_LIVE,
        ReadinessState.DATABASE_BOUND,
        ReadinessState.CLEF_FLAGGED,
        ReadinessState.GATES_PASSED,
        ReadinessState.BETA_READY,
    ]


def test_beta_ready_requires_operator_approval_and_checklist_receipts() -> None:
    base = _happy_path_events()[:5]

    state, _ = replay_readiness(
        base + [(ReadinessEvent.OPERATOR_APPROVE, _valid_evidence(operator_approved=False))]
    )
    assert state is ReadinessState.GATES_PASSED

    state, _ = replay_readiness(
        base + [(ReadinessEvent.OPERATOR_APPROVE, _valid_evidence(checklist_receipts=()))]
    )
    assert state is ReadinessState.GATES_PASSED

    state, _ = replay_readiness(
        base
        + [
            (
                ReadinessEvent.OPERATOR_APPROVE,
                _valid_evidence(operator_approved=False, checklist_receipts=()),
            )
        ]
    )
    assert state is ReadinessState.GATES_PASSED

    state, _ = replay_readiness(base + [(ReadinessEvent.OPERATOR_APPROVE, _valid_evidence())])
    assert state is ReadinessState.BETA_READY


def test_skipping_states_is_rejected_with_invalid_transition() -> None:
    evidence = _valid_evidence()
    for state in READINESS_ORDER:
        if state is ReadinessState.BETA_READY:
            continue
        for event in ReadinessEvent:
            if (state, event) in _VALID_PAIRS:
                continue
            result = readiness_transition(state, event, evidence)
            assert result.accepted is False, (state, event)
            assert result.to_state is state, (state, event)
            assert result.failed_checks == ("INVALID_TRANSITION",), (state, event, result)


def test_gates_passed_without_operator_approval_stays_gates_passed() -> None:
    evidence = _valid_evidence(operator_approved=False)
    result = readiness_transition(
        ReadinessState.GATES_PASSED, ReadinessEvent.OPERATOR_APPROVE, evidence
    )
    assert result.accepted is False
    assert result.from_state is ReadinessState.GATES_PASSED
    assert result.to_state is ReadinessState.GATES_PASSED
    assert "OPERATOR_APPROVAL_MISSING" in result.failed_checks


def test_invariant_payments_regression_blocks_gates_and_operator() -> None:
    evidence = _valid_evidence(payments_live_disabled=False)

    gates_result = readiness_transition(
        ReadinessState.CLEF_FLAGGED, ReadinessEvent.GATES_PASS, evidence
    )
    assert gates_result.accepted is False
    assert gates_result.to_state is ReadinessState.CLEF_FLAGGED
    assert "INVARIANT_PAYMENTS_LIVE_ENABLED" in gates_result.failed_checks

    operator_result = readiness_transition(
        ReadinessState.GATES_PASSED, ReadinessEvent.OPERATOR_APPROVE, evidence
    )
    assert operator_result.accepted is False
    assert operator_result.to_state is ReadinessState.GATES_PASSED
    assert "INVARIANT_PAYMENTS_LIVE_ENABLED" in operator_result.failed_checks


def test_bad_receipt_sha_blocks_gates_pass() -> None:
    for bad in ("A" * 64, "a" * 63, "a" * 65, "g" * 64, ""):
        evidence = _valid_evidence(evaluation_receipt_sha256=bad)
        result = readiness_transition(
            ReadinessState.CLEF_FLAGGED, ReadinessEvent.GATES_PASS, evidence
        )
        assert result.accepted is False, bad
        assert result.to_state is ReadinessState.CLEF_FLAGGED
        assert "EVALUATION_RECEIPT_SHA_INVALID" in result.failed_checks, bad


def _gates(evidence: ReadinessEvidence):
    return readiness_transition(ReadinessState.CLEF_FLAGGED, ReadinessEvent.GATES_PASS, evidence)


def test_gates_pass_accepts_the_signed_receipt() -> None:
    result = _gates(_valid_evidence())
    assert result.accepted, result.failed_checks
    assert result.to_state is ReadinessState.GATES_PASSED


def test_gates_pass_refuses_a_bare_sha_without_the_receipt() -> None:
    result = _gates(_valid_evidence(evaluation_receipt=None, evaluation_receipt_signature=None))
    assert result.accepted is False
    assert "EVALUATION_RECEIPT_MISSING" in result.failed_checks


def test_gates_pass_refuses_an_unsigned_receipt() -> None:
    result = _gates(_valid_evidence(evaluation_receipt_signature=None))
    assert result.accepted is False
    assert "EVALUATION_RECEIPT_UNVERIFIED:RECEIPT_SIGNATURE_MISSING" in result.failed_checks


def test_gates_pass_requires_the_evidence_sha_to_match_the_receipt() -> None:
    result = _gates(_valid_evidence(evaluation_receipt_sha256="b" * 64))
    assert result.accepted is False
    assert result.failed_checks == ("EVALUATION_RECEIPT_SHA_MISMATCH",)


def test_gates_pass_refuses_a_resealed_receipt() -> None:
    altered = _RECEIPT.model_copy(update={"source_commit_sha": "9" * 40})
    resealed = altered.model_copy(update={"receipt_sha256": altered.computed_sha256()})
    result = _gates(
        _valid_evidence(
            evaluation_receipt=resealed, evaluation_receipt_sha256=resealed.receipt_sha256
        )
    )
    assert result.accepted is False
    assert "EVALUATION_RECEIPT_UNVERIFIED:SIGNATURE_RECEIPT_SHA_MISMATCH" in result.failed_checks
    assert "EVALUATION_RECEIPT_UNVERIFIED:SIGNATURE_INVALID" in result.failed_checks


def test_gates_pass_refuses_a_signature_from_an_unlisted_key() -> None:
    other_key, _ = throwaway_approver("operator-1")
    forged = sign_receipt_sha256(
        other_key, key_id="operator-1", receipt_sha256=_RECEIPT.receipt_sha256
    )
    result = _gates(_valid_evidence(evaluation_receipt_signature=forged))
    assert result.accepted is False
    assert "EVALUATION_RECEIPT_UNVERIFIED:SIGNATURE_INVALID" in result.failed_checks


def test_gates_pass_refuses_a_revoked_key(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    revoked = _APPROVER_ENTRY.model_copy(update={"revoked_at": "2026-10-25T00:00:00Z"})
    install_allowlist(monkeypatch, tmp_path, revoked)
    result = _gates(_valid_evidence())
    assert result.accepted is False
    assert "EVALUATION_RECEIPT_UNVERIFIED:APPROVER_KEY_REVOKED" in result.failed_checks


def test_gates_pass_refuses_with_the_committed_empty_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import intelligence.receipt_signing as receipt_signing

    monkeypatch.setattr(
        receipt_signing,
        "APPROVER_ALLOWLIST_PATH",
        Path(receipt_signing.__file__).with_name("evaluation_approvers.json"),
    )
    result = _gates(_valid_evidence())
    assert result.accepted is False
    assert "EVALUATION_RECEIPT_UNVERIFIED:APPROVER_KEY_UNKNOWN" in result.failed_checks


def test_beta_ready_is_final() -> None:
    evidence = _valid_evidence()
    for event in ReadinessEvent:
        result = readiness_transition(ReadinessState.BETA_READY, event, evidence)
        assert result.accepted is False, event
        assert result.from_state is ReadinessState.BETA_READY
        assert result.to_state is ReadinessState.BETA_READY
        assert result.failed_checks == ("BETA_READY_FINAL",)


def test_production_claims_only_permitted_at_beta_ready() -> None:
    for state in READINESS_ORDER:
        expected = state is ReadinessState.BETA_READY
        assert production_claims_permitted(state) == expected, state


def test_live_payments_and_d1_never_permitted() -> None:
    for state in READINESS_ORDER:
        assert live_payments_permitted(state) is False, state
        assert d1_permitted(state) is False, state


def test_config_gate_checks_default_settings(clean_env: None) -> None:
    settings = Settings()
    checks = config_gate_checks(settings, expected_frontend_origin=None)
    by_code = {check.code: check for check in checks}

    assert by_code["PAYMENTS_LIVE_DISABLED"].passed is True
    assert by_code["STRIPE_TEST_MODE"].passed is True
    assert by_code["CLEF_FLAG_DEFAULT_OFF"].passed is True
    assert by_code["CLEF_FAIL_CLOSED_CONFIG"].passed is True
    assert by_code["CORS_EXACT_ORIGIN"].passed is False
    assert "OPERATOR_LOCKED" in by_code["CORS_EXACT_ORIGIN"].detail
    assert by_code["NO_D1_BINDING"].passed is True


def test_cors_exact_origin_passes(clean_env: None) -> None:
    settings = Settings(cors_origins=["https://app.example.test"])
    checks = config_gate_checks(
        settings, expected_frontend_origin="https://app.example.test"
    )
    by_code = {check.code: check for check in checks}
    assert by_code["CORS_EXACT_ORIGIN"].passed is True


def test_cors_wildcard_fails(clean_env: None) -> None:
    settings = Settings(cors_origins=["*"])
    checks = config_gate_checks(
        settings, expected_frontend_origin="https://app.example.test"
    )
    by_code = {check.code: check for check in checks}
    cors_check = by_code["CORS_EXACT_ORIGIN"]
    assert cors_check.passed is False
    assert "wildcard" in cors_check.detail.lower()


def test_cors_path_origin_fails(clean_env: None) -> None:
    settings = Settings(cors_origins=["https://app.example.test/extra"])
    checks = config_gate_checks(
        settings, expected_frontend_origin="https://app.example.test/extra"
    )
    by_code = {check.code: check for check in checks}
    cors_check = by_code["CORS_EXACT_ORIGIN"]
    assert cors_check.passed is False
    assert "path-free" in cors_check.detail


def test_clef_enabled_without_credentials_fails(clean_env: None) -> None:
    settings = Settings(enable_clef_provider=True)
    checks = config_gate_checks(settings, expected_frontend_origin=None)
    by_code = {check.code: check for check in checks}
    clef_check = by_code["CLEF_FAIL_CLOSED_CONFIG"]
    assert clef_check.passed is False
    assert "missing_or_invalid" in clef_check.detail


def test_clef_with_credentials_passes_and_no_secret_leak(clean_env: None) -> None:
    settings = Settings(
        enable_clef_provider=True,
        cloudflare_account_id="acct",
        cloudflare_ai_api_token="secret-token-value",
    )
    checks = config_gate_checks(settings, expected_frontend_origin=None)
    by_code = {check.code: check for check in checks}
    assert by_code["CLEF_FAIL_CLOSED_CONFIG"].passed is True
    assert "secret-token-value" not in str(summarize(checks))


def test_the_api_must_be_the_staging_environment() -> None:
    # The readiness drills run on the staging pair, never on production (2026-10-27).
    result = readiness_transition(
        ReadinessState.FRONTEND_ATTACHED,
        ReadinessEvent.API_PUBLISHED,
        _valid_evidence(api_environment_staging=False),
    )
    assert result.accepted is False
    assert result.to_state is ReadinessState.FRONTEND_ATTACHED
    assert result.failed_checks == ("API_ENVIRONMENT_NOT_STAGING",)
