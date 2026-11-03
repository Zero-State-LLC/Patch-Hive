# Intent

## Problem

Jev decision 006 OQ-3 `record_receipts_and_close` (`docs/evidence/JEV_DECISIONS_2026-11-01.md`) asks for a short evidence receipt per operator task and closure of the tasks whose evidence is complete. Since the 2026-11-01 receipts, both hosts moved to `ee5326e` and migrated to `20261101_user_deleted_at`. Four operator tasks are still open: 008 T030b, 006 T040b, 008 T050b and 006 T055b.

## Proposed outcome

One receipt file, `docs/evidence/OPERATOR_RECEIPTS_2026-11-02.md`, with read-only observations and one entry per task. A task is ticked only when its evidence meets its acceptance line. Each open task line points to the receipt and names what is missing.

Out of scope: running the seeder, the walkthrough, the pin or the R2 persistence check; any deploy, secret, environment or database change.

## Affected users / systems

Docs only: `docs/evidence/`, `specs/006-cloudflare-edge-clef/tasks.md`, `specs/008-dual-path-f5-design-receipts/tasks.md`.

## Constraints / non-goals

Read-only evidence: plain GETs to the public API hosts, `gh run view` of recorded runs, files in this tree. No login to any host, no Cloudflare or Neon API call, no secret printed. Fail closed: missing evidence keeps a task open.

## Open questions

None for this change. The operator runs the R2 persistence check (T055b) and the staging walkthrough (008 T030b, T040b); the 007 receipt (007 T060b) gates 008 T050b.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Both API hosts answer `/health/ready` 200 with `database: ok` | `OBSERVED` | curl 2026-11-02 21:53Z |
| Staging and prod migrate runs reached `20261101_user_deleted_at` at `ee5326e` | `OBSERVED` | `gh run view --log` 41424675176, 41428760962 |
| R2 buckets exist | `OBSERVED` (second hand) | `docs/evidence/OWNER_ACTIONS_2026-11-02.md` §4, read-only bucket listing |
| Files survive a container restart | `NOT_COMPUTABLE` | needs an upload, restart and fetch on staging |
| Seeded demo auth is aligned on staging | `NOT_COMPUTABLE` | needs the staging `DATABASE_URL`; no receipt in tree |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-02
