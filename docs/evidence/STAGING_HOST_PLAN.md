# Named staging host plan

## Decision, 2026-10-27

The owner delegated this choice ("you can handle"). Chosen: **E. Cloudflare Workers, a
second pair beside production**, superseding the A to D options below and the 2026-10-26
note that put the public API on the Neon staging branch.

| | Production | Staging |
| --- | --- | --- |
| Frontend | `https://patch-hive.com` | `https://staging.patch-hive.com` (`noindex`) |
| API | `https://api.patch-hive.com` | `https://api-staging.patch-hive.com` |
| `ENVIRONMENT` | `production` | `staging` |
| Database | Neon `main` (`PATCHHIVE_DATABASE_URL_PROD`) | Neon `staging` (`PATCHHIVE_DATABASE_URL_STAGING`) |
| R2 | `patchhive-prod-files` / `prod` | `patchhive-staging-files` / `staging` |
| Feature flags | none; every flag at its default (off) | set in `edge/api/wrangler.jsonc` `env.staging.vars` |

Why:

- Spec 007 enablement refuses unless the target is `staging` with no production traffic,
  and the 008 walkthrough seeds demo accounts into its target database. Neither can hold on
  the public host, so the public host has to be production.
- The prod catalog load (003 T027) only matters if a host reads Neon `main`.
- With `ENVIRONMENT=staging` on the public host, hosted-only safeguards (the Stripe webhook
  secret, placeholder `SECRET_KEY`) were weaker there than they should be.
- Same platform as production, so a staging pass says something about production.

Config: `edge/api/wrangler.jsonc` (`env.staging`), `edge/api/src/index.ts` (forwards
feature flags and provider credentials only outside production),
`frontend/wrangler.jsonc` (`env.staging`), `frontend/.env.staging`
(`npm run build:staging`).

Operator steps (none of them done yet):

1. Create the R2 bucket `patchhive-prod-files` (staging already has `patchhive-staging-files`).
2. Production API secrets: `DATABASE_URL` = Neon `main` pooled endpoint, `SECRET_KEY` (32+
   random bytes), the R2 S3 values; `STRIPE_WEBHOOK_SECRET` when Stripe is wired.
3. Staging API secrets: the same names with `--env staging`, `DATABASE_URL` = Neon
   `staging` pooled endpoint, and a different `SECRET_KEY`.
4. Deploy `edge/api` twice (`npx wrangler deploy`, then `--env staging`) and the frontend
   twice (`npm run build && npx wrangler deploy`; `npm run build:staging && npx wrangler deploy --env staging`).
5. Run `db-migrate.yml` for each target before its API serves traffic.

The rest of this file is the earlier plan, kept for the record.

**Date:** 2026-07-21  
**Baseline main:** `7727908` (post PR #82 legacy_pipeline unit migration)  
**Authority:** ops design + local Compose OBSERVED; **no cloud host provisioned in this pass**  
**Payments:** `ALLOW_PRODUCTION_PAYMENTS=false` always on staging  

## Intent

Define how to stand up a **named non-prod** environment (URL + secrets + Postgres) without claiming production readiness. Local Compose drill already PASSed ([STAGING_COMPOSE_RECEIPT.md](STAGING_COMPOSE_RECEIPT.md)).

## Host options (operator pick required)

| Option | Pros | Cons | When to pick |
|--------|------|------|--------------|
| **A. Compose on operator VPS** | Closest to monorepo; cheap; uses `docker-compose.staging.yml` | Operator owns TLS/DNS/backups | Default if you already run Docker hosts |
| **B. Render** | Existing `docs/RENDER_DOCKER.md` path | Free tier sleeps; env drift | Quick public URL |
| **C. Fly.io / Railway** | Snippets present | Less documented here | If team already uses Fly/Railway |
| **D. Azure** | Full template docs | Heaviest; overkill for staging | Enterprise only |

**Default recommendation (SPECULATIVE until operator confirms):** **A — Compose on a private VPS** named `staging.patchhive.<operator-domain>` (or private IP only).

## Required secrets (staging)

| Variable | Staging rule |
|----------|----------------|
| `DATABASE_URL` | Managed Postgres 15 or Compose `db` |
| `SECRET_KEY` | ≥32 random bytes; **not** dev default |
| `CORS_ORIGINS` | Exact frontend origin(s) |
| `STRIPE_TEST_MODE` | `true` |
| `ALLOW_PRODUCTION_PAYMENTS` | `false` |
| All `ENABLE_LEGACY_*` | `false` |
| `ENABLE_LEGACY_PATCHBOOK_DEBIT` | `false` |
| Vision cloud keys | **omit** (mock only) |

## Gate checklist (before sharing staging URL)

Copy of [OPERATIONS.md](../OPERATIONS.md) release gates, plus:

1. [ ] `alembic current` == `20260726_module_registry_slugs (head)` (re-check on SHA)  
2. [ ] `GET /health` → liveness healthy; `GET /health/ready` → `database: ok`  
3. [x] Acceptance suite against staging Postgres: `scripts/staging/acceptance.ps1` → [STAGING_ACCEPTANCE_RECEIPT_20260726.md](STAGING_ACCEPTANCE_RECEIPT_20260726.md) (local compose; re-run on named host)
4. [ ] Ledger reconcile / no double-debit smoke  
5. [ ] Manual a11y protocol ([ACCESSIBILITY.md](../ACCESSIBILITY.md))  
6. [ ] Backup/restore drill of staging DB (record receipt) — local: `scripts/staging/smoke.ps1` / `smoke.sh`  
7. [ ] No production payment keys present  

## Local staging-like Compose (this repo)

```bash
# Automated smoke (recommended): health + alembic head + pg_dump/restore drill
powershell -File scripts/staging/smoke.ps1   # Windows
# bash scripts/staging/smoke.sh              # Linux/macOS

# Manual:
docker compose -f docker-compose.staging.yml up -d --build
curl -sf http://localhost:8000/health/ready
docker compose -f docker-compose.staging.yml exec -T backend python -m alembic current
```

If host `:8000` is busy, use `STAGING_API_PORT` / `STAGING_FE_PORT` / `STAGING_PUBLIC_API_URL` / `STAGING_CORS_ORIGINS` (smoke scripts default to 18000/15173).

Class: **local OBSERVED** when run on a laptop — still **not** a named multi-tenant host.

## Status (this campaign)

| Claim | Status |
|-------|--------|
| Local Compose db+backend healthy | **PASS** — [BETA_STAGING_MIGRATIONS_HEALTH_RECEIPT_20260726.md](BETA_STAGING_MIGRATIONS_HEALTH_RECEIPT_20260726.md) |
| Alembic-on-deploy + DB wait entrypoint | **PASS** (#142, #144) |
| `docker-compose.staging.yml` checked in | **DONE** |
| Local Docker staging stack (db+backend+FE) | **PASS** — smoke scripts + prior receipts |
| Backup/restore local drill | **PASS** when `scripts/staging/smoke.*` completes |
| Operator-chosen public/private hostname | **DECIDED 2026-10-27**: `staging.patch-hive.com` / `api-staging.patch-hive.com` (see Decision above); not deployed |
| Production deploy | **NOT_PERFORMED** |

## Operator action required

Decided 2026-10-27 (see the top of this file). Agents still must not invent cloud credentials or claim staging is live until the operator steps there are done and receipted.
