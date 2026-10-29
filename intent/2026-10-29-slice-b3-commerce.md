# Intent

## Problem

Spec 004 research R2, R3 and R4 found three gaps against `docs/SECURITY.md`:

- `canonical_credit_ledger` is append-only by convention only. Nothing in the database stops an `UPDATE` or `DELETE` (FR-008).
- A live-mode webhook event is rejected only when `STRIPE_TEST_MODE=true`, and the startup payment policy checks only production. Staging with `STRIPE_TEST_MODE=false` would accept live-mode events (FR-013).
- The webhook keeps only the last `v1` signature, so a valid event can fail during secret rotation. A concurrent duplicate delivery that loses the insert race raises `IntegrityError` and answers 500, so the provider retries (FR-012, FR-013).

## Proposed outcome

- T042: migration `20261029_ledger_append_only` adds Postgres triggers that reject `UPDATE` and `DELETE` on `canonical_credit_ledger`, mirroring `20260925_decision_receipts`. No-op on SQLite. Corrections stay new rows (`reversal`).
- T041: a live-mode event is rejected unless the environment is `production` and `STRIPE_TEST_MODE=false`. Startup refuses `STRIPE_TEST_MODE=false` unless `ENVIRONMENT=production` (`validate_stripe_mode_startup_policy`).
- T040: the event is accepted if any `v1` value matches, each compared in constant time, with the existing 300 s tolerance. A header must carry exactly one `t`. A concurrent duplicate rolls back a savepoint, reloads the winner and answers 200 as a duplicate, or 409 `WEBHOOK_REPLAY_CONFLICT` if the payload differs.

Out of scope: T043–T051 (event processor, Machine B and C, legacy routes, activation review). `TRUNCATE` is not blocked; the acceptance suite truncates between tests.

## Affected users / systems

Payments flags, the Stripe webhook route, startup policy, the canonical ledger schema (Postgres), and operators: any non-production stack with `STRIPE_TEST_MODE=false` now refuses to start.

## Constraints / non-goals

Payments stay test mode; no provider call is made. Fail closed: the verifier's default rejects live-mode events. No change to the production payment policy in `canon/routes.py`. No audio DSP, no hardware control.

## Open questions

None blocking. Whether to also block `TRUNCATE` is left to a later decision (owner).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| No code path updates or deletes `canonical_credit_ledger` rows | `OBSERVED` | grep of `backend/` for `CanonicalCreditLedgerEntryRecord` and `canonical_credit_ledger`: only inserts and selects; compensation adds a `reversal` row |
| The triggers block `UPDATE` and `DELETE` on Postgres 15 after `alembic upgrade head` on an empty database | `OBSERVED` | throwaway `postgres:15` container; both statements failed with `canonical_credit_ledger is append-only`; downgrade and re-upgrade succeeded |
| The revision id fits `alembic_version.version_num` (VARCHAR(32)) | `OBSERVED` | 27 characters; unit test asserts it |
| No checked-in non-production config sets `STRIPE_TEST_MODE=false` | `OBSERVED` | grep of compose files, `.env.example`, wrangler config |
| The provider sends one `v1` per active secret during rotation | `INFERRED` | provider's documented header format (research R4) |

## Author / date

- Author: Claude (agent), for Daniel Meyer
- Date: 2026-10-29
