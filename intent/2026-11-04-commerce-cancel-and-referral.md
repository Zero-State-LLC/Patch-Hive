# Intent

## Problem

The owner settled three commerce questions on 2026-11-04 (decisions 42, 43 and 44, recorded in `docs/evidence/OWNER_DECISIONS_2026-11-04.md`, open PR #278). The code doesn't follow two of them, and the third has no test:

- 43: `request_subscription_cancel` refuses everything except `active`, so a subscriber on a trial or in payment retries can't schedule a cancel.
- 44: `apply_referral_reward` writes a 3-credit spendable grant into a referrer's account even after that account is deleted and anonymised. Nobody can spend it.
- 42: a paid invoice on a canceled subscription grants credits, and nothing pins that.

## Proposed outcome

`active`, `trialing` and `past_due` can schedule a cancel; terminal statuses and the flag-off answer don't change. A deleted referrer gets no reward in either ledger, the referral stays `Pending`, an audit row records why, and the buyer's purchase goes through unchanged. A test pins decision 42. The spec lines that contradict the decisions are updated.

Out of scope: decision 45 (tiers), anything parked by decision 46, ticking T046 to T053 or T090, and spec 004's T001 record (open PR #281).

## Affected users / systems

Payments code behind flags that stay off: `backend/canon/subscriptions.py`, `backend/monetization/referrals.py`, their tests, and `specs/004-commerce/spec.md`. No frontend: `frontend/src` has no subscription or cancel control.

## Constraints / non-goals

Payments stay test-mode and nothing here turns on sales. Ledger and referral rows stay append-only, with no new Machine A state. The buyer's purchase must not fail or wait on anything but a short row lock. No migration.

## Open questions

`unpaid`, `paused` and `incomplete` aren't in decision 43's list, so they stay refused with 409. The code's `_live_subscription` still counts them as live, so such a user can neither cancel here nor open a new checkout. The owner decides whether that needs a change.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Only `apply_referral_reward` writes referral rewards | `OBSERVED` | `grep` for `referral-reward` and `Referral reward` across `backend` |
| A reward and a deletion of its referrer serialize on the referrer's row | `OBSERVED` | `tests/acceptance/test_referral_purchase_postgres.py` on Postgres; the first race test fails with the lock removed |
| `frontend/src` has no cancel control to update | `OBSERVED` | `grep -ri subscription frontend/src` finds nothing |
| Stripe accepts `cancel_at_period_end` on `trialing` and `past_due` | `INFERRED` | Stripe's docs show the call and don't limit it by status; not run against a Stripe test account |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-04
