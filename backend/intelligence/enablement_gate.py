"""Gate the decision runtime on a signed spec 007 receipt (spec 005 T080, research R1).

Outside development and test, a decision provider may run only when a signed
``EvaluationEnablementReceipt`` verifies against the committed approver allowlist
(007 T081) and names the configured provider and ``decision_policy_version``.
Startup refuses otherwise, and the decision route answers 409
``ENABLEMENT_RECEIPT_REQUIRED`` as defence in depth. Production refuses decision
providers outright (``core.startup_policy``), so in practice this gates staging.

The receipt and its signature are JSON files named by
``DECISION_ENABLEMENT_RECEIPT_PATH`` and ``DECISION_ENABLEMENT_SIGNATURE_PATH``.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from intelligence.evaluation_enablement import (
    EvaluationEnablementReceipt,
    signed_enablement_receipt_failures,
)
from intelligence.receipt_signing import ApproverAllowlist, ReceiptSignature

UNGATED_ENVIRONMENTS = frozenset({"development", "dev", "test", "testing"})
DECISION_FLAGS = ("enable_decision_intelligence", "enable_clef_provider")


def decision_runtime_requested(app_settings: Any) -> bool:
    """True when any decision flag is on or a provider is selected."""
    provider = str(getattr(app_settings, "decision_provider", "disabled") or "disabled").lower()
    return provider != "disabled" or any(bool(getattr(app_settings, f, False)) for f in DECISION_FLAGS)


def _environment(app_settings: Any) -> str:
    return str(getattr(app_settings, "environment", "development") or "development").strip().lower()


def _read_json(path_value: str, missing: str, unreadable: str) -> tuple[Any, str | None]:
    if not path_value:
        return None, missing
    try:
        return json.loads(Path(path_value).read_text(encoding="utf-8")), None
    except (OSError, ValueError):
        return None, unreadable


def enablement_gate_failures(
    app_settings: Any,
    *,
    allowlist: ApproverAllowlist | None = None,
    now: datetime | None = None,
) -> tuple[str, ...]:
    """Failure codes; empty means the decision runtime may run in this environment."""
    if _environment(app_settings) in UNGATED_ENVIRONMENTS or not decision_runtime_requested(app_settings):
        return ()
    receipt_raw, receipt_error = _read_json(
        str(getattr(app_settings, "decision_enablement_receipt_path", "") or ""),
        "ENABLEMENT_RECEIPT_NOT_CONFIGURED",
        "ENABLEMENT_RECEIPT_UNREADABLE",
    )
    signature_raw, signature_error = _read_json(
        str(getattr(app_settings, "decision_enablement_signature_path", "") or ""),
        "ENABLEMENT_SIGNATURE_NOT_CONFIGURED",
        "ENABLEMENT_SIGNATURE_UNREADABLE",
    )
    failures = [code for code in (receipt_error, signature_error) if code]
    if failures:
        return tuple(failures)
    try:
        receipt = EvaluationEnablementReceipt.model_validate(receipt_raw)
    except ValidationError:
        return ("ENABLEMENT_RECEIPT_INVALID",)
    try:
        signature = ReceiptSignature.model_validate(signature_raw)
    except ValidationError:
        return ("ENABLEMENT_SIGNATURE_INVALID",)
    failures.extend(signed_enablement_receipt_failures(receipt, signature, allowlist=allowlist, now=now))
    provider = str(getattr(app_settings, "decision_provider", "disabled") or "disabled").lower()
    if provider not in {p.lower() for p in receipt.providers}:
        failures.append("ENABLEMENT_PROVIDER_NOT_COVERED")
    if receipt.policy_version != str(getattr(app_settings, "decision_policy_version", "")):
        failures.append("ENABLEMENT_POLICY_VERSION_MISMATCH")
    return tuple(dict.fromkeys(failures))


def validate_decision_enablement_startup(app_settings: Any) -> None:
    """Refuse to start when a decision provider is on without a valid signed receipt."""
    failures = enablement_gate_failures(app_settings)
    if failures:
        raise RuntimeError(
            "refusing to start: a decision provider is on in "
            f"{_environment(app_settings)} without a valid signed spec 007 enablement receipt ("
            + ", ".join(failures)
            + ")"
        )
