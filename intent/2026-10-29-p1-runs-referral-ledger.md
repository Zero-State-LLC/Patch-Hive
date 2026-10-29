# Intent

## Problem

From the 2026-10-29 gap analysis (P1):
- **Stuck runs (spec 001 FR-018/FR-019).** After a run was committed as `running`, an error in the export bridge or the Design Engine dual-write rolled back the `succeeded` write and left the run `running` for good. Only the generator call was guarded.
- **Admin rerun.** It inserted `Run(status="queued")` with no readiness gate (FR-022) and no worker, so the run never left `queued`.
- **Unspendable referral rewards (spec 004 FR-009).** They went only to the legacy `CreditsLedger`, while spending and the shown balance read the canonical ledger.

## Proposed outcome

- **One generation path.** `run_generation(db, rack, request)` holds the whole generate flow; any error after the run exists rolls back and sets the run `failed`.
- **Admin rerun** uses `run_generation`: 404 for a missing or deleted rig, 409 `RIG_NOT_COMPUTABLE` (with the gate code, no run) when the gate fails, otherwise the terminal run. The admin page shows refusals.
- **Referral rewards** for a provider-verified purchase are also written to the canonical ledger as a `grant`, keyed per referral, so they count once and can be spent. The user-callable legacy purchase route never earns a spendable reward (Codex review). No verified purchase path exists yet (spec 004 Machine B), so rewards stay unspendable until it does.

## Affected users / systems

Patch generation, admin runs API and page, referral rewards (off by default: `enable_legacy_referrals`).

## Constraints / non-goals

No change to generation output or the readiness gate. The legacy ledger is kept for history.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| A dual-write failure leaves the run `failed` | `OBSERVED` | `test_a_run_that_fails_after_generation_ends_failed` |
| Rerun is gated and terminal | `OBSERVED` | `test_admin_rerun_*` |
| A verified reward is spendable once; a self-reported one isn't | `OBSERVED` | `test_a_referral_reward_is_spendable_once`, `test_a_self_reported_purchase_earns_no_spendable_reward` |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-29
