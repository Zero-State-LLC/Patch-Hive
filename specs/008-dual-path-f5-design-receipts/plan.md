# Implementation plan — 008 Dual-Path F5 Cutover & Design Engine Staging Receipts

Reconstructed 2026-10-26 from the implementation (#53) and `OPERATOR_NOTES.md`.

## Technical context

- Backend: `backend/core/ops/f5_cutover.py` (state machine, alias evidence), `backend/core/ops/design_walkthrough.py` (live evidence, walkthrough, pin).
- Frontend: `frontend/src/pages/Racks.tsx`, `frontend/src/pages/Modules.tsx`, `frontend/src/lib/canonRigAdapter.ts`.
- Scripts: `scripts/seed_golden_demo.py`, `scripts/staging/design_engine_walkthrough.py`.
- Staging stack: `docker-compose.staging.design-engine.yml` with `STRIPE_TEST_MODE=true`, `ALLOW_PRODUCTION_PAYMENTS=false`.
- Tests: `backend/tests/integration/test_008_f5_cutover_machine.py`, `backend/tests/integration/test_008_f5_live.py` (T060).

## Constitution check

| Principle | How this feature complies |
| --- | --- |
| 1 Canon is deterministic | Parity evidence hashes full id sets from both list paths. |
| 6 Provenance is mandatory | Receipts carry source SHA and server-reported flags; pins require the receipt SHA. |
| 9 Fail closed | Seed drift, flag drift, health failure, or an unpinned SHA aborts with no receipt. |
| 10 Publishing law | Download pack is reduced to its SHA-256; no artifact rewritten. |

## Phases

### WP-01 Alias and FE cutover (T010, T020)
Parity and write-surface evidence; switch list pages only.

### WP-02 Seed auth (T030a)
Seeder owns demo credentials; `check_seed_auth` is read-only.

### WP-03 Walkthrough and pin tooling (T040a, T050a)
Walkthrough script, receipt capture, `pin_readiness_docs`, placeholders in readiness docs.

### WP-04 Operator run (T030b, T040b, T050b)
Follow `OPERATOR_NOTES.md` on the staging host. T050b also needs the Spec 007 receipt (007 T060b).

## Risks

- T050b is blocked until Spec 007 pins its enablement receipt, which is blocked on corpus promotion.
- Paginated canon and legacy lists can differ page by page; only full-set parity is asserted.
