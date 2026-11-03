# Spec 006 operator task receipts, 2026-11-01

Decision: spec 006 OQ-3 `record_receipts_and_close` (docs/evidence/JEV_DECISIONS_2026-11-01.md).
Method: read-only. Plain GETs to the public hosts, `gh run` for workflow history, and files in this
tree. No Cloudflare or Neon API call, no login, no write to any bucket or database.

## Observations (2026-11-02 06:35 UTC)

| Probe | Result |
| --- | --- |
| `GET https://api-staging.patch-hive.com/health/ready` | HTTP 200 `{"status":"healthy","app":"PatchHive","version":"0.3.0-alpha.5","abx_core_version":"1.3","database":"ok"}` |
| `GET https://api.patch-hive.com/health/ready` | HTTP 200, same body (`database: ok`) |
| `https://staging.patch-hive.com/` | HTTP 200, `server: cloudflare`, CSP `connect-src` names `https://api-staging.patch-hive.com`; bundle `assets/index-ubZcDQYj.js` embeds `https://api-staging.patch-hive.com/api` |
| `https://patch-hive.com/` | HTTP 200, `server: cloudflare`, CSP `connect-src` names `https://api.patch-hive.com`; bundle `assets/index-DsoYOw34.js` embeds `https://api.patch-hive.com/api` |
| `gh run list --workflow db-migrate.yml` | 10 most recent runs all `success`, 2026-10-28 to 2026-10-30. Latest: 41043042378 (10:45Z) and 41041862162 (10:35Z), both on `9dbb5ba`, both ran `alembic upgrade head` (`20261030_catalog_hp_source -> 20261030_power_configs`). The logs do not print the target; CURRENT_STATE.md states staging and prod were both migrated 2026-10-30. |
| `edge/api/wrangler.jsonc` | R2 buckets `patchhive-prod-files` (prod) and `patchhive-staging-files` (staging), `STORAGE_BACKEND=s3`; `ALLOW_PRODUCTION_PAYMENTS=false`, `STRIPE_TEST_MODE=true` in both |
| `edge/api/src/index.ts` | `REQUIRED_SECRETS` (DATABASE_URL, SECRET_KEY, S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY) are checked before the container starts; a missing one gives 503 |

## Per task

- **T030 CLOSED (superseded).** Spec 006 amendment 2026-10-29 reads "Pages" as the Workers static-assets frontend (PR #55, merged 2026-10-27). Acceptance is met on both hosts: build deployed, custom domains serve 200 over Cloudflare, `VITE_API_BASE_URL` is baked into each bundle with the matching API host.
- **T050b CLOSED.** Staging `/health/ready` reports `database: ok` through the Worker, which answers 503 without `DATABASE_URL`; `db-migrate.yml` runs succeeded through head `20261030_power_configs`.
- **T040b OPEN.** The deploy and `/health/ready` through the edge are evidenced for both hostnames, but the task also covers the R2 secrets and depends on T055b.
- **T055b OPEN.** Evidenced: the Worker only starts the container when all R2 secrets exist, and it is serving. Not evidenced read-only: that the buckets `patchhive-staging-files` and `patchhive-prod-files` exist, that the token is scoped to them, and the T055 acceptance (an evidence image, an export and a design pack surviving a container restart). Needs the operator: list the buckets, or upload through the staging API, restart the container, and fetch the same object back.
