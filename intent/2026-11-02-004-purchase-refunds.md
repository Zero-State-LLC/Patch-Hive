# Intent

## Problem

Spec 004 Machine B credits a one-time purchase but has no refund or dispute path (EC-12, OQ-2). A provider refund of a credited payment leaves the credits spendable, and `charge.refunded` and `charge.dispute.created` are `ignored`. OQ-2 was decided 2026-11-01 by Jev (owner-delegated), `A_reverse_unspent` (confidence 0.96, a lawyer must confirm): on a provider refund, reverse only unspent credits, record the remainder as unresolved for the operator, never go negative, never revoke a referral reward.

## Proposed outcome

- `charge.refunded` for a Machine B payment, found by `payment_intent` on its `provider_payments` record (`handle_payment_reversal_event` in `canon/checkout.py`):
  - Credits taken back by a cumulative `amount_refunded` are `floor(credits * amount_refunded / amount_cents)` (`credits_for_refund`). They are proportional to the amount paid, including the minimum charge. They round down, so a partial refund never takes back more than its share, and a full refund takes back exactly the credits purchased. The formula runs on the cumulative amount, so rounding does not add up across partial refunds.
  - Cap: the credits reversed now are `min(owed, current canonical balance)`, read under the same per-user lock an export debit takes. Credits are fungible, so any unspent credits count, not only the ones from this purchase. A balance never goes negative.
  - One append-only canonical `refund` entry, delta `-reversed`, keyed `purchase-refund:<payment_intent>:<amount_refunded>`. No entry when nothing is reversed.
  - The record keeps `refunded_cents` (the highest cumulative amount applied), `refund_reversed_credits` and `refund_unrecovered_credits`, and becomes `partially_refunded` or `refunded`.
  - Spent credits (`refund_unrecovered_credits` grew): the event is `unresolved` with `REFUND_EXCEEDS_UNSPENT` for the operator, and the reversal of the unspent part still commits (`EventDisposition.commit_effects`).
  - Idempotent: an `amount_refunded` no higher than `refunded_cents` is `duplicate` (`REFUND_ALREADY_RECORDED`). This covers a redelivered event, a new event id with the same total and an older total delivered late. The payment row lock serializes concurrent deliveries, and the unique ledger key backs them up.
- `charge.dispute.created`: `unresolved` (`DISPUTE_OPENED`), with no reversal. When a dispute opens, its outcome is unknown: the user may win, or the dispute may be withdrawn. Reversing then and restoring later would be two ledger movements for one operator decision. The operator sees it in the unresolved queue and decides with the dispute outcome.
- `refund.failed`: `unresolved` (`REFUND_FAILED`). Credits already reversed are not restored automatically.
- Unknown payment (`PAYMENT_RECORD_NOT_FOUND`), missing payment id (`PAYMENT_ID_MISSING`), amount, currency or over-refund mismatch (`AMOUNT_MISMATCH`), customer mismatch (`CUSTOMER_MISMATCH`), malformed payload (`EVENT_PAYLOAD_MALFORMED`), and a refund of a payment never credited (`PAYMENT_STATE_CONFLICT`) are all `unresolved`, and nothing is written. This matches T046.
- Referral rewards are untouched. The reward is the referrer's grant, and nothing here writes to the referrer or to `Referral` rows (FR-030).
- Migration `20261102_purchase_refunds` (revises `20261102_credit_checkout`, single head): three refund columns with default 0, and two new statuses in `ck_provider_payments_status`.
- `reconcile_ledger` counts only export-linked reversals, so a purchase refund is not reported as an export reversal.
- Tests: rows in the transitions test (Machine B refunds and disputes; Machine A `Rewarded --refund_processed--> Rewarded`), unit, webhook API, and Postgres acceptance tests (concurrent duplicate refunds reverse once; a refund after partial spend reverses only the remainder; a refund racing a spend never goes negative).

Out of scope: Machine C (subscription invoice) refunds (T049), `refund.created` / `refund.updated` (see Open questions), dispute closure (`charge.dispute.closed` stays `ignored`), operator resolve of refund events (resolve stays `RESOLVE_NOT_SUPPORTED` for non-checkout types; an operator rejects to close them), legacy `credits_ledger` rows, frontend, and flag changes.

## Affected users / systems

Webhook intake and the event processor (`canon/webhook_events.py`), Machine B (`canon/checkout.py`), `provider_payments`, the canonical credit ledger and balance, and the operator unresolved queue.

## Constraints / non-goals

Payments flags keep their defaults (`ENABLE_CREDIT_CHECKOUT=false`, `STRIPE_TEST_MODE=true`, `ALLOW_PRODUCTION_PAYMENTS=false`). Refund events arrive only through the signed webhook. Nothing calls the provider. Tests use signed fixture events and no network or keys. The ledger stays append-only. This is not legal advice: OQ-2 and OQ-13 need a lawyer to confirm.

## Open questions

- Lawyer to confirm OQ-2 itself (reverse unspent only; the provider-side refund of spent credits is a loss PatchHive absorbs, or the operator pursues).
- Owner to confirm the rounding rule (round down, cumulative) and the cap (current balance, any unspent credits, not only this purchase's).
- `charge.refunded` is the only event that reverses credits. Its `amount_refunded` is cumulative, so full and partial refunds and their ordering need no per-refund storage. Subscribing to `refund.created` / `refund.updated` as well would need a per-refund table to avoid double reversal. Owner to confirm.
- A buyer's own referral-reward credits (as a referrer) are part of their balance and can cover a reversal. Owner to confirm this does not count as revoking a reward. The referrer's reward for this purchase is never touched.
- `refund.failed` after a reversal: the operator restores credits by hand (admin grant). Owner to confirm.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| `charge.refunded` occurs whenever a charge is refunded, including partial refunds | `OBSERVED` | Stripe API reference, Types of events |
| `amount_refunded` on a Charge is the cumulative refunded amount | `INFERRED` | Stripe Charge object reference ("can be less than the amount attribute on the charge if a partial refund was issued") |
| `refund.failed` is sent when a refund has failed, for all refund types | `OBSERVED` | Stripe Refunds docs; changelog 2024-10-28 |
| Concurrent duplicate refund deliveries reverse once | `OBSERVED` | `tests/acceptance/test_purchase_refund_postgres.py` |
| A refund after partial spend reverses only the unspent remainder and never goes negative | `OBSERVED` | unit and acceptance tests |

## Author / date

- Author: Claude (agent), for Daniel Meyer
- Date: 2026-11-02
