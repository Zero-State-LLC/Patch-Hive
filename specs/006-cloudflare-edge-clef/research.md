# Research: 006-cloudflare-edge-clef

Decision research for the open edge decisions (2026-10-29). Each item gives the evidence, the options and the recommendation. Labels: `[OBSERVED: <source>]` or `[INFERRED]`. Effort: S (under a day), M (one to three days), L (more).

Already fixed and reconciled in [spec.md](spec.md): edge secrets reach the right Worker behind a target guard (#107); container startup migrations are opt-in (#110); exact-origin CORS and an enforced CSP (#113); API security headers (#130).

## R1. `gates_pass` accepts any 64-hex string (FR-006, FR-007)

**Evidence:** `_guard_gates_pass` checks `staging_host_plan_passed` and that `evaluation_receipt_sha256` matches `^[0-9a-f]{64}$`. It never loads or verifies the receipt [OBSERVED: backend/core/ops/edge_readiness.py; scratch run 2026-10-29: `"0"*64` passes].

**Options:** (1) keep the SHA string; (2) carry the receipt in `ReadinessEvidence` and call `verify_enablement_receipt`, then require the SHA to match.

**Recommendation:** option 2, after 007 signs receipts ([007 research R1](../007-evaluation-staging-enablement/research.md): Ed25519 plus replay). Effort S once 007 T081 lands.

## R2. Deploy workflows can target production with no approval gate

**Evidence**

- `db-migrate.yml` (`target: staging|prod`), `db-load.yml` (`env: staging|prod`) and `edge-secrets.yml` (`env: staging|production`) are `workflow_dispatch` only. None sets a job `environment:`, so anyone with write access can run them against production, and the production secrets are repo secrets [OBSERVED: .github/workflows/].
- The names differ: `prod` in the two database workflows, `production` in `edge-secrets.yml` [OBSERVED].
- A GitHub environment with required reviewers must be created by a repo admin in the settings. It cannot be created from the tree [INFERRED from GitHub Actions behaviour].

**Options:** (1) a typed acknowledgement input; (2) a job `environment:` set from the input, with required reviewers on `production` and the production secrets moved into that environment; (3) both.

**Recommendation:** option 2. Code: add `environment: ${{ inputs.target == 'prod' && 'production' || 'staging' }}` (and the same for `env`), and read secrets from the environment. Operator: create `staging` and `production` environments, add required reviewers and a `main`-only branch rule to `production`, move `PATCHHIVE_DATABASE_URL_PROD` and the Cloudflare token into it. Until the environment exists, GitHub creates it unprotected on first run, so the operator step comes first. Effort S code, S operator.

## R3. `deploy-worker-pin-pr.yml` belongs to another project

**Evidence:** it deploys `workers/noema`, clones `Zero-State-LLC/Noema-Specs`, uses `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `NOEMA_PIN_PR_TOKEN`, and its environment URL is `https://noema.guru`. This repo has no `workers/` directory [OBSERVED: .github/workflows/deploy-worker-pin-pr.yml, repo tree].

**Recommendation:** delete it from this repo. It can only fail here, and it asks for production secrets this project does not own. Effort S.

## R4. `db-load.yml` grants `actions: write`

**Evidence:** the job checks out, installs, runs `scripts/catalog_actions_load.py` and uploads an artifact. Nothing calls the Actions API [OBSERVED: .github/workflows/db-load.yml]. `actions/upload-artifact` does not need `actions: write` [INFERRED from the action's documentation].

**Recommendation:** drop it; keep `contents: read`. Effort S.

## R5. A new R2 token stays live when the bulk write fails

**Evidence:** `edge-secrets.yml` creates a bucket-scoped R2 token, then runs `wrangler secret bulk`. If that step fails or reports another Worker, the job exits and the revoke step (which only revokes older tokens) is skipped. The new token is never written anywhere and never revoked [OBSERVED: .github/workflows/edge-secrets.yml].

**Recommendation:** add an `if: failure() && env.NEW_R2_TOKEN_ID != ''` step that deletes `NEW_R2_TOKEN_ID`. Effort S.

## R6. Stale acceptance text

**Evidence:** "Acceptance summary" still names Pages and Hyperdrive. FR-001 and FR-003 were amended to Workers static assets and Neon's pooled endpoint (2026-10-26/27) [OBSERVED: spec.md].

**Recommendation:** amend the summary in place. RESOLVED in spec.md.
