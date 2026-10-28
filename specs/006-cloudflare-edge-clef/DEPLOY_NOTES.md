# Spec 006 Deploy Notes (Cloudflare Edge + Clef)

Status: code for T010, T020, T060, T070, T080, T090 is implemented and tested in-repo.
T030 is PARTIAL (frontend live; the `VITE_API_BASE_URL` build value is in `frontend/.env.production`
and ships on the next frontend deploy). T040a and T050a (code) are done; T040b and T050b are the
operator steps below. Cloudflare config in this repository: `frontend/wrangler.jsonc` and
`edge/api/wrangler.jsonc`. They name the operator-chosen hostnames; no account ids or secrets are
recorded here.

## Operator-locked decisions

Recorded 2026-10-26:

- Frontend origin: `https://patch-hive.com` (`www` redirects to it).
- API hostname: `api.patch-hive.com`.
- API origin: Cloudflare Containers (`edge/api`), not Tunnel.
- Database: Neon staging branch, pooled endpoint, connected directly from the container (FR-003 amendment approved 2026-10-26).

Superseded 2026-10-27 (owner delegated the staging decision; see
`docs/evidence/STAGING_HOST_PLAN.md`): the public pair is production and a second pair is staging.

| | Production | Staging |
| --- | --- | --- |
| Frontend | `patch-hive.com` (`patchhive-frontend`) | `staging.patch-hive.com` (`patchhive-frontend-staging`) |
| API | `api.patch-hive.com` (`patchhive-api`) | `api-staging.patch-hive.com` (`patchhive-api-staging`) |
| `ENVIRONMENT` | `production` | `staging` |
| Database | Neon `main` (pooled) | Neon `staging` (pooled) |
| R2 | `patchhive-prod-files`, prefix `prod` | `patchhive-staging-files`, prefix `staging` |
| Feature flags | none forwarded; all default off | set in `env.staging.vars` for 007/008 drills |
| Deploy | `npx wrangler deploy` | `npx wrangler deploy --env staging` |

Secrets are per Worker: repeat each `wrangler secret put` with `--env staging` for staging.
The manual workflow `.github/workflows/edge-secrets.yml` (input `staging` or `production`)
writes `DATABASE_URL` (Neon pooled, from the repo secret), the R2 S3 keys (from a
bucket-scoped token it creates, revoking the previous one) and, if missing, `SECRET_KEY`,
without printing any of them. It needs the repo secret `CLOUDFLARE_API_TOKEN` (Account API
Tokens: Edit, Workers Scripts: Edit) and the repo variable `CLOUDFLARE_ACCOUNT_ID`.
The readiness machine and FR-003 describe the staging pair.

Still owned by the operator and NOT set in code or config:

- Cloudflare account id and the Workers AI API token used by Clef.
- The `edge/api` secrets `DATABASE_URL` and `SECRET_KEY`.

Until the operator records them, `config_gate_checks(..., expected_frontend_origin=None)`
reports `CORS_EXACT_ORIGIN` as failed with `OPERATOR_LOCKED`, so the readiness machine
cannot reach GATES_PASSED from config alone.

## Deferred tasks

| Task | Action | Status | Repo scaffolding |
| --- | --- | --- | --- |
| T030 | Cloudflare edge deploy for the Vite frontend | PARTIAL, API base pending T040 | `frontend/wrangler.jsonc` (Workers static assets); `VITE_API_BASE_URL` documented in `.env.example` (read by `frontend/src/lib/api.ts`) |
| T040 | Publish API hostname and restrict CORS to the exact origin | T040a done; T040b operator | `edge/api/` (Containers Worker); `CORS_ORIGINS` exact-origin gate in `backend/core/ops/edge_readiness.py` |
| T050 | Provision the Neon staging database for the API container | T050a done; T050b operator | `edge/api/src/index.ts` passes `DATABASE_URL`/`SECRET_KEY` and fails closed without them |

T060 lists T050 as a dependency. The T060 code path is implemented and tested against the
existing database layer and does not change persistence.

### T030 checklist (operator)

Shipped on Workers static assets instead of Pages (Cloudflare's current recommendation for
static sites): `npx wrangler deploy` from `frontend/` uploads `dist` with SPA fallback, and a
minimal `frontend/worker/index.ts` 301s `www` to the apex.

1. Create the edge project from `frontend/` (build `npm run build`, output `dist`). DONE: Worker `patchhive-frontend`.
2. Set `VITE_API_BASE_URL` to the operator-locked API hostname plus `/api`. CODE DONE: `frontend/.env.production` sets `https://api.patch-hive.com/api` for `vite build`; redeploy the frontend to ship it.
3. Attach the operator-locked custom domain. DONE: `patch-hive.com` (custom domain), `www.patch-hive.com` redirects to it; the shared `workers.dev` route is disabled.
4. Record the build receipt (commit SHA, deployment id) as a checklist receipt.

Receipt, 2026-10-26: built from `7a7791f`, Worker version `23639333-97bc-490d-bf11-8ae6ecfff132`.
Production bundle verified free of demo credentials and seed-file hints. Redeploy after
step 2 and append a new receipt line.

### Durable files (T055)

The container's disk is wiped when it sleeps (15 minutes idle), restarts or redeploys. The
backend writes evidence uploads, PatchBook exports and design packs under `export_dir` /
`export_store_root` and stores those local paths in Postgres. With `STORAGE_BACKEND=s3`
(set in `edge/api/wrangler.jsonc`), `backend/core/storage.py` copies each durable file to R2
when it is written, restores a missing local copy from R2 before it is read, and deletes both
copies together. Paths and schema are unchanged. A file that cannot be persisted is not
recorded: an evidence upload is rejected for that file, a design pack fails and is
compensated, and the legacy PatchBook run export returns 503 before any credit is spent.
On-demand patch and rack PDFs are generated per request and stay on the scratch disk.
Legacy publishing (`enable_legacy_publishing`, off by default) is not covered.

T040b depends on T055b in `tasks.md`.

### T055b checklist (operator, before T040b)

1. Create the R2 bucket `patchhive-staging-files` (name set in `edge/api/wrangler.jsonc`).
2. Create an R2 API token with **Object Read & Write** scoped to that bucket only.
3. From `edge/api/`, store the S3 API values as Worker secrets (never in git):
   `npx wrangler secret put S3_ENDPOINT_URL` (`https://<account-id>.r2.cloudflarestorage.com`),
   `npx wrangler secret put S3_ACCESS_KEY_ID`, `npx wrangler secret put S3_SECRET_ACCESS_KEY`.
   The Worker answers 503 without starting the container until all five secrets exist.

### T050b checklist (operator, before T040b)

1. Create the Neon project and a `staging` branch. Copy the **pooled** connection string and make
   sure it ends in `?sslmode=require`.
2. From `edge/api/`, store it as a Worker secret (never in git): `npx wrangler secret put DATABASE_URL`.
3. Store a fresh signing key the same way: `npx wrangler secret put SECRET_KEY`
   (for example the output of `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`).
4. Migrations run on the container's first start (`alembic upgrade head`); no D1 and no new schema.

### T040b checklist (operator)

1. Containers need the Workers Paid plan on the account; confirm it is active.
2. From `edge/api/` with Docker running: `npm ci && npx wrangler deploy`. This builds
   `backend/Dockerfile`, pushes the image, and attaches `api.patch-hive.com`.
3. Confirm `ALLOW_PRODUCTION_PAYMENTS=false` and `STRIPE_TEST_MODE=true` (set in `edge/api/wrangler.jsonc`).
4. `curl https://api.patch-hive.com/health/ready` returns OK (the first call pays a cold start).
5. Redeploy the frontend so it picks up `frontend/.env.production`, then record both receipts here.

## Clef provider configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `ENABLE_DECISION_INTELLIGENCE` | `false` | Spec 005 master flag; route returns 409 when off |
| `DECISION_PROVIDER` | `disabled` | `disabled`, `jev`, or `clef` |
| `ENABLE_CLEF_PROVIDER` | `false` | Clef feature flag; DEFAULT OFF |
| `CLEF_MODEL` | `clef` | `clef` or `clef-flash` |
| `CLOUDFLARE_ACCOUNT_ID` | empty | operator secret |
| `CLOUDFLARE_AI_API_TOKEN` | empty | operator secret |
| `CLEF_BASE_URL` | `https://api.cloudflare.com/client/v4` | Workers AI REST base |
| `CLEF_TIMEOUT_SECONDS` | `10` | bounded request timeout |

Fail-closed behavior:

- With `DECISION_PROVIDER=clef` and `ENABLE_CLEF_PROVIDER=false`, the adapter is constructed
  inert. Every call fails with `CLEF_DISABLED` (HTTP 409) before any network call or image load.
- Timeouts map to `CLEF_TIMEOUT` (HTTP 504). Transport and HTTP errors map to
  `CLEF_UNAVAILABLE` (HTTP 502). Schema or candidate violations map to `CLEF_MALFORMED` (502).
- In the Spec 006 guarded flow, a provider failure moves the resolution machine to REJECT and
  writes NO decision receipt. The Spec 005 `resolve_module_identity` path is unchanged.
- Vision input: when the flag is on, the route passes a `BoundEvidenceImageLoader`
  (`intelligence/evidence_images.py`) for the image asset bound to the evidence record. It
  reuses the existing gates: `consent_provider_processing` must be true, and the asset must not
  be soft-deleted or past `retention_expires_at` (same predicate as `evidence/retention.py`).
  A denied or missing asset degrades to a text-only request without reading the file. A cleared
  asset is read only from inside the evidence storage root and must match `content_sha256`;
  any load failure fails closed as `CLEF_UNAVAILABLE` (REJECT, no receipt, no network call).
  The loader is not constructed with the flag off. Image bytes never enter packets, receipts,
  or telemetry.
- Disposition is always computed by the Spec 005 `DecisionPolicy`; Clef only supplies a
  `DecisionPacket`. Clef request and response types stay inside `intelligence/clef_provider.py`.
- Canonical inventory is never written by this path. `canon_write_permitted` is true only in
  CONFIRMED, which requires the existing user confirmation path.

## Edge readiness machine

`backend/core/ops/edge_readiness.py` models the deployment states in order and only allows
GATES_PASSED -> BETA_READY with explicit operator approval and checklist receipts. Invariants
re-checked at the gate and at approval:

- `ALLOW_PRODUCTION_PAYMENTS=false` (no live payments; `live_payments_permitted` is always false)
- no D1 binding and no D1 schema migration (`d1_permitted` is always false)
- Clef flag default off, and enabled only with credentials present
- a pinned Clef evaluation receipt SHA-256 (from `intelligence/clef_evaluation.py`)

## Evaluation harness (T080)

`intelligence/clef_evaluation.py` loads a labeled JSONL corpus that must contain both text and
vision cases, computes overall and per-modality metrics, and builds a pinned receipt
(`patchhive.clef-eval-receipt.v1`) whose SHA-256 is verified with `verify_pinned_receipt`.
Receipts are never auto-approved: the best status is `THRESHOLDS_MET_PENDING_OPERATOR`.
Operator thresholds are explicit; `false_canonicalization_max` is fixed at 0.
`intelligence/clef_telemetry.py` separates PROVIDER_FAILURE from LOW_CONFIDENCE and carries no
evidence, labels, images, or payloads.

A live Clef evaluation run against Workers AI is an operator action and is not performed in CI.
