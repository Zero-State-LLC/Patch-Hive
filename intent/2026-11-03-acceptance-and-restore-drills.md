# Intent

## Problem

The Project #8 beta cards "Acceptance suite against staging Postgres" and "Backup/restore + ledger reconcile drill receipts" have only local Compose receipts (`docs/evidence/STAGING_ACCEPTANCE_RECEIPT_20260726.md`, `docs/evidence/STAGING_BACKUP_RESTORE_RECEIPT_20260726.md`). CI skips `backend/tests/acceptance` (`.github/workflows/ci.yml` runs `--ignore=tests/acceptance`), and nothing runs the suite against Neon or rehearses a restore of a deployed database. `reconcile_ledger(session, user_id)` checks one user and has no command, so release gate 6 in `docs/OPERATIONS.md` has no repeatable form.

## Proposed outcome

- CI runs the acceptance suite in its own job against the job's service Postgres, through `ACCEPTANCE_DATABASE_URL`.
- The acceptance conftest refuses a database named `patchhive`, because it truncates every public table.
- `.github/workflows/acceptance-staging.yml` (manual, staging only) creates a throwaway database: either `patchhive_acceptance_<run>_<attempt>` on the Neon staging branch, or a Neon child branch of `staging` when `NEON_API_KEY` is set (it refuses with a clear message when it is not). It migrates that database to head, runs the suite, drops the database or branch, and keeps a counts-only receipt.
- `python -m canon.reconcile_all` runs `reconcile_ledger` for every user in a read-only transaction. It prints counts and mismatches (export ids only, never user names or emails) and exits 1 on any mismatch.
- `.github/workflows/db-restore-drill.yml` (manual) runs `pg_dump` on staging, or on production only with a typed confirmation phrase. It restores the dump into a Postgres container on the runner and checks `alembic current` is the checkout's head. It then runs the reconcile CLI on the restored copy and uploads a counts-only receipt. The dump never leaves the runner.
- `docs/OPERATIONS.md` documents how to dispatch each.

Out of scope: dispatching any of these against staging or production (the owner does that), scheduling them, `CURRENT_STATE.md`, `docs/ROADMAP.md`, `docs/KANBAN.md`, and closing the Project cards before receipts exist.

## Affected users / systems

CI and the Neon staging branch (a throwaway database or child branch per acceptance run, removed at the end of the run). Production can only be read by `pg_dump` and count queries, and only with the confirmation phrase. Nothing writes to a deployed `patchhive` database.

## Constraints / non-goals

Fail closed. No secret, URL, host, user name or email in logs, receipts or artifacts (artifacts in this repo are public). Payments stay test-mode. No change to product behaviour or to `reconcile_ledger` itself.

## Open questions

- Whether the staging role may `CREATE DATABASE` on Neon (role membership in `neon_superuser`). UNKNOWN until the first dispatch. If it cannot, the `neon-branch` isolation is the fallback.
- Whether the owner wants a `NEON_API_KEY` secret in the staging environment. Owner decides.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The acceptance suite passes on a fresh Postgres 15 database via `ACCEPTANCE_DATABASE_URL` | `OBSERVED` | local run on postgres:15.13, 35 passed |
| Neon staging and production both name their database `patchhive`, Postgres 15 | `OBSERVED` | `DEPLOY_STATUS.md` |
| Neon child branches copy roles, so the staging role can own a database on the child | `INFERRED` | Neon branching docs; the workflow asks the API for the connection string instead of assuming the password |
| `pg_dump` and `pg_restore` of the server's major version restore cleanly into a vanilla Postgres container of the same major | `INFERRED` | holds for the local Compose drill; NOT_COMPUTABLE for Neon until dispatched |

## Author / date

- Author: Claude Code session for Daniel Meyer
- Date: 2026-11-03
