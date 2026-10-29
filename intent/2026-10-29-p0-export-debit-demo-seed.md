# Intent

## Problem

The 2026-10-29 gap analysis found two P0s. Neither can bite today (no users or credits on prod or staging), but both would on first use.

1. **Exports took credits nothing would fulfill.** With the default flags, which production uses, `POST /api/canon/exports` debited credits and left the export `queued`. Inline fulfillment is the only fulfiller; there is no queue worker. The user lost the credits with no refund (spec 004 FR-005).
2. **A published Admin login.** `scripts/seed_golden_demo.py` hard-codes `admin_demo` / `admin-pass` (Admin role), the repo is public, and the seeder had no environment guard. The staging walkthrough (008 T030b) expects to seed these accounts on hosted staging.

## Proposed outcome

1. `POST /api/canon/exports` answers 503 `EXPORT_FULFILLMENT_UNAVAILABLE` before any debit unless both fulfillment flags are on. Inline fulfillment already refunds every failure it catches.
2. `seed_golden_demo` checks its target before any write:
   - production is refused;
   - a local database (localhost, socket, SQLite, the compose service) keeps the fixed demo passwords;
   - any hosted database must be declared `ENVIRONMENT=staging` and get both passwords from `PATCHHIVE_DEMO_USER_PASSWORD` / `PATCHHIVE_DEMO_ADMIN_PASSWORD` (16+ characters, never the published ones).

   The walkthrough logs in with whatever the seeder returns.

## Affected users / systems

Canonical export API; demo seeding (local, staging walkthrough); `docs/OPERATIONS.md`.

## Constraints / non-goals

No change to debit, idempotency or compensation logic. No queue worker is added.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Flags off: debit with no fulfiller | `OBSERVED` | `canon/routes.py` before this change; `fulfill_export` has one caller |
| No users, credits or exports on prod or staging | `OBSERVED` | read-only queries 2026-10-29 |
| With the flags off, no debit and 503 | `OBSERVED` | `test_an_export_nothing_will_fulfill_is_refused_before_any_debit` |
| Seeder refuses production and unsafe hosted targets | `OBSERVED` | `tests/unit/test_demo_seed_guard.py` |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-29
