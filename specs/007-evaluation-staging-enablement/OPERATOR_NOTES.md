# Spec 007 Operator Notes (Evaluation Corpus Freeze & Controlled Staging Enablement)

Status: the code paths for T010-T070 are implemented and tested in-repo with
synthetic in-test data only. The operator steps below are NOT performed by this
repository: no corpus has been frozen, no thresholds have been approved, and no
provider has been enabled in any environment.

T001 (feature tree and `specs/README.md` index line) was already satisfied on main
by the spec PR that added `tasks.md`; no further change was needed.

## Modules

| Task | Module | Artifact |
| --- | --- | --- |
| T010 | `backend/intelligence/evaluation_corpus.py` | `CorpusFreeze` (`patchhive.eval-corpus-freeze.v1`) |
| T020 | `backend/intelligence/evaluation_enablement.py` | `BaselineRun` (`patchhive.eval-baseline-run.v1`) |
| T030 | `backend/intelligence/evaluation_enablement.py` | `ThresholdProposal` (`patchhive.eval-threshold-proposal.v1`) |
| T040 | `backend/intelligence/evaluation_enablement.py` | `OperatorApproval` (`patchhive.eval-operator-approval.v1`) |
| T050 | `backend/intelligence/evaluation_enablement.py` | `StagingEnablement` (`patchhive.eval-staging-enablement.v1`) |
| T060 | `backend/intelligence/evaluation_enablement.py` | `EvaluationEnablementReceipt` (`patchhive.eval-enablement-receipt.v1`) |
| state machine | `backend/intelligence/enablement_machine.py` | CORPUS_DRAFT -> ... -> RECEIPT_PINNED |
| T070 | `backend/tests/integration/test_007_evaluation_enablement_machine.py` | gate and path tests |

Every artifact is a frozen record sealed by `record_sha256` (or `receipt_sha256`)
and carries the SHA of the artifact it depends on. The state machine re-verifies
integrity and the SHA link on every transition; a missing, tampered, or unlinked
artifact is rejected and the state does not change.

## Operator procedure

1. Freeze the corpus (T010). Promote rights-cleared, reviewed cases into
   `fixtures/vision_eval/pilot-manifest.json` per `docs/evidence/PILOT_CASE_PROMOTION.md`,
   then call `freeze_corpus(manifest)`. It runs the governed validator
   (`scripts/validate_vision_pilot.py`) and refuses anything not
   `ADMITTED_FOR_BASELINE`, plus an independent cross-partition leakage check
   (same image hash or case id in two partitions). The shipped intake shell has
   zero cases and is rejected with `CORPUS_EMPTY`; that is expected.
2. Run baseline vs provider-assisted (T020). Produce `LabeledCorpusCase` rows for
   both conditions covering exactly the frozen case ids (same expected choice and
   cohort; vision rows must reference an image hash bound to that case), then call
   `run_baseline_comparison(..., harness_sha=<pinned SHA>)`. A live provider run is
   an operator action and is not performed in CI. `harness_source_sha256()` gives a
   SHA-256 over the harness source files if a content pin is preferred over a git
   commit SHA.
3. Propose thresholds (T030) with `propose_thresholds(run, proposal_version=...)`.
4. Approve (T040) with `approve_thresholds(proposal, approved_by=..., approved_at=<tz-aware>, explicit_sign_off=True)`.
5. Authorize staging (T050) with `enable_staging(approval=..., run=..., settings_obj=<staging Settings>, target_environment="staging")`.
   Then set `ENABLE_CLEF_PROVIDER=true` (and `DECISION_PROVIDER=clef`) in the staging
   environment only: `env.staging.vars` in `edge/api/wrangler.jsonc` (the staging API on
   `api-staging.patch-hive.com`), with the Clef credentials as `--env staging` secrets.
   The production Worker never forwards these. This repository never sets the flag.
6. Pin the receipt (T060) with `pin_receipt(..., source_commit_sha=<git SHA>)` and
   retain it. Its `receipt_sha256` is accepted by the Spec 006 edge readiness
   `gates_pass` guard as the evaluation receipt SHA.

## Conservative interpretations

- Threshold proposal rule `non_regression_vs_baseline.v1`: the proposed limits are
  the measured baseline values (top-1 and top-k minimums; Brier, expected
  calibration error, and abstention maximums) and `false_canonicalization_max` is
  fixed at 0. The operator approves or rejects that exact proposal; there is no
  override path in code.
- Calibration error is reported as both the Spec 005 multiclass Brier score and an
  expected calibration error over 10 equal-width confidence bins.
- False canonicalization is the Spec 005 invariant (0) plus a structural count from
  the Spec 006 resolution machine: each case is driven to its policy disposition
  without a user confirmation and must not permit a canon write.
- Staging enablement is an authorization record, not a settings mutation. It is
  refused unless the target and settings environment are both `staging`, the
  approval is linked to the run, the provider is exactly the evaluated provider,
  the assisted metrics meet the approved thresholds (Spec 006 FR-007), and the
  Spec 006 config gates pass (no live payments, Clef flag class default off, no D1).

## Invariants

- Disposition is always computed by the Spec 005 `DecisionPolicy`.
- `ENABLE_CLEF_PROVIDER` class default stays false; `ALLOW_PRODUCTION_PAYMENTS` stays false.
- No D1. No schema migration. No network, database, or provider calls in these modules.
- Records hold identifiers, hashes, and aggregate metrics only: no packets, image
  bytes, rights payloads, source URLs, or secrets.

## Additional notes

- harness_sha is checked as a pinned git SHA (40 or 64 hex). It is not recomputed
  from source here. harness_source_sha256() is available for operators who want a
  content hash of the harness modules.
- Text-modality cases carry no image hash and are bound to the frozen corpus by
  case_id, label, and cohort. Vision cases must also match a frozen image hash.
- The state machine rebuilds the receipt from its own artifacts before pinning, so
  a resealed receipt with altered content is rejected.
