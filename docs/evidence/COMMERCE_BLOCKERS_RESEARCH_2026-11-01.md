# Commerce blockers: research, 2026-11-01

Spec 004 work that is blocked, and what the provider documentation settles. Sources are Stripe's own docs, read 2026-11-01. Decisions marked "owner" stay open; this note only narrows them.

## 1. OQ-5: operator resolve and reject (T048)

**Done (T048, reject):** an `unresolved` event can be closed by an Admin with a reason. It becomes `rejected` (Machine B `operator_rejects` → Abandoned), grants nothing, keeps its `reason_code`, and writes one `CanonicalAdminAuditEventRecord` (`commerce.event.reject`, before and after state hashes). Any other status answers 409 `INVALID_TRANSITION`. Admin readers can list unresolved events. This follows OQ-5's recommendation: Admin only, one canonical audit record per action, a reason required. Ops can't reject, even though Ops may run other admin mutations, because these events move money.

**Not done (T048b, resolve):** `operator_resolves` → Credited means "the same effect as the verified completion", which is Machine B's handler (T046). Two facts shape it:

- PatchHive stores only `payload_hash` for each event, not the event, so there is nothing local to re-apply.
- Stripe returns an event from the API "if it was created in the last 30 days" ([Retrieve an event](https://docs.stripe.com/api/events/retrieve)). Re-fetching the event works only inside that window.

Recommendation for T048b, after T046:

- Store the event's `data.object.id` (the Checkout Session id, which isn't personal data) at intake.
- At resolve time, retrieve the Checkout Session from the API and run the same idempotent fulfillment as the webhook path.
- Write one audit record, as reject does.
- If the object can't be retrieved, keep the event unresolved (fail closed).

## 2. Machine B (T046): what checkout fulfillment must handle

From [Fulfill orders](https://docs.stripe.com/checkout/fulfillment.md?ui=full-page):

- **Delayed payment methods.** Bank debits and transfers don't settle at checkout completion. They "generate a `checkout.session.async_payment_succeeded` event when payment succeeds later". The spec and `EVENT_HANDLERS` list only `checkout.session.completed`. T046 should handle `async_payment_succeeded`, and `async_payment_failed` to abandon the checkout.
- **Check `payment_status`.** A completed session can still be `unpaid`, so credit only when the session is paid.
- **Idempotency.** Fulfillment "might be called multiple times, possibly concurrently, for the same Checkout Session". T046's `purchase:<payment_id>` key and the unique payment id already cover this. Keying on the session id as well would make the landing-page path safe too.
- **Webhooks are required.** A landing-page trigger is optional on top, never instead.

Recommended spec change when T046 starts: Machine B's `checkout_completed` row requires `payment_status = paid`, and an `async_payment_succeeded` row leads to the same Credited effect. That needs no owner decision; it is how the provider reports a payment.

## 3. OQ-4: which subscription statuses grant access (owner)

From [How subscriptions work](https://docs.stripe.com/billing/subscriptions/overview):

| Stripe status | What Stripe says | Recommended tier effect |
|---|---|---|
| `trialing` | "you can safely provision your product" | the paid tier, if PatchHive offers trials (none planned) |
| `active` | "in good standing" | the paid tier |
| `past_due` | the latest invoice failed; Stripe may retry | keep the tier during retries (grace), with no new period grant |
| `unpaid` | "Revoke access to your product when the subscription is `unpaid`" | FREE |
| `incomplete` | first payment pending, 23 hours to pay | FREE |
| `incomplete_expired` | first payment never succeeded | FREE |
| `canceled` | terminal | FREE |
| `paused` | trial ended without a payment method | FREE |

**Period grants (Machine C).** Stripe sends `invoice.paid` when a subscription invoice is paid and says to listen for it. The spec's grant key `subscription-period:<subscription_id>:<period_start>` fits that event. `EVENT_HANDLERS` today lists only `customer.subscription.*`, so T049 should add `invoice.paid` as the grant trigger. The `customer.subscription.*` events then only update the stored status and tier.

The owner still decides whether `past_due` keeps access. The table's grace recommendation matches Stripe's retry model.

## 4. Still owner-only (unchanged)

- **OQ-1:** prices and credit quantities.
- **OQ-3:** does a subscription's first paid invoice count as the referral "first purchase"? Recommendation: yes, through `record_purchase(payment_verified=True)`.
- **OQ-7:** proration.
- **OQ-8:** what STUDIO "unlimited" means.

Nothing in the provider docs settles these; they are pricing and product choices. T046 needs OQ-1 and T001. T049 needs OQ-3, OQ-4, OQ-7 and OQ-8. T050 (tier from subscription) follows T049.
