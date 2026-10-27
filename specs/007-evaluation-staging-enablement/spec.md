# 007 — Evaluation Corpus Freeze & Controlled Staging Enablement

**Status:** DRAFT spec, reconstructed 2026-10-26 from `tasks.md` and `OPERATOR_NOTES.md` after implementation (#51). Code IMPLEMENTED; operator actions open. The operator must confirm every `[INFERRED]` item.  
**Date:** 2026-10-26  
**Depends on:** Spec 005 (DecisionProvider, DecisionPolicy, DecisionPacket, evaluation harness), Spec 006 (ClefProvider behind the same policy, flag default off).

## Problem

Spec 005 FR-010 and Spec 006 FR-007 keep Jev and Clef flagged off until a retained labeled corpus meets operator-approved thresholds. Nothing yet turns a reviewed pilot into a frozen corpus, a baseline run, approved thresholds, and a staging-only enablement that later gates can verify [OBSERVED: specs/005-decision-intelligence/tasks.md T061c–T070].

## Objective

Provide a SHA-linked chain of frozen records (corpus freeze → baseline run → threshold proposal → operator approval → staging enablement → pinned receipt) and a state machine that refuses to skip a link [OBSERVED: OPERATOR_NOTES.md].

## User scenarios and testing

### User story 1 — Freeze an admitted corpus (Priority: P1)

As the operator, I want to freeze a reviewed, rights-cleared pilot so that every later metric is tied to one immutable corpus.

**Independent test:** call `freeze_corpus` on a manifest with admitted and non-admitted cases.

**Acceptance scenarios:**

1. **Given** a manifest with zero cases, **when** the operator freezes it, **then** it is rejected with `CORPUS_EMPTY` [OBSERVED: OPERATOR_NOTES.md].
2. **Given** a case not `ADMITTED_FOR_BASELINE`, **when** the operator freezes, **then** the freeze is refused [OBSERVED: OPERATOR_NOTES.md].
3. **Given** the same image hash or case id in two partitions, **when** the operator freezes, **then** the freeze is refused [OBSERVED: tasks.md T010].

### User story 2 — Propose and approve thresholds from a baseline (Priority: P1)

As the operator, I want thresholds derived from observed baseline metrics so that no invented target is treated as evidence.

**Acceptance scenarios:**

1. **Given** a frozen corpus and a pinned harness SHA, **when** the baseline and provider-assisted runs complete, **then** top-1/top-k, Brier score, expected calibration error, abstention rate, and false-canonicalization count are reported [OBSERVED: OPERATOR_NOTES.md].
2. **Given** a baseline run, **when** thresholds are proposed, **then** they equal the measured baseline values and `false_canonicalization_max` is 0 [OBSERVED: OPERATOR_NOTES.md, rule `non_regression_vs_baseline.v1`].
3. **Given** a proposal, **when** the operator approves without `explicit_sign_off=True` or a timezone-aware timestamp, **then** approval is refused [OBSERVED: OPERATOR_NOTES.md].

### User story 3 — Enable a provider in staging only (Priority: P2)

As the operator, I want an authorization record for staging enablement so that no production path can enable a provider.

**Acceptance scenarios:**

1. **Given** no `OPERATOR_APPROVED` state, **when** `enable_staging` is attempted, **then** the machine does not reach `STAGING_ENABLED` [OBSERVED: tasks.md state machine].
2. **Given** a target or settings environment other than `staging`, **when** enablement is attempted, **then** it is refused [OBSERVED: OPERATOR_NOTES.md].
3. **Given** assisted metrics below the approved thresholds, **when** enablement is attempted, **then** it is refused [OBSERVED: OPERATOR_NOTES.md].

### Edge cases

- A resealed receipt with altered content is rejected because the machine rebuilds it from its own artifacts [OBSERVED: OPERATOR_NOTES.md].
- Text cases carry no image hash and bind by case id, label, and cohort; vision cases must also match a frozen image hash [OBSERVED: OPERATOR_NOTES.md].

## Requirements

### Functional requirements

- **FR-001** Every artifact MUST be a frozen record sealed by `record_sha256` (or `receipt_sha256`) and MUST carry the SHA of the artifact it depends on [OBSERVED: OPERATOR_NOTES.md].
- **FR-002** The state machine MUST re-verify integrity and SHA links on every transition and MUST leave state unchanged on rejection [OBSERVED: OPERATOR_NOTES.md].
- **FR-003** No path MAY reach `STAGING_ENABLED` without `OPERATOR_APPROVED` [OBSERVED: tasks.md].
- **FR-004** False-canonicalization MUST be zero, counted both as the Spec 005 invariant and structurally through the Spec 006 resolution machine [OBSERVED: OPERATOR_NOTES.md].
- **FR-005** Staging enablement MUST be an authorization record, not a settings mutation; this repository MUST NOT set `ENABLE_CLEF_PROVIDER` [OBSERVED: OPERATOR_NOTES.md].
- **FR-006** The pinned receipt's `receipt_sha256` MUST be accepted by the Spec 006 `gates_pass` guard as the evaluation receipt SHA [OBSERVED: OPERATOR_NOTES.md].

### Key entities

`CorpusFreeze`, `BaselineRun`, `ThresholdProposal`, `OperatorApproval`, `StagingEnablement`, `EvaluationEnablementReceipt` (schema ids `patchhive.eval-*.v1`) [OBSERVED: OPERATOR_NOTES.md].

## Authority, data, security, observability, rollback

- **Authority:** disposition stays with the Spec 005 `DecisionPolicy`; no canon write [OBSERVED: OPERATOR_NOTES.md invariants].
- **Data:** no schema migration, no D1, no network, database, or provider calls in these modules [OBSERVED: OPERATOR_NOTES.md].
- **Security/privacy:** records hold identifiers, hashes, and aggregate metrics only; no packets, image bytes, rights payloads, source URLs, or secrets [OBSERVED: OPERATOR_NOTES.md].
- **Observability:** the receipt chain is the audit trail; rejected events leave state unchanged [OBSERVED: OPERATOR_NOTES.md].
- **Rollback:** set `ENABLE_CLEF_PROVIDER=false` in staging; records are append-only, so nothing needs a data rollback [INFERRED].

## Success criteria

- **SC-001** A frozen corpus SHA, baseline run, approved thresholds, and pinned receipt exist for one exact source commit [OBSERVED: tasks.md T060].
- **SC-002** The integration suite proves no path reaches `STAGING_ENABLED` without approval (`backend/tests/integration/test_007_evaluation_enablement_machine.py`) [OBSERVED].
- **SC-003** False-canonicalization count is 0 in every retained run [OBSERVED: tasks.md].

## Out of scope

Production enablement, live provider runs in CI, and threshold overrides (there is no override path in code) [OBSERVED: OPERATOR_NOTES.md].
