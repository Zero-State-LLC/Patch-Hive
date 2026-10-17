# DEPLOY_STATUS (historical)

**Superseded (2026-07-20).**

The 2025-11 “Ready for Render” claim on an old Claude branch is **not** ship authority for the canon MVP.

- No production deploy was performed during PR #47.
- Payments remain test-mode only (`STRIPE_TEST_MODE=true`, `ALLOW_PRODUCTION_PAYMENTS=false`).
- Release gates → [docs/OPERATIONS.md](docs/OPERATIONS.md)
- Next ops work → [docs/CONTINUATION.md](docs/CONTINUATION.md) P0–P3

## Database (Neon, provisioned 2026-10-16)

OBSERVED:

- Provider: Neon, project `patchhive` (id `polished-night-86976142`), region `aws-us-west-2`, Postgres 15, database `patchhive`.
- Branches: `main` is **prod** (default); `staging` was branched from `main`.
- Compute: 0.25 CU fixed, scale-to-zero after 5 min.
- Hard project quota (the project suspends instead of overbilling): `compute_time_seconds` 180000 (about 50 CU-hours per month) and `logical_size_bytes` 1 GiB. The org is on the Neon Launch plan (usage-billed).
- Connection strings: GitHub Actions secrets `PATCHHIVE_DATABASE_URL_STAGING` and `PATCHHIVE_DATABASE_URL_PROD`. Never commit them.
- Migrations: run the manual workflow `.github/workflows/db-migrate.yml` (choose `staging` or `prod`). The agent box cannot reach Postgres port 5432 directly.
- Data: the schema only. The catalog load waits for the new importer PR and an operator yes.
