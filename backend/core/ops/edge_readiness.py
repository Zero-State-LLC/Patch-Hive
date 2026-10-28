"""Edge deployment readiness state machine (Spec 006, T070).

The machine tracks the staging pair chosen 2026-10-27 (docs/evidence/STAGING_HOST_PLAN.md):
the staging frontend Worker on staging.patch-hive.com and the staging API Worker on
api-staging.patch-hive.com, whose container reaches the Neon staging branch through its
pooled endpoint (FR-003 as amended 2026-10-26: Hyperdrive cannot serve a container, and
the SPA ships on Workers rather than Pages). T030/T040/T050 are operator-driven
Cloudflare actions. This module only evaluates
receipted evidence: it performs no network, database, or Cloudflare calls.
The public API hostname and the Tunnel-vs-Containers choice are operator-locked.

Live payments, D1, and production-readiness claims remain forbidden until the
readiness machine reaches BETA_READY via an explicit operator approval, and
live-payments / D1 stay forbidden even then (out of scope for 006).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def is_valid_receipt_sha(value: str) -> bool:
    """True when value is exactly 64 lowercase hexadecimal characters."""
    return isinstance(value, str) and _SHA256_RE.match(value) is not None


class ReadinessState(str, Enum):
    """Edge deployment readiness states, in linear order."""

    UNCONFIGURED = "UNCONFIGURED"
    FRONTEND_ATTACHED = "FRONTEND_ATTACHED"
    API_HOSTNAME_LIVE = "API_HOSTNAME_LIVE"
    DATABASE_BOUND = "DATABASE_BOUND"
    CLEF_FLAGGED = "CLEF_FLAGGED"
    GATES_PASSED = "GATES_PASSED"
    BETA_READY = "BETA_READY"


READINESS_ORDER: tuple[ReadinessState, ...] = (
    ReadinessState.UNCONFIGURED,
    ReadinessState.FRONTEND_ATTACHED,
    ReadinessState.API_HOSTNAME_LIVE,
    ReadinessState.DATABASE_BOUND,
    ReadinessState.CLEF_FLAGGED,
    ReadinessState.GATES_PASSED,
    ReadinessState.BETA_READY,
)


class ReadinessEvent(str, Enum):
    """Events driving the readiness machine."""

    FRONTEND_DEPLOYED = "frontend_deployed"
    API_PUBLISHED = "api_published"
    DATABASE_BOUND = "database_bound"
    CLEF_ADAPTER_WIRED = "clef_adapter_wired"
    GATES_PASS = "gates_pass"
    OPERATOR_APPROVE = "operator_approve"


@dataclass(frozen=True)
class ReadinessEvidence:
    """Operator-supplied and receipted facts about the deployment.

    Every field is a caller assertion; nothing here is probed live.
    """

    frontend_build_output_present: bool = False
    frontend_custom_domain_attached: bool = False
    api_cors_exact_origin: bool = False
    api_environment_staging: bool = False
    api_health_ok: bool = False
    payments_live_disabled: bool = False
    database_neon_staging_pooled: bool = False
    d1_absent: bool = False
    clef_flag_default_off: bool = False
    staging_host_plan_passed: bool = False
    evaluation_receipt_sha256: str = ""
    operator_approved: bool = False
    checklist_receipts: tuple[str, ...] = ()


Guard = Callable[[ReadinessEvidence], tuple[str, ...]]


def _guard_frontend_deployed(ev: ReadinessEvidence) -> tuple[str, ...]:
    failed: list[str] = []
    if not ev.frontend_build_output_present:
        failed.append("FRONTEND_BUILD_OUTPUT_MISSING")
    if not ev.frontend_custom_domain_attached:
        failed.append("FRONTEND_CUSTOM_DOMAIN_MISSING")
    return tuple(failed)


def _guard_api_published(ev: ReadinessEvidence) -> tuple[str, ...]:
    failed: list[str] = []
    if not ev.api_cors_exact_origin:
        failed.append("API_CORS_ORIGIN_NOT_EXACT")
    if not ev.api_environment_staging:
        # Drills (007 enablement, 008 walkthrough) run here, never on production.
        failed.append("API_ENVIRONMENT_NOT_STAGING")
    if not ev.api_health_ok:
        failed.append("API_HEALTH_NOT_OK")
    if not ev.payments_live_disabled:
        failed.append("PAYMENTS_LIVE_ENABLED")
    return tuple(failed)


def _guard_database_bound(ev: ReadinessEvidence) -> tuple[str, ...]:
    failed: list[str] = []
    if not ev.database_neon_staging_pooled:
        failed.append("DATABASE_NOT_NEON_STAGING_POOLED")
    if not ev.d1_absent:
        failed.append("D1_BINDING_PRESENT")
    return tuple(failed)


def _guard_clef_adapter_wired(ev: ReadinessEvidence) -> tuple[str, ...]:
    failed: list[str] = []
    if not ev.clef_flag_default_off:
        failed.append("CLEF_FLAG_NOT_DEFAULT_OFF")
    return tuple(failed)


def _invariant_failures(ev: ReadinessEvidence) -> list[str]:
    """Invariants re-checked on every later transition so regressions block."""
    failed: list[str] = []
    if not ev.payments_live_disabled:
        failed.append("INVARIANT_PAYMENTS_LIVE_ENABLED")
    if not ev.d1_absent:
        failed.append("INVARIANT_D1_BINDING_PRESENT")
    if not ev.clef_flag_default_off:
        failed.append("INVARIANT_CLEF_FLAG_NOT_DEFAULT_OFF")
    return failed


def _guard_gates_pass(ev: ReadinessEvidence) -> tuple[str, ...]:
    failed = _invariant_failures(ev)
    if not ev.staging_host_plan_passed:
        failed.append("STAGING_HOST_PLAN_NOT_PASSED")
    if not is_valid_receipt_sha(ev.evaluation_receipt_sha256):
        failed.append("EVALUATION_RECEIPT_SHA_INVALID")
    return tuple(failed)


def _guard_operator_approve(ev: ReadinessEvidence) -> tuple[str, ...]:
    failed = _invariant_failures(ev)
    if not ev.operator_approved:
        failed.append("OPERATOR_APPROVAL_MISSING")
    if not ev.checklist_receipts:
        failed.append("CHECKLIST_RECEIPTS_EMPTY")
    return tuple(failed)


GUARDS: Mapping[
    tuple[ReadinessState, ReadinessEvent], tuple[ReadinessState, Guard]
] = MappingProxyType({
    (ReadinessState.UNCONFIGURED, ReadinessEvent.FRONTEND_DEPLOYED): (
        ReadinessState.FRONTEND_ATTACHED,
        _guard_frontend_deployed,
    ),
    (ReadinessState.FRONTEND_ATTACHED, ReadinessEvent.API_PUBLISHED): (
        ReadinessState.API_HOSTNAME_LIVE,
        _guard_api_published,
    ),
    (ReadinessState.API_HOSTNAME_LIVE, ReadinessEvent.DATABASE_BOUND): (
        ReadinessState.DATABASE_BOUND,
        _guard_database_bound,
    ),
    (ReadinessState.DATABASE_BOUND, ReadinessEvent.CLEF_ADAPTER_WIRED): (
        ReadinessState.CLEF_FLAGGED,
        _guard_clef_adapter_wired,
    ),
    (ReadinessState.CLEF_FLAGGED, ReadinessEvent.GATES_PASS): (
        ReadinessState.GATES_PASSED,
        _guard_gates_pass,
    ),
    (ReadinessState.GATES_PASSED, ReadinessEvent.OPERATOR_APPROVE): (
        ReadinessState.BETA_READY,
        _guard_operator_approve,
    ),
})


@dataclass(frozen=True)
class ReadinessResult:
    """Outcome of one readiness transition attempt."""

    from_state: ReadinessState
    event: ReadinessEvent
    to_state: ReadinessState
    accepted: bool
    failed_checks: tuple[str, ...] = ()


def readiness_transition(
    state: ReadinessState,
    event: ReadinessEvent,
    evidence: ReadinessEvidence,
) -> ReadinessResult:
    """Pure guarded transition. State advances only when the guard passes."""
    if state is ReadinessState.BETA_READY:
        return ReadinessResult(
            from_state=state,
            event=event,
            to_state=state,
            accepted=False,
            failed_checks=("BETA_READY_FINAL",),
        )
    entry = GUARDS.get((state, event))
    if entry is None:
        return ReadinessResult(
            from_state=state,
            event=event,
            to_state=state,
            accepted=False,
            failed_checks=("INVALID_TRANSITION",),
        )
    to_state, guard = entry
    failed = guard(evidence)
    if failed:
        return ReadinessResult(
            from_state=state,
            event=event,
            to_state=state,
            accepted=False,
            failed_checks=failed,
        )
    return ReadinessResult(
        from_state=state,
        event=event,
        to_state=to_state,
        accepted=True,
        failed_checks=(),
    )


def production_claims_permitted(state: ReadinessState) -> bool:
    """True only at BETA_READY; no production-readiness claim before."""
    return state is ReadinessState.BETA_READY


def live_payments_permitted(state: ReadinessState) -> bool:
    """Always False in Spec 006: live payments are out of scope even at BETA_READY."""
    return False


def d1_permitted(state: ReadinessState) -> bool:
    """Always False in Spec 006: no D1 migration. Architectural continuity is Neon."""
    return False


@dataclass(frozen=True)
class GateCheck:
    """One configuration gate result. `detail` must never contain secrets."""

    code: str
    passed: bool
    detail: str


def _class_default_enable_clef(settings_obj: Any) -> bool | None:
    """Class-level default of `enable_clef_provider`, if discoverable."""
    fields = getattr(type(settings_obj), "model_fields", None)
    if fields is not None:
        try:
            field_info = fields["enable_clef_provider"]
        except (KeyError, TypeError):
            field_info = None
        if field_info is not None:
            default = getattr(field_info, "default", None)
            if isinstance(default, bool):
                return default
    default = getattr(settings_obj, "enable_clef_provider", None)
    return default if isinstance(default, bool) else None


def config_gate_checks(
    settings_obj: Any,
    *,
    expected_frontend_origin: str | None,
) -> tuple[GateCheck, ...]:
    """Pure config gate checks over a settings-like object. No network, no secrets."""
    checks: list[GateCheck] = []

    allow_payments = bool(getattr(settings_obj, "allow_production_payments", False))
    checks.append(
        GateCheck(
            code="PAYMENTS_LIVE_DISABLED",
            passed=not allow_payments,
            detail=(
                "allow_production_payments is false"
                if not allow_payments
                else "allow_production_payments is true"
            ),
        )
    )

    test_mode = bool(getattr(settings_obj, "stripe_test_mode", False))
    checks.append(
        GateCheck(
            code="STRIPE_TEST_MODE",
            passed=test_mode,
            detail="stripe_test_mode is true" if test_mode else "stripe_test_mode is false",
        )
    )

    class_default = _class_default_enable_clef(settings_obj)
    checks.append(
        GateCheck(
            code="CLEF_FLAG_DEFAULT_OFF",
            passed=class_default is False,
            detail=(
                "enable_clef_provider class default is false"
                if class_default is False
                else "enable_clef_provider class default is not false"
            ),
        )
    )

    enabled = bool(getattr(settings_obj, "enable_clef_provider", False))
    if not enabled:
        clef_fail_closed = GateCheck(
            code="CLEF_FAIL_CLOSED_CONFIG",
            passed=True,
            detail="clef provider disabled; no credentials required",
        )
    else:
        missing: list[str] = []
        if not getattr(settings_obj, "cloudflare_account_id", ""):
            missing.append("cloudflare_account_id")
        if not getattr(settings_obj, "cloudflare_ai_api_token", ""):
            missing.append("cloudflare_ai_api_token")
        model = getattr(settings_obj, "clef_model", "")
        if model not in {"clef", "clef-flash"}:
            missing.append("clef_model")
        clef_fail_closed = GateCheck(
            code="CLEF_FAIL_CLOSED_CONFIG",
            passed=not missing,
            detail=(
                "clef provider configured"
                if not missing
                else "missing_or_invalid: " + ", ".join(missing)
            ),
        )
    checks.append(clef_fail_closed)

    origins = list(getattr(settings_obj, "cors_origins", []) or [])
    if expected_frontend_origin is None:
        cors_check = GateCheck(
            code="CORS_EXACT_ORIGIN",
            passed=False,
            detail="OPERATOR_LOCKED: frontend origin not provided",
        )
    elif "*" in origins:
        cors_check = GateCheck(
            code="CORS_EXACT_ORIGIN",
            passed=False,
            detail="wildcard origin present",
        )
    elif origins != [expected_frontend_origin]:
        cors_check = GateCheck(
            code="CORS_EXACT_ORIGIN",
            passed=False,
            detail=f"cors_origins must equal exactly [{expected_frontend_origin}]",
        )
    elif not expected_frontend_origin.startswith("https://"):
        cors_check = GateCheck(
            code="CORS_EXACT_ORIGIN",
            passed=False,
            detail="origin must use https",
        )
    elif expected_frontend_origin.count("/") != 2:
        cors_check = GateCheck(
            code="CORS_EXACT_ORIGIN",
            passed=False,
            detail="origin must be path-free",
        )
    else:
        cors_check = GateCheck(
            code="CORS_EXACT_ORIGIN",
            passed=True,
            detail=f"exact origin {expected_frontend_origin}",
        )
    checks.append(cors_check)

    d1_id = getattr(settings_obj, "d1_database_id", None)
    checks.append(
        GateCheck(
            code="NO_D1_BINDING",
            passed=not d1_id,
            detail=(
                "no D1 binding in backend config"
                if not d1_id
                else "D1 binding present in backend config"
            ),
        )
    )

    return tuple(checks)


def summarize(checks: Iterable[GateCheck]) -> dict[str, object]:
    """Compact summary of a set of gate checks."""
    materialized = tuple(checks)
    failed = [check.code for check in materialized if not check.passed]
    return {
        "passed": not failed,
        "failed": failed,
        "checks": [
            {"code": check.code, "passed": check.passed, "detail": check.detail}
            for check in materialized
        ],
    }


def replay_readiness(
    events: Iterable[tuple[ReadinessEvent, ReadinessEvidence]],
) -> tuple[ReadinessState, tuple[ReadinessResult, ...]]:
    """Fold a stream of receipted events from UNCONFIGURED.

    Rejected transitions are recorded but do not advance state; replay continues.
    """
    state = ReadinessState.UNCONFIGURED
    results: list[ReadinessResult] = []
    for event, evidence in events:
        result = readiness_transition(state, event, evidence)
        results.append(result)
        if result.accepted:
            state = result.to_state
    return state, tuple(results)
