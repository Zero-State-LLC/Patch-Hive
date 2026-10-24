"""Unit tests for edge readiness state machine and config gates (Spec 006, T070)."""

from __future__ import annotations

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

_FIXED_RECEIPT_SHA = "a" * 64

_VALID_PAIRS = {
    (ReadinessState.UNCONFIGURED, ReadinessEvent.PAGES_DEPLOYED),
    (ReadinessState.PAGES_ATTACHED, ReadinessEvent.API_PUBLISHED),
    (ReadinessState.API_HOSTNAME_LIVE, ReadinessEvent.HYPERDRIVE_BOUND),
    (ReadinessState.HYPERDRIVE_BOUND, ReadinessEvent.CLEF_ADAPTER_WIRED),
    (ReadinessState.CLEF_FLAGGED, ReadinessEvent.GATES_PASS),
    (ReadinessState.GATES_PASSED, ReadinessEvent.OPERATOR_APPROVE),
}


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove settings-relevant env vars before constructing Settings."""
    for name in ("ENABLE_CLEF_PROVIDER", "CORS_ORIGINS", "ALLOW_PRODUCTION_PAYMENTS"):
        monkeypatch.delenv(name, raising=False)


def _valid_evidence(**overrides: object) -> ReadinessEvidence:
    fields: dict[str, object] = {
        "pages_build_output_present": True,
        "pages_custom_domain_attached": True,
        "api_cors_exact_origin": True,
        "api_health_ok": True,
        "payments_live_disabled": True,
        "hyperdrive_neon_staging": True,
        "d1_absent": True,
        "clef_flag_default_off": True,
        "staging_host_plan_passed": True,
        "evaluation_receipt_sha256": _FIXED_RECEIPT_SHA,
        "operator_approved": True,
        "checklist_receipts": ("receipt-1",),
    }
    fields.update(overrides)
    return ReadinessEvidence(**fields)  # type: ignore[arg-type]


def _happy_path_events() -> list[tuple[ReadinessEvent, ReadinessEvidence]]:
    return [
        (ReadinessEvent.PAGES_DEPLOYED, _valid_evidence()),
        (ReadinessEvent.API_PUBLISHED, _valid_evidence()),
        (ReadinessEvent.HYPERDRIVE_BOUND, _valid_evidence()),
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
        ReadinessState.PAGES_ATTACHED,
        ReadinessState.API_HOSTNAME_LIVE,
        ReadinessState.HYPERDRIVE_BOUND,
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
