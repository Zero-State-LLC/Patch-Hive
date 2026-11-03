# Intent

## Problem

Spec 004 Machine B (one-time credit purchase, T046) does not exist. `checkout.session.completed` is answered by `_machine_not_built` (`unresolved`, `HANDLER_NOT_IMPLEMENTED`), no provider customer link or payment record exists, and nothing calls `record_purchase(payment_verified=True)` (FR-006, FR-011, FR-012, FR-014, FR-020, FR-028).

## Proposed outcome

- A credit checkout route that refuses unless the new `ENABLE_CREDIT_CHECKOUT` flag is on (default off, FR-019), refuses in production unless `ALLOW_PRODUCTION_PAYMENTS` is on, and refuses a live provider key while `STRIPE_TEST_MODE=true`.
- One provider customer link per user, and one payment record per checkout session, unique on the provider payment id once known.
- Webhook handlers for `checkout.session.completed` (credit only when `payment_status == "paid"`), `checkout.session.async_payment_succeeded` (credit), `checkout.session.async_payment_failed` (failed, no credit) and `checkout.session.expired` (abandoned, no credit). Crediting appends a canonical `purchase` entry keyed `purchase:<payment_id>` and calls `record_purchase(payment_verified=True)` in the webhook transaction. A duplicate delivery is `duplicate`; a malformed or unmappable event is `unresolved` with a reason code.
- The event's `data.object.id` is stored at intake for T048b.
- One reversible migration, `20261102_credit_checkout`.

Out of scope: subscriptions (Machine C, T049; subscription-mode sessions stay `HANDLER_NOT_IMPLEMENTED`), operator resolve (T048b), refunds (OQ-2), frontend, turning sales on (OQ-13 `D_defer_sales`; the flag stays off), payment activation (T051).

## Affected users / systems

Canon ledger (new `purchase` entry type), legacy `credits_ledger` and referrals via `record_purchase`, webhook processor, payments flags, Alembic.

## Constraints / non-goals

Payments stay test-mode by default; no live keys in the tree; webhook tests use signed fixture events and a fake provider client. Fail closed: the payment record the server wrote, not event metadata, decides the user, credit count and amount. The customer is created with the user id only (no email or name), since disclosure to the provider is NOT_COMPUTABLE in the spec.

## Open questions

- OQ-1 prices are ratified only provisionally (Jev, confidence 0.29): $0.20/credit, $5.00 minimum charge, USD. Implemented as the observed rule `max(500, credits * 20)` cents (STRIPE_INTEGRATION_PROMPT.md). Owner to confirm.
- OQ-13 defers sales until counsel drafts terms. Building the machine behind an off flag does not sell anything; enabling it is an owner decision.
- The per-checkout quantity bound (1 to 1000 credits) is an engineering input bound, not a spec rule.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| `record_purchase` refuses unverified purchases | `OBSERVED` | `backend/monetization/referrals.py` |
| The webhook handler runs in a savepoint in the intake transaction | `OBSERVED` | `process_stripe_event` in `backend/canon/webhook_events.py` |
| A completed session can be `unpaid`; delayed methods settle with `async_payment_succeeded` | `OBSERVED` | docs/evidence/COMMERCE_BLOCKERS_RESEARCH_2026-11-01.md §2 |
| The payment intent id may be absent until the session is paid | `INFERRED` | Stripe Checkout creates the PaymentIntent at confirmation; the record keys the session id and fills the payment id on payment |

## Author / date

- Author: Claude (agent), for Daniel Meyer
- Date: 2026-11-02
