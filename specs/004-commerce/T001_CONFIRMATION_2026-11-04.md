# Spec 004 T001 confirmation record, 2026-11-04

**Who confirmed this.** An agent ran this T001 sitting in the owner's place. On 2026-11-04 the owner said "you can do all of this" about their open cards. That quote reached this agent through the session that launched it. Every CONFIRMED below is confirmed by an agent under the owner's delegation, not by the owner reading it: the owner has not read the spec. The owner approves by merging the PR. Merging accepts the Machine C correction and the T001 and T002 ticks.

**What this record does not do.** It decides no price, no legal question and no payment activation. Payments stay in test mode. T010, T046, T047, T048, T049, T050, T051, T053 and T090 stay open.

**Result.** T001 is ticked. No claim is wrong in a way that needs a human product decision before planning: every provider path is off by default, and each OPEN item below blocks a later task, not the plan. Of 66 rows: CONFIRMED 39, DRIFT 13, OPEN 14.

**Base and method.**

- Base: `org/main` at 007b437 (0.3.0-alpha.8). Python and `alembic` paths are under `backend/`; the rest are repo paths.
- `pytest` on 17 commerce test files: 440 passed, here on Python 3.14 and SQLite. CI uses 3.11.
- Postgres tests (`tests/acceptance`) did not run here. The `acceptance` job passed on 007b437 (CI run 41961450776).
- "Probe" means a throwaway test run against this code and not committed. No committed test covers that behavior.
- Spec references use FR, SC, EC and row names, because the line numbers in the owner action guide have moved.
- Test file short names: `transitions` is `tests/unit/test_spec_004_transitions.py`; `subs`, `checkout`, `tiers`, `processor` and `hardening` are `tests/unit/test_commerce_subscriptions.py`, `_credit_checkout.py`, `_tier_entitlements.py`, `_webhook_processor.py` and `_webhook_hardening.py`.

## Checklist claims

These are the 004 claims from `docs/evidence/OWNER_ACTIONS_2026-11-02.md` section 1, with the `[INFERRED]` lines they cover.

| # | Claim | Status | Evidence |
|---|---|---|---|
| 1 | Commerce never influences generation or visibility (Non-goals, FR-034, FR-035, SC-006, Authority boundary). | CONFIRMED | No module under `patches`, `runs`, `racks`, `patchhive`, `intelligence`, `ingest`, `gallery`, `publishing`, `leaderboards` or `core` imports `monetization`, `canon.entitlements`, `canon.checkout` or `canon.subscriptions`. The tier is read only at `canon/routes.py:756,859` to choose a template family. `tiers::test_design_entitlements_use_the_subscription_tier` covers that gate. No test compares generation output across tiers. |
| 2 | The refund, chargeback and dispute flow is not defined here and stays NOT_COMPUTABLE until counsel (Non-goals). | OPEN | O2. The text also conflicts with the Machine B refund rows: see D12. |
| 3 | Tax, invoicing, regional pricing and legal terms are not defined here (Non-goals, OQ-13). | OPEN | O3. |
| 4 | Unlimited is an explicit flag, not 999999 (FR-004, EC-9). | CONFIRMED | `canon/subscriptions.py:167-171,901-902`, `canon/entitlements.py:113-136`, `canon/exports.py:99-118`. `subs::test_studio_grants_the_unlimited_entitlement_with_its_fair_use_cap_and_no_credits`, `tiers::test_a_studio_export_takes_no_credits_and_points_at_the_period_grant`. `999999` appears only as test ids. |
| 5 | The canonical ledger is append-only (FR-008, Machine A illegal row). | CONFIRMED | Trigger in `alembic/versions/20261029_ledger_append_only.py`. `tests/acceptance/test_ledger_append_only.py::test_ledger_rows_are_append_only`, `transitions::test_append_only_purchase_refund_and_reversal_only_append_ledger_rows`. |
| 6 | Every other credit and referral table is append-only too (FR-008, FR-029). | DRIFT | D5. |
| 7 | Every provider event is verified before anything acts on it (FR-013). | CONFIRMED | `canon/exports.py:335-350,358-359`. `hardening::test_no_matching_v1_or_a_malformed_header_is_rejected`, `hardening::test_a_livemode_event_is_rejected_unless_production_without_test_mode`, `transitions::test_b_open_to_credited_needs_a_verified_provider_event`. |
| 8 | Unverifiable events end `Unresolved` with zero credits (P1 AC5, SC-004, Machine B unverified row). | DRIFT | D1. Zero credits holds; `Unresolved` does not. |
| 9 | Unmappable events end `Unresolved` with zero credits (FR-014, P2 AC4). | CONFIRMED | `canon/subscriptions.py:445,539`, `canon/checkout.py:407,413,443`. `transitions::test_c_unknown_customer_or_price_is_unresolved`, `checkout::test_a_malformed_or_unmappable_completion_is_unresolved_and_grants_nothing`, `subs::test_an_unmappable_invoice_is_unresolved_and_grants_nothing`. |
| 10 | Subscription credits are granted once per paid billing period; updates grant nothing (FR-016, SC-005, P2 AC3). | CONFIRMED | `canon/subscriptions.py:857-859`. `transitions::test_c_period_renewed_grants_the_new_period_once`, `transitions::test_c_second_grant_for_the_same_period_is_illegal`, `transitions::test_c_active_updated_same_period_syncs_only`, `tests/acceptance/test_subscription_postgres.py::test_concurrent_invoice_deliveries_for_one_period_grant_once_and_reward_once` |
| 11 | Cancelling keeps granted credits, and credits do not expire (P5 AC3, FR-010). | CONFIRMED | `canon/subscriptions.py:677-689` changes only the record. No ledger expiry field (`canon/models.py`, `monetization/models.py`). `transitions::test_c_subscription_deleted_becomes_canceled_and_keeps_credits`. |
| 12 | Every provider-confirmed purchase uses the one path that evaluates referrals (FR-028, P3 AC6, Machine B credit row, OQ-3). | CONFIRMED | `canon/checkout.py:477-483`, `canon/subscriptions.py:907-919`. `transitions::test_b_checkout_completed_verified_credits_through_machine_a`, `subs::test_each_new_period_grants_once_and_only_the_first_is_a_purchase`. Renewals are grants, not purchases, per OQ-3 `A_both`. |
| 13 | A purchase and its referral evaluation commit together; concurrent purchases give one reward (FR-032, SC-002, Machine A atomic row). | CONFIRMED | `monetization/referrals.py:125-133`, `uq_referrals_one_reward`. `tests/acceptance/test_referral_purchase_postgres.py::test_concurrent_first_provider_purchases_write_one_referral_reward`, `transitions::test_pending_first_purchase_rewards_once_atomically`. |
| 14 | A client cannot mint a purchase or trigger a reward (FR-033, SC-003, Machine A and B illegal rows). | CONFIRMED | `monetization/referrals.py:83-84`. The only `purchase` writer is `canon/checkout.py:470`, the only `Purchase` writer is `monetization/referrals.py:87`. `tests/api/test_p1_security.py::test_legacy_purchase_route_is_gone`, `transitions::test_pending_unverified_purchase_is_refused_without_reward`. |
| 15 | A referral code does not reveal an email (FR-036). | CONFIRMED | `monetization/referrals.py:21-30`, `account/services.py:25-31`. `tests/api/test_p0_security.py::test_referral_codes_are_not_derived_from_the_email`. Older codes are not verified. |
| 16 | Machine B opens, refuses, credits, abandons and resolves as the table says (P1 AC4, request_credits, expired, duplicate, operator_resolves, `Abandoned` to `Credited` illegal). | CONFIRMED | `canon/checkout.py:274-299,431-436,548-552,780-863`. `transitions` rows `test_b_none_request_credits_*`, `test_b_checkout_canceled_or_expired_is_abandoned`, `test_b_credited_duplicate_completion_is_a_no_op`, `test_b_unresolved_operator_resolves_credits_through_machine_a`, `test_b_abandoned_to_credited_is_illegal`. |
| 17 | The Machine B table lists every state and event the machine has. | DRIFT | D2. |
| 18 | Machine B refund and dispute rows (OQ-2). | OPEN | O2. The code matches the rows (`canon/checkout.py:607-721`, `transitions::test_b_credited_refund_after_spend_reverses_the_rest_and_holds_the_remainder`), but a lawyer must confirm the terms. |
| 19 | An event's `Unresolved` disposition exits only through operator action. | CONFIRMED | A redelivery does not reprocess it (`canon/exports.py:363-366`, `processor::test_a_redelivered_event_keeps_its_disposition_and_is_not_reprocessed`). Exits: `canon/webhook_events.py:183-232`, `canon/checkout.py:780-863`. |
| 20 | A checkout in `Unresolved` cannot reach `Credited` without an operator (Machine B illegal row). | DRIFT | D3. |
| 21 | `operator_rejects` moves the checkout to `Abandoned` (Machine B row). | DRIFT | D4. |
| 22 | Machine C grants on `invoice.paid`, and `customer.subscription.*` only sync. | CONFIRMED | Corrected in spec.md (see below). `canon/webhook_events.py:105-108`, `canon/subscriptions.py:641-715,782-921`. `transitions::test_c_subscription_created_known_active_then_paid_invoice_grants_once`. |
| 23 | The other corrected Machine C rows, states and illegal transitions. | CONFIRMED | Read row by row against `canon/subscriptions.py`, `canon/checkout.py:499-507,828-829`, and `_c_state` in `transitions`. Tests: the `test_c_*` rows in `transitions`. Probes for rows no test names: an update or a deletion arriving first creates the record, and a cleared cancel flag returns to `Active`. |
| 24 | A paid invoice on a `Canceled` subscription. | OPEN | O8. Probe: it grants 25 credits and the record stays `canceled`. |
| 25 | Operator resolve for Machine C. | OPEN | O9. |
| 26 | Who can schedule a cancel. | OPEN | O10. |
| 27 | `invoice.payment_failed` stays stored as `ignored`. | CONFIRMED | `canon/webhook_events.py:133-134`. It has no money effect, the event and disposition are stored, and `past_due` arrives through `customer.subscription.updated` (`transitions::test_c_active_updated_not_active_becomes_not_active`). `processor::test_an_event_type_with_no_handler_is_ignored` covers the rule; a probe covers this event type. |
| 28 | Payments are off by default (FR-019, P6 AC1, Machine B and C disabled rows). | CONFIRMED | `core/config.py:120-121,128,137`, `canon/checkout.py:274-299`, `canon/routes.py:1297-1299`. `checkout::test_payments_flags_keep_their_safe_defaults`, `subs::test_subscription_settings_keep_their_safe_defaults`, `transitions::test_b_none_request_credits_disabled_is_refused`. Live flags are not verified. |
| 29 | Turning a flag off leaves the existing ledger unchanged and readable (P6 AC3, SC-007). | CONFIRMED | The flags are read only by `checkout_gate` and at referral routes (`community/auth_routes.py:47,76`, `account/routes.py:92`, `community/routes.py:37`), and nothing writes on disable. `canon/routes.py:284-289` has no flag. Probe: a webhook for a checkout opened before the flag went off still credits; that appends a row, leaves existing rows alone, and the customer has paid. |
| 30 | EC-1: a duplicate or out-of-order completion. | CONFIRMED | `canon/exports.py:363-366`, `canon/checkout.py:431-432,544-545`. `checkout::test_a_duplicate_delivery_credits_nothing_more`, `checkout::test_an_async_success_before_the_unpaid_completion_still_credits_once`. |
| 31 | EC-2: an update before the created event. | CONFIRMED | `canon/subscriptions.py:694-704,839-853`. `subs::test_an_invoice_before_the_subscription_event_creates_the_record`, `subs::test_an_older_event_delivered_late_does_not_roll_the_record_back`. |
| 32 | EC-3: `Pending` can stay non-rewardable. | CONFIRMED | `monetization/referrals.py:115-121`. `transitions::test_pending_non_first_purchase_stays_pending_without_reward`. The observed bypass is gone; the only writer calls the evaluation. |
| 33 | EC-4: a zero-delta purchase counts as first. | CONFIRMED | Used on purpose for a first invoice: `canon/subscriptions.py:911-917`. `subs::test_the_first_paid_invoice_grants_the_period_and_records_one_purchase`. |
| 34 | EC-5: two first purchases at once. | CONFIRMED | Same as row 13. |
| 35 | EC-6: a referral code collision. | CONFIRMED | The generator retries (`monetization/referrals.py:27-30`). Read only; no test forces a collision. The spec's "appends random suffixes" is stale (D12). |
| 36 | EC-7: empty price settings. | CONFIRMED | `canon/subscriptions.py:145-161`. `subs::test_price_ids_map_to_tiers_from_settings_only`, and `SUBSCRIPTION_PRICE_MISSING` in `tests/api/test_subscription_api.py`. |
| 37 | EC-8: account deletion with ledger and referral rows. | CONFIRMED | `account/deletion.py`, `tests/api/test_account_deletion.py::test_delete_anonymizes_the_user_and_keeps_ledger_and_referral_rows`. Retention is O6. |
| 38 | EC-9: STUDIO meets a balance read or a spend. | CONFIRMED | Same as row 4. The balance shows the ledger only. The missing frontend allowance is in D8b. |
| 39 | EC-10: a subscription and a one-time purchase. | CONFIRMED | Both use `record_purchase`, and only the first counts (`monetization/referrals.py:115-121`). Each path is tested alone; the mix is read only. |
| 40 | EC-11: a tier change mid-period. | CONFIRMED | OQ-7. `subs::test_a_tier_change_is_stored_from_the_price_and_credits_from_the_next_period`. |
| 41 | EC-12: a refund or chargeback on a subscription invoice. | OPEN | O2. Today it is `unresolved` (`PAYMENT_RECORD_NOT_FOUND`) with no reversal: `transitions::test_b_refund_for_a_subscription_invoice_payment_is_unresolved`. |
| 42 | EC-13: a referrer who later deletes their account. | OPEN | O11. Probe: the old code stops resolving, and an existing `Pending` referral still rewards the deleted account with 3 credits. |

## Other `[INFERRED]` lines and what checking them turned up

| # | Claim | Status | Evidence |
|---|---|---|---|
| 43 | The spec chooses no stack (Non-goals). | CONFIRMED | The stack is in [plan.md](plan.md). |
| 44 | The canonical balance comes only from the user's own entries (FR-009). | CONFIRMED | `canon/exports.py:35-43`, `canon/routes.py:284-289`. `tests/api/test_canon_export_api.py` (balance reads at lines 108, 316, 466). |
| 45 | There is one balance endpoint (FR-009 status row). | DRIFT | D7. |
| 46 | The user sees the referral summary FR-031 and P4 AC2 describe. | DRIFT | D8a. |
| 47 | Users can buy, subscribe and cancel (P1 AC1, P2 AC1, P5 AC1). | DRIFT | D8b. The API exists; the frontend has no caller. |
| 48 | Machine A `Pending` rows and illegal rows. | CONFIRMED | `transitions` rows `test_none_*`, `test_pending_*`, `test_rewarded_*`, `test_a_rewarded_refund_processed_is_a_no_op`. |
| 49 | A code that does not resolve (Machine A row, OQ-6). | CONFIRMED | `community/auth_routes.py:46-50`. Probe: 400 `Invalid referral code` with referrals on, 201 with them off. No committed test. |
| 50 | Unresolved commerce events are kept for review, and every event is recorded with its disposition (Key entities, Observability). | CONFIRMED | `canon/webhook_events.py:158-161`, `admin/routes.py:245`. `processor::test_no_stored_event_is_left_received`. |
| 51 | Governing workflows and CI reuse (Workflows). | CONFIRMED | `AGENTS.md:64`, `.github/workflows/ci.yml`. The job list is stale (D10). |
| 52 | Owners: FORGE, a cloud agent, SCRIBE, ADVERSARY (Workflows). | DRIFT | D10. |
| 53 | Rollback never deletes ledger or referral rows. | CONFIRMED | Flags write nothing. `tests/acceptance/test_subscription_postgres.py::test_the_migration_refuses_to_downgrade_with_rows_and_round_trips_empty`, `tests/acceptance/test_studio_fair_use_postgres.py::test_the_migration_refuses_to_downgrade_with_covered_exports_and_round_trips`. |
| 54 | The provider receives the user's email and display name (Privacy). | DRIFT | D9. |
| 55 | Disclosure and consent for provider data (Privacy). | OPEN | O5. |
| 56 | Replaying an event sequence gives the same ledger (SC-001). | CONFIRMED | `processor::test_a_redelivered_event_keeps_its_disposition_and_is_not_reprocessed`, `hardening::test_a_sequential_redelivery_answers_duplicate`. Probe replays a whole sequence: same single ledger row. |
| 57 | A referral code is immutable (FR-021). | DRIFT | D6. |
| 58 | The spec's source-derived text still matches the code. | DRIFT | D12. |
| 59 | P2 AC2 grants on the provider's status report. | DRIFT | D11. |
| 60 | FR-029: a reward never edits the `Pending` row. | CONFIRMED | `monetization/referrals.py:157-165` appends; no code updates or deletes these rows. `transitions::test_pending_first_purchase_rewards_once_atomically`. The missing database guard is D5. |
| 61 | OQ-1: prices and credit quantities (FR-003, FR-006). | OPEN | O1. |
| 62 | FR-002: what "demo mode only" means, and the default tier. | OPEN | O7. |
| 63 | OQ-8: the STUDIO fair-use cap number. | OPEN | O4. The flag itself is row 4. |
| 64 | OQ-12: retention after account deletion. | OPEN | O6. |
| 65 | T051: payment activation. | OPEN | O12. |
| 66 | Jev's decisions OQ-3, OQ-4, OQ-5 (Machine B), OQ-7, OQ-9, OQ-10 and OQ-11 match the code. | CONFIRMED | `canon/subscriptions.py:907-919`; `canon/entitlements.py:37-50,65`; `canon/checkout.py:780-863`; `canon/webhook_events.py:183-232`; `docs/SECURITY.md`; `tiers::test_the_entitled_statuses_are_the_oq4_paid_tier_statuses`; `tests/api/test_p1_security.py::test_legacy_purchase_route_is_gone`. All have confidence above 0.5. |

## Machine C correction, for the owner to accept by merging

The old table in spec.md granted on `subscription_created`, `subscription_updated` and `period_renewed`. The code grants only on `invoice.paid`, and the research agrees: [COMMERCE_BLOCKERS_RESEARCH_2026-11-01.md](../../docs/evidence/COMMERCE_BLOCKERS_RESEARCH_2026-11-01.md) §3 says to grant on `invoice.paid` and let `customer.subscription.*` update status and tier, OQ-4 `A_stripe_mapping` (0.98) says the same, and T049 records it.

What changed in spec.md: the Machine C table, states, illegal transitions and diagram now state what the code does, and the FR-016 status row points there. That replaces the 2026-11-03 proposal, with these additions after checking it against the code:

- An update or deletion that arrives first can create the record (EC-2).
- A cancel flag can be cleared, returning to `Active`.
- 409 `SUBSCRIPTION_CHECKOUT_OPEN` when another tier's session is open.
- A row for a paid invoice on a `Canceled` subscription, marked OPEN.

The proposal's five questions are answered here: question 1 is this correction; question 5 is row 27; questions 2, 3 and 4 are O8, O9 and O10. If the owner rejects the correction, revert the Machine C section; the code would then have to change to match the old table.

## DRIFT

Each item says which side is right and which task covers it. None needs a product decision to start.

- **D1. Unverifiable events.** The spec says they end `Unresolved` (P1 AC5, SC-004, Machine B row). The code refuses them at intake and stores nothing (`canon/exports.py:335-350`). The code is right: FR-013 says reject, and zero credits holds either way. T090 corrects the spec wording.
- **D2. Machine B table is incomplete.** It has no `payment_status`, no `async_payment_succeeded` or `async_payment_failed`, no `pending` or `failed` status, and its final-state sentence conflicts with its refund rows and diagram. The code is right (research §2, T046; `canon/checkout.py:522-552`; `transitions::test_b_completed_unpaid_waits_and_async_success_credits_once`). T090 corrects the spec.
- **D3. `Unresolved` is per event in the code, per checkout in the spec.** After one event ends `unresolved`, a later signed event that matches the server's record credits with no operator, and the first event stays `unresolved` (probe). The code is right: FR-011 holds, because the provider confirmed and the record agrees. T090 corrects the illegal row; T010 adds the test.
- **D4. `operator_rejects`.** The spec says the checkout becomes `Abandoned`. The code marks only the event `rejected`, and the payment stays `open` (`canon/webhook_events.py:207-214`; `transitions::test_b_unresolved_operator_rejects_grants_nothing` asserts this). A later verified event then credits (probe). The spec is right: an operator's rejection should close the checkout, which fails closed. T090 changes the code and that test's assertion.
- **D5. Append-only reach.** FR-008 and FR-029 say append-only. Only `canonical_credit_ledger` has a database guard. `credits_ledger`, `credit_ledger_entries`, `referrals` and `subscription_period_grants` rely on convention; the code has no update or delete of them, and no route hard-deletes a user. This record reads "the credits ledger" as the canonical one, which spending and the balance use. The spec is right for all of them. T090 adds guards or retires the legacy tables; T010 already lists the gap.
- **D6. FR-021.** A referral code is "immutable once created", but `account/deletion.py:149` replaces it on account deletion, and no database guard exists. The replacement is right under OQ-12 (the old code must stop resolving). T090 adds the exception to the spec and a guard to the column.
- **D7. FR-009 "one balance endpoint".** `GET /api/me/credits` (`account/routes.py:58-73`) sums `credit_ledger_entries`, which no production code writes. Probe: it answers 0 while the canonical balance is 30. The frontend does not call it (`frontend/src/lib/api.ts:794-795`). The spec is right. T090 removes the route or points it at the canonical ledger.
- **D8a. FR-031 and P4 AC2.** The Account page (`frontend/src/pages/Account.tsx:90`, `frontend/src/lib/api.ts:830`) reads `GET /api/me/referrals`, built on `account_referrals`, a second table written at signup (`community/auth_routes.py:76-88`) that nothing moves to `earned`. Probe after a reward: it shows 1 pending and 0 earned, while `get_referral_summary` shows 0 pending, 1 rewarded and 3 credits. That correct summary is mounted only with `ENABLE_LEGACY_SOCIAL` (`main.py:197-200`, off by default). The spec is right. Referrals are off by default, so no user sees this today. T090 fixes it.
- **D8b. No user interface for commerce.** `frontend/src` has no caller of the checkout or cancel routes. T050 also left no STUDIO allowance and a generic error for 429 `FAIR_USE_CAP_REACHED`. The spec is right. T090 builds these before T051.
- **D9. Provider data.** The Privacy line says the provider receives email and display name. The code sends only `metadata[user_id]` (`canon/checkout.py:175-176`; `checkout::test_the_stripe_client_sends_form_requests_with_idempotency_keys`). The code is right: least data. T090 corrects the line. Disclosure stays O5.
- **D10. Workflows owners and CI jobs.** FORGE and cloud agents are defined (`Zero-State-LLC/agent-context` `DECISIONS.md:45`, which also says "No extra bots"). SCRIBE appears only in specs and ADVERSARY only in specs and `docs/evidence`. Neither is in that repo's `TEAM.md` or `templates/sdlc/README.md`, and `AGENTS.md` forbids inventing bots. `AGENTS.md` is right: read "ADVERSARY" as an adversarial review pass, and drop SCRIBE. The CI line names two of six jobs (`backend`, `migrations`, `acceptance`, `backend-lint`, `frontend`, `frontend-e2e`). T090 corrects the spec.
- **D11. P2 AC2.** It grants when the provider reports an active subscription. Machine C now grants on `invoice.paid`. The code is right. It is outside the correction this PR was allowed to make, so T090 corrects it.
- **D12. Stale text left as it is, because this PR may not rewrite spec.md beyond Machine C.** T090 cleans these up:
  - The status line still says DRAFT, and "No requirement is confirmed until the operator signs off". The status of each claim is here.
  - The refund non-goal conflicts with the Machine B refund rows and OQ-2.
  - The Implementation status intro still says prices stay unconfirmed "(OQ-1, T001)"; only OQ-1 still applies.
  - FR-028 says OQ-3 is unresolved.
  - P6 AC2 and the `[OBSERVED: backend/monetization/routes.py]` labels name a file and route that are gone.
  - The Machine A row for an unknown code says the outcome is unresolved, though OQ-6 answers it.
  - EC-6, EC-11 and EC-12 describe code from before T049.
  - OQ items say "Still open (owner)" next to their decisions.
  - Outside the spec: `backend/tests/unit/test_spec_004_transitions.py:612` calls this a "decided deviation from the table" (T010). `docs/evidence/JEV_DECISIONS_2026-11-01.md`, `docs/evidence/OWNER_ACTIONS_2026-11-02.md` section 2.7 and `CURRENT_STATE.md:129` still describe Machines B and C as not built.

## OPEN

Not decided here. Each default is a recommendation only.

- **O1. Prices and credit quantities (OQ-1, FR-003, FR-006).** Owner decides, and a lawyer must confirm. Today's settings are provisional (0.29). Default: do not ratify sheet A; `OWNER_ACTIONS_2026-11-02.md` sections 2.7 and 6 recommend sheet C to launch and sheet B's ladder when subscriptions start. Blocks T046, and through it T047, T048b, T049, T050 and T053.
- **O2. Refund and dispute terms (OQ-2, EC-12).** A lawyer must confirm the rule, and the owner its rounding and cap. Subscription invoice refunds have no rule. Default: keep the built rules in test mode, and hold subscription refunds as `unresolved`, until counsel answers section 5 of the owner guide.
- **O3. Tax, invoicing, regional pricing and sales terms (OQ-13).** Counsel. Default: `D_defer_sales`, no sales until counsel drafts terms.
- **O4. STUDIO fair-use cap number (OQ-8).** Owner, with O1. Default: keep 100 per period until prices are set.
- **O5. Disclosure and consent for provider data.** Counsel. Default: keep sending only the user id.
- **O6. Retention after account deletion (OQ-12).** Counsel. Default: keep T052 as built until counsel sets periods and says whether free text in kept rows must go.
- **O7. FR-002 "demo mode only" and the default tier.** Owner. "Demo mode" is undefined. A user who never subscribed resolves to `core` (`core/config.py:176`), while a lapsed subscriber resolves to FREE (`canon/entitlements.py:93-110`), so never paying gets more than having paid. Default: read FREE as 0 signup credits and the free template families, keep `core` while sales are off, and switch the default to `free` when sales start.
- **O8. A paid invoice on a `Canceled` subscription.** Owner, money. Today it grants, and no test covers it. Default: hold it as `Unresolved` so an operator refunds or grants, which fails closed. Add the test either way.
- **O9. Operator resolve for Machine C (T048).** Owner. Today an operator can only reject, and T048 stays open on this. Default: keep it refused while sales are off, and decide before T051.
- **O10. Who can schedule a cancel (FR-017).** Owner, money, and counsel may care. Only `active` can (`canon/subscriptions.py:376`; probe for `trialing` and `past_due`), and with the flag off cancel is 403 (`subs::test_cancel_is_refused_when_subscriptions_are_off`), so a rollback would stop subscribers cancelling here. Default: allow it for every live status, and keep it working with the sale flag off.
- **O11. EC-13: reward for a deleted referrer.** Owner. Today it is written (`monetization/referrals.py:150-165`). Default: skip the reward and leave the row `Pending`; nobody can spend it, and it adds a row about a deleted person. Add the test either way.
- **O12. Payment activation (T051, FR-019).** Never here. Default: stay in test mode until the adversarial review, O1, O2 and O3 are done and the owner gives explicit authority.

## Not verified

- Live environment flags, production data and the provider account were not read. So the live flag values, and whether referral codes issued before 2026-10-29 reveal an email (FR-036), are unknown here.
- SC-006 and SC-007 have no direct committed test. Their rows rest on code search and a probe.
