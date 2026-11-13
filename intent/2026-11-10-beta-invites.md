# Intent

## Problem

The next milestone is a closed staging beta, but anyone can sign up on staging, and a new account has no credits, so its first export answers 402.

## Proposed outcome

- While `ENABLE_INVITE_ONLY_SIGNUP` is on, sign-up needs a one-use invite code.
- An admin mints codes at `/admin/invites`. Each carries a number of test credits.
- Redeeming a code creates the account and grants its credits in one transaction, through the same ledger path as an admin grant.
- The flag is on in the staging Worker only. Production never receives it, so production sign-up doesn't change.

Out of scope: inviting by email, expiring codes, and selling credits.

## Affected users / systems

Staging sign-up, the admin console, a new `beta_invites` table, and the Rig owners who join the beta.

## Constraints / non-goals

- Only a code's hash is stored, and the code appears once, in the reply that mints it.
- A missing, wrong or used code gets one reply, ahead of every other sign-up check, so sign-up tells an uninvited caller nothing about which accounts exist.
- Credits are test credits. Payments stay in test mode and there are no sales during beta (decision 32).

## Open questions

None for this slice.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| One code makes one account and one grant | `OBSERVED` | `backend/tests/api/test_beta_invites.py` |
| Two simultaneous sign-ups with one code can't both win | `INFERRED` | One conditional update and a unique `redeemed_by`; no concurrent test against Postgres |
| Production never receives the flag | `OBSERVED` | `optionalEnv` in `edge/api/src/index.ts` drops `FLAG_VARS` in production |

## Author / date

- Author: Claude Opus 5.5, for the owner
- Date: 2026-11-10
