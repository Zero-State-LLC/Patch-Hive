# Intent

## Problem

008 T030b/T040b and 006 T060b are operator runs against the staging API. They need the Neon staging connection string and two demo passwords in a shell, and staging does not set the Design Engine flags, so the walkthrough would refuse (`FLAGS_*`). The owner approved running these checks on `api-staging.patch-hive.com` (2026-11-02, in chat).

## Proposed outcome

- `edge/api/wrangler.jsonc` sets, for staging only, the four flags the local overlay uses: Design Engine, canon export fulfillment and inline fulfillment on, publication profile off. Payments stay test-only; `src/index.ts` forwards flags only outside production.
- `.github/workflows/staging-walkthrough.yml` (manual, staging environment only) seeds the golden demo with the existing `PATCHHIVE_DATABASE_URL_STAGING` secret, runs `design_engine_walkthrough.py`, then `evidence_resolution_check.py`, and keeps both receipts as an artifact. Demo passwords are generated per run, masked, and never stored; the seeder's printed password is stripped.
- `scripts/staging/evidence_resolution_check.py` signs in as the demo user, uploads one PNG it generates, reads the evidence id from the candidates listing and calls decision-resolution twice with one key. A fail-closed 409 (no provider enabled) or a 200 with the same decision twice passes.

Out of scope: enabling a decision provider on staging, production, closing tasks before the receipts exist.

## Affected users / systems

Staging API and Neon staging branch (demo users, a rack, runs, credits, exports, one evidence image, R2 staging bucket). Production is untouched: the workflow has no production target and the check refuses any API other than `api-staging.`.

## Constraints / non-goals

Test payments only. No secret in the repo, logs or receipts. No third-party image is sent to a provider.

## Open questions

- Whether the deployed staging container accepts the walkthrough on the first run (UNKNOWN until run).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| `Settings()` loads with `ENVIRONMENT=staging` and a hosted URL | `OBSERVED` | local check |
| The check passes on a fail-closed 409 or a stable 200 and fails on 404/5xx | `OBSERVED` | `backend/tests/unit/test_staging_evidence_resolution_check.py` |
| The staging environment holds `PATCHHIVE_DATABASE_URL_STAGING` | `OBSERVED` | db-migrate staging run 41540758612 |
| Staging serves `GET /api/admin/ops/runtime-flags` | `INFERRED` | route on main; staging must be redeployed from main first |
