"""Spec 007 T020-T060: baseline run, thresholds, approval, staging, receipt."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from core.config import Settings
from intelligence.clef_evaluation import OperatorThresholds
from intelligence.evaluation_corpus import freeze_corpus
from intelligence.evaluation_enablement import (
    ENABLEMENT_RECEIPT_SCHEMA,
    PROPOSAL_RULE,
    EnablementError,
    ProposedThresholds,
    approve_thresholds,
    enable_staging,
    expected_calibration_error,
    harness_source_sha256,
    is_pinned_sha,
    pin_receipt,
    propose_thresholds,
    run_baseline_comparison,
    structural_false_canonicalizations,
    verify_enablement_receipt,
)
from tests.eval007_helpers import (
    APPROVED_AT,
    HARNESS_SHA,
    POLICY,
    SOURCE_SHA,
    admitted_manifest,
    assisted_cases,
    baseline_cases,
    settings_namespace,
    staging_settings,
)


@pytest.fixture()
def manifest() -> dict:
    return admitted_manifest()


@pytest.fixture()
def corpus(manifest):
    return freeze_corpus(manifest)


def _run(corpus, manifest, *, degrade: bool = False):
    return run_baseline_comparison(
        corpus=corpus,
        baseline_cases=baseline_cases(manifest),
        assisted_cases=assisted_cases(manifest, degrade=degrade),
        policy=POLICY,
        harness_sha=HARNESS_SHA,
        baseline_provider_id="fixture",
        assisted_provider_id="clef",
    )


def _chain(corpus, manifest):
    run = _run(corpus, manifest)
    proposal = propose_thresholds(run, proposal_version="thresholds-v1")
    approval = approve_thresholds(
        proposal, approved_by="operator-1", approved_at=APPROVED_AT, explicit_sign_off=True
    )
    staging = enable_staging(
        approval=approval, run=run, settings_obj=staging_settings(), target_environment="staging"
    )
    return run, proposal, approval, staging


# --- T020 -------------------------------------------------------------------


def test_baseline_vs_assisted_reports_required_metrics(corpus, manifest) -> None:
    run = _run(corpus, manifest)
    assert run.corpus_sha256 == corpus.corpus_sha256
    assert run.harness_sha == HARNESS_SHA
    for metrics in (run.baseline, run.assisted):
        assert metrics.case_count == corpus.case_count
        for name in ("top1_accuracy", "topk_accuracy", "brier_score", "calibration_error", "abstention_rate"):
            assert 0.0 <= getattr(metrics, name) <= 1.0
        assert metrics.false_canonicalization_count == 0
    assert run.baseline.provider_id == "fixture"
    assert run.assisted.provider_id == "clef"
    assert run.assisted.top1_accuracy > run.baseline.top1_accuracy
    assert run.intact()


def test_run_is_deterministic(corpus, manifest) -> None:
    assert _run(corpus, manifest).record_sha256 == _run(corpus, manifest).record_sha256


def test_run_requires_frozen_corpus_and_pinned_harness(corpus, manifest) -> None:
    kwargs = dict(
        baseline_cases=baseline_cases(manifest),
        assisted_cases=assisted_cases(manifest),
        policy=POLICY,
        baseline_provider_id="fixture",
        assisted_provider_id="clef",
    )
    with pytest.raises(EnablementError) as exc:
        run_baseline_comparison(corpus=None, harness_sha=HARNESS_SHA, **kwargs)
    assert exc.value.code == "CORPUS_MISSING_OR_UNFROZEN"
    tampered = corpus.model_copy(update={"case_count": 1})
    with pytest.raises(EnablementError):
        run_baseline_comparison(corpus=tampered, harness_sha=HARNESS_SHA, **kwargs)
    for bad in ("", "main", "ABC" * 14, "1" * 39):
        with pytest.raises(EnablementError) as exc:
            run_baseline_comparison(corpus=corpus, harness_sha=bad, **kwargs)
        assert exc.value.code == "HARNESS_SHA_NOT_PINNED"


def test_run_must_cover_exact_frozen_cases(corpus, manifest) -> None:
    assisted = assisted_cases(manifest)
    with pytest.raises(EnablementError) as exc:
        run_baseline_comparison(
            corpus=corpus,
            baseline_cases=baseline_cases(manifest),
            assisted_cases=assisted[1:],
            policy=POLICY,
            harness_sha=HARNESS_SHA,
            baseline_provider_id="fixture",
            assisted_provider_id="clef",
        )
    assert exc.value.code == "CASES_NOT_FROZEN_CORPUS"


def test_label_drift_and_foreign_images_are_rejected(corpus, manifest) -> None:
    assisted = list(assisted_cases(manifest))
    first = assisted[1]
    assisted[1] = first.model_copy(update={"expected_choice": "maker:drifted"})
    with pytest.raises(EnablementError) as exc:
        run_baseline_comparison(
            corpus=corpus, baseline_cases=baseline_cases(manifest), assisted_cases=assisted,
            policy=POLICY, harness_sha=HARNESS_SHA, baseline_provider_id="fixture",
            assisted_provider_id="clef",
        )
    assert exc.value.code == "LABEL_DRIFT"

    assisted = list(assisted_cases(manifest))
    vision = next(i for i, c in enumerate(assisted) if c.image_sha256)
    assisted[vision] = assisted[vision].model_copy(update={"image_sha256": "f" * 64})
    with pytest.raises(EnablementError) as exc:
        run_baseline_comparison(
            corpus=corpus, baseline_cases=baseline_cases(manifest), assisted_cases=assisted,
            policy=POLICY, harness_sha=HARNESS_SHA, baseline_provider_id="fixture",
            assisted_provider_id="clef",
        )
    assert exc.value.code == "IMAGE_NOT_IN_FROZEN_CORPUS"


def test_provider_identity_is_enforced(corpus, manifest) -> None:
    common = dict(corpus=corpus, policy=POLICY, harness_sha=HARNESS_SHA)
    with pytest.raises(EnablementError) as exc:
        run_baseline_comparison(
            baseline_cases=baseline_cases(manifest), assisted_cases=assisted_cases(manifest, "jev"),
            baseline_provider_id="fixture", assisted_provider_id="clef", **common,
        )
    assert exc.value.code == "ASSISTED_PROVIDER_MISMATCH"
    with pytest.raises(EnablementError) as exc:
        run_baseline_comparison(
            baseline_cases=assisted_cases(manifest), assisted_cases=assisted_cases(manifest),
            baseline_provider_id="clef", assisted_provider_id="clef", **common,
        )
    assert exc.value.code == "BASELINE_EQUALS_ASSISTED"
    with pytest.raises(EnablementError) as exc:
        run_baseline_comparison(
            baseline_cases=baseline_cases(manifest), assisted_cases=assisted_cases(manifest),
            baseline_provider_id="fixture", assisted_provider_id="unknown", **common,
        )
    assert exc.value.code == "ASSISTED_PROVIDER_UNKNOWN"


def test_expected_calibration_error_values(manifest) -> None:
    assert expected_calibration_error(assisted_cases(manifest)) == pytest.approx(0.05)
    # baseline: confidence 0.6, accuracy = open-set share (8 of 64)
    assert expected_calibration_error(baseline_cases(manifest)) == pytest.approx(0.6 - 8 / 64)


def test_structural_false_canonicalization_is_zero(manifest) -> None:
    # 0.95 confidence -> AUTO_PROPOSE; still no canon write without user confirmation.
    assert structural_false_canonicalizations(assisted_cases(manifest), POLICY) == 0


def test_harness_source_sha_is_pinned_hex() -> None:
    value = harness_source_sha256()
    assert is_pinned_sha(value) and len(value) == 64
    assert value == harness_source_sha256()


# --- T030 -------------------------------------------------------------------


def test_proposal_covers_all_threshold_families_and_is_versioned(corpus, manifest) -> None:
    run = _run(corpus, manifest)
    proposal = propose_thresholds(run, proposal_version="thresholds-v1")
    t = proposal.thresholds
    assert proposal.proposal_version == "thresholds-v1"
    assert proposal.rule == PROPOSAL_RULE
    assert proposal.status == "PROPOSED_PENDING_OPERATOR"
    assert proposal.run_sha256 == run.record_sha256
    assert t.top1_min == run.baseline.top1_accuracy
    assert t.topk_min == run.baseline.topk_accuracy
    assert t.brier_max == run.baseline.brier_score
    assert t.calibration_error_max == run.baseline.calibration_error
    assert t.abstention_max == run.baseline.abstention_rate
    assert t.false_canonicalization_max == 0
    other = propose_thresholds(run, proposal_version="thresholds-v2")
    assert other.record_sha256 != proposal.record_sha256


def test_proposal_fails_closed(corpus, manifest) -> None:
    run = _run(corpus, manifest)
    with pytest.raises(EnablementError):
        propose_thresholds(None, proposal_version="v1")
    with pytest.raises(EnablementError):
        propose_thresholds(run, proposal_version=" ")
    tampered = run.model_copy(update={"harness_sha": "3" * 40})
    with pytest.raises(EnablementError) as exc:
        propose_thresholds(tampered, proposal_version="v1")
    assert exc.value.code == "BASELINE_RUN_MISSING_OR_TAMPERED"
    with pytest.raises(ValidationError):
        ProposedThresholds(
            top1_min=0, topk_min=0, brier_max=1, calibration_error_max=1, abstention_max=1,
            false_canonicalization_max=1,
        )


# --- T040 -------------------------------------------------------------------


def test_approval_is_explicit_timestamped_and_sha_linked(corpus, manifest) -> None:
    run = _run(corpus, manifest)
    proposal = propose_thresholds(run, proposal_version="thresholds-v1")
    approval = approve_thresholds(
        proposal, approved_by="operator-1", approved_at=APPROVED_AT, explicit_sign_off=True
    )
    assert approval.decision == "APPROVED"
    assert approval.explicit_sign_off is True
    assert approval.approved_at == "2026-10-24T10:00:00Z"
    assert approval.proposal_sha256 == proposal.record_sha256
    assert approval.run_sha256 == run.record_sha256
    assert approval.corpus_sha256 == corpus.corpus_sha256
    assert approval.thresholds == proposal.thresholds
    assert approval.intact()
    frozen = approval.to_operator_thresholds()
    assert isinstance(frozen, OperatorThresholds)
    assert frozen.thresholds_version == "thresholds-v1"
    with pytest.raises(ValidationError):
        approval.thresholds = proposal.thresholds  # type: ignore[misc]


def test_approval_fails_closed(corpus, manifest) -> None:
    proposal = propose_thresholds(_run(corpus, manifest), proposal_version="v1")
    with pytest.raises(EnablementError) as exc:
        approve_thresholds(proposal, approved_by="op", approved_at=APPROVED_AT, explicit_sign_off=False)
    assert exc.value.code == "EXPLICIT_SIGN_OFF_REQUIRED"
    with pytest.raises(EnablementError) as exc:
        approve_thresholds(
            proposal, approved_by="op", approved_at=datetime(2026, 10, 24), explicit_sign_off=True
        )
    assert exc.value.code == "APPROVAL_TIMESTAMP_INVALID"
    with pytest.raises(EnablementError) as exc:
        approve_thresholds(proposal, approved_by="", approved_at=APPROVED_AT, explicit_sign_off=True)
    assert exc.value.code == "APPROVER_MISSING"
    with pytest.raises(EnablementError) as exc:
        approve_thresholds(None, approved_by="op", approved_at=APPROVED_AT, explicit_sign_off=True)
    assert exc.value.code == "PROPOSAL_MISSING_OR_TAMPERED"


# --- T050 -------------------------------------------------------------------


def test_staging_enablement_after_approval(corpus, manifest) -> None:
    run, _, approval, staging = _chain(corpus, manifest)
    assert staging.environment == "staging"
    assert staging.providers == ("clef",)
    assert staging.approval_sha256 == approval.record_sha256
    assert staging.production_flag_default_off is True
    assert staging.production_traffic is False
    assert staging.live_payments is False
    assert staging.d1_permitted is False
    assert all(check.passed for check in staging.threshold_checks)
    # Enablement is an authorization record only; the flag default stays off.
    assert Settings.model_fields["enable_clef_provider"].default is False
    assert Settings().enable_clef_provider is False


@pytest.mark.parametrize("environment", ["production", "development", "test", ""])
def test_staging_enablement_refuses_non_staging(corpus, manifest, environment) -> None:
    run, _, approval, _ = _chain(corpus, manifest)
    with pytest.raises(EnablementError) as exc:
        enable_staging(
            approval=approval, run=run, settings_obj=staging_settings(), target_environment=environment
        )
    assert exc.value.code == "NON_STAGING_ENVIRONMENT"
    with pytest.raises(EnablementError) as exc:
        enable_staging(
            approval=approval,
            run=run,
            settings_obj=settings_namespace(environment=environment),
            target_environment="staging",
        )
    assert exc.value.code == "NON_STAGING_ENVIRONMENT"


def test_staging_enablement_requires_approval(corpus, manifest) -> None:
    run = _run(corpus, manifest)
    with pytest.raises(EnablementError) as exc:
        enable_staging(approval=None, run=run, settings_obj=staging_settings(), target_environment="staging")
    assert exc.value.code == "THRESHOLDS_NOT_APPROVED"


def test_staging_enablement_rejects_unsafe_config(corpus, manifest) -> None:
    run, _, approval, _ = _chain(corpus, manifest)
    for overrides, code in (
        ({"allow_production_payments": True}, "PAYMENTS_LIVE_DISABLED"),
        ({"d1_database_id": "d1-id"}, "NO_D1_BINDING"),
    ):
        with pytest.raises(EnablementError) as exc:
            enable_staging(
                approval=approval, run=run, settings_obj=settings_namespace(**overrides),
                target_environment="staging",
            )
        assert exc.value.code == "CONFIG_GATES_FAILED"
        assert code in exc.value.detail


def test_staging_enablement_only_for_evaluated_provider(corpus, manifest) -> None:
    run, _, approval, _ = _chain(corpus, manifest)
    for providers in (("jev",), ("clef", "jev"), ("other",), ()):
        with pytest.raises(EnablementError):
            enable_staging(
                approval=approval, run=run, settings_obj=staging_settings(),
                target_environment="staging", providers=providers,
            )


def test_staging_enablement_requires_thresholds_met(corpus, manifest) -> None:
    run = _run(corpus, manifest, degrade=True)
    proposal = propose_thresholds(run, proposal_version="v1")
    approval = approve_thresholds(proposal, approved_by="op", approved_at=APPROVED_AT, explicit_sign_off=True)
    with pytest.raises(EnablementError) as exc:
        enable_staging(approval=approval, run=run, settings_obj=staging_settings(), target_environment="staging")
    assert exc.value.code == "THRESHOLDS_NOT_MET"


def test_staging_enablement_rejects_unlinked_run(corpus, manifest) -> None:
    _, _, approval, _ = _chain(corpus, manifest)
    other_run = _run(corpus, manifest, degrade=True)
    with pytest.raises(EnablementError) as exc:
        enable_staging(approval=approval, run=other_run, settings_obj=staging_settings(), target_environment="staging")
    assert exc.value.code == "APPROVAL_NOT_LINKED_TO_RUN"


# --- T060 -------------------------------------------------------------------


def test_receipt_is_pinned_and_references_exact_shas(corpus, manifest) -> None:
    run, proposal, approval, staging = _chain(corpus, manifest)
    receipt = pin_receipt(
        corpus=corpus, run=run, proposal=proposal, approval=approval, staging=staging,
        source_commit_sha=SOURCE_SHA,
    )
    assert receipt.schema_version == ENABLEMENT_RECEIPT_SCHEMA
    assert receipt.status == "RECEIPT_PINNED"
    assert receipt.source_commit_sha == SOURCE_SHA
    assert receipt.harness_sha == HARNESS_SHA
    assert receipt.corpus_sha256 == corpus.corpus_sha256
    assert receipt.run_sha256 == run.record_sha256
    assert receipt.proposal_sha256 == proposal.record_sha256
    assert receipt.approval_sha256 == approval.record_sha256
    assert receipt.staging_enablement_sha256 == staging.record_sha256
    assert receipt.false_canonicalization_count == 0
    assert verify_enablement_receipt(receipt)
    assert verify_enablement_receipt(receipt.as_payload())


def test_receipt_is_immutable_and_tamper_evident(corpus, manifest) -> None:
    run, proposal, approval, staging = _chain(corpus, manifest)
    receipt = pin_receipt(
        corpus=corpus, run=run, proposal=proposal, approval=approval, staging=staging,
        source_commit_sha=SOURCE_SHA,
    )
    with pytest.raises(ValidationError):
        receipt.source_commit_sha = "4" * 40  # type: ignore[misc]
    assert not verify_enablement_receipt(receipt.model_copy(update={"source_commit_sha": "4" * 40}))
    payload = receipt.as_payload()
    payload["thresholds"]["top1_min"] = 0.0
    assert not verify_enablement_receipt(payload)
    assert not verify_enablement_receipt(None)


def test_receipt_rejects_broken_chain_and_unpinned_source(corpus, manifest) -> None:
    run, proposal, approval, staging = _chain(corpus, manifest)
    with pytest.raises(EnablementError) as exc:
        pin_receipt(
            corpus=corpus, run=run, proposal=proposal, approval=approval, staging=staging,
            source_commit_sha="HEAD",
        )
    assert exc.value.code == "SOURCE_SHA_NOT_PINNED"
    other_proposal = propose_thresholds(run, proposal_version="other")
    with pytest.raises(EnablementError) as exc:
        pin_receipt(
            corpus=corpus, run=run, proposal=other_proposal, approval=approval, staging=staging,
            source_commit_sha=SOURCE_SHA,
        )
    assert exc.value.code == "SHA_CHAIN_BROKEN"
    with pytest.raises(EnablementError) as exc:
        pin_receipt(
            corpus=corpus, run=run, proposal=proposal, approval=approval, staging=None,
            source_commit_sha=SOURCE_SHA,
        )
    assert exc.value.code == "CHAIN_RECORD_MISSING_OR_TAMPERED"


def test_receipt_contains_no_evidence_payloads_or_secrets(corpus, manifest) -> None:
    run, proposal, approval, staging = _chain(corpus, manifest)
    receipt = pin_receipt(
        corpus=corpus, run=run, proposal=proposal, approval=approval, staging=staging,
        source_commit_sha=SOURCE_SHA,
    )
    dumped = json.dumps(receipt.as_payload())
    for forbidden in ("packet", "probabilities", "image_bytes", "sha256:", "api_token", "secret", "source_url"):
        assert forbidden not in dumped
    for record in (run, proposal, approval, staging):
        text = json.dumps(record.model_dump(mode="json"))
        assert "probabilities" not in text
        assert "sha256:" not in text


def test_baseline_must_use_single_declared_provider() -> None:
    from intelligence.evaluation_corpus import freeze_corpus
    from intelligence.evaluation_enablement import EnablementError, run_baseline_comparison
    from tests.eval007_helpers import (
        HARNESS_SHA,
        POLICY,
        admitted_manifest,
        assisted_cases,
        baseline_cases,
    )

    manifest = admitted_manifest()
    with pytest.raises(EnablementError) as exc:
        run_baseline_comparison(
            corpus=freeze_corpus(manifest),
            baseline_cases=baseline_cases(manifest),
            assisted_cases=assisted_cases(manifest),
            policy=POLICY,
            harness_sha=HARNESS_SHA,
            baseline_provider_id="some-other-baseline",
            assisted_provider_id="clef",
        )
    assert exc.value.code == "BASELINE_PROVIDER_MISMATCH"
