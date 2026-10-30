# Intent

## Problem

`POST /api/monetization/purchases` took a client-chosen `credits_delta` and wrote a `Purchase` ledger row (spec 004 FR-033, OQ-11, research R5). It mints no spendable credit since #131, but the row can use up a referred user's first-purchase slot (EC-3). It shared one flag, `enable_legacy_referrals`, with referral signup and the referral summaries.

## Proposed outcome

- Delete the route, `PurchaseCreate` and the now-empty `monetization` router mount (owner chose option A, decision 2 in `docs/evidence/OPEN_DECISIONS_2026-10-30.md` on PR #148).
- Replace `enable_legacy_referrals` with `enable_referrals` (default false) for referral signup, `/api/community/users/me/referrals` and `/api/me/referrals`. The old flag is removed.
- Replace the negative test with one that asserts the route is gone whatever the flag.

Out of scope: dropping tables, migrations, and `record_purchase` (its `payment_verified` path is the future provider caller, T046).

## Affected users / systems

Backend monetization, community and account routes; settings; `.env.example`, staging compose, docs. Payment flags untouched.

## Constraints / non-goals

Payments stay test-mode. No schema change. Fail closed: the new flag defaults off.

## Open questions

None. Deploy note: any host that sets `ENABLE_LEGACY_REFERRALS` loses referrals until it sets `ENABLE_REFERRALS`.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| No frontend code calls the route | `OBSERVED` | grep of `frontend/src` |
| `record_purchase` has no production caller after this change | `OBSERVED` | grep; tests only |
| No table is orphaned (`credits_ledger`, `referrals` still used) | `OBSERVED` | referral summary and reward code |

## Author / date

- Author: Claude
- Date: 2026-10-30
