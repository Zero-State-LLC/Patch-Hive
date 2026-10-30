# Intent

## Problem

Spec 004 gap closure T044 and T045.

- Two balance endpoints disagree. `GET /api/monetization/credits/balance` sums the legacy ledger; spending reads the canonical one. The referral summary's `earned_credits` also reads the legacy ledger, so it can show credits a user cannot spend (FR-009, FR-031, research R6).
- The Stripe webhook stores every event as `received` and never looks at it again. `processed_at` is never set, and there is no unresolved state (FR-011, FR-014, research R1).

## Proposed outcome

- T044: the legacy balance route is gone. `earned_credits` sums the user's canonical `grant` entries keyed `referral-reward:<referral id>` for their own referrals.
- T045: one event processor runs inside the webhook transaction after verification. It dispatches by event type and sets `status` to `processed`, `duplicate`, `unresolved` (with a `reason_code`) or `ignored`, and sets `processed_at`. A migration adds `reason_code` and moves any stored `received` row to `unresolved` (`RECEIVED_BEFORE_PROCESSOR`), since the payload was never stored and cannot be replayed. No event stays `received`.
- Out of scope: Machine B and C handlers (T046, T049), the legacy purchase route (T043), operator resolve (T048), payment activation (T051).

## Affected users / systems

Commerce backend (`canon/exports.py`, `canon/routes.py`, `canon/models.py`, `canon/contracts.py`, `monetization/`), one Alembic migration, the TypeScript contract binding in `frontend/src/types/canon.ts`.

## Constraints / non-goals

Payments stay in test mode; `STRIPE_TEST_MODE` and `ALLOW_PRODUCTION_PAYMENTS` defaults do not change. The processor grants no credits: no handler that writes ledger entries exists until T046. Fail closed: the provider event types whose machine is not built yet are recorded `unresolved`, not `ignored`.

## Open questions

- Which provider event types count as "owned by a machine not built yet"? Chosen: `checkout.session.completed` and `customer.subscription.created/updated/deleted`, the four types the observed integration handled (STRIPE_INTEGRATION_PROMPT.md). Everything else is `ignored`. T046 and T049 replace these with real handlers.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| No frontend code calls `/api/monetization/credits/balance` | `OBSERVED` | grep of `frontend/src`; `getBalance` uses `/canon/credits/balance` |
| Canonical referral rewards are keyed `referral-reward:<pending referral id>` | `OBSERVED` | `monetization/referrals.py` `apply_referral_reward` |
| The webhook payload is not stored, so legacy `received` rows cannot be reprocessed | `OBSERVED` | `canon/models.py` `StripeEventRecordModel` has only `payload_hash` |
| The observed integration handled four event types | `OBSERVED` | `STRIPE_INTEGRATION_PROMPT.md` webhook handler |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-29
