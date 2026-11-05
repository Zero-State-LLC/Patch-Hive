# Operations and deployment

PatchHive remains a modular monolith. Apply the single Alembic head before application rollout, then start the FastAPI and static frontend processes. Production persistence is PostgreSQL; SQLite is a unit-test adapter only.

**Campaign note (2026-07-21):** No production deployment was performed on PR #47 or #49. Main HEAD `71a4dfa` is CI-green; staging may be stood up using the gates below. See [CONTINUATION.md](CONTINUATION.md) P0–P3. Prefer `/api/canon/*` for export/credit clients; legacy PatchBook debit POST remains transitional until acceptance migrates.

## Release gates

1. Install exactly from `backend/pyproject.toml` / `backend/requirements.txt` and `frontend/package-lock.json`.
2. Run backend, frontend, property/contract, security, and accessibility automation (or rely on green PR CI).
3. Run `alembic heads` and require a **single head**. As of 2026-07-26, head includes `20260726_module_registry_slugs` (after device registry + PDB wiring). Re-check on the release SHA; do not trust this note alone.
4. Run PostgreSQL integration and migration tests (`alembic upgrade head` against Postgres 15). Deployed databases (Cloudflare staging and production) are migrated only by the manual `db-migrate.yml` workflow, run before deploying code that adds a migration. Container startup migrations are opt-in (`RUN_MIGRATIONS` exactly `true` or `1`; default off) and are not enabled on either Cloudflare Worker, so a cold start never mutates the database. Never use `init_db()`/`create_all()` as the production schema path.
5. Generate and retain Python/npm CycloneDX SBOMs and build provenance (Security workflow artifacts).
6. Run ledger reconciliation (`python -m canon.reconcile_all`, or the restore drill below) and require no mismatches.
7. Verify all legacy feature flags are false (`ENABLE_LEGACY_SOCIAL`, `ENABLE_LEGACY_PUBLISHING`, `ENABLE_LEGACY_LEADERBOARDS`) and `ENABLE_REFERRALS` is false unless referrals are intended.
8. Verify `STRIPE_TEST_MODE=true` and `ALLOW_PRODUCTION_PAYMENTS=false`.
9. Perform the manual accessibility protocol ([ACCESSIBILITY.md](ACCESSIBILITY.md)).
10. Confirm CORS, `SECRET_KEY`, and DB networking meet [SECURITY.md](SECURITY.md).
11. For Patch Book output, pass every gate in [PATCH_BOOK_GENERATOR.md](PATCH_BOOK_GENERATOR.md), including one-patch-per-page, page-fit, accessibility, manifest, and deterministic replay validation.

## Patch Book production gate

A Patch Book export may be marked `ready` only when:

- every published patch maps to exactly one accepted PatchPageSpec
- patch count equals patch-page count
- PDF page count equals PatchBookManifest page count
- no required content block overflows, clips, or falls below minimum typography
- diagram routes and ordered connection steps encode the same PatchGraph
- grayscale and non-color interpretation pass
- every page binds to patch ID, source run, source rig revision, generator version, canonical hash, and page asset hash
- all table-of-contents, index, and cross-reference targets resolve
- all included assets match their manifest hashes
- deterministic replay reproduces canonical-equivalent JSON and stable SVG structure

A failed page cannot be silently omitted from a paid export. The export must fail with a machine-readable reason, preserve diagnostics, and follow the existing idempotent compensation path.

## Local / Compose

```bash
# Optional Docker path
make dev
make db-migrate
make test
```

Environment template: repository root `.env.example`. Never commit real secrets.

## Staging (named host)

**Plan:** [evidence/STAGING_HOST_PLAN.md](evidence/STAGING_HOST_PLAN.md)  
**Local Compose receipt:** [evidence/STAGING_COMPOSE_RECEIPT.md](evidence/STAGING_COMPOSE_RECEIPT.md)

### Staging-like Compose (image-built backend, no --reload)

```bash
# Unified automation (preferred):
#   bash scripts/test/run.sh ci            # unit + frontend + acceptance
#   bash scripts/test/run.sh docker-suite  # full Docker path (preferred local staging)
#   bash scripts/test/run.sh staging       # smoke + host-venv acceptance + design-engine
# Windows:
#   powershell -File scripts/test/run.ps1 ci
#   powershell -File scripts/test/run.ps1 docker-suite

# Or individual staging scripts:
# Automated readiness + alembic head + pg_dump/restore side-DB drill
powershell -File scripts/staging/smoke.ps1   # Windows (PowerShell 5+)
# bash scripts/staging/smoke.sh              # Linux/macOS

# Acceptance suite against compose Postgres (dedicated patchhive_acceptance DB):
powershell -File scripts/staging/acceptance.ps1
# bash scripts/staging/acceptance.sh

# Design Engine flags + preview/export walkthrough (test payments only):
powershell -File scripts/staging/design-engine.ps1
# bash scripts/staging/design-engine.sh

# Manual:
export STAGING_SECRET_KEY="$(openssl rand -base64 32)"
export STAGING_DB_PASSWORD="$(openssl rand -base64 18)"
docker compose -f docker-compose.staging.yml up -d --build
curl -sf http://localhost:8000/health/ready
docker compose -f docker-compose.staging.yml exec -T backend python -m alembic current
# expect: 20260726_module_registry_slugs (head as of 2026-07-26; re-check on SHA)
```

Staging **must** keep `ALLOW_PRODUCTION_PAYMENTS=false` and `STRIPE_TEST_MODE=true`.  
A public hostname requires an explicit operator host pick (Compose VPS / Render / Fly / Azure) — agents must not invent cloud accounts.

### Demo credentials (local Docker staging)

Restored by `scripts/staging/seed-demo.ps1` (also run at end of `smoke.ps1`):

| Account | Username | Password | Role |
|---------|----------|----------|------|
| Demo user | `golden_demo` | `demo-pass` | User |
| Admin | `admin_demo` | `admin-pass` | Admin |

These passwords are public and work only on a **local** database. The seeder refuses production, and refuses any hosted database unless `ENVIRONMENT=staging` and `PATCHHIVE_DEMO_USER_PASSWORD` / `PATCHHIVE_DEMO_ADMIN_PASSWORD` (16+ characters, not the ones above) are set; the walkthrough then logs in with those.

**Not valid:** `Admin` / `Admin` (old UI label only — fixed on Login page).

### Staging vs production

| | Staging | Production |
|--|---------|------------|
| Payments | test only | separate reviewed enablement |
| Deploy authority | operator host pick | release gates + operator |
| Vision | mock/fixture | ops secret + eval dataset |

## Evidence-image expiry

Evidence images carry `retention_expires_at` (default 30 days, at most 90). The owner can also delete an image, which removes its stored file at once. Access is refused after expiry, but stored bytes and rows are only cleaned up when an operator runs the expiry command. Nothing schedules it; automatic scheduling (a Cloudflare cron or GitHub scheduled workflow) is an owner decision.

```bash
cd backend
python -m evidence.expire           # dry run (default): prints JSON counts, changes nothing
python -m evidence.expire --apply   # soft-delete expired image_assets rows and purge their bytes
```

Output is one JSON line: `mode`, `as_of`, `soft_deleted`, `purged_files`, `purge_deferred`. In a dry run the counts are what `--apply` would do, assuming storage deletes succeed. The command uses `DATABASE_URL` and the configured storage backend, so point it at the intended environment first. Run the dry run first and compare. Exit code 1 means some storage deletes failed (`purge_deferred > 0`); those rows stay undeleted and the next run retries them.

The database change is flushed before any stored bytes are deleted, so a failed flush never leaves deleted bytes behind. It writes only `image_assets.deleted_at` and deletes the stored image object. Bytes still referenced by a live asset with the same hash are kept. Append-only tables (classification evidence, receipts, ledgers) are not touched.

## Database drills

Three repeatable checks for the beta release gates. CI runs the first on every pull request; the owner dispatches the two workflows. None of them writes to a deployed `patchhive` database. Every artifact holds counts, revisions and hashes only, because this repo's Actions artifacts are public. Both workflows share the `neon-db-<env>` concurrency group with `db-migrate.yml` and `db-load.yml`, so they never overlap a migration or a load. A `workflow_dispatch` workflow can be dispatched only once its file is on `main`.

### Acceptance suite

The acceptance conftest truncates every public table before each test, so it refuses any URL whose database is `patchhive` (the database name on Neon staging and production).

- **CI:** the `acceptance` job in `ci.yml` runs `backend/tests/acceptance` against its own service Postgres (`ACCEPTANCE_DATABASE_URL`, database `patchhive_acceptance`). The suite migrates it to head.
- **Neon staging:** `acceptance-staging.yml` runs the same suite on Neon staging, in a throwaway database it creates, migrates to head and removes.

```bash
gh workflow run acceptance-staging.yml --repo Zero-State-LLC/Patch-Hive --ref main -f isolation=database
```

- `isolation=database` (default) creates `patchhive_acceptance_<run>_<attempt>` on the staging branch with the `PATCHHIVE_DATABASE_URL_STAGING` role, and drops it at the end. Nothing in `patchhive` is read or written.
- `isolation=neon-branch` creates a child branch `acceptance-<run>-<attempt>` of `staging` through the Neon API, puts a throwaway database on it, and deletes the branch at the end. It needs a `NEON_API_KEY` secret in the `staging` environment and refuses without one. `NEON_PROJECT_ID` is an optional variable (default `polished-night-86976142`). Use it if `isolation=database` fails with `SQLSTATE 42501` (the role may not create databases).

The run uses `ENVIRONMENT=staging` and fresh masked demo passwords, as `staging-walkthrough.yml` does. A cleanup step runs whatever happened, so a cancelled run does not leave a database or branch behind. Receipt: artifact `acceptance-staging-receipt` (`receipt.json`: alembic head and current, server major version, passed/failed/errors/skipped, teardown status).

### Ledger reconcile

```bash
cd backend
python -m canon.reconcile_all                      # one JSON line
python -m canon.reconcile_all --json-out out.json  # also write it to a file
```

Runs `reconcile_ledger` for every user (every account, ledger entry and export owner) against `DATABASE_URL`, in a read-only transaction that is always rolled back. Output: `status`, `users_checked`, `users_with_ledger_entries`, `ledger_entries`, `exports`, `balance_total`, `export_debits_total`, `reversals_total`, `mismatch_count`, and `mismatches` (export id and anomaly; at most 100 listed). It never prints a user id, name or email. Exit code 0 means no mismatch, 1 means at least one, and 2 means the database could not be read (only the error class is printed). The restore drill runs it on a restored copy, which is the usual way to check a deployed database without connecting a shell to it.

### Backup/restore drill

```bash
gh workflow run db-restore-drill.yml --repo Zero-State-LLC/Patch-Hive --ref main -f env=staging
gh workflow run db-restore-drill.yml --repo Zero-State-LLC/Patch-Hive --ref main -f env=prod -f confirm_production="dump production read-only"
```

1. A gate job with no secrets refuses `env=prod` unless `confirm_production` is exactly `dump production read-only`. The `production` environment's own protection rules still apply.
2. Counts every public table on the source (read-only) and reads its Postgres major version.
3. `pg_dump --format=custom` of the source, with the client of that major version. The dump stays on the runner: only its size and sha256 are recorded, and it is deleted after the restore.
4. Counts the source again, then `pg_restore --exit-on-error --single-transaction` into a Postgres container of the same major version on the runner.
5. `alembic current` on the restored copy must equal this checkout's head. Dispatch from the ref the database was last migrated from (`db-migrate.yml`), or this step fails.
6. `python -m canon.reconcile_all` on the restored copy must report no mismatch.
7. The receipt compares restored row counts with the source. They must match table for table when the source did not change during the dump; if it did, the comparison is marked not conclusive, and every table must still exist.

Receipt: artifact `restore-drill-receipt-<env>` (`receipt.json`: dump size and sha256, alembic head and current, per-table counts, reconcile counts, and `result`).

## Failure recovery

- A terminal export failure creates one immutable reversal keyed to the export and changes the mutable export state to refunded.
- Repeated export requests return the existing idempotent export and do not debit again.
- Replayed Stripe events with identical payloads are no-ops; a payload mismatch for the same event ID is rejected.
- Generation never overwrites a prior run; retry orchestration must create or resume an explicit job and preserve receipts.
- Page compilation retries must reuse the same normalized input identity and may not create conflicting accepted page artifacts.
- A PageFitReport failure remains attached to the failed export diagnostics and is never rewritten into a pass.
- Prefer `/api/canon/*` for new export/credit clients; treat legacy `/api/export` as transitional until CONTINUATION P1 completes.

## CI authority

| Workflow | Role |
|----------|------|
| `ci.yml` | PostgreSQL 15: backend and acceptance suites; Ruff, Black, mypy; ESLint, tsc, Vitest, build, Playwright |
| `codeql.yml` | CodeQL for Python and JavaScript |
| `security.yml` | pip-audit, npm audit, Bandit, Gitleaks, CycloneDX SBOMs |

No workflow deploys the application or activates production payments.

Patch-book implementation must add contract/property coverage, representative golden fixtures, SVG structural regression, rendered visual regression, and PDF/manifest page-count verification before production export is enabled.

## Deploy targets (inventory only)

Historical packaging exists for Render, Azure, Docker Compose, Fly/Railway snippets, and Replit export. None are certified “production ready” by this document without a fresh gate pass on the post-merge SHA. Ignore root `DEPLOY_STATUS.md` (2025-11) as ship authority.