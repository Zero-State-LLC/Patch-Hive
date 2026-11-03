# PatchBook Design Engine — staging enablement (hosted and local)

**Status:** operational runbook  
**Related:** `docs/FEATURE_FLAGS.md`, `docs/design/PATCHBOOK_DESIGN_ENGINE.md`

## Goal

Turn on Design Engine export fulfillment and Style Studio against **local Docker staging** without enabling production payments.

## Hosted staging (Cloudflare, since 2026-11-03)

The hosted staging pair (`staging.patch-hive.com`, `api-staging.patch-hive.com`) runs with the Design Engine on:

- The flags live in `edge/api/wrangler.jsonc` under `env.staging.vars` (#213): `ENABLE_PATCHBOOK_DESIGN_ENGINE`, `ENABLE_CANON_EXPORT_FULFILLMENT` and `ENABLE_INLINE_EXPORT_FULFILLMENT` are `true`, and `ENABLE_PATCHBOOK_PUBLICATION_PROFILE` is `false`.
- `edge/api/src/index.ts` forwards only the names in its `FLAG_VARS` list, and production sets none.
- Payments stay test-only (`STRIPE_TEST_MODE=true`, `ALLOW_PRODUCTION_PAYMENTS=false`).

To deploy, run `cd edge/api && npx wrangler deploy --env staging` from a checkout of `main`.

To verify, dispatch `.github/workflows/staging-walkthrough.yml`. It seeds per-run demo users, runs `scripts/staging/design_engine_walkthrough.py` against `api-staging.patch-hive.com`, reads the server's flags from `GET /api/admin/ops/runtime-flags`, and keeps the receipt. The first pass was on 2026-11-03 (run 41557808902, #216).

The local Docker path below remains for development.

## Automated walkthrough (recommended)

```powershell
# Flags via overlay + seed + preview + export (test payments only)
powershell -File scripts/staging/design-engine.ps1
```

Compose overlay: `docker-compose.staging.design-engine.yml`  
Receipt: [../evidence/DESIGN_ENGINE_STAGING_ENABLEMENT_RECEIPT_20260726.md](../evidence/DESIGN_ENGINE_STAGING_ENABLEMENT_RECEIPT_20260726.md)

## Required flags (backend)

Add to `.env.staging.local` (or compose `environment:` / design-engine overlay):

```bash
ENABLE_PATCHBOOK_DESIGN_ENGINE=true
ENABLE_CANON_EXPORT_FULFILLMENT=true
ENABLE_INLINE_EXPORT_FULFILLMENT=true
# Artistic / dual-artifact publication (optional)
ENABLE_PATCHBOOK_PUBLICATION_PROFILE=false
REQUIRE_SEALED_GENERATED_PATCHES=false
DESIGN_ENGINE_DEFAULT_TIER=core
PREVIEW_RATE_LIMIT_PER_MINUTE=30
EXPORT_STORE_ROOT=/app/exports
```

`ENABLE_INLINE_EXPORT_FULFILLMENT=true` is recommended for local staging so debits leave `queued` and return a pack in the same request.

## Migration

```bash
cd backend
alembic upgrade head
# head includes:
#   20260721_design_engine
#   20260721_user_style_recipes
```

## Walkthrough

1. Sign in on `http://localhost:5173`
2. Open a rig → confirm inventory → generate patches
3. **Exports** tab → **Open Style Studio**
4. Adjust weights / influences → **Preview (free)**
5. Optionally **Save recipe** (server library when signed in)
6. **Export with recipe** — status should become `succeeded` when fulfillment flags are on
7. Pack files land under `EXPORT_STORE_ROOT/design_packs/<export_id>/`

## API surface (new)

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/canon/style-recipes` | Owner library |
| `POST` | `/api/canon/style-recipes` | Create (max 40); optional `is_shared` |
| `GET/PATCH/DELETE` | `/api/canon/style-recipes/{id}` | Owner CRUD |
| `GET` | `/api/canon/style-recipes/shared/{id}` | Any authenticated user if `is_shared` |
| `POST` | `/api/canon/exports/preview` | Free; accepts `style_recipe` **or** `style_recipe_id` |
| `POST` | `/api/canon/exports` | Debit; same recipe fields; seals snapshot |
| `POST` | `/api/canon/exports/{id}/download-token` | Short-lived token (requires `succeeded` when fulfillment on) |
| `GET` | `/api/canon/exports/{id}/artifacts/{pdf\|zip\|companion\|manifest}?token=` | Stream pack files |

Do not send both `style_recipe` and `style_recipe_id` (400 `STYLE_RECIPE_SOURCE_CONFLICT`).

## Safety

- Production payments remain off unless separately reviewed (`ALLOW_PRODUCTION_PAYMENTS`)
- Legacy patchbook debit stays 410 by default
- Canonical content is never mutated by styling
