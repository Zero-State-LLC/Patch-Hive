# Intent

## Problem

Spec 004 T047 asks for proof that a referral reward is earned through a real provider purchase (Machine B, T046), not only through a direct `record_purchase` call: one spendable canonical reward on the referred user's first purchase, none on a duplicate delivery, and one when two first purchases race (FR-026, FR-027, FR-032, SC-002). T046 has a single happy-path test; the duplicate and concurrent cases were untested on the webhook path.

## Proposed outcome

- Unit tests (SQLite) that open a checkout with a fake provider and deliver signed `checkout.session.*` events through `receive_stripe_webhook`: first purchase writes one `referral-reward:<id>` canonical grant that the referrer can spend; duplicates (same event id, new event id, async repeat), a later purchase and an unresolved purchase write none.
- A Postgres acceptance test: two concurrent first purchases on two connections write one reward.
- Code changes only if a test exposes a real bug. None did.

Out of scope: operator resolve (T048b), Machine C, refunds, any flag change.

## Affected users / systems

Tests only: `backend/tests/unit/`, `backend/tests/acceptance/`, `specs/004-commerce/tasks.md`.

## Constraints / non-goals

No network, no live keys, fake provider only. Payments flags keep their defaults. T047 stays `[ ]` because T046 is open (`check_spec_dag --strict`).

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The concurrent test detects a missing referral lock | `OBSERVED` | Removing `.with_for_update()` in `apply_referral_reward` (local run, reverted) fails the test with `uq_referrals_one_reward` |
| A repeated event id is answered from its record without re-running the handler | `OBSERVED` | `receive_stripe_webhook` returns `duplicate=True` for a stored event id |

## Author / date

- Author: Claude (agent), for Daniel Meyer
- Date: 2026-11-02
