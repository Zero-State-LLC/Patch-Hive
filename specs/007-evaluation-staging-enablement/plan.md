# Implementation plan — 007 Evaluation Corpus Freeze & Controlled Staging Enablement

Reconstructed 2026-10-26 from the implementation (#51) and `OPERATOR_NOTES.md`.

## Technical context

- Python 3.11+, FastAPI backend; pure modules with no network, database, or provider calls.
- Modules: `backend/intelligence/evaluation_corpus.py` (T010a), `backend/intelligence/evaluation_enablement.py` (T020a–T060a), `backend/intelligence/enablement_machine.py` (state machine).
- Validator reused: `scripts/validate_vision_pilot.py`; promotion workflow: `docs/evidence/PILOT_CASE_PROMOTION.md`.
- Tests: `backend/tests/integration/test_007_evaluation_enablement_machine.py` (T070).

## Constitution check

| Principle | How this feature complies |
| --- | --- |
| 2 Evidence is not canon | Records hold metrics and hashes only; nothing writes inventory. |
| 4 Probabilistic systems propose | Thresholds come from observed baseline; disposition stays with `DecisionPolicy`. |
| 5 Confirmation is explicit | `approve_thresholds` requires `explicit_sign_off=True`. |
| 6 Provenance is mandatory | Each record carries the SHA of its predecessor; receipt pins source commit. |
| 9 Fail closed | Missing, tampered, or unlinked artifacts are rejected with no state change. |

## Phases

### WP-01 Corpus freeze (T010a)
`freeze_corpus(manifest)` over the governed validator plus an independent cross-partition leakage check.

### WP-02 Baseline and thresholds (T020a, T030a, T040a)
`run_baseline_comparison`, `propose_thresholds` (`non_regression_vs_baseline.v1`), `approve_thresholds`.

### WP-03 Staging authorization and receipt (T050a, T060a)
`enable_staging` refuses any non-staging target; `pin_receipt` seals the chain for the Spec 006 `gates_pass` guard.

### WP-04 Operator run (T010b–T060b)
Follow the procedure in `OPERATOR_NOTES.md`. Not performed by CI or this repository.

## Risks

- The pilot manifest has 0 cases; every operator task is blocked on case promotion (005 T061c).
- Thresholds equal baseline values; a weak baseline yields weak thresholds. The operator may reject the proposal.
