# Intent

## Problem

Spec 004 Machine B has an `Unresolved --operator_resolves--> Credited` row (same effect as the verified completion), but only reject exists (T048). An unresolved Checkout Session event can be closed with no grant, never credited. PatchHive keeps only the event's payload hash, and Stripe serves events for 30 days only, so there is nothing local to replay (research 2026-11-01 §1). OQ-5 was decided `A_refetch_session`.

## Proposed outcome

- `POST /api/admin/commerce/events/{id}/resolve`, Admin only, reason required, beside reject.
- It retrieves the Checkout Session from the provider by the `object_id` T046 stores at intake (`StripeCheckoutProvider.retrieve_checkout_session`), and runs Machine B's fulfillment (`handle_checkout_session_event`) once on it, in a savepoint, only when the provider reports it `paid`.
- The event becomes `processed` (or `duplicate` when the payment was already credited), or stays `unresolved` with the new reason code. One `CanonicalAdminAuditEventRecord` (`commerce.event.resolve`) per resolve that reaches fulfillment.
- Fail closed with no write (event stays unresolved, no ledger entry, no audit): not `unresolved` (409 `INVALID_TRANSITION`), not a Machine B type (409 `RESOLVE_NOT_SUPPORTED`), no stored object id (409 `OBJECT_ID_MISSING`), payments gate refuses (the checkout codes and statuses), provider error (502 `PAYMENT_PROVIDER_ERROR`), wrong object returned (502 `PROVIDER_OBJECT_MISMATCH`).
- `operator_resolves` rows in the transitions test.

Out of scope: Machine C resolve (T049), refunds, frontend, flag changes, migrations.

## Affected users / systems

Admin commerce routes, `canon/checkout.py` (provider client, resolve), webhook event records, canon ledger and referrals through Machine B.

## Constraints / non-goals

Payments flags keep their defaults (`ENABLE_CREDIT_CHECKOUT=false`, `STRIPE_TEST_MODE=true`, `ALLOW_PRODUCTION_PAYMENTS=false`); the same `checkout_gate` refuses resolve, so a live key is refused outside activated production. Tests use a fake retriever or `httpx.MockTransport`; no network. The provider client sends only the session id (URL-quoted) and the key in the header; errors never carry the key.

## Open questions

- A refused resolve (provider unreachable, gate closed) writes no audit record, as a refused reject does. An attempt that reaches fulfillment and still cannot map the session is audited. Owner to confirm that split.
- A resolve whose payment was already credited by a later delivery records the event as `duplicate`, not `processed`. Owner to confirm.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Stripe returns a Checkout Session by id with `GET /v1/checkout/sessions/{id}` | `OBSERVED` | Stripe API reference (Retrieve a Checkout Session) |
| Two overlapping resolves credit once | `OBSERVED` | `tests/acceptance/test_operator_resolve_postgres.py` |
| The retrieved session carries the metadata Machine B checks | `INFERRED` | The session is created with that metadata (`StripeCheckoutProvider.create_checkout_session`) |

## Author / date

- Author: Claude (agent), for Daniel Meyer
- Date: 2026-11-02
