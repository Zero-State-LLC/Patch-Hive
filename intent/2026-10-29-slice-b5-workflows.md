# Intent

## Problem

Spec 006 research (R3, R4, R5) found three CI defects: a workflow that belongs to another project, an unneeded `actions: write` grant, and an R2 token that stays live when the Worker secret write fails.

## Proposed outcome

- R3 (T102): delete `.github/workflows/deploy-worker-pin-pr.yml`. It deployed the Noema project's `workers/noema` with Noema secrets; this repo has no `workers/` directory and nothing references the file (grep found only the spec and audit docs).
- R4 (T103): drop `actions: write` from `db-load.yml`; `contents: read` stays. The job only checks out, installs, runs the loader and uploads an artifact, none of which needs it.
- R5 (T104): add an `if: failure()` step to `edge-secrets.yml` that deletes the new R2 token through the same Cloudflare API and credentials that created it. It runs only when the "Write Worker secrets" step did not succeed, so a failure in the later older-token revoke never revokes a token the Worker is already using. The token id is already captured in `NEW_R2_TOKEN_ID`; it is not a secret and no token value is printed.
- Out of scope: GitHub environment protection (T101, needs a repo admin) and renaming `prod`/`production` inputs.

## Affected users / systems

CI only: `.github/workflows/`, `backend/tests/test_db_load_workflow.py`, spec 006 tasks. Operators who dispatch `edge-secrets.yml` and `db-load.yml`.

## Constraints / non-goals

No workflow is triggered, nothing deployed or pushed. Operators keep using `prod` (`db-load.yml`, `db-migrate.yml`) and `production` (`edge-secrets.yml`); the mismatch is noted, not changed.

## Open questions

- Add a revoke for a token created but not yet recorded in `NEW_R2_TOKEN_ID` (a failure between token creation and the `GITHUB_ENV` write)? Narrow window; left as is.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Nothing references `deploy-worker-pin-pr.yml` outside spec/audit docs | `OBSERVED` | grep of the worktree |
| `db-load.yml` makes no Actions API calls | `OBSERVED` | read the workflow |
| `upload-artifact` needs no `actions: write` | `INFERRED` | action documentation |
| `DELETE /accounts/{id}/tokens/{id}` revokes the token | `OBSERVED` | same call the existing older-token revoke uses |

## Author / date

- Author: Claude (slice B5)
- Date: 2026-10-29
