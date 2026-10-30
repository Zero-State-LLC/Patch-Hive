"""Spec 007 T080 (verify by replay) and T081 (signed receipts).

Synthetic chain from tests/eval007_helpers.py. Approver keys are throwaway keys
generated in memory; nothing here touches the committed allowlist except the
test that loads it to prove it holds no keys.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import pytest

from intelligence.evaluation_enablement import (
    EnablementChain,
    enablement_receipt_failures,
    signed_enablement_receipt_failures,
    verify_enablement_receipt,
    verify_signed_enablement_receipt,
)
from intelligence.receipt_signing import (
    APPROVER_ALLOWLIST_PATH,
    APPROVER_ALLOWLIST_SCHEMA,
    SIGNING_DOMAIN,
    ApproverKey,
    ReceiptSignature,
    SignatureError,
    load_approver_allowlist,
    sign_receipt_sha256,
    signing_message,
)
from tests.eval007_helpers import (
    allowlist_of,
    build_receipt_chain,
    install_allowlist,
    throwaway_approver,
)

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def chain() -> dict:
    return build_receipt_chain()


@pytest.fixture(scope="module")
def approver():
    return throwaway_approver("operator-1")


def _records(chain: dict) -> EnablementChain:
    return EnablementChain(
        corpus=chain["corpus"],
        run=chain["run"],
        proposal=chain["proposal"],
        approval=chain["approval"],
        staging=chain["staging"],
    )


def _sign(key, receipt, key_id: str = "operator-1") -> ReceiptSignature:
    return sign_receipt_sha256(key, key_id=key_id, receipt_sha256=receipt.receipt_sha256)


# --- T080 verify by replay ---------------------------------------------------


def test_receipt_verifies_as_model_payload_and_by_replay(chain) -> None:
    receipt = chain["receipt"]
    assert verify_enablement_receipt(receipt)
    assert verify_enablement_receipt(receipt.as_payload())
    assert verify_enablement_receipt(receipt, chain=_records(chain))


def test_bare_mapping_with_matching_sha_is_refused(chain) -> None:
    from intelligence.clef_evaluation import receipt_sha256

    forged: dict[str, object] = {
        "schema_version": chain["receipt"].schema_version,
        "approved_by": "operator-1",
    }
    forged["receipt_sha256"] = receipt_sha256(forged)
    assert not verify_enablement_receipt(forged)
    assert enablement_receipt_failures(forged) == ("RECEIPT_SCHEMA_INVALID",)


def test_extra_or_coerced_fields_are_refused(chain) -> None:
    from intelligence.clef_evaluation import receipt_sha256

    extra = chain["receipt"].as_payload()
    extra["note"] = "x"
    extra["receipt_sha256"] = receipt_sha256(extra)
    assert enablement_receipt_failures(extra) == ("RECEIPT_SCHEMA_INVALID",)

    coerced = chain["receipt"].as_payload()
    coerced["baseline_metrics"]["case_count"] = str(coerced["baseline_metrics"]["case_count"])
    coerced["receipt_sha256"] = receipt_sha256(coerced)
    assert enablement_receipt_failures(coerced) == ("RECEIPT_NOT_CANONICAL",)


def test_unvalidated_model_copy_is_revalidated(chain) -> None:
    receipt = chain["receipt"]
    broken = receipt.model_copy(update={"environment": "production"})
    broken = broken.model_copy(update={"receipt_sha256": broken.computed_sha256()})
    assert enablement_receipt_failures(broken) == ("RECEIPT_SCHEMA_INVALID",)


def test_non_receipt_inputs_are_refused() -> None:
    assert enablement_receipt_failures(None) == ("RECEIPT_MISSING",)
    assert enablement_receipt_failures("a" * 64) == ("RECEIPT_NOT_A_RECEIPT",)  # type: ignore[arg-type]


def test_resealed_receipt_fails_replay(chain) -> None:
    altered = chain["receipt"].model_copy(update={"approved_by": "someone-else"})
    resealed = altered.model_copy(update={"receipt_sha256": altered.computed_sha256()})
    assert verify_enablement_receipt(resealed)  # self-consistent only
    assert enablement_receipt_failures(resealed, chain=_records(chain)) == (
        "RECEIPT_CONTENT_MISMATCH",
    )


def test_replay_against_a_broken_chain_is_refused(chain) -> None:
    records = _records(chain)
    tampered = EnablementChain(
        corpus=records.corpus,
        run=records.run,
        proposal=records.proposal,
        approval=records.approval.model_copy(update={"approved_by": "x"}),
        staging=records.staging,
    )
    failures = enablement_receipt_failures(chain["receipt"], chain=tampered)
    assert failures == ("RECEIPT_CHAIN_INVALID:CHAIN_RECORD_MISSING_OR_TAMPERED",)


# --- T081 signatures -----------------------------------------------------------


def test_signed_receipt_verifies(chain, approver) -> None:
    key, entry = approver
    receipt = chain["receipt"]
    signature = _sign(key, receipt)
    allowlist = allowlist_of(entry)
    assert verify_signed_enablement_receipt(receipt, signature, allowlist=allowlist, now=NOW)
    assert verify_signed_enablement_receipt(
        receipt, signature, allowlist=allowlist, chain=_records(chain), now=NOW
    )


def test_signature_message_is_domain_separated(chain) -> None:
    sha = chain["receipt"].receipt_sha256
    assert signing_message(sha) == SIGNING_DOMAIN + sha.encode("ascii")
    with pytest.raises(SignatureError):
        signing_message("A" * 64)


def test_missing_signature_refuses(chain, approver) -> None:
    _, entry = approver
    failures = signed_enablement_receipt_failures(
        chain["receipt"], None, allowlist=allowlist_of(entry), now=NOW
    )
    assert failures == ("RECEIPT_SIGNATURE_MISSING",)


def test_unknown_key_refuses(chain, approver) -> None:
    key, _ = approver
    _, other_entry = throwaway_approver("operator-2")
    failures = signed_enablement_receipt_failures(
        chain["receipt"], _sign(key, chain["receipt"]), allowlist=allowlist_of(other_entry), now=NOW
    )
    assert failures == ("APPROVER_KEY_UNKNOWN",)


def test_signing_key_must_be_the_receipt_approver(chain) -> None:
    key, entry = throwaway_approver("operator-2")
    failures = signed_enablement_receipt_failures(
        chain["receipt"],
        _sign(key, chain["receipt"], key_id="operator-2"),
        allowlist=allowlist_of(entry),
        now=NOW,
    )
    assert failures == ("SIGNATURE_KEY_NOT_APPROVER",)


def test_wrong_private_key_refuses(chain, approver) -> None:
    _, entry = approver
    impostor, _ = throwaway_approver("operator-1")
    failures = signed_enablement_receipt_failures(
        chain["receipt"], _sign(impostor, chain["receipt"]), allowlist=allowlist_of(entry), now=NOW
    )
    assert failures == ("SIGNATURE_INVALID",)


def test_signature_for_another_sha_refuses(chain, approver) -> None:
    key, entry = approver
    other = sign_receipt_sha256(key, key_id="operator-1", receipt_sha256="c" * 64)
    failures = signed_enablement_receipt_failures(
        chain["receipt"], other, allowlist=allowlist_of(entry), now=NOW
    )
    assert failures == ("SIGNATURE_RECEIPT_SHA_MISMATCH", "SIGNATURE_INVALID")


def test_signature_without_domain_prefix_refuses(chain, approver) -> None:
    key, entry = approver
    sha = chain["receipt"].receipt_sha256
    raw = key.sign(sha.encode("ascii"))
    bare = ReceiptSignature(
        key_id="operator-1", receipt_sha256=sha, signature=base64.b64encode(raw).decode("ascii")
    )
    failures = signed_enablement_receipt_failures(
        chain["receipt"], bare, allowlist=allowlist_of(entry), now=NOW
    )
    assert failures == ("SIGNATURE_INVALID",)


def test_resealed_receipt_refuses_even_with_the_old_signature(chain, approver) -> None:
    key, entry = approver
    signature = _sign(key, chain["receipt"])
    altered = chain["receipt"].model_copy(update={"source_commit_sha": "9" * 40})
    resealed = altered.model_copy(update={"receipt_sha256": altered.computed_sha256()})
    failures = signed_enablement_receipt_failures(
        resealed, signature, allowlist=allowlist_of(entry), now=NOW
    )
    assert "SIGNATURE_RECEIPT_SHA_MISMATCH" in failures
    assert "SIGNATURE_INVALID" in failures


def test_tampered_receipt_refuses_before_the_signature(chain, approver) -> None:
    key, entry = approver
    payload = chain["receipt"].as_payload()
    payload["thresholds"]["top1_min"] = 0.0
    failures = signed_enablement_receipt_failures(
        payload, _sign(key, chain["receipt"]), allowlist=allowlist_of(entry), now=NOW
    )
    assert failures == ("RECEIPT_SHA_MISMATCH",)


@pytest.mark.parametrize(
    "revoked_at",
    [
        "2026-10-20T00:00:00Z",  # revoked before approved_at (2026-10-24)
        "2026-10-26T00:00:00Z",  # revoked after approval, before verification
        "2026-10-29T12:00:00Z",  # revoked exactly at verification time
    ],
)
def test_revoked_key_refuses(chain, approver, revoked_at: str) -> None:
    key, entry = approver
    revoked = entry.model_copy(update={"revoked_at": revoked_at})
    failures = signed_enablement_receipt_failures(
        chain["receipt"], _sign(key, chain["receipt"]), allowlist=allowlist_of(revoked), now=NOW
    )
    assert failures == ("APPROVER_KEY_REVOKED",)


def test_key_with_future_revocation_still_verifies(chain, approver) -> None:
    key, entry = approver
    scheduled = entry.model_copy(update={"revoked_at": "2027-01-01T00:00:00Z"})
    assert verify_signed_enablement_receipt(
        chain["receipt"], _sign(key, chain["receipt"]), allowlist=allowlist_of(scheduled), now=NOW
    )


@pytest.mark.parametrize(
    "valid_from",
    [
        "2026-10-25T00:00:00Z",  # after approved_at
        "2026-11-01T00:00:00Z",  # after verification time
    ],
)
def test_key_not_yet_valid_refuses(chain, valid_from: str) -> None:
    key, entry = throwaway_approver("operator-1", valid_from=valid_from)
    failures = signed_enablement_receipt_failures(
        chain["receipt"], _sign(key, chain["receipt"]), allowlist=allowlist_of(entry), now=NOW
    )
    assert failures == ("APPROVER_KEY_NOT_YET_VALID",)


def test_naive_verification_time_refuses(chain, approver) -> None:
    key, entry = approver
    failures = signed_enablement_receipt_failures(
        chain["receipt"],
        _sign(key, chain["receipt"]),
        allowlist=allowlist_of(entry),
        now=datetime(2026, 10, 29, 12, 0),
    )
    assert failures == ("VERIFICATION_TIME_INVALID",)


def test_tampered_signature_model_copy_is_revalidated(chain, approver) -> None:
    key, entry = approver
    signature = _sign(key, chain["receipt"]).model_copy(update={"signature": "not-base64!"})
    failures = signed_enablement_receipt_failures(
        chain["receipt"], signature, allowlist=allowlist_of(entry), now=NOW
    )
    assert failures == ("RECEIPT_SIGNATURE_MALFORMED",)


# --- allowlist format and loader ------------------------------------------------


def test_committed_allowlist_loads_and_holds_no_keys() -> None:
    allowlist = load_approver_allowlist(APPROVER_ALLOWLIST_PATH)
    assert allowlist.schema_version == APPROVER_ALLOWLIST_SCHEMA
    # T082 (operator) adds the first reviewed public key. Until then nothing verifies.
    assert allowlist.approvers == ()
    text = APPROVER_ALLOWLIST_PATH.read_text(encoding="utf-8")
    assert "PRIVATE KEY" not in text


def test_committed_allowlist_refuses_every_signature(chain, approver) -> None:
    key, _ = approver
    failures = signed_enablement_receipt_failures(
        chain["receipt"], _sign(key, chain["receipt"]), now=NOW
    )
    assert failures == ("APPROVER_KEY_UNKNOWN",)


def test_installed_allowlist_is_used_by_default(chain, approver, monkeypatch, tmp_path) -> None:
    key, entry = approver
    install_allowlist(monkeypatch, tmp_path, entry)
    assert verify_signed_enablement_receipt(chain["receipt"], _sign(key, chain["receipt"]), now=NOW)


def test_unreadable_or_invalid_allowlist_refuses(chain, approver, monkeypatch, tmp_path) -> None:
    import intelligence.receipt_signing as receipt_signing

    key, entry = approver
    signature = _sign(key, chain["receipt"])

    monkeypatch.setattr(receipt_signing, "APPROVER_ALLOWLIST_PATH", tmp_path / "missing.json")
    assert signed_enablement_receipt_failures(chain["receipt"], signature, now=NOW) == (
        "APPROVER_ALLOWLIST_UNREADABLE",
    )

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(receipt_signing, "APPROVER_ALLOWLIST_PATH", bad)
    assert signed_enablement_receipt_failures(chain["receipt"], signature, now=NOW) == (
        "APPROVER_ALLOWLIST_UNREADABLE",
    )

    duplicate = tmp_path / "dup.json"
    duplicate.write_text(
        json.dumps(
            {
                "schema_version": APPROVER_ALLOWLIST_SCHEMA,
                "approvers": [entry.model_dump(), entry.model_dump()],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(receipt_signing, "APPROVER_ALLOWLIST_PATH", duplicate)
    assert signed_enablement_receipt_failures(chain["receipt"], signature, now=NOW) == (
        "APPROVER_ALLOWLIST_INVALID",
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"key_id": "Operator 1"},
        {"public_key": "AAAA"},
        {"public_key": "not base64"},
        {"valid_from": "2026-01-01T00:00:00"},
        {"revoked_at": "2025-12-31T00:00:00Z"},
        {"algorithm": "rsa"},
    ],
)
def test_malformed_approver_entries_are_rejected(approver, overrides: dict) -> None:
    _, entry = approver
    with pytest.raises(ValueError):
        ApproverKey.model_validate({**entry.model_dump(), **overrides})
