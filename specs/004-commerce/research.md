# Research: 004-commerce

Decision research for the open commerce decisions (2026-10-29). Each item gives the evidence, the options and the recommendation, with an effort size (S, M or L). Labels follow the spec: `[OBSERVED: <source>]` or `[INFERRED]`. Code paths are relative to `backend/`.

Already fixed and not researched again: per-user export idempotency, admin-only grants and one referral reward under a row lock (#82, #98); the server-set export price; the export debit under `pg_advisory_xact_lock`; idempotent `compensate_failed_export`; the production webhook 403 and the startup payment policy; the 503 `EXPORT_FULFILLMENT_UNAVAILABLE` refusal before any debit (#129); the referral reward in the canonical ledger only for a provider-verified purchase (#131).

## R1. The provider purchase path (Machines B and C; FR-011, FR-012, FR-014–FR-018, FR-028)

**Evidence**

- `POST /api/canon/webhooks/stripe` verifies the signature, stores a `stripe_event_records` row with `status = "received"`, commits and returns. Nothing reads the event body after that [OBSERVED: canon/routes.py, canon/exports.py `verify_stripe_webhook`].
- `processed_at` exists on the model but no code sets it [OBSERVED: canon/models.py `StripeEventRecordModel`].
- No code creates a checkout session, a provider customer, a subscription record or a payment record [OBSERVED: repo grep for `checkout`, `subscription`, `stripe_customer`, 2026-10-29].
- Tiers resolve from one setting, not from a subscription: "Until a real subscription model exists, resolve a single default tier (core)" [OBSERVED: canon/entitlements.py `resolve_user_tier`].
- The only writers of positive canonical entries are the admin grant and the referral reward [OBSERVED: admin/routes.py `grant_user_credits`, monetization/referrals.py]. So users can't buy credits; only an admin can mint them.
- `record_purchase(..., payment_verified=True)` is ready for a provider caller, but nothing calls it with `True` [OBSERVED: monetization/referrals.py].
- The canonical ledger has entry types `grant`, `debit` and `reversal`. It has no `purchase` type [OBSERVED: canon/exports.py, admin/routes.py].

**Options**

1. Build Machine B first (one-time credits), then Machine C (subscriptions), on one event processor.
2. Build both machines together.
3. Keep admin grants as the only credit source and defer the provider path.

**Recommendation:** option 1. One processor runs inside the webhook transaction, after verification. It sets `status` to `processed`, `duplicate` or `unresolved`, with `processed_at` and a reason code. An event type the processor does not handle is recorded as `ignored`, never left as `received`. Machine B adds a provider customer link (FR-020), a payment record unique on the provider payment id, a canonical `purchase` entry keyed `purchase:<payment_id>`, and a call to `record_purchase(payment_verified=True)` in the same transaction (FR-028, FR-032). Machine C then adds subscription records and one grant per billing period, keyed `subscription-period:<subscription_id>:<period_start>` (FR-016). Prices need owner ratification first (OQ-1). Effort: L for B (with the processor), L for C.

## R2. Append-only canonical ledger (FR-008)

**Evidence**

- `docs/SECURITY.md` states "credit entries are append-only" [OBSERVED: docs/SECURITY.md].
- No trigger, rule or grant enforces it on `canonical_credit_ledger`. Code only inserts [OBSERVED: canon/models.py, alembic/versions grep for `TRIGGER`].
- The repo already guards another table this way: `trg_decision_receipts_no_update` and `trg_decision_receipts_no_delete` [OBSERVED: alembic/versions/20260925_decision_receipts.py].
- The canonical ledger's `users.id` foreign key is `ON DELETE RESTRICT`, so a delete trigger does not change user deletion behavior [OBSERVED: canon/models.py].

**Options**

1. A Postgres trigger that rejects `UPDATE` and `DELETE`, mirroring the decision-receipts migration.
2. Revoke `UPDATE` and `DELETE` from the app role. That depends on hosted role setup, which the repo doesn't own.
3. Keep the convention and a reconciliation check (`reconcile_ledger`).

**Recommendation:** option 1, with a test that an update and a delete both fail on Postgres. SQLite tests keep the convention. Effort: S.

## R3. Live-mode events outside production (FR-013)

**Evidence**

- The handler rejects a live-mode event only when `test_mode` is true: `if test_mode and livemode` [OBSERVED: canon/exports.py].
- The startup policy returns early for every environment except `production` [OBSERVED: canon/routes.py `validate_payment_startup_policy`].
- So staging with `STRIPE_TEST_MODE=false` accepts live-mode events [INFERRED from the two lines above].
- `docs/SECURITY.md` says to keep `STRIPE_TEST_MODE=true` until a separate payment activation review [OBSERVED: docs/SECURITY.md].

**Options**

1. Reject live-mode events in every environment except `production`, whatever `STRIPE_TEST_MODE` says; and refuse to start with `STRIPE_TEST_MODE=false` outside production.
2. Only the startup check.
3. Only document it.

**Recommendation:** option 1. Live money belongs only to production, after the activation review. Effort: S.

## R4. Webhook signature rotation and concurrent duplicates (FR-012, FR-013)

**Evidence**

- The header is parsed with `dict(part.split("=", 1) ...)`, so only the last `v1` value survives. The provider sends one `v1` per active secret during rotation, so a valid event can fail if its match isn't last [OBSERVED: canon/exports.py; rotation behavior INFERRED from the provider's documented header format].
- Two concurrent deliveries of one event can both miss `session.get` and both insert. The second `flush` raises `IntegrityError`. The route catches only `ExportBoundaryError` and re-raises the rest, so the provider gets a 500 and retries [OBSERVED: canon/exports.py, canon/routes.py].

**Options**

1. Collect every `v1` value and accept if any matches (constant-time each). On `IntegrityError`, roll back a savepoint, reload the winner and answer as a duplicate (or 409 on a payload-hash conflict).
2. Lock on the event id (`pg_advisory_xact_lock`) before the lookup.

**Recommendation:** option 1. It mirrors the export path's savepoint pattern (`request_export`). Effort: S.

## R5. Legacy `POST /api/monetization/purchases` (FR-033, OQ-11)

**Evidence**

- The route takes `credits_delta` and `notes` from the client and calls `record_purchase` without `payment_verified`. It is off unless `enable_legacy_referrals` is set [OBSERVED: monetization/routes.py, core/config.py].
- Since #131 it mints no spendable credit [OBSERVED: monetization/referrals.py].
- It still writes a legacy `Purchase` row. FR-027 counts those rows. So a self-reported purchase can use up the referred user's first-purchase slot, and a later real purchase then never rewards the referrer (EC-3) [INFERRED from monetization/referrals.py].
- No frontend code calls it [OBSERVED: frontend/src/lib/api.ts].
- The same flag also gates referral signup and the referral summary [OBSERVED: community/auth_routes.py, community/routes.py].

**Options**

1. Delete the route and its schema. Give referral signup and summary their own flag.
2. Keep it, admin-only.
3. Keep it behind the flag as now.

**Recommendation:** option 1. Machine B is the only purchase source (FR-033). Owner sign-off is needed (OQ-11). Effort: S.

## R6. Two balance endpoints

**Evidence**

- `GET /api/monetization/credits/balance` sums the legacy `credits_ledger` [OBSERVED: monetization/routes.py, monetization/credits.py].
- `GET /api/canon/credits/balance` sums `canonical_credit_ledger`, which spending reads [OBSERVED: canon/routes.py, canon/exports.py `credit_balance`].
- They disagree: unverified referral rewards and the legacy export path's `Spend` rows exist only in the legacy ledger [OBSERVED: monetization/referrals.py, export/routes.py].
- The frontend reads only the canonical one; `monetizationApi.balance` is an alias for it [OBSERVED: frontend/src/lib/api.ts].
- The referral summary's `earned_credits` also reads the legacy ledger, so it can show credits that are not spendable [OBSERVED: monetization/referrals.py `get_referral_summary`].

**Options**

1. Remove the legacy balance route.
2. Make it return the canonical balance.
3. Keep both.

**Recommendation:** option 1, since nothing calls it. Make `earned_credits` count canonical referral grants (`referral-reward:` keys) so the summary matches what a user can spend. Effort: S.

## R7. Open questions the code now answers

**Evidence**

- OQ-6: with referrals on, a code that does not resolve fails signup with 400 `Invalid referral code`. With referrals off, the code is ignored [OBSERVED: community/auth_routes.py].
- OQ-10: `docs/SECURITY.md` now exists. It requires append-only credit entries, constant-time HMAC, timestamp tolerance, unique event ids, replay-conflict detection and a livemode gate, and test mode until an activation review [OBSERVED: docs/SECURITY.md].
- OQ-9 (part): Design Engine template families have a tier floor [OBSERVED: canon/entitlements.py `_FAMILY_TIER_FLOOR`].
- OQ-12 (part): the canonical ledger blocks deleting a user who has entries (`RESTRICT`); the legacy ledger cascades. No account-deletion route was found [OBSERVED: canon/models.py, monetization/models.py; route absence from repo grep].
- OQ-2 (part): a failed export gets one `reversal`; an export never takes a balance below zero [OBSERVED: canon/exports.py].
- FR-036: referral codes are random (`secrets.token_urlsafe`), not derived from the email [OBSERVED: monetization/referrals.py, account/services.py].

**Recommendation:** mark OQ-6 and OQ-10 resolved. Record the partial answers on OQ-2, OQ-9 and OQ-12. Leave the business, legal and owner questions open with the recommendations in spec.md.

## R8. Spec confirmation (T001)

The spec is still DRAFT with `[INFERRED]` claims. Pricing (OQ-1), subscription statuses (OQ-4) and tier changes (OQ-7) block Machine B and C. Recommendation: one owner sitting that settles OQ-1, OQ-3, OQ-4, OQ-7, OQ-8 and OQ-11 before T046 starts. Effort: S (owner time).
