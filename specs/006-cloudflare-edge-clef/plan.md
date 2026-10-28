# Implementation plan — 006 Cloudflare Edge + Clef

## Architecture

Workers static assets (Vite, `patch-hive.com`) → `api.patch-hive.com` (Containers Worker `edge/api`) → FastAPI container  
FastAPI container → Neon staging (pooled endpoint, TLS). Hyperdrive does not apply to container clients.  
Workers AI Clef → ClefProvider adapter → Spec 005 DecisionPolicy → confirmation UI

## Phases

### WP-00 Spec tree
Create feature directory and index entry. No bulk moves.

### WP-01 Frontend edge
Cloudflare Pages project. Build: `cd frontend && npm ci && npm run build`. Output: `frontend/dist`. Attach custom domain. Set `VITE_API_BASE_URL`.

### WP-02 API surface
`edge/api` Worker on `api.patch-hive.com` proxies to one container built from `backend/Dockerfile`. CORS is exactly `https://patch-hive.com`. `ALLOW_PRODUCTION_PAYMENTS=false`, `STRIPE_TEST_MODE=true`. Verify `/health/ready` through the edge.

### WP-03 Data plane
Neon staging branch, pooled connection string as the `edge/api` `DATABASE_URL` secret. Alembic runs on container start. No schema change.

### WP-03b Durable files
Evidence uploads, exports and design packs move from the container's local disk to R2 (T055) before the API is deployed. The container disk is temporary.

### WP-04 Clef adapter
Implement ClefProvider. Map System One response to DecisionPacket. Feature flag default off. Fail-closed. No type leakage.

### WP-05 State machines
Implement the three machines defined in tasks.md as pure transition tables.

### WP-06 Evaluation
Extend harness with labeled corpus. Pin receipt SHA. Operator sets thresholds.

### WP-07 Gates
Re-run STAGING_HOST_PLAN. Update DOMAIN_CUTOVER_CHECKLIST with receipts. Only then BETA_READY.

## Risks

- CORS origin mismatch blocks frontend.
- Containers chosen (2026-10-26). One instance (`max_instances: 1`); the container sleeps after 15 minutes idle, so the first request after that pays a cold start (image boot). Startup migrations are off on both Workers (2026-10-28); databases are migrated by the `db-migrate.yml` workflow.
- 2026-10-27: the account creates only `durable_object` scheduling-policy container applications, so `edge/api/src/index.ts` is its own Durable Object (no `@cloudflare/containers` helper). It starts the `api` image on `standard-1`, waits for `/health`, and proxies; one Durable Object (`primary`) still means one container, and the 15-minute idle stop is `setInactivityTimeout`.
- Container disks are ephemeral. `backend/core/storage.py` mirrors durable files to R2 and restores them on read (T055a); T040b (deploy) still depends on T055b, the bucket and its secrets.
- Clef vision cost/latency; flag stays off until evaluation.
- Frontend hosting moved from Pages to Workers in PR #55; FR-001 and T030 still name Pages and need an operator decision.

## Constitution check

| Principle | How this feature complies |
| --- | --- |
| 4 Probabilistic systems propose | Clef never leaves CLASSIFYING; disposition is the Spec 005 policy. |
| 7 Providers are replaceable adapters | Clef types stay inside `intelligence/clef_provider.py`. |
| 9 Fail closed | Timeout, malformed, unavailable, and disabled all map to explicit errors with no receipt. |
| Authority boundary | `canon_write_permitted` only in CONFIRMED via the existing confirmation path. |

Gap: the constitution's chain also asks for journeys, workflows, contracts, security, and rollback. This feature records them only in DEPLOY_NOTES.md.
