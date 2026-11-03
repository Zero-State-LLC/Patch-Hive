# Intent

## Problem

Spec 002 OQ-10 and OQ-13 were decided 2026-11-01 but not built. An owner and an admin acting on one publication at once can interleave (the owner's status change may land over an admin hide). The report route has no rate limit and lets one reader file the same report repeatedly.

## Proposed outcome

- OQ-10 `row_lock`: the owner PATCH and the admin hide and remove handlers load the publication with `SELECT ... FOR UPDATE` (`populate_existing`), so the owner path checks the moderation state after the lock. No-op on SQLite.
- OQ-13 `limit_and_require_dedupe`: `POST /p/{slug}/report` keeps anonymous reports, adds a per-client-address limit (10 an hour, 429 `REPORT_RATE_LIMIT`) reusing `community.login_guard`, and answers 200 `already_reported` instead of storing a second report from the same signed-in reporter on the same publication.

Out of scope: report and audit-log retention (still the owner's call, and a lawyer must confirm), a database unique constraint, de-duplicating anonymous reports.

## Affected users / systems

Legacy publishing routes (`ENABLE_LEGACY_PUBLISHING`, off by default). No migration.

## Constraints / non-goals

No schema change. The limit is per process, like the sign-in limit; Cloudflare rate limiting is the edge backstop. Dedupe is a locked read-then-insert on the publication row; without Postgres (SQLite) concurrent duplicates are not serialized.

## Open questions

- Retention for reports and audit logs (owner, lawyer).
- Whether the report limit should be tighter or be per user as well as per address (owner; the decision is provisional, confidence 0.34).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Lock behavior under real concurrency on Postgres | `INFERRED` | `FOR UPDATE` semantics; not exercised in a test (SQLite fixtures) |
| Stale-session moderation read, limit and dedupe behave as described | `OBSERVED` | `tests/unit/test_spec_002_report_limits_and_locks.py` |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-01
