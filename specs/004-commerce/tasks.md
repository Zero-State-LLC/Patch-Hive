# Tasks: 004-commerce

## Setup

- [ ] T001 Confirm the spec with the operator (it is INFERRED today)
- [ ] T002 Write plan.md
  - depends_on: [T001]

## Gap closure (2026-10-29)

From [research.md](research.md) R1–R8. Machine B (T046) lands before any referral reward can become spendable (T047). Payments stay off until T051.

- [x] T040 Webhook hardening: accept the event if any `v1` signature matches (secret rotation); on a concurrent duplicate insert, roll back a savepoint and answer as a duplicate, not 500 (FR-012, FR-013, research R4). Effort S. Done 2026-10-29: `receive_stripe_webhook` in `canon/exports.py`; tests in `tests/unit/test_commerce_webhook_hardening.py` and `tests/api/test_canon_export_api.py`.
  - depends_on: []
- [x] T041 Reject live-mode events in every environment except production, whatever `STRIPE_TEST_MODE` says, and refuse to start with `STRIPE_TEST_MODE=false` outside production (FR-013, research R3). Effort S. Done 2026-10-29: live-mode gate in `canon/exports.py`; `validate_stripe_mode_startup_policy` in `core/startup_policy.py`.
  - depends_on: []
- [x] T042 Append-only trigger on `canonical_credit_ledger` that rejects `UPDATE` and `DELETE`, mirroring `20260925_decision_receipts`, with a Postgres test (FR-008, research R2). Effort S. Done 2026-10-29: migration `20261029_ledger_append_only`; Postgres test `tests/acceptance/test_ledger_append_only.py`.
  - depends_on: []
- [x] T043 Delete `POST /api/monetization/purchases` and `PurchaseCreate`; move referral signup and the referral summary to their own flag (FR-033, OQ-11, research R5). Needs owner sign-off on OQ-11. Effort S. Done 2026-10-30: owner chose option A; route, `PurchaseCreate` and the `monetization` router mount deleted; referral signup and summaries now use `enable_referrals` (`ENABLE_LEGACY_REFERRALS` removed); tests in `tests/api/test_p1_security.py`.
  - depends_on: []
- [x] T044 Delete `GET /api/monetization/credits/balance`, and make the referral summary's `earned_credits` count canonical referral grants (FR-009, FR-031, research R6). Effort S. Done 2026-10-29: route removed from `monetization/routes.py` (no frontend caller; `getBalance` already reads `/canon/credits/balance`); `get_referral_summary` sums canonical `referral-reward:<id>` grants; tests in `tests/unit/test_referrals.py` and `tests/api/test_canon_export_api.py`.
  - depends_on: []
- [x] T045 Webhook event processor: dispatch by type in the webhook transaction; set `status` to `processed`, `duplicate`, `unresolved` (with a reason code) or `ignored`, and set `processed_at`. No event stays `received` (FR-014, observability, research R1). Effort M. Done 2026-10-29: `process_stripe_event` in `canon/webhook_events.py`, called by `receive_stripe_webhook`; payment types without a machine are `unresolved` (`HANDLER_NOT_IMPLEMENTED`) until T046/T049; migration `20261029_webhook_disposition` adds `reason_code` and moves stored `received` rows to `unresolved`; tests in `tests/unit/test_commerce_webhook_processor.py` and `tests/acceptance/test_webhook_processor_postgres.py`.
  - depends_on: [T040, T041]
- [ ] T046 Machine B: credit checkout behind the payments flag; provider customer link (one per user); payment record unique on the provider payment id; on `checkout.session.completed`, append a canonical `purchase` entry keyed `purchase:<payment_id>` and call `record_purchase(payment_verified=True)` in one transaction; an expired session is abandoned; a malformed or unmappable event is unresolved (FR-006, FR-011, FR-012, FR-014, FR-020, FR-028, research R1). Needs OQ-1 ratified. Effort L.
  - depends_on: [T001, T042, T045]
- [ ] T047 Referral reward on a provider purchase: test that a referred user's first Machine B purchase writes one spendable canonical reward, a duplicate delivery writes none, and concurrent first purchases write one (FR-026, FR-027, FR-032, SC-002). Effort S.
  - depends_on: [T043, T046]
- [ ] T048 Operator resolve and reject for unresolved events: admin-only, with a `CanonicalAdminAuditEventRecord` per action (OQ-5, Machines B and C). Effort M.
  - depends_on: [T045]
- [ ] T049 Machine C: subscription checkout; subscription records (tier, status, period, cancel-at-period-end); one grant per billing period keyed `subscription-period:<subscription_id>:<period_start>`; cancel at period end; deleted becomes `canceled`; unknown price or customer is unresolved (FR-003, FR-004, FR-015–FR-018, research R1). Needs OQ-3, OQ-4, OQ-7 and OQ-8 settled. Effort L.
  - depends_on: [T046]
- [ ] T050 Resolve the user's tier from their active subscription instead of the default-tier setting (FR-001, FR-035, canon/entitlements.py). Effort S.
  - depends_on: [T049]
- [ ] T051 Payment activation review: ADVERSARY review of the provider path, owner sign-off, then `ALLOW_PRODUCTION_PAYMENTS=true` with `STRIPE_TEST_MODE=false` in production only (FR-019, docs/SECURITY.md). Operator-run.
  - depends_on: [T044, T047, T048, T049]

## Foundational

- [ ] T010 Encode the transitions table as tests (workflows: anti-slop-code, production-systems)
  - depends_on: [T002]

## Polish

- [ ] T090 Converge the code against the spec
  - depends_on: [T010]
