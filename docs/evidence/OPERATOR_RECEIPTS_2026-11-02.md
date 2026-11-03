# Operator task receipts, 2026-11-02

Decision: spec 006 OQ-3 `record_receipts_and_close` (docs/evidence/JEV_DECISIONS_2026-11-01.md).
Follows `006_OPERATOR_TASK_RECEIPTS_2026-11-01.md`, which closed 006 T030 and T050b (#190).
Method: read-only. Plain GETs to the public API hosts, `gh run view` of runs recorded in
`CURRENT_STATE.md`, and files in this tree. No login, no Cloudflare or Neon API call, no write to
any bucket or database, no secret read.

Result: no task closes. Each one still lacks evidence its acceptance line requires.

## Observations (2026-11-02 21:53 UTC)

| Probe | Result |
| --- | --- |
| `GET https://api-staging.patch-hive.com/health/ready` | HTTP 200 `{"status":"healthy","app":"PatchHive","version":"0.3.0-alpha.5","abx_core_version":"1.3","database":"ok"}` |
| `GET https://api-staging.patch-hive.com/health` | HTTP 200, same without `database` |
| `GET https://api.patch-hive.com/health/ready` | HTTP 200, same body as staging (`database: ok`) |
| `GET https://api.patch-hive.com/health` | HTTP 200, same without `database` |
| Staging migrate run [41424675176](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/41424675176) | `success`, `ee5326e`, 2026-11-02 09:56Z; log: `20261030_power_configs -> 20261101_user_deleted_at`, then `20261101_user_deleted_at (head)` |
| Production migrate run [41428760962](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/41428760962) | `success`, `ee5326e`, 2026-11-02 10:25Z; same upgrade and head |
| `db-load.yml` runs | 8 most recent all `success`, 2026-11-02 00:09Z to 02:57Z: 41365598102, 41365938520 (`5b46781`); 41375941276, 41377269417, 41377653481, 41379966451, 41380197542, 41380460510 (`ada8949`) |
| Deployed versions (`CURRENT_STATE.md`) | both hosts run `ee5326e`: staging API Worker `6a957dfb`, frontend `9259b090`; production API `ae714896`, frontend `289a7544`. `/health` reports 0.3.0-alpha.5 because release PR #169 is not merged |
| R2 buckets (`OWNER_ACTIONS_2026-11-02.md` §4) | `patchhive-prod-files` and `patchhive-staging-files` exist (created 2026-10-28), from a read-only bucket listing; not re-checked here |
| Readiness placeholders | `PENDING_OPERATOR_WALKTHROUGH` still in `PRODUCTION_READINESS_MATRIX.md` (4 fields) and `DOMAIN_CUTOVER_CHECKLIST.md` |
| Walkthrough or seed-auth receipt | none in `docs/evidence/` |

## Per task

- **006 T055b OPEN.** Evidenced: both buckets exist; the Worker starts the container only with
  every R2 secret set (`edge/api/src/index.ts` `REQUIRED_SECRETS`), and both hosts serve. Missing:
  the T055 acceptance, that an evidence image, an export and a design pack survive a container
  restart. Needs the operator: upload through the staging API, let the container sleep or redeploy,
  fetch the same object back (OWNER_ACTIONS §4). Token scope to the two buckets is also not shown.
- **006 T040b OPEN.** Evidenced: deployed, and `/health/ready` through the edge is 200 with
  `database: ok` on both hostnames. Its R2 secrets are only proven once T055b closes.
- **008 T030b OPEN.** Missing: the `aligned=True` seed-auth line from `check_seed_auth` on the
  staging database. That needs the staging `DATABASE_URL` and the seeded demo login, which this
  read-only pass does not use. The walkthrough prints it (OWNER_ACTIONS Item 4).
- **008 T050b OPEN.** Missing: the walkthrough receipt (008 T040b, not run) and the signed Spec 007
  receipt (007 T060b, open). The placeholders above are unchanged.
