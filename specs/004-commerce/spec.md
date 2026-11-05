# 004: Commerce: tiers, credits, referrals

Status: DRAFT (2026-10-16). Filled by Opus 5.5 via OpenRouter from the repo docs and code listed under Sources. Each claim is labeled `[OBSERVED: <file>]` or `[INFERRED]`. The operator must confirm every `[INFERRED]` item before planning.

- **[OBSERVED: <file>]** means a source states the item.
- **[INFERRED]** means the item is derived from the sources or the constitution. The operator must confirm it.

No requirement is confirmed until the operator signs off. Prices, tier quantities, and legal or tax status come from an implementation prompt, not from a ratified pricing decision. See [Open questions](#open-questions).

## Sources

- `STRIPE_INTEGRATION_PROMPT.md`. This is an implementation prompt. It describes intended behavior, not verified shipped behavior. The excerpt was truncated at `cancel_subscription`.
- `REFERRAL_IMPLEMENTATION.md`. This file states the referral canon rules.
- `backend/monetization/`. The retained files are `routes.py` and `referrals.py`. The prompt proposes `stripe_models.py` and `stripe_service.py`, but neither is retained.
- `docs/SECURITY.md`. Its contents were not provided when this spec was drafted. It now exists; see OQ-10.

## Summary

PatchHive sells access tiers and credits through a payment provider. The sources name Stripe as that provider. A PatchBook export spends credits. Users can buy credits once or subscribe to a tier that grants credits each billing period. A referrer earns a one-time credit reward when a referred user makes a first paid purchase. All credit changes are recorded in an append-only ledger.

Why: monetization funds the product. Commerce must not leak into canon. Tier, credit, and referral state never change what PatchHive generates, shows, or lets a user explore. The constitution sets three rules for this boundary:

- Canon is deterministic.
- Evidence is not canon.
- Commerce fails closed at trust boundaries.

## Implementation status (2026-11-03)

Checked against the code on `main` at 3688037 (0.3.0-alpha.6). Paths are under `backend/` unless shown otherwise. The 2026-10-29 table had been patched row by row since; its rows counted 16 implemented, 10 partial and 10 missing. Machine B (#209, #210, #211, #214), Machine C (#219, #224), the event processor (#145) and the webhook hardening (#139) closed 16 of them. Totals: 32 implemented, 4 partial, 0 missing. "Implemented" means the code and its tests exist on `main`; every provider path is still off by default (`ENABLE_CREDIT_CHECKOUT`, `ENABLE_SUBSCRIPTION_CHECKOUT`, `STRIPE_TEST_MODE=true`, `ALLOW_PRODUCTION_PAYMENTS=false`; `core/config.py`) until T051, and the prices and credit counts stay unconfirmed (OQ-1, T001). Gaps map to [research.md](research.md) and the Gap closure tasks in [tasks.md](tasks.md).

| FR | Status | Evidence |
|---|---|---|
| FR-001 | Implemented | Tier names and Design Engine family floors (`canon/entitlements.py`). Since T050 (#224) `resolve_user_tier` returns the tier of the newest subscription whose provider status is `active`, `trialing` or `past_due` (`ENTITLED_STATUSES`, OQ-4), FREE for a user whose subscriptions are all lapsed, and `design_engine_default_tier` for a user who never subscribed. Used by `get_design_entitlements` (`canon/routes.py`). |
| FR-002 | Partial | Signup writes no ledger entry (`community/auth_routes.py`). "Demo mode only" is not defined, and the default tier for a user who never subscribed is `core` (`canon/entitlements.py`, `core/config.py`). |
| FR-003 | Implemented | `invoice.paid` writes one `SubscriptionPeriodGrantRecord` per billing period, keyed `subscription-period:<subscription_id>:<period_start>`. CORE gets 25 and PRO 100 credits as a canonical `grant` (`SUBSCRIPTION_CREDITS_CORE/PRO`, provisional OQ-1; `canon/subscriptions.py`, `core/config.py`) and STUDIO gets the unlimited entitlement (#219). Prices stay unconfirmed (OQ-1). |
| FR-004 | Implemented | STUDIO period grants carry `unlimited=true` and `fair_use_export_cap` (`SUBSCRIPTION_STUDIO_FAIR_USE_EXPORTS_PER_PERIOD`, default 100) and no credits; no numeric sentinel (`canon/subscriptions.py`, #219). An export covered by one takes no debit and counts against the cap, refused 429 `FAIR_USE_CAP_REACHED` at the cap (`canon/exports.py`, `canon/entitlements.py`, #224). |
| FR-005 | Implemented | Server-set price `patchbook_export_cost = 3` (`core/config.py`, `canon/routes.py`); 503 `EXPORT_FULFILLMENT_UNAVAILABLE` before any debit (#129). |
| FR-006 | Implemented | `credit_charge_cents` charges `max(minimum, credits * price)` with `credit_price_cents = 20` and `credit_minimum_charge_cents = 500`; `POST /api/canon/checkout/credits` behind `ENABLE_CREDIT_CHECKOUT` (`canon/checkout.py`, `canon/routes.py`, `core/config.py`, #209). The rule is provisional (OQ-1). |
| FR-007 | Implemented | The canonical ledger writes `purchase` (`canon/checkout.py`), `debit` and `reversal` (`canon/exports.py`), `grant` (`canon/subscriptions.py`, referral rewards) and `refund` (`canon/checkout.py`, #214); `debit` is the spec's Spend. The legacy `credits_ledger` keeps `Purchase`, `Spend`, `Grant` (`monetization/referrals.py`). |
| FR-008 | Partial | Postgres triggers reject `UPDATE` and `DELETE` on `canonical_credit_ledger` (migration `20261029_ledger_append_only`, #139). The legacy `credits_ledger`, `referrals`, `subscription_period_grants` have no database guard (`tasks.md` T010), and SQLite has no trigger. |
| FR-009 | Implemented | One balance endpoint, `GET /api/canon/credits/balance`, sums the canonical ledger for the user (`canon/routes.py`, `canon/exports.py`). The legacy `/api/monetization/credits/balance` and `monetization/routes.py` are gone (#145). |
| FR-010 | Implemented | No expiry field or logic in either ledger (`canon/models.py`, `monetization/models.py`). |
| FR-011 | Implemented | The webhook credits only on a verified `checkout.session.completed` with `payment_status` paid, or `async_payment_succeeded`, in the webhook transaction (`canon/checkout.py` `_credit`, `handle_checkout_session_event`, #209). Dispatch by `process_stripe_event` (`canon/webhook_events.py`, #145). |
| FR-012 | Implemented | `provider_payments` is unique on the session id and the provider payment id; the canonical entry key is `purchase:<payment_intent>`; a repeat is `duplicate` (`canon/models.py`, `canon/checkout.py`, #209). Event-id replay safety and savepoint on a concurrent duplicate insert (`canon/exports.py`, #139). Subscription periods are unique on `grant_key` and `provider_invoice_id` (`canon/subscriptions.py`). |
| FR-013 | Implemented | Constant-time HMAC over every `v1` value (secret rotation), 300 s tolerance, livemode gate rejecting live events outside production (`canon/exports.py`, #139); `validate_stripe_mode_startup_policy` refuses `STRIPE_TEST_MODE=false` outside production (`core/startup_policy.py`). |
| FR-014 | Implemented | `process_stripe_event` sets every event to `processed`, `duplicate`, `unresolved` (reason code) or `ignored`, and sets `processed_at`; an unresolved outcome rolls its effects back (`canon/webhook_events.py`, migration `20261029_webhook_disposition`, #145). Machine B and C handlers raise reason codes for an unknown customer, an unmapped price, a bad payload and a missing payment id (`canon/checkout.py`, `canon/subscriptions.py`). An event type with no handler is `ignored` with no reason code (`canon/webhook_events.py`). |
| FR-015 | Implemented | `ProviderSubscriptionRecord` holds tier, provider status, current period and `cancel_at_period_end`; `customer.subscription.created`/`updated` sync it (`canon/models.py`, `canon/subscriptions.py`, migration `20261102_subscriptions`, #219). |
| FR-016 | Implemented | `invoice.paid` is the only grant trigger, once per period key; `customer.subscription.*` never grant (`canon/subscriptions.py` `handle_invoice_paid`, `handle_subscription_event`, #219). The Machine C table says the same since the T001 correction (2026-11-04). |
| FR-017 | Implemented | `POST /api/canon/subscription/cancel` calls `request_subscription_cancel`, which sets `cancel_at_period_end` at the provider and locally for the user's `active`, `trialing` or `past_due` subscription (owner decision 43, 2026-11-04; `canon/routes.py`, `canon/subscriptions.py`, #219). |
| FR-018 | Implemented | `customer.subscription.deleted` sets `canceled`, final, and keeps granted credits (`canon/subscriptions.py`, #219). |
| FR-019 | Implemented | `stripe_test_mode = True`, `allow_production_payments = False`, `enable_credit_checkout = False`, `enable_subscription_checkout = False` by default (`core/config.py`); production webhook 403 `PRODUCTION_PAYMENTS_DISABLED`; `checkout_gate` refuses a disabled flag, production without activation, a missing key and a live key outside activated production (`canon/checkout.py`, `canon/routes.py`). |
| FR-020 | Implemented | `ProviderCustomerRecord` is unique on `user_id` and on the provider customer id; `get_or_create_customer` (`canon/models.py`, `canon/checkout.py`, #209). |
| FR-021 | Partial | `users.referral_code` is unique and random, and `ensure_referral_code` sets it only when empty (`community/models.py`, `account/services.py`); nothing at the database blocks a change. |
| FR-022 | Implemented | `/signup?ref=<code>` (`monetization/referrals.py`). |
| FR-023 | Implemented | Behind `enable_referrals` (`community/auth_routes.py`). |
| FR-024 | Implemented | `create_referral` and `apply_referral_reward` (`monetization/referrals.py`). |
| FR-025 | Implemented | `create_referral` rejects pending and rewarded users (`monetization/referrals.py`). |
| FR-026 | Implemented | 3-credit `Grant` with the note and `referral_id`; the spendable canonical copy only for a provider-verified purchase (#131). |
| FR-027 | Implemented | `purchase_count != 1` returns no reward (`monetization/referrals.py`). |
| FR-028 | Implemented | Both provider paths call `record_purchase(payment_verified=True)`: the one-time purchase in `_credit` (`canon/checkout.py`, #209, tested in #210) and a subscription's first paid invoice with `credits_delta=0` (`canon/subscriptions.py`, #219, OQ-3 `A_both`). `record_purchase` raises for an unverified purchase (`monetization/referrals.py`, #183). |
| FR-029 | Partial | Code appends a `Rewarded` row and never edits `Pending`; no database guard (`alembic/versions/20240921_make_referrals_append_only.py` drops the unique pair only). |
| FR-030 | Implemented | The Machine B refund path (T053, `canon/checkout.py`, #214) reverses only the buyer's credits and never touches the referrer's grant or `Referral` rows. |
| FR-031 | Implemented | `get_referral_summary` behind the flag (`community/routes.py`); `earned_credits` now sums canonical `referral-reward:<id>` grants (`monetization/referrals.py`, #145). |
| FR-032 | Implemented | Row lock on the `Pending` row plus `uq_referrals_one_reward` (#98); concurrent first provider purchases write one reward (`tests/acceptance/test_referral_purchase_postgres.py`, #210). |
| FR-033 | Implemented | The legacy `POST /api/monetization/purchases` route and `PurchaseCreate` are deleted (#150); `record_purchase` raises unless `payment_verified` (#183). The only callers are `canon/checkout.py` and `canon/subscriptions.py`. |
| FR-034 | Implemented | No generation module imports `monetization` or `canon.entitlements` (repo grep of `patchhive/`, `intelligence/`, `runs/`, `core/`, `ingest/`). |
| FR-035 | Implemented | The tier is read only at export, to choose a template family (`canon/routes.py`, `canon/entitlements.py`); it is not a generation input. |
| FR-036 | Implemented | Codes come from `secrets.token_urlsafe`, not the email (`monetization/referrals.py`, `account/services.py`). |

## Scope

In scope:

- Tier catalog: FREE, CORE, PRO, and STUDIO. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- One-time credit purchases. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- Subscription lifecycle: checkout, activation, updates, cancellation at period end, and deletion. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- The credits ledger and balance reads. [OBSERVED: backend/monetization/routes.py]
- The referral program: codes, the pending state, the reward, and the summary. [OBSERVED: REFERRAL_IMPLEMENTATION.md, backend/monetization/referrals.py]
- Feature flags that disable payments and legacy referrals. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md, backend/monetization/routes.py]

## Non-goals

- Commerce does not influence patch generation, patch visibility, or exploration. [OBSERVED: REFERRAL_IMPLEMENTATION.md] This spec extends that rule from referrals to tiers and credits. [INFERRED]
- Credits do not expire, and no expiry logic exists. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- Refunds never revoke referral rewards. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- This spec does not define the refund, chargeback, or dispute flow for purchases. That flow is NOT_COMPUTABLE. See [Open questions](#open-questions). [INFERRED]
- This spec does not define tax, invoicing, regional pricing, or legal terms. These are NOT_COMPUTABLE. [INFERRED]
- This spec does not choose a technology stack. The plan holds that decision. [INFERRED]

## User stories

### P1: Buy credits once [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]

As a signed-in user, I want to buy a block of credits so that I can export PatchBooks without subscribing.

Acceptance criteria:

1. **Given** payments are enabled and I am signed in, **when** I request N credits, **then** I am sent to a provider checkout page for that amount. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
2. **Given** the provider confirms that my checkout completed, **when** PatchHive processes the confirmation, **then** it appends one `Purchase` ledger entry of +N credits and one payment record. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
3. **Given** the same completion confirmation arrives twice, **when** PatchHive processes the second one, **then** it does not credit me again. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
4. **Given** I cancel at the provider checkout page, **when** I return to PatchHive, **then** my balance is unchanged and the ledger has no new entry. [INFERRED]
5. **Given** a completion confirmation fails authenticity checks or lacks a resolvable user, **when** PatchHive processes it, **then** it grants no credits and records an explicit unresolved state. [INFERRED]

### P2: Subscribe to a tier [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]

As a user, I want to subscribe to CORE, PRO, or STUDIO so that I receive credits each billing period.

Acceptance criteria:

1. **Given** payments are enabled, **when** I choose a paid tier, **then** I am sent to a provider subscription checkout page for that tier. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
2. **Given** the provider reports that my subscription is active for a known tier, **when** PatchHive processes the report, **then** it records the tier, the status, and the period boundaries, and it grants that tier's credits for the period. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
3. **Given** my subscription is active and the provider sends an update within the same billing period, **when** PatchHive processes the update, **then** it syncs status and period fields and grants no additional credits. [INFERRED] This criterion corrects observed behavior. See FR-016.
4. **Given** the provider reports a price that maps to no known tier, or a customer that maps to no user, **when** PatchHive processes the report, **then** it grants no credits and records an explicit unresolved state. [INFERRED] The observed code silently ignores these cases.

### P3: Earn a referral reward [OBSERVED: REFERRAL_IMPLEMENTATION.md]

As a referrer, I want 3 credits when someone I referred makes a first paid purchase.

Acceptance criteria:

1. **Given** I have a referral code, **when** a new user signs up with my link, **then** PatchHive stores me as the new user's referrer and appends a `Pending` referral row. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
2. **Given** a referred user has a `Pending` referral, **when** their first paid purchase is recorded, **then** PatchHive appends a `Grant` of 3 credits to my ledger and a `Rewarded` referral row. The `Grant` has the note `Referral reward: <referred_user_id>`. [OBSERVED: REFERRAL_IMPLEMENTATION.md, backend/monetization/referrals.py]
3. **Given** the referred user has already been rewarded for, **when** they make another purchase, **then** I receive nothing more. [OBSERVED: backend/monetization/referrals.py]
4. **Given** I try to use my own code, **when** the referral is created, **then** PatchHive rejects it. [OBSERVED: REFERRAL_IMPLEMENTATION.md, backend/monetization/referrals.py]
5. **Given** the referred user's first purchase is later refunded, **when** the refund is processed, **then** my reward stays in my balance. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
6. **Given** a referred user completes a first paid purchase through the payment provider, **when** PatchHive processes it, **then** it evaluates the referral reward through the same path as every other purchase. [INFERRED] The observed provider path bypasses referral evaluation. See FR-028.

### P4: See my balance and referral status [OBSERVED: backend/monetization/routes.py, backend/monetization/referrals.py]

As a user, I want to see my credit balance and my referral activity.

Acceptance criteria:

1. **Given** I am signed in, **when** I request my balance, **then** I see my current credits balance. [OBSERVED: backend/monetization/routes.py]
2. **Given** I am signed in, **when** I open my referral summary, **then** I see the following. [OBSERVED: backend/monetization/referrals.py]
   - My code and my `/signup?ref=<code>` link.
   - Pending referrals, excluding any referred user who is already rewarded.
   - Rewarded referrals.
   - My total credits earned from referrals.

### P5: Cancel my subscription [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]

As a subscriber, I want to cancel so that I am not billed again, and I want to keep access until the period ends.

Acceptance criteria:

1. **Given** I have an active subscription, **when** I cancel, **then** PatchHive flags the subscription to end at the period end. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
2. **Given** the provider reports that the subscription is deleted, **when** PatchHive processes the report, **then** the subscription status becomes `canceled`. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
3. **Given** my subscription is canceled, **when** I check my balance, **then** previously granted credits remain. [INFERRED] Credits do not expire, per REFERRAL_IMPLEMENTATION.md.

### P6: The operator disables commerce safely [INFERRED]

As the operator, I want to turn off payments or legacy referrals without corrupting the ledger.

Acceptance criteria:

1. **Given** payments are disabled, which is the default, **when** a user tries to check out, **then** PatchHive refuses the request and creates no provider session. [INFERRED] The source sets `stripe_enabled` to default false, per STRIPE_INTEGRATION_PROMPT.md.
2. **Given** legacy referrals are disabled, **when** a client calls the purchase-recording endpoint, **then** PatchHive responds "not enabled" and writes nothing. [OBSERVED: backend/monetization/routes.py]
3. **Given** either flag is turned off, **when** a user reads their balance, **then** the existing ledger is unchanged and readable. [INFERRED]

## Functional requirements

### Tiers and pricing

- **FR-001** PatchHive offers four tiers: FREE, CORE, PRO, and STUDIO. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **FR-002** FREE is demo mode only and grants 0 credits on signup. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **FR-003** Each paid tier grants credits per billing period. The source lists CORE at 25 credits each month and PRO at 100 credits each month. It lists STUDIO as unlimited. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md] The source also lists prices of $4.99, $14.99, and $29.99. These prices are unconfirmed. See OQ-1.
- **FR-004** PatchHive represents unlimited credits as an explicit unlimited entitlement. It must not use a large numeric sentinel. [INFERRED] The observed code uses `999999`, per STRIPE_INTEGRATION_PROMPT.md.
- **FR-005** A PatchBook export costs 3 credits. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md] Implemented 2026-10-29 (#129): the server sets the price (`patchbook_export_cost`) and ignores a client cost, and an export that nothing will fulfill is refused with 503 `EXPORT_FULFILLMENT_UNAVAILABLE` before any debit.
- **FR-006** A one-time purchase charges according to a published per-credit rule. The source specifies $0.20 per credit with a $5.00 minimum charge. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md] This rule is unconfirmed. See OQ-1.

### Ledger

- **FR-007** The credits ledger supports these change types: `Purchase`, `Spend`, `Grant`, and `Refund`. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **FR-008** The credits ledger is append-only. PatchHive never updates or deletes an entry. Corrections are new entries. [INFERRED] This follows the skeleton summary and the append-only referral rule in REFERRAL_IMPLEMENTATION.md.
- **FR-009** A user can read their own credits balance. [OBSERVED: backend/monetization/routes.py] The balance is derived only from that user's ledger entries. [INFERRED]
- **FR-010** Credits do not expire. [OBSERVED: REFERRAL_IMPLEMENTATION.md]

### Payments

- **FR-011** PatchHive credits a one-time purchase only after the payment provider confirms that checkout completed. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **FR-012** Payment processing is idempotent for each provider payment identifier. A repeated confirmation never produces a second credit. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **FR-013** PatchHive verifies the authenticity of every provider event before acting on it. It rejects events it cannot verify. [INFERRED] A webhook secret setting appears in STRIPE_INTEGRATION_PROMPT.md, but the verification step is not in the retained excerpt.
- **FR-014** PatchHive fails closed on provider events in these cases. It grants no credits and records an explicit unresolved state for operator review. [INFERRED] The constitution principle 9 requires fail-closed behavior. The observed code returns silently, per STRIPE_INTEGRATION_PROMPT.md.
  - The customer is unknown.
  - The price maps to no tier.
  - The user metadata is missing or malformed.
  - The payment identifier is missing.
- **FR-015** For each subscription, PatchHive records the tier, the provider status, the period start and end, and the cancel-at-period-end flag. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **FR-016** PatchHive grants subscription credits exactly once per subscription billing period. Status or metadata updates within a period grant nothing. [INFERRED] The observed code grants credits on every "created" or "updated" event while the status is `active`, per STRIPE_INTEGRATION_PROMPT.md.
- **FR-017** A user can cancel a subscription. Cancellation takes effect at the period end. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **FR-018** When the provider reports that a subscription is deleted, PatchHive marks the subscription `canceled`. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **FR-019** Payments are disabled by default. They are active only when the operator enables them. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **FR-020** Each user maps to at most one provider customer. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]

### Referrals

- **FR-021** Each user has a unique referral code that is immutable once created. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- **FR-022** The referral link format is `/signup?ref=<referral_code>`. [OBSERVED: backend/monetization/referrals.py]
- **FR-023** Signup with a valid code stores `referred_by` on the new user and appends a `Pending` referral row. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- **FR-024** PatchHive rejects self-referral both when it creates a referral and when it evaluates a reward. [OBSERVED: REFERRAL_IMPLEMENTATION.md, backend/monetization/referrals.py]
- **FR-025** A referred user has at most one `Pending` row. PatchHive rejects a new referral for a user who is already pending or already rewarded. [OBSERVED: backend/monetization/referrals.py]
- **FR-026** The reward is 3 credits. PatchHive appends it to the referrer's ledger as a `Grant` with the following properties. [OBSERVED: REFERRAL_IMPLEMENTATION.md, backend/monetization/referrals.py]
  - The note is `Referral reward: <referred_user_id>`.
  - The entry links to the referral.

  Implemented 2026-10-29 (#131): the spendable copy in the canonical ledger is written once per referral, and only for a provider-verified purchase (`payment_verified`). A self-reported purchase never earns spendable credit.
- **FR-027** The reward fires only when the referred user's `Purchase` ledger count equals exactly 1, a `Pending` row exists, and no `Rewarded` row exists. [OBSERVED: backend/monetization/referrals.py]
- **FR-028** Every provider-confirmed paid purchase, both one-time and subscription, goes through the single purchase-recording path that evaluates referral eligibility. [INFERRED] The observed one-time provider path writes `Purchase` directly and skips referral evaluation. The observed subscription path writes `Grant`, not `Purchase`. Both behaviors appear in STRIPE_INTEGRATION_PROMPT.md. Whether a subscription payment counts as a "paid purchase" is unresolved. See OQ-3.
- **FR-029** Referral rows are append-only. A reward appends a `Rewarded` row with `first_purchase_id` and `rewarded_at`. PatchHive never modifies the `Pending` row. [OBSERVED: REFERRAL_IMPLEMENTATION.md, backend/monetization/referrals.py]
- **FR-030** Refunds never revoke referral rewards. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- **FR-031** The referral summary returns the following. [OBSERVED: backend/monetization/referrals.py]
  - The code and the link.
  - Pending referrals, excluding referred users who are already rewarded.
  - Rewarded referrals.
  - The total of the user's `Grant` entries that link to a referral.
- **FR-032** The `Purchase` entry and its referral evaluation commit atomically. Concurrent purchases by one referred user produce at most one reward. [INFERRED] Implemented 2026-10-28 (#98): the `Pending` row is locked, and the partial unique index `uq_referrals_one_reward` is the backstop.

### Trust boundary

- **FR-033** Only server-side confirmation from a verified payment provider can create a `Purchase` ledger entry. A client-submitted purchase must not mint credits or trigger rewards. [INFERRED] In the observed code, the legacy `/purchases` endpoint accepts an authenticated user's own `credits_delta`. A feature flag gates that endpoint, per backend/monetization/routes.py. ADVERSARY must review this endpoint.
- **FR-034** Referral logic never affects generation, patch visibility, or exploration. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- **FR-035** Tier and credit state may gate whether a user can perform an action, such as an export. That state is never an input to canonical generation, so output for fixed canonical inputs stays identical across tiers. [INFERRED] This follows constitution principle 1.
- **FR-036** A referral code must not let anyone recover or confirm a user's email address. [INFERRED] The observed code derives the code from a truncated hash of the username and email, per backend/monetization/referrals.py. ADVERSARY must review this derivation. Update 2026-10-29: codes are now random (`secrets.token_urlsafe`), so they carry no email [OBSERVED: monetization/referrals.py, account/services.py]. Codes issued before that change were not checked.

## Key entities

- **User**. Holds a referral code, which is unique and immutable, and an optional referrer. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- **Credits ledger entry**. An append-only record of a credit change. It holds the user, the change type, the signed delta, a note, and an optional referral link. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md, backend/monetization/referrals.py]
- **Referral event**. An append-only record that holds the referrer, the referred user, the status (`Pending` or `Rewarded`), the first purchase, and the reward time. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- **Tier**. FREE, CORE, PRO, or STUDIO, with a per-period credit entitlement. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **Provider customer link**. Maps one user to one payment-provider customer. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **Subscription record**. Holds the tier, the provider status, the period boundaries, and the cancel-at-period-end flag. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **Payment record**. A one-time payment keyed by the provider payment identifier. It holds the amount, the currency, the status, and the credits granted. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- **Unresolved commerce event**. A provider event that PatchHive could not safely apply, held for operator review. [INFERRED]

## Workflows

Status: INFERRED skeleton. Confirm before you plan.

- Governing workflows (skills): anti-slop-code, production-systems, google-developer-style.
- Owners: FORGE decomposes, a cloud agent implements, SCRIBE files the compact artifact, ADVERSARY reviews the threat model.
- CI: reuse `.github/workflows/ci.yml` (jobs `backend` and `frontend`). Do not add a new CI path.

## Stateful behavior

This spec defines three machines. Implementers treat each transitions table as the contract. A label in the `effect` cell marks the provenance of each row.

### Machine A: Referral (per referred user)

The effective state is derived from append-only rows. The state is `Rewarded` if any `Rewarded` row exists for the referred user. Otherwise, the state is `Pending` if a `Pending` row exists. Otherwise, the state is `NONE`. [OBSERVED: backend/monetization/referrals.py]

States:

- `NONE`. No referral exists. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- `Pending`. A referral is recorded, and the user has not been rewarded. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- `Rewarded`. The referrer has been rewarded once. [OBSERVED: REFERRAL_IMPLEMENTATION.md]

The initial state is `NONE`. The final state is `Rewarded`.

`Pending` can be permanently non-rewardable. This happens when the first purchase happened without triggering a reward, so the purchase count is already greater than 1. [INFERRED] See EC-3.

| from | event | guard | to | effect |
|---|---|---|---|---|
| NONE | signup_with_code | The code resolves to a user. The referrer is not the referred user. No `Pending` or `Rewarded` row exists. | Pending | Set `referred_by`. Append a `Pending` row. [OBSERVED: REFERRAL_IMPLEMENTATION.md] |
| NONE | signup_with_code | The referrer is the referred user. | NONE | Reject with an error. Write no row. [OBSERVED: backend/monetization/referrals.py] |
| NONE | signup_with_code | The code does not resolve. | NONE | Write no referral row. The signup outcome is unresolved. See OQ-6. [INFERRED] |
| Pending | purchase_recorded | The `Purchase` count is exactly 1. The referrer is not the referred user. No `Rewarded` row exists. The referrer's account is not deleted. | Rewarded | In one atomic unit, append a `Grant` of +3 to the referrer with `referral_id` and the note `Referral reward: <referred_user_id>`. Append a `Rewarded` row with `first_purchase_id` and `rewarded_at`. [OBSERVED: backend/monetization/referrals.py] Atomicity is [INFERRED]. |
| Pending | purchase_recorded | The `Purchase` count is not 1. | Pending | No reward. [OBSERVED: backend/monetization/referrals.py] |
| Pending | purchase_recorded | The `Purchase` count is exactly 1. No `Rewarded` row exists. The referrer's account is deleted (`users.deleted_at`, read under a row lock so it serializes with account deletion). | Pending | No reward in either ledger and no `Rewarded` row. Append one `admin_audit_log` row (`referral_reward_withheld`, `REFERRER_ACCOUNT_DELETED`). The buyer's purchase is unaffected. Owner decision 44, 2026-11-04. |
| Pending | signup_with_code | Any. | Pending | Reject with "already recorded." [OBSERVED: backend/monetization/referrals.py] |
| Rewarded | purchase_recorded | Any. | Rewarded | No operation. [OBSERVED: backend/monetization/referrals.py] |
| Rewarded | refund_processed | Any. | Rewarded | No revocation. [OBSERVED: REFERRAL_IMPLEMENTATION.md] |
| Rewarded | signup_with_code | Any. | Rewarded | Reject with "already rewarded." [OBSERVED: backend/monetization/referrals.py] |

Illegal transitions:

- `Rewarded` to `Rewarded` with a second `Grant`. This is a double reward. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- `Pending` to `Rewarded` on a purchase that is not the first purchase. [OBSERVED: backend/monetization/referrals.py]
- `NONE` to `Pending` for a self-referral. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- `Rewarded` to `NONE` or `Rewarded` to `Pending` for any reason, including refund. [OBSERVED: REFERRAL_IMPLEMENTATION.md]
- Any update or delete of a referral row or a ledger entry. Both are append-only. [OBSERVED: REFERRAL_IMPLEMENTATION.md] The ledger rule is [INFERRED].
- A reward triggered by a client-submitted purchase that has no verified provider confirmation. [INFERRED]

```mermaid
stateDiagram-v2
    [*] --> NONE
    NONE --> Pending: signup_with_code [valid, not self, no prior row]
    NONE --> NONE: signup_with_code [self or unresolved code] / reject
    Pending --> Rewarded: purchase_recorded [purchase count == 1, not rewarded, referrer not deleted]
    Pending --> Pending: purchase_recorded [count != 1 or referrer deleted]
    Rewarded --> Rewarded: purchase_recorded or refund_processed / no-op
    Rewarded --> [*]
```

### Machine B: One-time credit purchase (per checkout)

States:

- `NONE`. No checkout exists. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- `CheckoutOpen`. The provider session exists, and the user is at checkout. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- `Credited`. A payment record and a `Purchase` entry exist. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- `Abandoned`. The user canceled, or the session expired. [INFERRED] A cancel URL appears in STRIPE_INTEGRATION_PROMPT.md.
- `Unresolved`. A provider event could not be safely applied. [INFERRED] This follows constitution principle 9.
- `PartiallyRefunded` and `Refunded`. The provider refunded part or all of a credited payment. [OBSERVED: canon/checkout.py] Decided by OQ-2.

The initial state is `NONE`. The final states are `Credited` and `Abandoned`. `Unresolved` is not a final state. Only an operator action, defined in OQ-5, can exit it.

| from | event | guard | to | effect |
|---|---|---|---|---|
| NONE | request_credits | Payments are enabled. The user is signed in. The quantity is valid. | CheckoutOpen | Get or create the provider customer. Create a payment session that carries the user, the credit count, and the purchase type. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md] |
| NONE | request_credits | Payments are disabled. | NONE | Refuse the request. Create no session. [INFERRED] |
| CheckoutOpen | checkout_completed | The event is verified. The user resolves. The payment identifier is present and unseen. | Credited | Append a payment record. Record the `Purchase` (+N) through the purchase-recording path, which evaluates Machine A. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md] Routing through Machine A is [INFERRED]. See FR-028. |
| CheckoutOpen | checkout_completed | The event is unverified, the metadata is malformed, the user is unknown, or the payment identifier is missing. | Unresolved | Grant nothing. Retain the event for review. [INFERRED] |
| CheckoutOpen | checkout_canceled_or_expired | Any. | Abandoned | Write no ledger entry. [INFERRED] |
| Credited | checkout_completed | The payment identifier has already been processed. | Credited | No operation. This is idempotent. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md] |
| Unresolved | operator_resolves | The operator verifies the identity and the payment. | Credited | Same effect as the verified completion. [INFERRED] |
| Unresolved | operator_rejects | Any. | Abandoned | Grant nothing. [INFERRED] |
| Credited or PartiallyRefunded | provider_refunded | The cumulative refunded amount is higher than any applied. | PartiallyRefunded, or Refunded when fully refunded | Append one `Refund` entry for `floor(credits * refunded / amount)` less earlier reversals, capped at the current balance. Any spent remainder is held as `Unresolved` for the operator. [OBSERVED: canon/checkout.py] Decided by OQ-2. |
| PartiallyRefunded or Refunded | provider_refunded | The cumulative amount was already applied. | Unchanged | No operation. This is idempotent. [OBSERVED: canon/checkout.py] Decided by OQ-2. |
| Credited | dispute_opened | Any. | Credited | No reversal. Hold the event as `Unresolved` for the operator. [OBSERVED: canon/checkout.py] Decided by OQ-2. |

Illegal transitions:

- `Credited` to `Credited` with a second `Purchase` for the same payment identifier. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md]
- A refund reversal for a payment that was never credited, or one that takes a balance below zero. [OBSERVED: canon/checkout.py] Decided by OQ-2.
- `NONE` or `CheckoutOpen` to `Credited` without a verified provider confirmation, including through a client call. [INFERRED]
- `Abandoned` to `Credited`. A new checkout is required. [INFERRED]
- `Unresolved` to `Credited` without operator action. [INFERRED]

```mermaid
stateDiagram-v2
    [*] --> NONE
    NONE --> CheckoutOpen: request_credits [payments enabled]
    CheckoutOpen --> Credited: checkout_completed [verified, new payment id]
    CheckoutOpen --> Unresolved: checkout_completed [unverified or malformed]
    CheckoutOpen --> Abandoned: checkout_canceled_or_expired
    Credited --> Credited: checkout_completed [duplicate] / no-op
    Unresolved --> Credited: operator_resolves
    Unresolved --> Abandoned: operator_rejects
    Credited --> PartiallyRefunded: provider_refunded [part]
    Credited --> Refunded: provider_refunded [all]
    PartiallyRefunded --> Refunded: provider_refunded [rest]
    Credited --> Credited: dispute_opened / held for the operator
    Credited --> [*]
    Refunded --> [*]
    Abandoned --> [*]
```

### Machine C: Subscription (per subscription)

Corrected 2026-11-04 at T001. The earlier table granted on `subscription_created`, `subscription_updated` and `period_renewed`. The code grants only on `invoice.paid`, once per billing period, and `customer.subscription.*` events only sync the record (`backend/canon/subscriptions.py`; T049 #219, T050 #224). That follows OQ-4 `A_stripe_mapping` and [research 2026-11-01](../../docs/evidence/COMMERCE_BLOCKERS_RESEARCH_2026-11-01.md) §3. An agent made this correction under the owner's delegation, and the owner accepts it by merging; see [the T001 record](T001_CONFIRMATION_2026-11-04.md). Rows marked OPEN state what the code does today. They are not settled.

The code stores the provider status, not these states. The states below map to it the same way as `_c_state` in `backend/tests/unit/test_spec_004_transitions.py`.

States:

- `NONE`. No subscription exists.
- `CheckoutOpen`. The subscription checkout session exists. This is a `SubscriptionCheckoutRecord` reservation, not a subscription record.
- `Active`. The provider status is `active`, and `cancel_at_period_end` is false.
- `CancelScheduled`. The provider status is `active`, `trialing` or `past_due` (owner decision 43), and `cancel_at_period_end` is true.
- `NotActive`. The provider status is any other value except `canceled`, such as `past_due`.
- `Canceled`. The provider status is `canceled`.
- `Abandoned`. The user left checkout. The reservation expired, and no subscription record exists.
- `Unresolved`. The disposition of a stored event, not a state of the subscription record: the customer is unknown, the price maps to no tier, or the payload is malformed.

The initial state is `NONE`. The final states are `Canceled` and `Abandoned`. An event's `Unresolved` disposition exits only through operator action.

Every row below is [OBSERVED: backend/canon/subscriptions.py, backend/canon/checkout.py, backend/canon/webhook_events.py].

| from | event | guard | to | effect |
|---|---|---|---|---|
| NONE | choose_tier | `ENABLE_SUBSCRIPTION_CHECKOUT` and `checkout_gate` pass; the tier is CORE, PRO, or STUDIO and has a configured price; the user has no live subscription. | CheckoutOpen | Get or create the provider customer. Create a `subscription`-mode session for the tier's price. Write a reservation and no subscription record. A repeat for the same tier reuses the open session. |
| NONE | choose_tier | Disabled, invalid tier, no configured price (503 `SUBSCRIPTION_PRICE_MISSING`), a live subscription exists (409 `SUBSCRIPTION_EXISTS`), or another tier's session is open (409 `SUBSCRIPTION_CHECKOUT_OPEN`). | NONE | Refuse the request. |
| CheckoutOpen | checkout_canceled_or_expired (`checkout.session.expired`) | The session has an open reservation. | Abandoned | Mark the reservation expired. Write no subscription record. |
| NONE, CheckoutOpen | subscription_created (`customer.subscription.created`), or subscription_updated with no record yet (EC-2) | Verified. The customer is known. One item whose price maps to a tier. A provider status. | The state the status and flag map to | Record the subscription (tier from the provider price, status, period, cancel flag). Grant nothing. |
| Active, NotActive, CancelScheduled | subscription_updated | Newer than the last applied event, and something changed. | Active, CancelScheduled or NotActive, from the new status and flag | Sync the fields. The tier always comes from the provider price (OQ-7). Grant nothing. |
| Active, NotActive, CancelScheduled | subscription_updated | Older than the last applied event, or nothing changed. | Unchanged | `duplicate` (`STALE_EVENT`, `SUBSCRIPTION_UNCHANGED`). |
| NONE, Active, NotActive, CancelScheduled | invoice_paid (`invoice.paid`) | Verified. The invoice is `paid` and `amount_paid > 0`. A non-proration line whose price maps to a tier. The customer matches. The period `subscription-period:<subscription_id>:<period_start>` has no grant. | Unchanged. A missing record is created as `active` (EC-2). | Grant once for the period. CORE and PRO get a canonical `grant` of the tier's credits. STUDIO gets the unlimited entitlement with the fair-use cap, and no credits (FR-004, OQ-8). The subscription's first paid invoice also records a purchase for Machine A (FR-028, OQ-3). |
| Canceled | invoice_paid | The same guard as the row above. | Canceled | Grant once, because money was received, and the record stays `canceled` (owner decision 42, 2026-11-04). `test_c_canceled_invoice_paid_grants_once_and_stays_canceled` pins it. |
| any | invoice_paid | The period was already granted. | Unchanged | `duplicate` (`PERIOD_ALREADY_GRANTED`). Grant nothing. |
| any | invoice_paid | The invoice has only proration lines. | Unchanged | `ignored` (`INVOICE_PRORATION_ONLY`). The new tier's credits come with the next period (OQ-7). |
| any | invoice_paid | Not paid, a zero amount, no subscription, unknown customer or price, the same invoice already granted for another period, or a malformed payload. | Unresolved | Grant nothing. Keep the event with its reason code. |
| CheckoutOpen, Active, NotActive, CancelScheduled | subscription_created or subscription_updated | Unknown customer, a price that maps to no tier, not exactly one item, a malformed period, a customer mismatch, or an unknown status. | Unresolved | Grant nothing. Keep the event with its reason code. |
| Active, NotActive | cancel_requested | `ENABLE_SUBSCRIPTION_CHECKOUT` and `checkout_gate` pass. The user's newest non-terminal subscription, with provider status `active`, `trialing` or `past_due` (owner decision 43, 2026-11-04). | CancelScheduled | Set cancel-at-period-end at the provider and locally. Refused: 404 `SUBSCRIPTION_NOT_FOUND` when there is none, 409 `SUBSCRIPTION_NOT_ACTIVE` for any other status, and 403 `PAYMENTS_DISABLED` with the flag off. |
| NONE, Active, NotActive, CancelScheduled | subscription_deleted | Verified. The customer matches. With no record yet, the price must also map to a tier. | Canceled | Set the status to `canceled`. Keep the granted credits. |
| Canceled | subscription_created, subscription_updated or subscription_deleted | The customer matches. | Canceled | `duplicate` (`SUBSCRIPTION_ALREADY_CANCELED`). |
| Unresolved | operator_rejects | An admin, with a reason (OQ-5, T048). | Unresolved, closed as rejected | Grant nothing. Write one admin audit record. |
| Unresolved | operator_resolves | Any. | Unchanged | Refused with 409 `RESOLVE_NOT_SUPPORTED`, so an operator can only reject. OPEN whether to build resolve. |

An event whose signature does not verify is refused at intake, before any handler runs. Such an event is never stored and never becomes `Unresolved`. `invoice.payment_failed` has no handler, so it is stored as `ignored`; `past_due` arrives through `customer.subscription.updated`. A `subscription`-mode `checkout.session.completed` marks the reservation completed and grants nothing. A reservation also stops blocking a new checkout once its `expires_at` passes. Entitlement by status (OQ-4): `active`, `trialing` and `past_due` keep the paid tier; every other status resolves to FREE (`ENTITLED_STATUSES`).

Illegal transitions:

- A second grant for the same subscription and billing period.
- `Canceled` to any other state through a `customer.subscription.*` event. Resubscribing starts a new subscription from `NONE`.
- Any grant for an unknown tier or an unknown customer.
- A tier change derived from client input instead of the provider price.

```mermaid
stateDiagram-v2
    [*] --> NONE
    NONE --> CheckoutOpen: choose_tier [enabled, priced tier, no live subscription]
    CheckoutOpen --> Abandoned: checkout.session.expired
    NONE --> Active: subscription_created [known, active]
    NONE --> NotActive: subscription_created [known, not active]
    CheckoutOpen --> Active: subscription_created [known, active]
    CheckoutOpen --> NotActive: subscription_created [known, not active]
    NONE --> Active: invoice_paid [no record yet, EC-2] / grant once
    Active --> Active: invoice_paid [new period] / grant once
    NotActive --> NotActive: invoice_paid [new period] / grant once
    CancelScheduled --> CancelScheduled: invoice_paid [new period] / grant once
    Canceled --> Canceled: invoice_paid [new period] / grant once
    Active --> NotActive: subscription_updated [not active]
    NotActive --> Active: subscription_updated [active]
    Active --> CancelScheduled: cancel_requested or subscription_updated [flag set]
    NotActive --> CancelScheduled: cancel_requested [trialing or past_due]
    Canceled --> Canceled: invoice_paid [new period] / grant once
    CancelScheduled --> Active: subscription_updated [flag cleared]
    CancelScheduled --> NotActive: subscription_updated [not active]
    Active --> Canceled: subscription_deleted
    NotActive --> Canceled: subscription_deleted
    CancelScheduled --> Canceled: subscription_deleted
    Canceled --> [*]
    Abandoned --> [*]
```

## Security, privacy, observability, and rollback

- **Security.** ADVERSARY reviews these items: the legacy client-submitted purchase endpoint (FR-033), provider event verification (FR-013), and referral-code derivation (FR-036). `docs/SECURITY.md` now states the payment rules; see OQ-10.
- **Privacy.** The provider receives the user's email and display name when PatchHive creates the customer. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md] Disclosure and consent requirements are NOT_COMPUTABLE. [INFERRED]
- **Observability.** Every applied, duplicate, and unresolved provider event is recorded with its provider event identifier and its disposition. [INFERRED] The constitution principle 6 requires this provenance.
- **Rollback.** Payments are flag-gated and default to disabled. Legacy referrals are flag-gated. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md, backend/monetization/routes.py] Rollback never deletes ledger or referral rows. [INFERRED]
- **Authority boundary.** Commerce state cannot mutate canonical rigs or patches, and it cannot enter generation inputs. [INFERRED] This follows constitution principles 1 and 8.

## Success criteria

Each criterion is a pass or fail test. No numeric business targets are set. Business targets are NOT_COMPUTABLE.

- **SC-001** Replaying any provider event sequence twice, including duplicates, produces the same ledger as replaying it once. [INFERRED]
- **SC-002** Across all test scenarios, no referred user produces more than one referral `Grant`. This includes concurrent first purchases. [INFERRED]
- **SC-003** No test scenario creates a `Purchase` entry without a verified provider confirmation. [INFERRED]
- **SC-004** Every unverifiable or unmappable provider event ends in `Unresolved` with zero credits granted. [INFERRED]
- **SC-005** For each subscription, every billing period produces exactly one entitlement grant. [INFERRED]
- **SC-006** Canonical generation output for fixed inputs is identical for FREE, CORE, PRO, and STUDIO users, and for any credit balance. [INFERRED]
- **SC-007** Disabling either flag leaves the existing ledger and referral history byte-identical. [INFERRED]

## Edge cases

- **EC-1** The provider delivers the same completion event twice, or out of order. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md] The idempotency check covers the duplicate case. Out-of-order delivery is [INFERRED].
- **EC-2** A subscription update arrives before the subscription-created event. [INFERRED]
- **EC-3** A referred user's first `Purchase` was recorded without referral evaluation, for example through the observed provider path. The referral then stays `Pending` permanently because the count is no longer 1. [INFERRED]
- **EC-4** A `Purchase` with a delta of 0 counts as a first purchase, because `credits_delta` defaults to 0. [OBSERVED: backend/monetization/referrals.py]
- **EC-5** Two first purchases for one referred user commit concurrently. [INFERRED]
- **EC-6** A referral code collides. The observed generator appends random suffixes, so the code is not deterministic on collision. [OBSERVED: backend/monetization/referrals.py]
- **EC-7** The tier price identifiers are not configured, which leaves them empty. A provider price might then match an empty mapping. [INFERRED] Empty defaults appear in STRIPE_INTEGRATION_PROMPT.md.
- **EC-8** A user deletes their account while ledger or referral rows reference them. The observed proposal cascades provider records on user deletion. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md] Resolved 2026-11-01 (OQ-12, T052): the user row is anonymized, never deleted, so every ledger, export and referral row keeps its `user_id` and nothing append-only is updated or deleted. [OBSERVED: backend/account/deletion.py]
- **EC-9** A STUDIO user's "unlimited" balance meets a balance read or a spend. [INFERR
ED] The observed sentinel `999999` can be exhausted or shown as a literal number. See FR-004.
- **EC-10** A user subscribes and also buys one-time credits. The first of those events to complete is the referral-qualifying purchase only if it goes through the purchase-recording path. [INFERRED] See FR-028 and OQ-3.
- **EC-11** A user changes tiers mid-period through the provider. The observed code updates status and period fields but not the stored tier or price. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md] Proration and entitlement on tier change are NOT_COMPUTABLE. See OQ-7.
- **EC-12** A refund or chargeback arrives for a one-time purchase or a subscription invoice. The ledger supports `Refund`, but no source defines when PatchHive appends one. [OBSERVED: STRIPE_INTEGRATION_PROMPT.md] The flow is NOT_COMPUTABLE. See OQ-2. One-time purchases follow OQ-2 `A_reverse_unspent` since 2026-11-02 (T053, Machine B refund rows); subscription invoices wait for Machine C (T049).
- **EC-13** A user signs up with a code for a referrer whose account is later deleted. [INFERRED]

## Open questions

Reviewed 2026-10-29 against the code ([research.md](research.md) R7). Items the code answers are marked RESOLVED with evidence. The rest are owner, business or legal decisions; each carries a recommendation.

- **OQ-1** Are the tier prices ($4.99, $14.99, $29.99), the monthly credit quantities (25, 100, unlimited), and the one-time rule ($0.20 per credit, $5.00 minimum) ratified? They come from an implementation prompt only. Currency, tax, and regional pricing are also undefined. NOT_COMPUTABLE. Still open (owner). Recommendation: ratify prices, quantities and currency before T046. The export price is already a server setting (`patchbook_export_cost = 3`). **Decided 2026-11-01 by Jev (owner-delegated):** `A_ratify_as_is` (confidence 0.29) (provisional: low confidence, owner to confirm; a lawyer must confirm): Keep $4.99/$14.99/$29.99, 25/100/unlimited, $0.20/credit, $5 min, USD only. Fastest; but CORE has no discount vs credit packs, STUDIO unlimited is open-ended cost, and Stripe fees are ~9% on CORE/min pack. Matches 'ratify' recommendation in spec. See [the decision record](../../docs/evidence/JEV_DECISIONS_2026-11-01.md).
- **OQ-2** What is the refund, chargeback, and dispute flow for purchases? When does PatchHive append a `Refund` entry, and can a balance go negative? NOT_COMPUTABLE. Partly answered: a failed export gets one `reversal`, and an export never takes a balance below zero [OBSERVED: canon/exports.py]. Purchase refunds and chargebacks are still open (owner, legal). Recommendation: on a provider refund, reverse only unspent credits, record the rest as unresolved, never go negative, and never revoke a referral reward (FR-030). **Decided 2026-11-01 by Jev (owner-delegated):** `A_reverse_unspent` (confidence 0.96) (a lawyer must confirm): On provider refund reverse only unspent credits, record remainder unresolved for operator, never negative, never revoke referral reward. Matches spec recommendation; simple, may leave small loss. See [the decision record](../../docs/evidence/JEV_DECISIONS_2026-11-01.md). Built 2026-11-02 for one-time purchases (T053): credits back are `floor(credits * amount_refunded / amount_cents)` on the cumulative refunded amount, capped at the current balance; the spent remainder is `unresolved` (`REFUND_EXCEEDS_UNSPENT`); a dispute is `unresolved` (`DISPUTE_OPENED`) with no reversal. Rounding and cap need owner confirmation.
- **OQ-3** Does a subscription payment count as a "first paid purchase" for referral rewards? If yes, does it record a `Purchase` entry, a `Grant` entry, or both? NOT_COMPUTABLE. Still open (owner). Recommendation: yes. The first paid invoice records a provider-verified purchase through `record_purchase(payment_verified=True)`, and the period credits are a separate grant. **Decided 2026-11-01 by Jev (owner-delegated):** `A_both` (confidence 0.96): First paid invoice records a provider-verified Purchase via record_purchase(payment_verified=True) and the period credits are a separate Grant. Matches spec recommendation; referral rewards work for subscribers. See [the decision record](../../docs/evidence/JEV_DECISIONS_2026-11-01.md).
- **OQ-4** Which provider subscription statuses, such as `past_due`, `unpaid`, `incomplete`, and `trialing`, must PatchHive distinguish? What entitlement applies in each? NOT_COMPUTABLE. Still open (owner). Recommendation: grant only when an invoice is paid for a new period; `trialing`, `incomplete`, `past_due` and `unpaid` grant nothing and keep credits already granted. Research 2026-11-01: Stripe says to revoke access when `unpaid` and to grant on `invoice.paid`; recommended mapping in [research 2026-11-01](../../docs/evidence/COMMERCE_BLOCKERS_RESEARCH_2026-11-01.md) §3. **Decided 2026-11-01 by Jev (owner-delegated):** `A_stripe_mapping` (confidence 0.98): Per research table: active/trialing -> paid tier; past_due -> keep tier during retries, no new grant; unpaid/incomplete/incomplete_expired/canceled/paused -> FREE; grant only on invoice.paid. Matches spec recommendation and Stripe guidance. See [the decision record](../../docs/evidence/JEV_DECISIONS_2026-11-01.md).
- **OQ-5** What operator action resolves or rejects an `Unresolved` commerce event? Who is authorized, and what audit record does it produce? NOT_COMPUTABLE. Still open (owner). Recommendation: admin role only, one `CanonicalAdminAuditEventRecord` per resolve or reject, with a reason (T048). Reject built to this recommendation 2026-11-01; resolve waits for Machine B (T048b). See [research 2026-11-01](../../docs/evidence/COMMERCE_BLOCKERS_RESEARCH_2026-11-01.md) §1. **Decided 2026-11-01 by Jev (owner-delegated):** `A_refetch_session` (confidence 0.85): Implement resolve by retrieving the Checkout Session by stored object id and running idempotent fulfillment; audit record; unresolved if not retrievable. Matches research recommendation. See [the decision record](../../docs/evidence/JEV_DECISIONS_2026-11-01.md).
- **OQ-6** Does signup succeed, fail, or warn when the referral code does not resolve? RESOLVED 2026-10-29: with referrals on, a code that does not resolve fails signup with 400 `Invalid referral code`; with referrals off, the code is ignored [OBSERVED: community/auth_routes.py]. **Answered (checked 2026-11-01):** RESOLVED 2026-10-29: with referrals on, unresolved code fails signup with 400 Invalid referral code; with referrals off, code ignored.
- **OQ-7** How do upgrades, downgrades, and proration affect the stored tier and the per-period grant? NOT_COMPUTABLE. Still open (owner). Recommendation: store the tier from the provider price on every update; grant the new tier's credits only at the next period, with no proration. **Decided 2026-11-01 by Jev (owner-delegated):** `A_next_period_no_proration` (confidence 0.98): Store tier from the provider price on every update; new tier credits granted at next period; no proration. Matches spec recommendation; simplest, mid-period upgrade gets no extra credits. See [the decision record](../../docs/evidence/JEV_DECISIONS_2026-11-01.md).
- **OQ-8** What does "unlimited" mean for STUDIO: no spend check, a fair-use cap, or something else? NOT_COMPUTABLE. Still open (owner). Recommendation: an explicit entitlement flag, not a number (FR-004), with a fair-use cap the owner sets. **Decided 2026-11-01 by Jev (owner-delegated):** `A_flag_with_fair_use` (confidence 1.0): Explicit entitlement flag with owner-set fair-use cap (e.g. monthly export ceiling). Matches spec recommendation; bounded cost. See [the decision record](../../docs/evidence/JEV_DECISIONS_2026-11-01.md).
- **OQ-9** Which features does each tier gate beyond credits? The sources say "Basic," "Advanced," and "All" PatchBook features without a list. NOT_COMPUTABLE. Partly answered: Design Engine template families have a tier floor [OBSERVED: canon/entitlements.py]. Other tier features are still open (owner). **Decided 2026-11-01 by Jev (owner-delegated):** `A_templates_only` (confidence 0.79): Gate only Design Engine template families (already coded) plus credits. No new work; tiers differ little beyond credits. See [the decision record](../../docs/evidence/JEV_DECISIONS_2026-11-01.md).
- **OQ-10** What does `docs/SECURITY.md` require for payment secrets, webhook handling, and personal data? RESOLVED 2026-10-29: `docs/SECURITY.md` requires append-only credit entries; webhooks with constant-time HMAC, timestamp tolerance, unique event ids, replay-conflict detection and a livemode gate; and `STRIPE_TEST_MODE=true` with `ALLOW_PRODUCTION_PAYMENTS=false` until a payment activation review [OBSERVED: docs/SECURITY.md]. Gaps against it: T040, T041, T042. **Answered (checked 2026-11-01):** RESOLVED 2026-10-29: append-only credit entries; constant-time HMAC, timestamp tolerance, unique event ids, replay-conflict detection, livemode gate; STRIPE_TEST_MODE=true and ALLOW_PRODUCTION_PAYMENTS=false until activation review.
- **OQ-11** Is the legacy `/purchases` endpoint retired, restricted to server use, or kept? See FR-033. NOT_COMPUTABLE. Still open (owner). Recommendation: delete the route (research R5, T043). It mints no spendable credit since #131, but its `Purchase` row can use up a referred user's first-purchase slot (EC-3). **Answered (checked 2026-11-01):** Retired: owner chose option A; route, PurchaseCreate and monetization router deleted; referrals use enable_referrals (T043 done 2026-10-30).
- **OQ-12** How does account deletion interact with the append-only ledger and referral rows? See EC-8. NOT_COMPUTABLE. Partly answered: the canonical ledger blocks deleting a user who has entries (`ON DELETE RESTRICT`), while the legacy ledger cascades; no account-deletion route was found [OBSERVED: canon/models.py, monetization/models.py]. Still open (owner, legal). Recommendation: anonymize the user and keep ledger and referral rows. **Decided 2026-11-01 by Jev (owner-delegated):** `A_anonymize_keep` (confidence 1.0) (a lawyer must confirm): Anonymize the user (strip PII), keep ledger and referral rows. Matches spec recommendation; preserves financial records, needs an anonymization routine and account-deletion route. Lawyer to confirm retention periods. See [the decision record](../../docs/evidence/JEV_DECISIONS_2026-11-01.md). **Implemented 2026-11-01 (T052):** signed-in `DELETE /api/me` with the current password. In one transaction it revokes every session and token; replaces email, username, display name, avatar, bio, password hash (unusable) and referral code, resets role to `User` and sets `users.deleted_at`; and writes one `admin_audit_log` row (`account_deleted`, per-table counts, no personal data). Personal content, smallest safe rule: comments, votes, patch overlays, patch annotations and style recipes are deleted (a canonical export's pointer to a deleted recipe is set NULL; its sealed recipe snapshot stays); racks are soft-deleted with name, description and tags cleared and made private (runs and canonical history are append-only); publications become `removed` (`ACCOUNT_DELETED`) with title, description and cover cleared and downloads off; publication reports the user filed are kept with the reporter detached; evidence images are expired at once and their stored bytes purged after the commit (a failed purge is retried by `python -m evidence.expire --apply`). Kept: canonical and legacy ledgers, canonical exports, generation runs, licenses, export records, referral rows, `referred_by`, admin audit rows. Gaps, not handled: (a) retention periods for every kept row, and whether a kept row must later be erased, need a lawyer; (b) free text inside kept rows (ledger `notes`/`description`, license `metadata`, publication report `details`, classification evidence and inventory revisions bound to the user's images, rig revisions and patches generated from their racks, sealed recipe JSON in exports) is not scrubbed; (c) publication export artifacts in storage are not deleted; (d) nothing at the payment provider is touched (no provider customer link exists yet, T046); (e) backups and logs are out of scope.
- **OQ-13** What legal terms, refund policy, and consumer-protection obligations apply to selling credits and subscriptions? NOT_COMPUTABLE. Still open (legal). No recommendation from engineering. **Decided 2026-11-01 by Jev (owner-delegated):** `D_defer_sales` (confidence 0.95) (a lawyer must confirm): Launch with admin grants only (no sales) until counsel drafts terms. Zero legal exposure now; delays revenue. Matches OPEN_DECISIONS 'D now'. See [the decision record](../../docs/evidence/JEV_DECISIONS_2026-11-01.md).
