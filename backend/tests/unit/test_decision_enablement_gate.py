"""Spec 005 T080 (research R1): the decision runtime needs a signed 007 receipt.

Outside development and test, with any decision flag on or a provider selected,
startup refuses and the decision route answers 409 ``ENABLEMENT_RECEIPT_REQUIRED``
unless a signed receipt verifies against the approver allowlist and names the
configured provider and policy version. The receipt chain is the synthetic 007
chain; the approver key is a throwaway generated in memory.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from intelligence.enablement_gate import (
    enablement_gate_failures,
    validate_decision_enablement_startup,
)
from intelligence.receipt_signing import sign_receipt_sha256
from tests.eval007_helpers import build_receipt_chain, install_allowlist, throwaway_approver

_RECEIPT = build_receipt_chain()["receipt"]
_KEY, _ENTRY = throwaway_approver("operator-1")
_SIGNATURE = sign_receipt_sha256(_KEY, key_id="operator-1", receipt_sha256=_RECEIPT.receipt_sha256)


@pytest.fixture(autouse=True)
def approver_allowlist(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    install_allowlist(monkeypatch, tmp_path, _ENTRY)


@pytest.fixture
def files(tmp_path):
    receipt = tmp_path / "receipt.json"
    signature = tmp_path / "receipt.sig.json"
    receipt.write_text(json.dumps(_RECEIPT.as_payload()), encoding="utf-8")
    signature.write_text(_SIGNATURE.model_dump_json(), encoding="utf-8")
    return receipt, signature


def _settings(files=None, **overrides) -> SimpleNamespace:
    values = {
        "environment": "staging",
        "enable_decision_intelligence": True,
        "enable_clef_provider": True,
        "decision_provider": "clef",
        "decision_policy_version": _RECEIPT.policy_version,
        "decision_enablement_receipt_path": str(files[0]) if files else "",
        "decision_enablement_signature_path": str(files[1]) if files else "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_a_signed_receipt_naming_the_provider_and_policy_passes(files) -> None:
    assert _RECEIPT.providers == ("clef",)
    assert enablement_gate_failures(_settings(files)) == ()
    validate_decision_enablement_startup(_settings(files))


@pytest.mark.parametrize("environment", ["development", "test"])
def test_development_and_test_are_not_gated(environment) -> None:
    assert enablement_gate_failures(_settings(environment=environment)) == ()


def test_nothing_is_gated_while_every_decision_setting_is_off() -> None:
    off = _settings(enable_decision_intelligence=False, enable_clef_provider=False, decision_provider="disabled")
    assert enablement_gate_failures(off) == ()


@pytest.mark.parametrize(
    "overrides",
    [
        {"enable_decision_intelligence": True, "enable_clef_provider": False, "decision_provider": "disabled"},
        {"enable_decision_intelligence": False, "enable_clef_provider": True, "decision_provider": "disabled"},
        {"enable_decision_intelligence": False, "enable_clef_provider": False, "decision_provider": "jev"},
    ],
)
def test_any_decision_setting_requires_the_receipt(overrides) -> None:
    failures = enablement_gate_failures(_settings(**overrides))
    assert failures == ("ENABLEMENT_RECEIPT_NOT_CONFIGURED", "ENABLEMENT_SIGNATURE_NOT_CONFIGURED")
    with pytest.raises(RuntimeError, match="ENABLEMENT_RECEIPT_NOT_CONFIGURED"):
        validate_decision_enablement_startup(_settings(**overrides))


def test_unreadable_and_invalid_files_are_refused(files, tmp_path) -> None:
    missing = _settings(files, decision_enablement_receipt_path=str(tmp_path / "nope.json"))
    assert enablement_gate_failures(missing) == ("ENABLEMENT_RECEIPT_UNREADABLE",)
    files[0].write_text('{"schema_version": "x"}', encoding="utf-8")
    assert enablement_gate_failures(_settings(files)) == ("ENABLEMENT_RECEIPT_INVALID",)


def test_a_receipt_for_another_provider_or_policy_is_refused(files) -> None:
    assert "ENABLEMENT_PROVIDER_NOT_COVERED" in enablement_gate_failures(_settings(files, decision_provider="jev"))
    assert enablement_gate_failures(_settings(files, decision_policy_version="decision-policy-v9")) == (
        "ENABLEMENT_POLICY_VERSION_MISMATCH",
    )


def test_an_unsigned_or_wrongly_signed_receipt_is_refused(files) -> None:
    other_key, _ = throwaway_approver("operator-1")
    forged = sign_receipt_sha256(other_key, key_id="operator-1", receipt_sha256=_RECEIPT.receipt_sha256)
    files[1].write_text(forged.model_dump_json(), encoding="utf-8")
    failures = enablement_gate_failures(_settings(files))
    assert failures and "ENABLEMENT_PROVIDER_NOT_COVERED" not in failures
    with pytest.raises(RuntimeError, match="refusing to start"):
        validate_decision_enablement_startup(_settings(files))


def test_a_tampered_receipt_is_refused(files) -> None:
    payload = _RECEIPT.as_payload()
    payload["policy_version"] = "decision-policy-v2"
    files[0].write_text(json.dumps(payload), encoding="utf-8")
    assert enablement_gate_failures(_settings(files, decision_policy_version="decision-policy-v2"))


def test_the_decision_route_answers_409_when_the_gate_fails(monkeypatch) -> None:
    from fastapi import HTTPException

    import evidence.routes as routes

    gated = _settings()
    monkeypatch.setattr(routes, "settings", gated)
    monkeypatch.setattr(routes, "owned_private_rack", lambda *a, **k: None)

    class _Db:
        def get(self, model, key):
            return SimpleNamespace(image_asset_id=1, rack_id=7, deleted_at=None)

    body = SimpleNamespace(evidence_id="ev-1")
    with pytest.raises(HTTPException) as exc:
        routes.resolve_rack_evidence_decision(7, body, db=_Db(), current_user=None)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "ENABLEMENT_RECEIPT_REQUIRED"
    assert "ENABLEMENT_RECEIPT_NOT_CONFIGURED" in exc.value.detail["failures"]
