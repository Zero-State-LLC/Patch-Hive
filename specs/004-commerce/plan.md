# Plan: 004-commerce

An agent wrote and finished this plan on 2026-11-04, under the owner's delegation, from spec.md, [the T001 record](T001_CONFIRMATION_2026-11-04.md) and the code on `main` at 007b437 (0.3.0-alpha.8). The owner has not read the spec or this plan, and approves both by merging the PR. Payments stay in test mode.

## Stack (as built)

- Backend: Python 3.11 (`backend/Dockerfile`; the CI test jobs run 3.11 and `backend-lint` runs 3.12), FastAPI, SQLAlchemy 2, Alembic migrations, Pydantic 2 (`backend/pyproject.toml`).
- Database: Postgres 15 (Neon in staging and production, a Postgres service in CI); unit tests use SQLite fixtures (`backend/tests/conftest.py`).
- Frontend: React 18, TypeScript, Vite, React Router (`frontend/package.json`).
- Edge: the Cloudflare Worker in `edge/api` fronts the API (spec 006).
- CI: `.github/workflows/ci.yml`, jobs `backend`, `migrations`, `acceptance`, `backend-lint`, `frontend` and `frontend-e2e`. `just spec-dag` runs the task DAG check.

## Architecture

- **Canonical ledger.** `canonical_credit_ledger` (`backend/canon/models.py`) is append-only, enforced by a Postgres trigger (#139). The entry types are `purchase`, `debit`, `reversal`, `grant` and `refund`. `GET /api/canon/credits/balance` is the balance spending uses (`backend/canon/routes.py`, `backend/canon/exports.py`).
- **Legacy tables.** `credits_ledger` holds the `Purchase` rows Machine A counts (`backend/monetization/models.py`), and is append-only, as are `referrals` and `subscription_period_grants` (#346). `credit_ledger_entries` and `account_referrals` are retired: nothing reads or writes them, and the tables stay so any old rows are kept (#345).
- **Webhook intake.** `receive_stripe_webhook` (`backend/canon/exports.py`) verifies the signature (constant-time HMAC over every `v1`, 300 s tolerance, livemode gate) and refuses what it cannot verify, storing nothing. `process_stripe_event` (`backend/canon/webhook_events.py`) then dispatches by type and gives every stored event a disposition: `processed`, `duplicate`, `unresolved` with a reason code, or `ignored`.
- **Machine B.** `backend/canon/checkout.py`: credit checkout behind `ENABLE_CREDIT_CHECKOUT` and `checkout_gate`, one provider customer per user, payments unique on the provider ids, refunds and disputes (OQ-2), and operator resolve (T048b).
- **Machine C.** `backend/canon/subscriptions.py`: subscription checkout behind `ENABLE_SUBSCRIPTION_CHECKOUT`, a record synced by `customer.subscription.*`, a period grant on `invoice.paid`, and cancel at period end. `backend/canon/entitlements.py` resolves the tier from the subscription and spends the STUDIO fair-use entitlement (T050).
- **Machine A.** `backend/monetization/referrals.py`: append-only referral rows. A reward comes only from a provider-verified first purchase (`record_purchase(payment_verified=True)`). Referral signup and the summaries sit behind `ENABLE_REFERRALS`.
- **Operator.** Admin reject and resolve for unresolved events (`backend/canon/webhook_events.py`, `backend/canon/checkout.py`), each with an audit record. A rejection closes the event's checkout if it's still open (#344). Resolve is Machine B only.
- **Account page.** `GET /api/canon/commerce` (`backend/canon/commerce_status.py`) says what's open and what the user holds, and `frontend/src/components/AccountCommerce.tsx` offers only that (#347). The export pages read the STUDIO allowance from the same route.
- **Defaults.** `STRIPE_TEST_MODE=true`, `ALLOW_PRODUCTION_PAYMENTS=false`, both checkout flags off (`backend/core/config.py`). `validate_stripe_mode_startup_policy` refuses live mode outside production.

## What T001 settled

[The T001 record](T001_CONFIRMATION_2026-11-04.md) classifies every checklist claim and `[INFERRED]` line. An agent confirmed them under the owner's delegation, not the owner by reading them.

- Machine C grants on `invoice.paid`. The corrected table is below and in spec.md.
- Workflows: the governing skills and the CI reuse stand; the owners line is drift (D10).
- FR-008: T001 read "the credits ledger" as the canonical ledger and treated the other tables as drift (D5). T090 guarded them too (#346).

## Work list

T010 and T090 are done. What each plan item became:

| Item | Result |
|---|---|
| T010: tests for what only a probe covered | #343 |
| Spec text: D1, D2, D3, D9, D10, D11, D12 | This PR |
| D4: a rejection closes the checkout | #344 |
| D5, D6: database guards | #346 |
| D7, D8a: the balance route and the referral summary | #345 |
| D8b: buying, plans, cancelling and the STUDIO allowance | #347 |

### Other open work

Nothing below activates payments.

1. **Owner and counsel.** From the record's OPEN list: O2, O3, O5 and O6 are with counsel (decisions 33 and 46). O1 is not ratified (decision 32). O4, and O9 for subscription events, wait for sales (decision 46). O7 is settled for when sales open (decision 45). O8, O10 and O11 are decided (decisions 42, 43 and 44, #292), but O10's second half is not: with the sale flag off, a plan holder can't cancel here, and the page says so (#347).
2. **T046 to T053.** The code exists and stays unticked while prices aren't ratified (decision 32). T048 also waits on operator resolve for subscription events.
3. **T051.** Payment activation, last: it needs the adversarial review of the provider path, which should include a real test-mode checkout, and explicit owner authority.

Also still undefined: `data-model.md` and `contracts/README.md` are TODO stubs. No task names them; `docs/DATA_MODEL.md` and the code are the sources for now.

## Verification

- `cd backend && pytest tests/unit/test_spec_004_transitions.py -q`, which covers Machines A, B and C as the code reads them.
- `tests/unit/test_commerce_subscriptions.py`, `tests/unit/test_commerce_credit_checkout.py`, `tests/unit/test_commerce_operator_resolve.py`, `tests/unit/test_commerce_webhook_processor.py`, `tests/unit/test_commerce_purchase_refunds.py`, `tests/api/test_commerce_status_api.py`.
- `cd frontend && npx vitest run src/components/AccountCommerce.test.tsx src/lib/commerce.test.ts`, and `npx playwright test -c tests/ui/playwright.config.ts tests/ui/commerce.spec.ts`, with every API call mocked.
- `cd backend && python -m pytest tests/acceptance -q`, which needs Postgres (CI job `acceptance`): append-only triggers, the referral code guard, concurrent checkout, grant, refund, reject and referral paths, and the refusing downgrades.
- `just spec-dag`.

## Spec text

Workflows and the stateful sections used to be copied here. They now live only in [spec.md](spec.md).
