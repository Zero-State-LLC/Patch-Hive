# 007 Tasks — Evaluation Corpus Freeze & Controlled Staging Enablement

## Upstream
- Depends on Spec 005 (DecisionProvider, DecisionPolicy, DecisionPacket, evaluation harness).
- Depends on Spec 006 (ClefProvider adapter wired behind the same policy; feature flag default off).
- Constitution authority boundary unchanged: no canon write without existing confirmation path.

## State machine (Evaluation & Enablement)
States: CORPUS_DRAFT → CORPUS_FROZEN → BASELINE_RUN → THRESHOLDS_PROPOSED → OPERATOR_APPROVED → STAGING_ENABLED → RECEIPT_PINNED

| From | Event | Guard | To |
|------|-------|-------|----|
| CORPUS_DRAFT | promote_cases | rights-cleared + admission checks pass | CORPUS_FROZEN |
| CORPUS_FROZEN | run_baseline | harness SHA pinned | BASELINE_RUN |
| BASELINE_RUN | propose_thresholds | calibration + abstention metrics collected | THRESHOLDS_PROPOSED |
| THRESHOLDS_PROPOSED | operator_approve | explicit sign-off | OPERATOR_APPROVED |
| OPERATOR_APPROVED | enable_staging | flag remains default-off in prod | STAGING_ENABLED |
| STAGING_ENABLED | pin_receipt | evaluation receipt SHA retained | RECEIPT_PINNED |

No path reaches STAGING_ENABLED without OPERATOR_APPROVED. False-canonicalization count must remain zero.

## Tasks (topological order)

Status reflects `main` at e0fb6a1 (see `OPERATOR_NOTES.md`). Each task that pairs repository code
with an operator action is split: sub-task `a` is the code, sub-task `b` is the operator action. A
parent is done only when both are. `scripts/check_spec_dag.py` checks this file.

- [x] T001 Create feature tree `specs/007-evaluation-staging-enablement/` and add index line to `specs/README.md`.
  - depends_on: []

- [ ] T010 Promote rights-cleared evidence into a representative reviewed pilot set and freeze corpus SHA.
  - depends_on: [T001]
  - acceptance: admission validator rejects cross-partition leakage; corpus hash is immutable and recorded.
  - [x] T010a Implement `freeze_corpus` (`CorpusFreeze`) over the governed pilot validator plus the leakage check (code).
    - depends_on: [T001]
  - [ ] T010b Promote reviewed cases into `fixtures/vision_eval/pilot-manifest.json` and freeze the corpus SHA (operator; the manifest has held 5 Commons cases since 2026-11-08 and isn't admitted yet). Since 2026-11-07 the cases are whole-rig photos, not photos of single Modules (spec 009 T070b).
    - depends_on: [T010a, 005:T061b2]
    - Note (2026-11-02): candidate photos can now be found with `scripts/vision/find_corpus_photos.py` (owner-approved 300 context.dev searches, approval `corpus-photos-2026-11`; Commons and Flickr only; CC0, public domain, CC BY, CC BY-SA only; images stay outside the repo). Its rows are UNVERIFIED candidates for `scripts/build_vision_promotion_queue.py`; identity verification and review remain this operator task. Commands in `docs/evidence/PILOT_CASE_PROMOTION.md`.
    - Note (2026-11-02, run): the 300 approved searches are spent. Only 2 images (6 rows: one Doepfer NAMM rack photo, one Verbos Complex Oscillator photo) name their module; the rest were generic photos, now excluded as `identity_not_named` ([run record](../../docs/evidence/CORPUS_PHOTO_SEARCH_2026-11-02.md)). Open web search will not reach 50 to 100 identities; owner or maker-licensed photos are the remaining source.

- [ ] T020 Run baseline vs Clef-assisted evaluation on the frozen corpus.
  - depends_on: [T010]
  - acceptance: top-1/top-k, calibration error, abstention rate, and zero false-canonicalization are reported.
  - [x] T020a Implement `run_baseline_comparison` (`BaselineRun`) (code).
    - depends_on: [T010a]
  - [ ] T020b Run the live baseline vs provider-assisted evaluation (operator).
    - depends_on: [T010b, T020a]

- [ ] T030 Propose operator-approved thresholds from baseline results.
  - depends_on: [T020]
  - acceptance: thresholds cover ranking, calibration, abstention, and false-canonicalization; proposal is versioned.
  - [x] T030a Implement `propose_thresholds` (`ThresholdProposal`, rule `non_regression_vs_baseline.v1`) (code).
    - depends_on: [T020a]
  - [ ] T030b Propose thresholds from the retained baseline run (operator).
    - depends_on: [T020b, T030a]

- [ ] T040 Obtain operator approval and freeze thresholds.
  - depends_on: [T030]
  - acceptance: approval is an explicit, timestamped, SHA-linked decision.
  - [x] T040a Implement `approve_thresholds` (`OperatorApproval`) (code).
    - depends_on: [T030a]
  - [ ] T040b Approve or reject the exact proposal (operator).
    - depends_on: [T030b, T040a]

- [ ] T050 Enable Clef (and any other provider) in staging only after approval.
  - depends_on: [T040]
  - acceptance: feature flag remains default-off outside staging; no production traffic.
  - [x] T050a Implement `enable_staging` (`StagingEnablement`) authorization record (code).
    - depends_on: [T040a]
  - [ ] T050b Record the staging authorization (`enable-staging`) for the approved proposal (operator). No flag is set here: since #185 the container refuses provider flags without a signed receipt, so the flag waits for T085.
    - depends_on: [T040b, T050a]

- [ ] T060 Retain SHA-pinned evaluation receipt covering corpus, harness, thresholds, and staging enablement.
  - depends_on: [T050]
  - acceptance: receipt is immutable and references the exact source SHAs.
  - [x] T060a Implement `pin_receipt` (`EvaluationEnablementReceipt`) and the enablement state machine (code).
    - depends_on: [T050a]
  - [ ] T060b Pin and retain the receipt for the exact source commit (operator).
    - depends_on: [T050b, T060a]

- [x] T070 Integration tests for the evaluation state machine and gate checks.
  - depends_on: [T010a, T060a]
  - acceptance: no path reaches STAGING_ENABLED without OPERATOR_APPROVED; fail-closed on missing corpus or unapproved thresholds.

## Gap closure (2026-10-29)

From [research.md](research.md). Effort in brackets.

- [x] T080 Verify by replay: `verify_enablement_receipt` validates the full `EvaluationEnablementReceipt` model (no bare mapping) and, given the chain records, rebuilds the receipt with `pin_receipt` and compares (R1) [S]. Done 2026-10-29: mappings and models re-validate and must round-trip exactly; `chain=EnablementChain(...)` replays through `pin_receipt`.
  - depends_on: [T060a]
- [x] T081 Sign receipts: an Ed25519 signature over `receipt_sha256` against a committed approver allowlist (`key_id`, public key, `valid_from`, `revoked_at`); `approved_by` becomes the key id; reject unknown or revoked keys (R1) [M]. Done 2026-10-29: `intelligence/receipt_signing.py` and `verify_signed_enablement_receipt`; `intelligence/evaluation_approvers.json` is committed with no keys (T082 adds one).
  - depends_on: [T080]
- [x] T082 Generate the approver key pair offline and commit only the public key to the allowlist through a reviewed PR (operator) [S]. Done 2026-11-02 at the owner's direction: key id `approver-2026-11`, `valid_from` 2026-11-02T10:00:00Z, public key in `backend/intelligence/evaluation_approvers.json`; the private key stays in `~/patchhive-approver/` on the owner's machine (mode 0600), never in the repo, CI or Cloudflare. Receipts must use `approved_by = approver-2026-11`.
  - depends_on: [T081]
- [ ] T083 Sign the receipt pinned in T060b with the approver key and retain the signature beside it (operator) [S]. To enable a provider in staging, point `DECISION_ENABLEMENT_RECEIPT_PATH` and `DECISION_ENABLEMENT_SIGNATURE_PATH` at those two JSON files (005 T080).
  - depends_on: [T060b, T082]
- [x] T084 Operator driver for the chain: `scripts/staging/run_007_evaluation.py` runs freeze, run (live provider or `--dry-run` fixture), propose, approve, enable-staging, pin, sign and verify as commands over sealed JSON artifacts (owner guide 2026-11-02, finding 1) [S]. Done 2026-11-02; offline end-to-end and refusal tests in `backend/tests/integration/test_007_evaluation_driver.py`. The operator actions T010b to T083 are unchanged and still open.
  - depends_on: [T081]
- [ ] T085 Set the provider flag in the staging environment only, pointing `DECISION_ENABLEMENT_RECEIPT_PATH` and `DECISION_ENABLEMENT_SIGNATURE_PATH` at the files signed in T083, then deploy staging (operator). Split from T050b on 2026-11-03: since #185 the container refuses provider flags without a signed receipt, so the flag can only be set after T083.
  - depends_on: [T083]
