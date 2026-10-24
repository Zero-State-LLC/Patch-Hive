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

- [ ] T001 Create feature tree `specs/007-evaluation-staging-enablement/` and add index line to `specs/README.md`.
  - depends_on: []

- [ ] T010 Promote rights-cleared evidence into a representative reviewed pilot set and freeze corpus SHA.
  - depends_on: [T001]
  - acceptance: admission validator rejects cross-partition leakage; corpus hash is immutable and recorded.

- [ ] T020 Run baseline vs Clef-assisted evaluation on the frozen corpus.
  - depends_on: [T010]
  - acceptance: top-1/top-k, calibration error, abstention rate, and zero false-canonicalization are reported.

- [ ] T030 Propose operator-approved thresholds from baseline results.
  - depends_on: [T020]
  - acceptance: thresholds cover ranking, calibration, abstention, and false-canonicalization; proposal is versioned.

- [ ] T040 Obtain operator approval and freeze thresholds.
  - depends_on: [T030]
  - acceptance: approval is an explicit, timestamped, SHA-linked decision.

- [ ] T050 Enable Clef (and any other provider) in staging only after approval.
  - depends_on: [T040]
  - acceptance: feature flag remains default-off outside staging; no production traffic.

- [ ] T060 Retain SHA-pinned evaluation receipt covering corpus, harness, thresholds, and staging enablement.
  - depends_on: [T050]
  - acceptance: receipt is immutable and references the exact source SHAs.

- [ ] T070 Integration tests for the evaluation state machine and gate checks.
  - depends_on: [T010, T060]
  - acceptance: no path reaches STAGING_ENABLED without OPERATOR_APPROVED; fail-closed on missing corpus or unapproved thresholds.
