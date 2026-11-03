# Intent

## Problem

Spec 004 T050: every user resolves to the `design_engine_default_tier` setting (`canon/entitlements.py`), whatever they subscribe to (FR-001 Partial). Since T049 (#219) a `ProviderSubscriptionRecord` holds each subscription's tier (from the provider price) and provider status, and a STUDIO `invoice.paid` writes a `SubscriptionPeriodGrantRecord` with `unlimited=true` and `fair_use_export_cap`, but nothing reads either: a STUDIO subscriber gets the default tier's template families and pays for exports with credits STUDIO never grants (FR-004).

## Proposed outcome

- **Tier rule (OQ-4 `A_stripe_mapping`).** `resolve_user_tier(session, user_id)` returns the tier of the user's newest subscription whose provider status is entitled: `active`, `trialing`, or `past_due` (keeps the tier while the provider retries). Any other status (`incomplete`, `incomplete_expired`, `unpaid`, `paused`, `canceled`), or no subscription, falls back to the default-tier setting. `get_design_entitlements` takes the session; both export routes pass it.
- **Tier changes (OQ-7 `A_next_period_no_proration`).** No proration logic. The stored tier is what subscription sync took from the provider price. What the user can spend follows the period grant, which `invoice.paid` writes for the billed tier, so a tier change brings its credits or unlimited entitlement with the next paid period.
- **STUDIO spending (FR-004, OQ-8 `A_flag_with_fair_use`).** `request_export` asks `current_unlimited_grant` for an unlimited period grant of the user's entitled subscription covering the request time. If there is one, the export takes no debit (`credit_cost=0`, no ledger entry) and records `subscription_grant_id`. The cap counts exports pointing at that grant that are not `failed` or `refunded` (a failed export gives its slot back, as a failed paid export gets its credits back, FR-005). At the cap the export is refused `FAIR_USE_CAP_REACHED` (HTTP 429), and it does not fall through to the credit ledger. The count runs under `request_export`'s existing per-user lock (`pg_advisory_xact_lock`), so two concurrent spends cannot both take the last slot. An idempotent retry of a covered export returns it even at the cap.
- **No current STUDIO grant** (no entitled subscription, a CORE or PRO grant, or a period not yet paid, for example `past_due` after the period rolled over): the credit ledger, unchanged. CORE and PRO always use the ledger.
- **Schema.** Migration `20261102_export_fair_use` (revises `20261102_subscriptions`, single head): nullable `canonical_exports.subscription_grant_id` FK to `subscription_period_grants.id` (`RESTRICT`), indexed, and `ck_canonical_exports_grant_shape`: a covered export has `credit_cost = 0` and no ledger entry. Downgrade refuses while a covered export exists.

Out of scope: frontend (it shows any 429 as a generic error and has no STUDIO copy), showing the remaining fair-use allowance, `invoice.payment_failed`, subscription refunds and disputes, operator resolve for Machine C, flag or setting changes.

## Affected users / systems

`canon/entitlements.py`, `canon/exports.py` (`request_export`), `canon/routes.py` (export and preview routes, 429 mapping), `canon/models.py` (`CanonicalExportRecord`), new Alembic revision. Payments flags unchanged: subscriptions stay behind `ENABLE_SUBSCRIPTION_CHECKOUT=false`, `STRIPE_TEST_MODE=true`, `ALLOW_PRODUCTION_PAYMENTS=false`.

## Constraints / non-goals

Fail closed: an unentitled status never keeps a paid tier, and a reached cap never spends credits instead. The tier stays a gate, never a generation input (FR-035). The ledger stays append-only. No migration is run against any environment by this change.

## Open questions

- Owner: OQ-4's decision maps the unentitled statuses to FREE. This change follows the task wording and falls back to the default-tier setting (`core` by default), which is what every non-subscriber gets today. If lapsed subscribers must get FREE while non-subscribers keep `core`, that is a one-line change in `resolve_user_tier`.
- Owner: the fair-use refusal is HTTP 429 `FAIR_USE_CAP_REACHED`; 402 is taken by `INSUFFICIENT_CREDITS` and the frontend labels every 402 that way.
- Owner: whether a STUDIO subscriber at the cap may spend credits they hold (from purchases or referrals). This change refuses instead.
- Owner: an entitled status is trusted until the provider says otherwise; an `active` record whose period end has passed with no new event still counts (the provider sends `past_due` or `canceled`).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| OQ-4 maps `active`/`trialing` to the paid tier and keeps it for `past_due` | `OBSERVED` | `specs/004-commerce/spec.md` OQ-4 decision |
| STUDIO period grants carry `unlimited=true` and a cap of at least 1, and no ledger entry | `OBSERVED` | `SUBSCRIPTION_GRANT_SHAPE` in `canon/models.py` |
| Two concurrent spends for the last slot take it once on Postgres, and the test fails with the per-user lock removed | `OBSERVED` | `tests/acceptance/test_studio_fair_use_postgres.py`, run locally with the lock disabled |

## Author / date

- Author: Claude (agent), for Daniel Meyer
- Date: 2026-11-02
