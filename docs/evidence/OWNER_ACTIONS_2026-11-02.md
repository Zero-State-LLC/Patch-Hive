# Owner action guide, 2026-11-02

Everything on Patch-Hive that only the owner can do, researched on 2026-11-02 against `main` at `9dba804` and the live hosts. Each item gives what and why, current state, exact steps, how to check it worked, and what it unblocks. Nothing here was run or changed while researching (read-only `gh`, `curl` and documentation reads only). Secret values never appear; only their names.

## Start here: the ten things that unblock the most

| # | Do this | Why now | Time | Section |
|---|---|---|---|---|
| 1 | Protect the `production` environment (required reviewer = you, `main` only, prevent self-review **off**) and move the prod secrets into it (T101b) | Every later prod migration, load and deploy is then gated; unblocks the daily evidence-expiry job (T101c) | 30 min | Operations §3 |
| 2 | Run `db-migrate` for `20261101_user_deleted_at` (#194) on staging, then prod | A catalog load or deploy of current main refuses until the database is at the code's migration head | 15 min | Operations §1 |
| 3 | Merge release PR #169, then deploy staging, smoke-test, deploy prod | Hosts still run `9dbb5ba` (0.3.0-alpha.5); #183–#200 are on `main` only | 1–2 h | Operations §2 |
| 4 | Generate the approver key offline and commit only the public key (007 T082) | Unblocks every receipt-gated feature: the decision-provider gate (#185), signed readiness pins (#186), Clef and NVIDIA enablement | 30 min + PR | Enablement §1 |
| 5 | Confirm specs 001–004 (T001) | Lets Claude write their plans (T002) and close the transition-test tasks (T010) | 1–2 h | Decisions §1 |
| 6 | Confirm or change the seven provisional Jev decisions | Two are recommended for change (002 OQ-12 license: defer; 004 OQ-1 prices: not ratified) | 30 min | Decisions §2 |
| 7 | R2 scoping and persistence check (T055b, T040b) | Closes the last spec 006 operator tasks | 45 min | Operations §4 |
| 8 | Send the maker emails (17 unsourced widths, Akemie's Castle) | Only route to close 003 T039 | 30 min | Decisions §3 |
| 9 | Build the evaluation corpus (007 T010b) | 70% of the 30–55 h needed before any vision provider (Clef or NVIDIA) can be enabled | 20–40 h | Enablement §2 |
| 10 | Hand the legal brief to counsel | Sales stay deferred until terms exist (004 OQ-13); retention and license choices need confirming | — | Decisions §5 |

Open PRs to decide on: #169 (release), #191 (live NVIDIA smoke test, docs and test only; merge), #192 (staging NVIDIA timeout and pinned Llama fallback; enables nothing; decide whether the 007 receipt should pin the model), #199 (Dependabot follow-redirects patch bump). CURRENT_STATE.md is stale on a few points found here: #106, #109 and #111 are merged, `RELEASE_PLEASE_TOKEN` exists (only `PROJECT_TOKEN` is missing), and the `staging` and `production` environments exist but have no protection or secrets.

## What Claude can do once you unblock it

- **Now, no owner step needed:** a driver script for the 007 chain (`scripts/staging/run_007_evaluation.py`): freeze the corpus, run the baseline against a provider, propose thresholds, record the approval, pin and sign the receipt. Today these exist only as library functions that tests call. Also the design-engine flags PR for staging (needed by 008 T040b), and refreshing CURRENT_STATE.md.
- **After T101b:** the daily `evidence-expire.yml` job (T101c).
- **After T001:** plan.md for specs 001–004 (T002), then closing T010.
- **After a maker reply:** the reviewed correction or overlay entry for each width.
- **After a signed receipt:** committing it under `backend/`, wiring the receipt paths for staging, and verifying the provider path (006 T060b).
- **Now, before T060b:** fix the evidence id mismatch that stops an uploaded image from reaching the decision route (the candidate id `evidence-<hash>` vs the stored `ev-<uuid>`; Enablement §3).

---

## Operations: migrations, deploys, GitHub and Cloudflare setup, NVIDIA

Checked 2026-11-02 against `Zero-State-LLC/Patch-Hive` main `9dba804` (#200), using read-only `gh`/`curl`, a read-only Cloudflare bucket listing, and official docs. Nothing was changed. No secret values were read or are written here, only names.

Where live state differs from `CURRENT_STATE.md` (it is stale on these):

- #106, #109 and #111 are all MERGED (2026-10-29/30). They are not stale PRs.
- `RELEASE_PLEASE_TOKEN` already exists as a repo secret (set 2026-10-28).
- The GitHub environments `staging` and `production` already exist (created 2026-10-30 by the first workflow runs) but have no protection rules and hold no secrets. T101b is half done by accident: the names exist, the protection does not.
- Both R2 buckets exist (created 2026-10-28).
- Live open PRs: #169 (release), #191, #192 (NVIDIA), #199 (Dependabot follow-redirects).

Items are numbered as you asked. A suggested order, by what unblocks most, is at the end.

---

### 1. Migration `20261101_user_deleted_at` (#194) and catalog loads (#198)

**What and why.** #194 adds a nullable `users.deleted_at` column (additive only) so deleted accounts can be told apart. Deployed code that uses it (account deletion) fails until the column exists. Startup migrations are off on both Workers, so the only way to migrate is the `db-migrate.yml` workflow.

**Current state.**
- `backend/alembic/versions/20261101_user_deleted_at.py` revises `20261030_power_configs`. The last `db-migrate` runs were 2026-10-30 (all success), so neither database should have this revision yet. I cannot see the database head from here; the workflow prints `alembic current` as its last step.
- `db-migrate.yml` input: `target` = `staging` or `prod`. It uses secrets `PATCHHIVE_DATABASE_URL_STAGING` / `PATCHHIVE_DATABASE_URL_PROD` and runs in environment `staging` or `production`.
- `db-load.yml` inputs (read from the file): `env` (`staging`|`prod`), `mode` (`dry-run`|`apply`, default dry-run), `plan_hash`, `inputs_hash` (both only for apply). Since #198 (merged 2026-11-02 07:30Z) an apply needs BOTH hashes from the reviewed dry run, and refuses even if the planned writes are unchanged but the inputs differ. The load also refuses to start unless the database is at this checkout's alembic head, so migrate first.
- The latest catalog loads (runs from 2026-11-02 02:xx) predate #198 and no catalog data has changed since, so you do not need a load now. The forms below are for the next data PR.

**Steps (migration).**

1. Staging first:
```bash
gh workflow run db-migrate.yml -R Zero-State-LLC/Patch-Hive --ref main -f target=staging
```
2. Watch it:
```bash
gh run watch -R Zero-State-LLC/Patch-Hive $(gh run list -R Zero-State-LLC/Patch-Hive --workflow db-migrate.yml --limit 1 --json databaseId --jq '.[0].databaseId') --exit-status
```
3. Open the run log; the last step prints `20261101_user_deleted_at (head)`.
4. Deploy and smoke staging (item 2), then migrate prod:
```bash
gh workflow run db-migrate.yml -R Zero-State-LLC/Patch-Hive --ref main -f target=prod
```
   Once item 3 is done, this waits for your approval click on the run page.

**Steps (catalog load, when a data PR lands).** Run db-migrate for the same ref first.

1. Dry run (writes nothing):
```bash
gh workflow run db-load.yml -R Zero-State-LLC/Patch-Hive --ref main -f env=staging -f mode=dry-run
```
2. Download the counts-only receipt and read both hashes (they are also in the run's job summary):
```bash
gh run download -R Zero-State-LLC/Patch-Hive <RUN_ID> -n catalog-load-receipt-staging-dry-run -D /tmp/dry && jq '{plan_hash, inputs_hash}' /tmp/dry/receipt.json
```
3. Review the counts in the receipt, then apply with both hashes:
```bash
gh workflow run db-load.yml -R Zero-State-LLC/Patch-Hive --ref main -f env=staging -f mode=apply -f plan_hash=<PLAN_HASH> -f inputs_hash=<INPUTS_HASH>
```
4. Repeat with `-f env=prod` and artifact `catalog-load-receipt-prod-dry-run`. Hashes from staging do not carry over to prod.

`<RUN_ID>` comes from `gh run list -R Zero-State-LLC/Patch-Hive --workflow db-load.yml --limit 1`. If an apply is rejected for a hash mismatch, the inputs or plan changed since your dry run: re-run the dry run; do not edit the hashes.

**Check it worked.** Migrate log ends with the new revision as head. Load: the job summary shows applied counts, and a second dry run plans zero writes.

**Unblocks.** Deploying #194 (account deletion), and item 2.

**Time.** About 5 minutes per migration run; 10 minutes per load.

**Risk / notes.** The migration is additive and nullable, so the currently deployed code keeps working if you migrate before deploying. Do staging, then prod. Apply loads dump the affected tables first (the dump stays on the runner). A prod apply needs your explicit yes by the repo's own rule.

---

### 2. Deploy staging then production

**What and why.** Staging and production both run `9dbb5ba` (0.3.0-alpha.5). Main has since gained backend changes (#183-#186, #189, #194, #197, #198) that nothing is running. There is no deploy workflow; you deploy by hand with wrangler from a main checkout. Docker must be running because the API image is built locally.

**Current state (verified live).** `GET /health/ready` and `GET /health` on both `https://api.patch-hive.com` and `https://api-staging.patch-hive.com` return `healthy`, version `0.3.0-alpha.5`, database `ok`. `/health` reports the version from `backend/pyproject.toml`, so it shows `0.3.0-alpha.6` only if #169 is merged before you build.

**Release PR #169 (Release Please, 0.3.0-alpha.6).** It is a bot PR that edits `CHANGELOG.md`, `.release-please-manifest.json`, `backend/pyproject.toml` and `frontend/package.json`. Merging it creates tag `v0.3.0-alpha.6` and a GitHub pre-release (`release.yml` publishes on the tag). `release-please.yml` says "Nothing deploys from here." Its checks are green; it is mergeable but blocked on a review (branch protection requires one code-owner approval; your account is on the bypass list). Recommendation: merge it BEFORE deploying, so the deployed `/health` says alpha.6 and the tag matches what runs.

**Before you start.** Decide #191/#192 (item 5). #192 changes `edge/api` and backend code; if you want it, merge it first so you deploy once.

**Steps.**

1. Get current main:
```bash
cd ~/Patch-Hive && git switch main && git pull --ff-only
```
2. Start Docker Desktop. Migrate staging (item 1).
3. Deploy the staging API (builds `backend/Dockerfile`):
```bash
cd ~/Patch-Hive/edge/api && npm ci && npx wrangler deploy --env staging
```
4. Deploy the staging frontend:
```bash
cd ~/Patch-Hive/frontend && npm ci && npm run build:staging && npx wrangler deploy --env staging
```
5. Smoke staging:
```bash
curl -s https://api-staging.patch-hive.com/health/ready
```
   Expect `healthy`, the new version, `database: ok` (the first call pays a cold start). Load `https://staging.patch-hive.com` and sign in with a staging account. (`scripts/staging/smoke.sh` is for the local Compose stack, not the hosted Workers.)
6. Migrate prod (item 1), then deploy the production API:
```bash
cd ~/Patch-Hive/edge/api && npx wrangler deploy
```
7. Production frontend:
```bash
cd ~/Patch-Hive/frontend && npm run build && npx wrangler deploy
```
8. Smoke production:
```bash
curl -s https://api.patch-hive.com/health/ready
```
   Load `https://patch-hive.com`. Production sets no feature flags and keeps `STRIPE_TEST_MODE=true` and `ALLOW_PRODUCTION_PAYMENTS=false`.

wrangler auth: `npx wrangler login` (browser) or export `CLOUDFLARE_API_TOKEN` for the session. Containers need the Workers Paid plan (already live).

**Check it worked.** `version` in `/health` matches `backend/pyproject.toml`; `/health/ready` is `ok` on both hosts; sign-in works.

**Unblocks.** Everything on main since `9dbb5ba`, the real production sign-up check, and the T101b test run.

**Time.** 30-45 minutes including Docker builds.

**Risk / notes.** Production is live (accounts open, payments test-mode). Soak staging first. Rollback: `npx wrangler rollback` for a Worker (I did not test it here); the DB column is additive, so it needs no rollback. A deploy only replaces the running container when the image digest or env hash changed (`startAndWaitUntilHealthy` in `edge/api/src/index.ts`). Claude can update `CURRENT_STATE.md` afterwards.

---

### 3. T101b: GitHub environments, plus Jev's OQ-1 and OQ-2

**What and why.** Put the production database URL and Cloudflare token behind an environment that needs your approval and only accepts runs from `main`, so a workflow on any other branch cannot reach prod secrets.

**Current state (verified via `gh api`).**
- Environments `production` and `staging` exist; both show `protection_rules: []`, `deployment_branch_policy: null`, `can_admins_bypass: true`. The workflows still read repo-level secrets.
- Repo secrets: `CLOUDFLARE_API_TOKEN`, `PATCHHIVE_DATABASE_URL_PROD`, `PATCHHIVE_DATABASE_URL_STAGING`, `RELEASE_PLEASE_TOKEN`. Repo variable: `CLOUDFLARE_ACCOUNT_ID`. `PROJECT_TOKEN` does not exist.
- Names used by the three gated workflows: `PATCHHIVE_DATABASE_URL_PROD` and `PATCHHIVE_DATABASE_URL_STAGING` (all three), `CLOUDFLARE_API_TOKEN` (secret) and `CLOUDFLARE_ACCOUNT_ID` (variable), both in `edge-secrets.yml` only. `release-please.yml` uses `RELEASE_PLEASE_TOKEN` and `project-collaboration.yml` uses `PROJECT_TOKEN`; neither has an `environment:`, so they stay repo-level.
- The org is on the GitHub Team plan, so environment protection works for public or private repos.

**OQ-1 (Jev: `owner_reviewer_main_only`, confidence 0.36, low): prevent-self-review OFF while you are the only reviewer.** GitHub docs: "Prevent self-review" stops a user approving a run they triggered, and only one listed reviewer needs to approve ([Managing environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments), [changelog](https://github.blog/changelog/2023-10-16-actions-prevent-self-reviews-for-secure-deployments-across-actions-environments)). The docs do not say in words what happens when the only reviewer triggered the run. Read literally, with it ON nobody else can approve, so the run waits forever (the repo's DEPLOY_NOTES also say it deadlocks); treat that as likely, not documented. With it OFF you can approve your own run: you still get a deliberate click and the `main`-only rule, but no second pair of eyes. That is reasonable for a solo operator; turn it ON when a second reviewer exists. I agree with Jev.

**OQ-2 (Jev: `separate_staging_token`, confidence 0.97): yes.** Permissions, from what `edge-secrets.yml` and `DEPLOY_NOTES.md` actually use:
- Account > Workers Scripts > Edit (writes Worker secrets; [Cloudflare permissions list](https://developers.cloudflare.com/fundamentals/api/reference/permissions/) calls it Workers Scripts Edit/Write).
- Account API Tokens > Edit (the workflow creates a bucket-scoped R2 token at run time and revokes the older one). The permissions page I fetched lists only "API Tokens Edit" under user scope, so pick whatever the dashboard picker calls the account-level token edit permission; I could not confirm the exact label.
- The "Workers R2 Storage Bucket Item Write" group named in the workflow is looked up by name and attached to the new R2 token. Your own token does not need it.

Honest limit: Cloudflare tokens are scoped to an account, zone or resource type, not to one Worker name, so a staging token with these permissions can still write secrets on the production Worker and mint tokens for the prod bucket. The split stops a staging run reading the production token and lets you rotate or revoke them separately; it does not stop that. Real least-privilege would need a later redesign of `edge-secrets.yml`.

**Steps (UI).** Repo Settings > Environments.

1. Open `production`. Tick **Required reviewers** and add `scrimshawlife-ctrl`. Leave **Prevent self-review** unticked. Untick **Allow administrators to bypass configured protection rules**. Save protection rules.
2. Under **Deployment branches and tags** choose **Selected branches and tags**, then add a Branch rule `main`.
3. Under **Environment secrets** add `PATCHHIVE_DATABASE_URL_PROD`. GitHub will not show the current value; get the connection string from Neon console > project `patchhive` > branch `main`.
4. Create the production Cloudflare token in the Cloudflare dashboard (Manage Account > Account API Tokens) with the two permissions above. Add it as environment secret `CLOUDFLARE_API_TOKEN`, and add environment variable `CLOUDFLARE_ACCOUNT_ID` (same value as the repo variable).
5. Open `staging` (no reviewers). Add `PATCHHIVE_DATABASE_URL_STAGING`, a second Cloudflare token as `CLOUDFLARE_API_TOKEN`, and `CLOUDFLARE_ACCOUNT_ID`.
6. Test from `main`: run `db-migrate.yml` with `target=prod` (or `edge-secrets.yml` with `staging`). Prod must show "Waiting for review"; approve it; secrets must resolve.
7. Only after step 6 passes, delete the repo-level `PATCHHIVE_DATABASE_URL_PROD`, `PATCHHIVE_DATABASE_URL_STAGING`, `CLOUDFLARE_API_TOKEN` and the repo variable `CLOUDFLARE_ACCOUNT_ID` (Settings > Secrets and variables > Actions). Keep `RELEASE_PLEASE_TOKEN`. Then revoke the old Cloudflare token in Cloudflare.
8. Verify the rules:
```bash
gh api repos/Zero-State-LLC/Patch-Hive/environments/production --jq '{rules:.protection_rules, branches:.deployment_branch_policy, admins:.can_admins_bypass}'
```
   Expect a `required_reviewers` rule, `custom_branch_policies: true`, `admins: false`.

(There is a REST route to do steps 1-2 from the CLI, `PUT /repos/.../environments/production` plus `POST .../deployment-branch-policies`. I did not test it; use the UI.)

**Check it worked.** The step 6 run stops at "Waiting for review", and a run dispatched from a non-main branch is refused for `production`.

**Unblocks.** T101b closed. **T101c becomes buildable:** Claude can add `.github/workflows/evidence-expire.yml`, a daily scheduled job in the `staging` and `production` environments running `python -m evidence.expire --apply` (command exists, documented in `docs/OPERATIONS.md`; it exits 1 when a purge is deferred so the job fails visibly), with a workflow test. Open design points Claude must raise then: the R2 S3 keys live only on the Worker, not in GitHub, and a scheduled job in `production` will wait for your approval each day. There are 0 evidence images today, so this is not urgent.

**Time.** 30-45 minutes.

**Risk / notes.** Do not delete the repo-level secrets before step 6 passes, or every migrate/load/secrets run fails. Keep the old Cloudflare token until the new one works. With admin bypass off and you as sole reviewer, losing your GitHub session blocks prod runs; keep your 2FA recovery codes.

---

### 4. T055b / T040b: R2 buckets and the persistence check

**What and why.** Prove uploaded files survive a container restart because they are mirrored to R2. That closes T055b, which unblocks T040b.

**Current state.**
- Verified (read-only Cloudflare API bucket listing): `patchhive-prod-files` and `patchhive-staging-files` both exist (created 2026-10-28), matching `S3_BUCKET` in `edge/api/wrangler.jsonc` (key prefixes `prod` and `staging`).
- NOT verified: that the credentials are bucket-scoped and that writes work. `edge-secrets.yml` creates a token named `patchhive-api-<env>-r2` with only "Workers R2 Storage Bucket Item Write" on that one bucket and revokes older tokens of that name. `/health/ready` is 200 on both hosts and the Worker answers 503 until all required secrets exist, so the secrets are set.
- Container behaviour: inactivity timeout is 15 minutes (`INACTIVITY_TIMEOUT_MS`) and disk is ephemeral ([Cloudflare Containers FAQ](https://developers.cloudflare.com/containers/faq/)).

**Steps.**

1. Scoping check. Cloudflare dashboard > Manage Account > Account API Tokens. Open `patchhive-api-staging-r2` (and `-production-r2`). Each must show one permission and one resource, its own bucket. Two tokens with the same name mean the revoke step failed; delete the older one.
2. Upload through the staging API. Sign in at `https://staging.patch-hive.com`, create a rack, and upload an evidence image (route `POST /api/racks/{id}/evidence/images`, multipart field `files`). Note the asset id from `GET /api/racks/{id}/evidence/images`.
3. Confirm the copy in R2: dashboard > R2 > `patchhive-staging-files` > Objects, under the `staging/` prefix, a new object with today's timestamp.
4. Restart the container. Wait 15 minutes with no requests (it sleeps and the disk is discarded). A redeploy (`npx wrangler deploy --env staging` from `edge/api`) restarts it only if the image digest or env changed, so prefer the wait. I found no verified wrangler command to restart an instance.
5. Wake it and read back:
```bash
curl -s https://api-staging.patch-hive.com/health/ready
```
   Then repeat `GET /api/racks/{id}/evidence/images`; the asset must still be listed. Caveat: the repo has no plain "download the image" route. The code that restores a missing file from R2 on read is used by the decision flow (`intelligence/evidence_images.py`) and design-pack downloads (`canon/routes.py`). The direct proof is the R2 object from step 3 plus a design pack or export that still downloads after the restart. If you want a one-command check, ask Claude to add a small script for upload, wait, fetch.

**Check it worked.** Object visible in R2; asset, pack or export still readable after the container slept; no 5xx. Claude can draft the T055b/T040b receipts from your output (006 OQ-3).

**Unblocks.** T055b, T040b, 006 OQ-3 closure.

**Time.** 30 minutes plus a 15-minute wait.

**Risk / notes.** Use a test account and a non-sensitive image on staging. Do not paste token values anywhere. No production account exists yet, so run the production half only as the token check plus `/health/ready`.

---

### 5. NVIDIA provider, Inception, and PRs #191 / #192

**What and why.** NVIDIA vision models as a second decision provider beside Clef (T086; code merged in #189, inert by default).

**Current state.**
- Code: `NVIDIA_API_KEY` is in the staging-only secret list (`STAGING_SECRETS` in `edge/api/src/index.ts`); `ENABLE_NVIDIA_PROVIDER`, `NVIDIA_MODEL`, `DECISION_PROVIDER` and `ENABLE_DECISION_INTELLIGENCE` are in `FLAG_VARS`. Production never receives them and `core/startup_policy.py` refuses the NVIDIA flag in production.
- #191's description says `NVIDIA_API_KEY` is already set on `patchhive-api-staging` and `ENABLE_NVIDIA_PROVIDER` is not set. I cannot check Worker secrets without a Cloudflare login, so treat it as the other session's claim. To check names: `cd edge/api && npx wrangler secret list --env staging`.
- `edge-secrets.yml` does NOT manage NVIDIA, Clef or Typesafe keys; set this one with wrangler.
- Enabling is gated: outside development, any decision flag or provider needs a signed 007 enablement receipt (#185, `DECISION_ENABLEMENT_RECEIPT_PATH` and `DECISION_ENABLEMENT_SIGNATURE_PATH`), and the approver key (007 T082) has not been created. If you set `ENABLE_NVIDIA_PROVIDER` on staging before then, startup refuses. Do not turn flags on yet.

**Steps (key).**

1. Go to build.nvidia.com, open a model page, click **Get API Key**, sign in or create an NVIDIA account, and copy the key ([API quickstart](https://docs.api.nvidia.com/nim/docs/api-quickstart)). If #191's claim is right you already have one; skip to step 3.
2. Set it on the staging Worker only (the command prompts; the value is not echoed):
```bash
cd ~/Patch-Hive/edge/api && npx wrangler secret put NVIDIA_API_KEY --env staging
```
3. Check the name appears:
```bash
cd ~/Patch-Hive/edge/api && npx wrangler secret list --env staging
```
4. Flags come later, as a reviewed PR to `env.staging.vars` in `edge/api/wrangler.jsonc`, then a staging redeploy: `ENABLE_DECISION_INTELLIGENCE=true`, `DECISION_PROVIDER=nvidia`, `ENABLE_NVIDIA_PROVIDER=true`, optional `NVIDIA_MODEL` (default `nvidia/nemotron-3.5-super-vl-120b-a12b`) and the two receipt paths. First: 007 T082 (generate the approver key pair offline, commit only the public key) and a 007 evaluation run naming `nvidia`. Claude can prepare the PR; you must generate and hold the private key.

**Inception and hosted API production use (researched).**
- Official ([Inception FAQ](https://www.nvidia.com/en-us/startups/faq/)): free to join, no equity; company must be incorporated and under 10 years old, with a working website and a use case; benefits are courses, preferred hardware/software pricing, partner offers, VC network, and "free cloud credits from NVIDIA and partners". It does not mention API-catalog or NIM credits, and says nothing about production use of build.nvidia.com.
- Third-party blogs claim Inception members get free NIM endpoints on build.nvidia.com for prototyping; they are not NVIDIA sources and conflict on production use. Unverified.
- Trial limits: NVIDIA's own terms were not retrievable. Forum threads describe a default of 40 requests per minute on free keys, and say increases are not granted on free personal accounts, pointing to NVIDIA AI Enterprise or self-hosted NIM ([forum thread](https://forums.developer.nvidia.com/t/request-for-nvidia-build-api-rate-limit-increase-40-rpm-200-rpm/373495)). Unofficial.
- The repo's DEPLOY_NOTES already say production use needs paid or program entitlement confirmed first. Conclusion: the key is fine for staging evaluation. Do not plan production traffic on it until you read the API trial terms at build.nvidia.com and get written confirmation from NVIDIA (the Inception portal contact) of what is allowed in production and at what limits. Applying to Inception is free, but joining does not itself grant production API rights.

**PRs #191 and #192 (another session's work; both open, CI green).**
- #191 `test(005): opt-in live NVIDIA smoke test; record the first live call`. Tests and docs only: a pytest that runs only with `RUN_NVIDIA_LIVE=1` and a key, never in CI; provider code unchanged. Records that both pinned Nemotron models returned in-schema JSON in 0.5-1.4 s, and that the first call to the 120B model hit the 20 s timeout. Low risk. Recommend merge.
- #192 `staging NVIDIA timeout 60 s and a pinned Meta Llama fallback model`. Stacked on #191 (merge #191 first). Sets `NVIDIA_TIMEOUT_SECONDS=60` in staging vars (forwarded outside production only); adds `meta/llama-3.2-90b-vision-instruct` as a third pinned model (used only if `NVIDIA_MODEL` selects it; no automatic retry); warns in the log on a non-default model; mocked tests. It enables nothing. Live, the Llama 90B call took 48 s. Its open question for you: the 007 receipt names the provider (`nvidia`), not the model, so a receipt earned with one model also admits the others. Should the receipt pin `NVIDIA_MODEL`? My suggestion: yes, as a small follow-up; #192 itself can merge meanwhile since it enables nothing. That is a design call, so it is yours.
- Neither is deployed. If you merge them, do it before the item 2 deploy so you deploy once.

**Check it worked.** `wrangler secret list --env staging` shows `NVIDIA_API_KEY` (name only). The provider stays inert until flags are set.

**Unblocks.** The 007 evaluation of `nvidia`.

**Time.** 15 minutes for the key; flags are later work.

**Risk / notes.** The key is a secret: never in git, chat or a PR; rotate it if it is ever pasted. Production must not get it (the Worker will not forward it there).

---

### 6. GitHub housekeeping

**What and why.** Small operator items from `CURRENT_STATE.md`.

- **`RELEASE_PLEASE_TOKEN`: already set** (2026-10-28), and #169 is being kept open by it, so nothing to add. Used by `release-please.yml` (`RELEASE_PLEASE_TOKEN || GITHUB_TOKEN`). Per the workflow comment it is a fine-grained PAT on this repo with Contents, Pull requests and Issues read/write. A PAT-opened release PR also triggers CI; GITHUB_TOKEN-opened ones do not. Rotate before its expiry.
- **`PROJECT_TOKEN`: not set.** Used only by `project-collaboration.yml` to add new issues and PRs to org Project #8 (GraphQL). Without it the step degrades to a warning; PRs #82-#116 never reached the board. The workflow asks for "a PAT or App token with `project` scope". The documented-safe choice is a classic PAT with the `project` scope (this repo is public, so no `repo` scope). Whether a fine-grained PAT's organization "Projects" permission works for ProjectsV2 GraphQL on github.com I could not confirm ([permissions reference](https://docs.github.com/en/enterprise-server@3.12/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens), an Enterprise Server page). Give it an expiry. Add it (paste at the prompt):
```bash
gh secret set PROJECT_TOKEN -R Zero-State-LLC/Patch-Hive
```
  If the org restricts PATs you may have to approve the token under the org's personal access token settings.
- **Repo visibility vs Actions budget.** The repo is PUBLIC (verified), so Actions use free minutes. `CURRENT_STATE.md` says that while it was private the Actions budget blocked every job. The org plan is Team (verified); I cannot see the spending budget (Settings > Billing and plans > Budgets). Recommendation: stay public while you depend on free Actions; the workflows are already built for public logs (masking, counts-only receipts). If you go private, check the budget first. Environment protection works either way on Team. **Keep it public while you rely on the production approval gate:** on the Team plan GitHub offers required reviewers on environments only for public repositories ("required reviewers are only available for public repositories"). Environment secrets and the `main`-only branch rule still work in a private repo, but the approval click in Operations §3 would disappear, and `db-migrate.yml`, `db-load.yml` and `edge-secrets.yml` would run against production without it.
- **Rotate the context.dev and OpenRouter keys.** Per the notes they live in `~/.zshenv` (not opened). In each provider dashboard create a new key, replace the line in `~/.zshenv`, open a new shell, confirm it works, then delete the old key. Neither name is in the repo's secret list.
- **Stale PRs.** #106, #109 and #111 are already MERGED. Open now: #169 (release; see item 2), #191 and #192 (item 5), #199 (Dependabot, follow-redirects 1.16.1 to 1.16.2 in `/frontend`; a patch bump, safe to merge once CI is green). Nothing is stale.
- `main` branch protection requires 5 checks and 1 code-owner review, with admins enforced; you are on the PR-bypass list.

**Check it worked.** `gh secret list -R Zero-State-LLC/Patch-Hive` shows `PROJECT_TOKEN`; the next PR opened gets a board item on Project #8.

**Time.** About 10 minutes each.

**Risk / notes.** Smallest scope, with an expiry. Never paste a key into chat.

---

### Suggested order

1. Merge #191 then #192 if wanted, then #199, then #169.
2. Item 3 (protect `production`), so every later prod run is gated.
3. Item 1 staging migrate, item 2 staging deploy and smoke, item 4 R2 check, then item 1 prod migrate and item 2 prod deploy.
4. Item 6 housekeeping; item 5 NVIDIA key and flags whenever you want to evaluate.

Sources: [GitHub: managing environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments), [GitHub changelog: prevent self-reviews](https://github.blog/changelog/2023-10-16-actions-prevent-self-reviews-for-secure-deployments-across-actions-environments), [Cloudflare API token permissions](https://developers.cloudflare.com/fundamentals/api/reference/permissions/), [Cloudflare Containers FAQ](https://developers.cloudflare.com/containers/faq/), [NVIDIA Inception FAQ](https://www.nvidia.com/en-us/startups/faq/), [NVIDIA API quickstart](https://docs.api.nvidia.com/nim/docs/api-quickstart).

---

## Evaluation and enablement chain (specs 005 / 006 / 007 / 008)

Verified against main `9dba804` of Zero-State-LLC/Patch-Hive (checkout `/Users/appliedalchemylabs/Patch-Hive-state-rec`), read-only. Open PRs that matter: #191 (live NVIDIA smoke test), #192 (staging `NVIDIA_TIMEOUT_SECONDS=60`, pinned Llama fallback model).

### Read this first: four findings that change the plan

1. **There is no CLI for the 007 chain.** `freeze_corpus`, `run_baseline_comparison`, `propose_thresholds`, `approve_thresholds`, `enable_staging` and `pin_receipt` are Python functions in `backend/intelligence/` (called only by tests). `specs/007.../OPERATOR_NOTES.md` describes the calls but no script runs them. Nothing under `scripts/` runs an evaluation, and nothing signs. The only operator scripts in this chain are `scripts/validate_vision_pilot.py`, `scripts/build_vision_promotion_queue.py` and (008) `scripts/staging/design_engine_walkthrough.py`. **Update (007 T084): the driver now exists** as `scripts/staging/run_007_evaluation.py`, with subcommands `freeze`, `candidate-hashes`, `run`, `propose`, `approve`, `enable-staging`, `pin`, `sign` and `verify`. Item 2 below gives the exact commands; `specs/007.../OPERATOR_NOTES.md` ("Driver script") documents the run-inputs file and every refusal. The hand-written signing snippets further down still work but are no longer needed.
2. **The receipt files have no way into the staging container except the image.** `DECISION_ENABLEMENT_RECEIPT_PATH` and `DECISION_ENABLEMENT_SIGNATURE_PATH` are read from the container's disk (`backend/intelligence/enablement_gate.py`). The container disk is wiped on sleep/redeploy (`specs/006.../DEPLOY_NOTES.md`, "Durable files"), the Dockerfile does `COPY . .` from `backend/` (so `backend/x` becomes `/app/x`), and `backend/.dockerignore` does not exclude `.json`. So the receipt and signature must be committed under `backend/` (they hold hashes and aggregate metrics only, no secrets) and shipped by `npx wrangler deploy --env staging`. No other delivery path exists in code. This also explains the ordering: receipt commit, then deploy, then flip the flags.
3. **One receipt covers exactly one provider.** `enable_staging` requires `providers == (assisted_provider_id,)`. The gate needs the configured `DECISION_PROVIDER` to be in the receipt, and only one receipt path is configured at a time. So Clef and NVIDIA each need their own run, approval, receipt and signature, and staging runs one at a time. Also the receipt names the provider, not the model: a receipt earned with `nvidia/nemotron-3.5-super-vl-120b-a12b` also admits the other pinned models (open question in PR #192). Keep `NVIDIA_MODEL` fixed to the evaluated one.
4. **006 T060b cannot be verified for Clef until a signed Clef receipt exists.** Setting `DECISION_PROVIDER=clef` counts as "decision runtime requested", and outside development/test the container refuses to start without a valid signed receipt naming that provider (`enablement_gate.validate_decision_enablement_startup`). Even the "flag off, expect CLEF_DISABLED 409" check needs a receipt first. T060b therefore sits at the end of the 007 chain. Verifying with the NVIDIA receipt exercises the same adapter and resolution machine (NVIDIA reuses the Clef adapter) but is not literally "Clef". Decide whether to rescope T060b to "the wired provider path" (recommended) or run a Clef evaluation too.

### Critical path (in order)

| # | Step | Who does the work | Hands-on time | Waiting |
|---|------|-------------------|---------------|---------|
| 1 | T082 approver key + allowlist PR | you | 30 min | PR review/merge, ~1 day |
| 2 | T010b corpus promotion and freeze | you (photos, labels) + agent for tooling | 20 to 40 h | 2 to 4 weeks calendar |
| 3 | Driver script for the 007 chain (`scripts/staging/run_007_evaluation.py`, T084; review the PR) | agent writes, you review | 1 to 2 h review | 1 day |
| 4 | Merge #191/#192, set provider secrets, deploy staging code | you | 1 h | build/deploy ~15 min |
| 5 | T020b live baseline vs provider run | you | 1 to 3 h | provider latency |
| 6 | T030b, T040b, T050a(code run), T060b pin | you | 1 h | none |
| 7 | T083 sign receipt | you (offline key) | 15 min | none |
| 8 | Commit receipt + signature, set staging vars (T050b), redeploy | you | 1 to 2 h | PR review + deploy |
| 9 | 006 T060b verify wired path on staging | you | 1 h | none |
| 10 | 008 T030b, T040b (needs design flags on staging + redeploy) | you | 2 to 3 h | deploy |
| 11 | 008 T050b/T072 pin docs, signed pin | you (offline key) + agent for driver | 1 to 2 h | PR review |

**Honest total:** about 30 to 55 hours of your time, roughly 3 to 5 weeks calendar. Step 2 is 70% of it. Without a corpus, nothing downstream can start (the validator refuses an empty manifest with `CORPUS_EMPTY`). Everything except step 2 is about 1.5 working days if there are no surprises; allow double for surprises (first live runs, the 008 staging walkthrough has never run against a hosted host).

Steps 1, 3 and 4 can run in parallel with step 2.

---

### Item 1. 007 T082: approver key pair

**What and why.** Create the Ed25519 key that signs the 007 evaluation receipt (T083) and the 008 readiness pin (T071/T072). Only the public key is committed. Until it is, every signed-receipt check refuses with `APPROVER_KEY_UNKNOWN` and no decision provider can run outside development.

**Current state.** `backend/intelligence/evaluation_approvers.json` has `"approvers": []`. Format from `backend/intelligence/receipt_signing.py`: `key_id` matches `^[a-z0-9][a-z0-9._-]{0,63}$`; `algorithm` is `ed25519`; `public_key` is base64 of the 32 raw public key bytes (strictly 32 bytes); `valid_from` is a timezone-aware ISO-8601 timestamp; `revoked_at` is optional and must be after `valid_from`. `key_id`s and public keys must be unique. The receipt's `approved_by` must equal the key id, so **use the key id as the `approved_by` value in step T040b**.

**Steps.**

1. On an offline or at least trusted Mac, make a private directory.

```bash
mkdir -p ~/patchhive-approver && chmod 700 ~/patchhive-approver
```

2. Save this generator as `~/patchhive-approver/gen.py` (it writes the private key PEM with mode 0600, refuses to overwrite, and prints only the public key).

```python
import base64, os, sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
out, key_id = sys.argv[1], sys.argv[2]
k = Ed25519PrivateKey.generate()
pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
os.write(fd, pem); os.close(fd)
pub = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
print(key_id, base64.b64encode(pub).decode())
```

3. Run it (needs the `cryptography` package; the system python3 here has it, or use the backend venv).

```bash
python3 ~/patchhive-approver/gen.py ~/patchhive-approver/approver-2026-11.pem approver-2026-11
```

4. Back the private key up (see "Where to keep it" below) before doing anything else.
5. In a branch, edit `backend/intelligence/evaluation_approvers.json` so `approvers` is (use the printed base64 for `public_key`, and a `valid_from` a few minutes in the past in UTC):

```json
{
  "key_id": "approver-2026-11",
  "algorithm": "ed25519",
  "public_key": "<base64 printed by gen.py>",
  "valid_from": "2026-11-02T12:00:00Z"
}
```

6. Open the PR (title must pass `pr-title.yml`, so use a conventional-commit title), get the code-owner review (main requires 1 approving review and code owner review), merge.

```bash
git checkout -b chore/007-t082-approver-key && git add backend/intelligence/evaluation_approvers.json && git commit -m "chore(007): add approver public key (T082)"
```

**Check it worked.**

```bash
cd backend && PYTHONPATH=. python3 -c "from intelligence.receipt_signing import load_approver_allowlist as l; print([k.key_id for k in l().approvers])"
```

Expect `['approver-2026-11']`. Existing tests (`backend/tests/unit/test_receipt_verification.py`) install throwaway keys in memory, so CI should stay green.

**Unblocks.** T083, the signed receipt, 005 T080 gate, 008 T071/T072, and 006 `gates_pass`.

**Time.** 30 min plus review wait.

**Risk / notes.**
- `valid_from` must be earlier than both the verification time and the receipt's `approved_at`, so do not set it in the future, and merge before you approve thresholds.
- Where to keep the private key: the `.pem` stays off GitHub, off Cloudflare, off the repo and off CI. Keep one copy in a password manager that supports file attachments or secure notes (store the PEM text), and one encrypted offline copy (an encrypted disk image or hardware-encrypted USB in a drawer). Do not put it in a synced folder (iCloud/Dropbox) unencrypted. The signing is done by hand on this machine only (T083, T072). Note: a password-protected PEM is better but the repo's helper snippets load it with `password=None`; if you encrypt it, pass the password to `load_pem_private_key` instead.
- **Rotation.** Add a second entry with a new `key_id` and new `valid_from` via a reviewed PR. Re-sign the receipt with the new key. Because the signature check requires `approved_by == key_id`, a new key means the receipt's `approved_by` changes, so a re-run of `approve_thresholds`/`pin_receipt` with the new id (receipt SHA changes; it is not just re-signing). Plan rotation as "re-run T040b to T083".
- **Revocation (lost or leaked key).** Set `revoked_at` on that entry (a timestamp that must be after its `valid_from`) via a PR. The verifier refuses any key whose `revoked_at` is at or before the verification time, whatever the receipt's `approved_at` says (`signature_failures`), so every receipt and pin that key signed stops verifying immediately, and staging refuses to start with that receipt. Re-sign with a new key as above. Remove nothing from the file; keep revoked entries for history.

---

### Item 2. 007 T010b to T083: corpus, live evaluation, approval, enablement, receipt, signature

**What and why.** Prove with real rig photos that a vision provider does not regress against the baseline, then record an approved, SHA-chained, signed receipt that lets that provider run on staging. Disposition stays with the 005 `DecisionPolicy`; the provider only supplies a packet.

**Current state.**
- `fixtures/vision_eval/pilot-manifest.json` has `"cases": []`, status `COLLECTION_OPEN_NOT_ADMITTED`. All code (T010a to T060a, T080, T081) is merged; T010b to T060b, T082, T083 are open (`specs/007.../tasks.md`).
- Admission rules (from `scripts/validate_vision_pilot.py`, which `freeze_corpus` runs): every case needs `RIGHTS_CONFIRMED` with a non-empty `source_url`, `annotation_status=REVIEWED`, `ground_truth_status` of `OPERATOR_VERIFIED` or `TWO_SOURCE_VERIFIED`, at least one reviewer, `none_of_above_allowed=true`, a `candidate_set_hash`, `expected_choice` (must be in `ground_truth_inventory` unless the partition is `unknown_open_set`, where it must be `none_of_above`), `image_asset_hashes` as `sha256:<64 hex>`, and a `contamination.used_for_tuning` flag. Corpus-level: **50 to 100 distinct identities**, all 8 cohorts (clear_front_panel, installed_rack, partial_occlusion, cable_obscured, low_light_or_glare, revision_or_panel_variant, hard_negative, unknown_open_set), and at least one case each in `validation`, `locked_test` and `unknown_open_set`. The same image hash in two partitions fails. A case in `locked_test` with `used_for_tuning=true` fails.
- The 2026-09-25 acquisition reported 43 RIGHTS_CONFIRMED images (`docs/evidence/PILOT_CASE_PROMOTION.md`), and those are candidates, not admitted cases. 43 is below the 50-identity minimum, so you need extra photos anyway. Public manufacturer/Commons images are weak for `locked_test` (pretraining exposure); the repo advises your own photos there.
- Jev decided 005 OQ-5 as `baseline_equal` (`docs/evidence/JEV_DECISIONS_2026-11-01.md`): thresholds equal the measured baseline (top-1 and top-k minimums; Brier, expected calibration error and abstention maximums), false canonicalization max 0. This is what `propose_thresholds` (rule `non_regression_vs_baseline.v1`) already does. You approve or reject that exact proposal; there is no override. In practice the provider must be at least as good as the baseline on every metric on the frozen corpus, or `enable_staging` raises `THRESHOLDS_NOT_MET`.

**Steps.**

*A. Promote cases (T010b).*

1. Collect photos. For your own shots use `fixtures/vision_eval/operator-shot-intake-template.json` (set `proposed_partition` to `locked_test` for clean ones and keep `used_for_tuning` false). Rights for your own photos: `RIGHTS_CONFIRMED`, `consent_record: operator-owned-photo`, `source_url: operator://local`.
2. If using the retained pilot bundle, build the review queue (only if `deliverables/patchhive-corpus/pilot-2026-09-25/` exists locally; it is not in the repo checkout).

```bash
python scripts/build_vision_promotion_queue.py --discovery deliverables/patchhive-corpus/pilot-2026-09-25/discovery-manifest.jsonl --modules deliverables/patchhive-corpus/pilot-2026-09-25/module-records.jsonl --output work/vision-pilot-promotion-queue.json
```

3. For each case, hash the image and fill `fixtures/vision_eval/pilot-case-template.json` fields by hand from retained evidence (identity, candidate set from the Device Registry including `none_of_above`, candidate_set_hash, scene conditions, exactly one cohort, partition, reviewer name). Never invent metadata to make validation pass.

```bash
shasum -a 256 path/to/photo.jpg
```

4. Add cases to `fixtures/vision_eval/pilot-manifest.json`. Rules of thumb: choose validation cases before looking at any provider output; freeze `locked_test` before any measurement and never tune on it; `unknown_open_set` cases expect `none_of_above`. Where do the image files live? The repo stores only hashes. Keep the originals in a private place (e.g. a private R2 bucket or an encrypted folder) and note it in your notes. **GAP:** no tool in the repo stores the raw corpus images; the live run needs them on your machine.
5. Validate until `ADMITTED_FOR_BASELINE`.

```bash
python scripts/validate_vision_pilot.py fixtures/vision_eval/pilot-manifest.json
```

6. Open a PR with the manifest (hashes and labels, no image bytes), merge. The corpus SHA is `corpus_manifest_sha256(manifest)`; it is computed and recorded in the next step.

*B to E with the driver (T084).* From the repo root with the backend venv. Artifacts go to `backend/intelligence/enablement/nvidia/` (override with `--dir`); nothing is ever overwritten, and any refusal prints its code and exits 1. First write a run-inputs file next to your private images (format in `specs/007.../OPERATOR_NOTES.md`, "Driver script": per case, the candidate options and the image paths) and record each case's `candidate_set_hash` in the manifest from:

```bash
python scripts/staging/run_007_evaluation.py --provider nvidia candidate-hashes --inputs ~/patchhive-corpus/run-inputs.json
```

Then, with `ENABLE_NVIDIA_PROVIDER=true` and `NVIDIA_API_KEY` exported in this shell only:

```bash
python scripts/staging/run_007_evaluation.py --provider nvidia freeze --manifest fixtures/vision_eval/pilot-manifest.json
python scripts/staging/run_007_evaluation.py --provider nvidia run --inputs ~/patchhive-corpus/run-inputs.json --harness-sha "$(git rev-parse HEAD)" --manifest fixtures/vision_eval/pilot-manifest.json
python scripts/staging/run_007_evaluation.py --provider nvidia propose --proposal-version thresholds-v1
python scripts/staging/run_007_evaluation.py --provider nvidia approve --approved-by approver-2026-11 --yes-i-approve
python scripts/staging/run_007_evaluation.py --provider nvidia enable-staging
python scripts/staging/run_007_evaluation.py --provider nvidia pin --source-commit-sha "$(git rev-parse HEAD)"
python scripts/staging/run_007_evaluation.py --provider nvidia sign --key ~/patchhive-approver/approver-2026-11.pem
python scripts/staging/run_007_evaluation.py --provider nvidia verify
```

`pin` and `sign` print the `DECISION_ENABLEMENT_RECEIPT_PATH` and `DECISION_ENABLEMENT_SIGNATURE_PATH` values for step 15 (`/app/intelligence/enablement/nvidia/receipt.json` and `.../signature.json`). `verify` must print `PASS`. The baseline condition is a deterministic no-model abstainer (fixture provider, `abstain-uniform.v1`). For Clef use `--provider clef` with `ENABLE_CLEF_PROVIDER`, `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_AI_API_TOKEN`. The notes below describe what each step does and its rules.

*B. Freeze and run the live evaluation (T010b freeze, T020b).* The driver does, in order: load the manifest, call `freeze_corpus(manifest)` and save the `CorpusFreeze` JSON; for each frozen case build a `LabeledCorpusCase` for the **baseline** (a non-provider condition; `fixture_provider.py` or a deterministic abstainer, `baseline_provider_id` must differ from the assisted id and every baseline packet's `provider` must equal it) and for the **assisted** condition by calling the real provider; call `run_baseline_comparison(corpus=..., baseline_cases=..., assisted_cases=..., policy=DecisionPolicy(PolicyThresholds(policy_version=<must equal DECISION_POLICY_VERSION, default "decision-policy-v1">, ...)), harness_sha=<40 or 64 hex git SHA>, baseline_provider_id=..., assisted_provider_id="nvidia" | "clef")`; save the `BaselineRun`. Both condition sets must cover exactly the frozen case ids; vision rows carry the image hash bound to the case; text-modality rows carry none.

7. Before the run, make the provider reachable from your machine, not from the container. For NVIDIA: `NVIDIA_API_KEY` from your NVIDIA account in your shell (name only; never paste it anywhere). Merge #191 and #192 first (they add the live smoke test and the 60 s staging timeout; the very first 120B call timed out at 20 s). Smoke-test with the opt-in test from #191.

```bash
cd backend && RUN_NVIDIA_LIVE=1 python -m pytest tests/integration/test_nvidia_live.py -q
```

(That test only exists once #191 is merged. Do not run it in CI; it needs the key in your shell only.) For Clef: the provider calls Cloudflare Workers AI with `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_AI_API_TOKEN`; `intelligence/clef_provider.py` is the client.

8. Pin the harness SHA: the commit you run from (`git rev-parse HEAD`, must be a pushed commit on main so it is reproducible). If you prefer a content hash, `harness_source_sha256()` exists.
9. Run once on the frozen corpus. Do not iterate on prompts/models after seeing `locked_test` results; if you must, the corpus is burned for locked_test and you need new cases. Expected runtime: depends on corpus size; the logged NVIDIA calls took 0.5 to 1.7 s for Nemotron, 7 to 48 s for the Llama 90B fallback (PR #192 body), so 100 cases is minutes for Nemotron.

*C. Propose, approve, enable, pin (T030b, T040b, T050, T060b), all in the driver.*

10. `propose_thresholds(run, proposal_version="...")`. Review the printed proposal (the baseline numbers). If the assisted metrics do not meet them, stop: `enable_staging` will refuse. Do not edit thresholds by hand.
11. `approve_thresholds(proposal, approved_by="approver-2026-11", approved_at=<tz-aware now, after the allowlist key's valid_from>, explicit_sign_off=True)`. **`approved_by` must be exactly your key id** or the signature check fails with `SIGNATURE_KEY_NOT_APPROVER`.
12. `enable_staging(approval=..., run=..., settings_obj=<Settings with environment="staging">, target_environment="staging", providers=("nvidia",))`. This is an authorization record only; it checks payments stay off, the Clef flag class default is off, no D1, and thresholds met. It changes no settings.
13. `pin_receipt(corpus=..., run=..., proposal=..., approval=..., staging=..., source_commit_sha=<the commit the harness ran from>)`. Save the receipt JSON (`receipt.model_dump_json(indent=2)`).

*D. Sign (T083), offline, on the machine with the key.* Save as `~/patchhive-approver/sign.py`:

```python
import json, sys
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from intelligence.receipt_signing import sign_receipt_sha256
pem, key_id, receipt_path, out = sys.argv[1:5]
key = serialization.load_pem_private_key(Path(pem).read_bytes(), password=None)
sha = json.loads(Path(receipt_path).read_text())["receipt_sha256"]
Path(out).write_text(sign_receipt_sha256(key, key_id=key_id, receipt_sha256=sha).model_dump_json(indent=2) + "\n")
print("signed", sha)
```

```bash
PYTHONPATH=backend python3 ~/patchhive-approver/sign.py ~/patchhive-approver/approver-2026-11.pem approver-2026-11 receipt-nvidia.json receipt-nvidia.signature.json
```

(I tested this exact code against the repo with a throwaway key; it produces a valid `patchhive.eval-receipt-signature.v1` file.)

*E. Verify locally before deploying.*

```bash
cd backend && PYTHONPATH=. python3 -c "import json;from intelligence.evaluation_enablement import EvaluationEnablementReceipt as R, signed_enablement_receipt_failures as f;from intelligence.receipt_signing import ReceiptSignature as S;print(f(R.model_validate(json.load(open('../receipt-nvidia.json'))),S.model_validate(json.load(open('../receipt-nvidia.signature.json')))))"
```

Expect `()`.

*F. Ship the receipt to staging and enable the provider (T050b).*

14. Put the two JSON files in the repo under `backend/`, for example `backend/intelligence/enablement/nvidia/receipt.json` and `.../signature.json` (path is my suggestion; any path under `backend/` works).
15. In `edge/api/wrangler.jsonc` `env.staging.vars` add (staging only; production must stay without them):

```jsonc
"ENABLE_DECISION_INTELLIGENCE": "true",
"DECISION_PROVIDER": "nvidia",
"ENABLE_NVIDIA_PROVIDER": "true",
"NVIDIA_MODEL": "nvidia/nemotron-3.5-super-vl-120b-a12b",
"DECISION_ENABLEMENT_RECEIPT_PATH": "/app/intelligence/enablement/nvidia/receipt.json",
"DECISION_ENABLEMENT_SIGNATURE_PATH": "/app/intelligence/enablement/nvidia/signature.json"
```

All six names are already in `FLAG_VARS` in `edge/api/src/index.ts`, and `NVIDIA_API_KEY` is in `STAGING_SECRETS`. For Clef instead: `DECISION_PROVIDER=clef`, `ENABLE_CLEF_PROVIDER=true`, plus secrets `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_AI_API_TOKEN`. Also check `DECISION_POLICY_VERSION` equals the receipt's `policy_version` (default `decision-policy-v1`; the gate fails with `ENABLEMENT_POLICY_VERSION_MISMATCH` otherwise; it is not forwarded by the edge, so only change the evaluation side, not staging).

16. Check which staging secrets exist (names only, no values).

```bash
cd edge/api && npx wrangler secret list --env staging
```

17. If `NVIDIA_API_KEY` (or the Clef pair) is missing, set it from your shell (prompts for the value; never put it on the command line).

```bash
cd edge/api && npx wrangler secret put NVIDIA_API_KEY --env staging
```

18. Merge the PR (receipt + wrangler vars), then deploy (needs Docker running and the Workers Paid plan).

```bash
cd edge/api && npm ci && npx wrangler deploy --env staging
```

**Check it worked.**

```bash
curl -s https://api-staging.patch-hive.com/health/ready
```

Expect HTTP 200 `status: healthy`. If startup refuses, the container does not become healthy; the refusal message lists failure codes (for example `APPROVER_KEY_UNKNOWN`, `ENABLEMENT_PROVIDER_NOT_COVERED`, `ENABLEMENT_RECEIPT_UNREADABLE`) in the Worker/container logs (`npx wrangler tail --env staging`). Also `python scripts/check_spec_dag.py --strict` is the repo's DAG check; tick T010b to T083 in `specs/007.../tasks.md` through a docs PR when each is done.

**Unblocks.** 006 T060b, 005 provider use on staging, 008 T050b/T072 (needs the signed receipt), and the 006 `gates_pass` readiness guard.

**Time.** Corpus 20 to 40 h (the bottleneck). Everything else in this item: 4 to 8 h once the driver exists.

**Risk / notes.**
- The corpus is the part only you can do (rights and ground truth are human judgments). The validator is fail-closed, so "I have 43 images" will not pass; a lower admitted count is acceptable evidence, a fabricated one is not.
- Production never runs a decision provider (`core/startup_policy.py` refuses the flags in production). This chain enables staging only.
- NVIDIA hosted API catalog terms: the repo notes it is governed by NVIDIA's API trial terms, and production use needs the paid or program entitlement (NVIDIA Inception) confirmed first (`specs/006.../DEPLOY_NOTES.md`). I did not re-verify NVIDIA's current terms; check them before anything beyond staging.
- Sending corpus images to a hosted provider: only send images whose rights allow third-party processing; operator-owned photos are fine.
- The receipt names the provider, not the model (PR #192 open question). Keep the model fixed or re-evaluate on change.
- `source_commit_sha` in the receipt: use the commit the harness ran from. Committing the receipt creates a later commit; that is expected.

---

### Item 3. 006 T060b: verify the wired provider path on the Neon-backed staging API

**What and why.** Show that `POST /api/racks/{rack_id}/evidence/decision-resolution` works end to end on staging: provider call, policy disposition, receipt persisted, no canonical inventory change.

**Current state.** Code done (T060a). Staging `/health/ready` is 200 with `database: ok` (`docs/evidence/006_OPERATOR_TASK_RECEIPTS_2026-11-01.md`). T060b depends on 006 T050 (closed). In practice it also depends on Item 2 (finding 4). Nothing in the repo currently uploads a test evidence record to staging.

**Code gap fixed (found in review, 2026-11-02).** The mock vision provider gave candidates an `evidence-<hash>` id while the upload stored the classification evidence under a separate `ev-<uuid>` id, so the id from the candidates endpoint answered 404 at the resolution route. The upload now binds every candidate to the stored record id (`bind_packet_to_evidence` in `backend/evidence/vision_provider.py`), so the id the candidates endpoint returns is the id the resolution route accepts. `backend/tests/api/test_evidence_upload.py` covers upload, candidates, resolution, idempotent replay and the other-rack refusal. The fix must be deployed to staging first. Evidence uploaded before the fix keeps the old id and still cannot be resolved; upload a fresh image in step 2.

**Steps.** (After Item 2 step 18, and after the fix above is deployed to staging.)

1. Log in to staging as a staging user you own (the seeded `golden_demo` account from Item 4 works; its password is in your shell env `PATCHHIVE_DEMO_USER_PASSWORD`). Login route: `POST /api/community/auth/login` (as used by `backend/core/ops/design_walkthrough.py`). Do not paste the password into notes.
2. Upload one test image you own to a private rack with provider consent: `POST /api/racks/{rack_id}/evidence/images` (multipart: `files`, `consent_provider_processing=true`). The response lists the image asset; classification evidence records are created with it.
3. Find the evidence id via `GET /api/racks/{rack_id}/evidence/candidates` or the evidence listing in the same router.
4. Call the resolution once, then again with the same `idempotency_key` to check idempotency.

```bash
curl -s -X POST https://api-staging.patch-hive.com/api/racks/RACK_ID/evidence/decision-resolution -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"evidence_id":"EVIDENCE_ID","idempotency_key":"t060b-1"}'
```

**Check it worked.** HTTP 200 with a `disposition` and `selected_choice`; the second call with the same key returns the same decision; `GET .../evidence/candidates` shows `decision_advisory` for that candidate; no inventory revision was minted (advisory only). Failure paths to know: 409 `DECISION_INTELLIGENCE_DISABLED`, 409 `ENABLEMENT_RECEIPT_REQUIRED` (receipt/signature problem), 409 `NVIDIA_DISABLED`/`CLEF_DISABLED` (flag off), 504 timeout, 502 unavailable. Record the result as a short line in `docs/evidence/` through a docs PR (same style as `006_OPERATOR_TASK_RECEIPTS_2026-11-01.md`).

**Unblocks.** Closes 006 T060b and the Clef/NVIDIA staging claim.

**Time.** 1 h.

**Risk / notes.** Writes one test image, evidence row and decision receipt into the Neon staging database and R2 staging bucket. The image sent to the provider must be one you can legally send. 90-day evidence retention applies (#193). I could not verify the exact evidence-id lookup call on a live host; confirm with `GET /api/racks/{rack_id}/evidence/candidates` output (the field `evidence_id` exists in its items per `backend/evidence/routes.py`).

---

### Item 4. 008 T030b and T040b: seeded auth and the Design Engine walkthrough on staging

**What and why.** T030b proves the seeded demo accounts on the staging database are aligned (exist with the expected password and role). T040b runs the Design Engine walkthrough (preview, credit grant, export debit, fulfillment, download token, pack download) against the hosted staging API with test payments only, and writes a SHA-sealed receipt.

**Current state.** `scripts/staging/design_engine_walkthrough.py` exists and passed in-process only (`specs/008.../OPERATOR_NOTES.md`). It: seeds the golden demo into the DB given by `DATABASE_URL`, runs `check_seed_auth` (read-only), then talks to `STAGING_API_URL`, reads the target's flags from `GET /api/admin/ops/runtime-flags`, and refuses unless they show the design engine and canon export fulfillment on, `STRIPE_TEST_MODE=true`, `ALLOW_PRODUCTION_PAYMENTS=false`, and `environment == "staging"`. **Staging does not currently set the design-engine flags**: `edge/api/wrangler.jsonc` only has them as a comment. The local compose overlay (`docker-compose.staging.design-engine.yml`) shows the intended set: `ENABLE_PATCHBOOK_DESIGN_ENGINE`, `ENABLE_CANON_EXPORT_FULFILLMENT`, `ENABLE_INLINE_EXPORT_FULFILLMENT` true, `ENABLE_PATCHBOOK_PUBLICATION_PROFILE` false. All four names are forwarded by `FLAG_VARS`. The overlay also sets `REQUIRE_SEALED_GENERATED_PATCHES=false` and `DESIGN_ENGINE_DEFAULT_TIER=core`, which the edge does not forward, so I cannot confirm the container defaults are enough. **UNKNOWN: whether staging's code is current main** (staging reports `0.3.0-alpha.5`; the `runtime-flags` route must exist or the script fails closed on a 404).

**Steps.**

1. PR: add the three true flags and the publication profile false to `env.staging.vars` in `edge/api/wrangler.jsonc` (keep `STRIPE_TEST_MODE` true and `ALLOW_PRODUCTION_PAYMENTS` false). Merge, then deploy staging.

```bash
cd edge/api && npx wrangler deploy --env staging
```

2. Choose two long (16+ characters) demo passwords. They are NOT stored in the repo, the Worker or the container; they only live in the DB hashes and your shell. Hosted DBs refuse the published `demo-pass`/`admin-pass` (`scripts/seed_golden_demo.py::demo_passwords`).
3. Get the Neon **staging** branch connection string from the Neon console (the one you gave the Worker as `DATABASE_URL`, or a direct/non-pooled one). Export it in a throwaway shell, never in a file or ticket. `ENVIRONMENT=staging` is mandatory; without it the seeder refuses a hosted host.

```bash
export ENVIRONMENT=staging PYTHONPATH=backend STAGING_API_URL=https://api-staging.patch-hive.com
```

4. Then set the secrets in the same shell (type the values; they are not echoed in this guide): `DATABASE_URL`, `PATCHHIVE_DEMO_USER_PASSWORD`, `PATCHHIVE_DEMO_ADMIN_PASSWORD`. Use `read -s` so nothing lands in shell history.

```bash
read -s "DATABASE_URL?Neon staging URL: " && export DATABASE_URL
```

5. **T030b:** seed and verify. The seeder is idempotent and the walkthrough re-checks alignment read-only. Run seeding explicitly first.

```bash
python scripts/seed_golden_demo.py
```

6. Check out the exact commit to pin and make sure it is the one deployed. Optionally pin it.

```bash
export WALKTHROUGH_SOURCE_SHA=$(git rev-parse HEAD)
```

7. **T040b:** run the walkthrough.

```bash
python scripts/staging/design_engine_walkthrough.py --receipt-out design-walkthrough-receipt.json
```

**Check it worked.** Output ends with `WALKTHROUGH PASS receipt_sha256=<64 hex>` and `source_commit_sha=<sha>`. `aligned=True` in the seed auth line is the T030b evidence. On failure it prints codes only, for example `SEED_AUTH...`, `SERVER_FLAGS_UNVERIFIABLE`, `FLAGS_NOT_TEST_MODE`, `SERVER_ENVIRONMENT_MISMATCH`, `SERVER_FLAGS_CHANGED`, and writes no receipt. Keep `design-walkthrough-receipt.json` (it holds hashes and step outcomes, no passwords or pack bytes).

**Unblocks.** 008 T050b/T072 and the BETA_ELIGIBLE evidence decision.

**Time.** 2 to 3 h including the deploy and a likely first-run failure.

**Risk / notes.**
- This writes to the live Neon staging DB: it creates/updates the demo users, a rack, and truncates and recreates the rack's runs, plus credits, ledger and export rows, and writes packs to the staging R2 bucket. Staging only; never point `DATABASE_URL` at the production branch. Production is refused by the seeder only if `ENVIRONMENT` says production, so double-check the URL host.
- The script's default `DATABASE_URL` (a local compose URL) is used if the env var is not set; always set it explicitly.
- I did not run the script and could not verify the staging container's other design-engine defaults; the first run will tell you.

---

### Item 5. 008 T050b / T072: pin the readiness docs with the signed receipt and a signed pin

**What and why.** Bind `docs/evidence/PRODUCTION_READINESS_MATRIX.md` and `docs/evidence/DOMAIN_CUTOVER_CHECKLIST.md` to the walkthrough commit SHA and the signed 007 receipt, producing a `ReadinessPin` signed with the same approver key. This is evidence only; it flips no flag and enables no payments.

**Current state.** The placeholders `PENDING_OPERATOR_WALKTHROUGH` are in `PRODUCTION_READINESS_MATRIX.md` (`walkthrough_source_sha`, `walkthrough_receipt_sha256`, `enablement_receipt_007_sha256`, `unresolved_p0`) and `DOMAIN_CUTOVER_CHECKLIST.md` (`walkthrough_source_sha`, `walkthrough_receipt_sha256`, and more). `pin_readiness_docs(receipt, documents, unresolved_p0, enablement_receipt, enablement_signature, pinned_by, signing_key, ...)` is in `backend/core/ops/f5_cutover.py` (T071 merged in #186). It refuses unless: the walkthrough receipt is intact, the 007 receipt and its signature verify against the committed allowlist, both docs contain the walkthrough `source_commit_sha`, and the P0 list is empty. **There is no CLI and no script for this** (GAP; same driver-script need as Item 2). Also `unresolved_p0` must be empty: open P0 regressions block the pin; I did not check the current P0 list.

**Steps.**

1. Have the walkthrough bundle (`design-walkthrough-receipt.json`, Item 4), the 007 receipt and signature (Item 2), and your private key.
2. In both docs, replace every `PENDING_OPERATOR_WALKTHROUGH` with the real value (walkthrough `source_commit_sha`, walkthrough `record_sha256`, the 007 `receipt_sha256`, an empty P0 list). Do not commit yet.
3. On the machine with the key, run a small script (to be written; not in the repo) that loads the `WalkthroughReceipt` from the bundle, the `EvaluationEnablementReceipt` and `ReceiptSignature`, reads the two edited docs into a dict `{repo-relative path: text}`, loads the PEM, and calls `pin_readiness_docs(..., pinned_by="approver-2026-11", signing_key=<key>)`. It must print the resulting pin JSON (`pin_signature`, `pinned_at`).
4. Replay the five machine events (`expose_canon_alias`, `switch_fe_list`, `run_walkthrough`, `capture_receipt`, `operator_pin`) and check `beta_eligible(machine)` is true (per `specs/008.../OPERATOR_NOTES.md` step 5; the test `backend/tests/integration/test_008_f5_cutover_machine.py` shows the call sequence to copy).
5. Commit the edited docs, the 007 receipt/signature copies (if not already committed) and the pin JSON through a PR. The docs commit is later than the walkthrough SHA; that is fine (the check is that the doc text contains the walkthrough SHA).

**Check it worked.** `pin_readiness_docs` returns without raising `CutoverError`; `beta_eligible` is true; no `PENDING_OPERATOR_WALKTHROUGH` remains.

```bash
grep -rn PENDING_OPERATOR_WALKTHROUGH docs/evidence/PRODUCTION_READINESS_MATRIX.md docs/evidence/DOMAIN_CUTOVER_CHECKLIST.md
```

Expect no output.

**Unblocks.** Closes 008 T050b and T072, 008 BETA_ELIGIBLE (terminal), and the cutover checklist evidence.

**Time.** 1 to 2 h once the driver exists and Items 2 and 4 are done.

**Risk / notes.** The pin signature uses the same private key under its own domain (`patchhive.readiness-pin.v1`), so it cannot be replayed as a receipt approval. Revoking the key (Item 1) invalidates the pin as well. Use the signed 007 receipt for the provider you actually enabled.

---

### Gaps list (things the repo does not provide)

1. ~~Driver script for 007~~ Closed by T084: `scripts/staging/run_007_evaluation.py` (freeze, run against a live provider or a `--dry-run` fixture, propose, approve, enable-staging, pin, sign, verify; JSON artifacts). Commands in Item 2 and `specs/007.../OPERATOR_NOTES.md`.
2. Driver script for the 008 pin and the five-event replay. Needs writing.
3. A reproducible location and tool for the raw corpus images (the repo holds only hashes).
4. A mechanism to deliver receipt files to staging other than committing them under `backend/` and redeploying.
5. 006 T060b is blocked on a signed receipt for the provider used; rescope or run a Clef evaluation.
6. Staging code currency and the container's design-engine defaults are unverified by me.
7. NVIDIA terms for anything beyond staging were not re-verified; the repo's own note says confirm the entitlement.

Sources used: repository files cited above; PRs #191 and #192 (via `gh pr view`, read-only). No outside web sources were needed; I did not verify Cloudflare or NVIDIA documentation online. The Wrangler commands used (`wrangler secret put/list`, `wrangler deploy --env staging`) are the ones in `edge/api/wrangler.jsonc` comments and `specs/006.../DEPLOY_NOTES.md`; `wrangler secret list` is standard Wrangler but is not mentioned in the repo.

---

## Decisions, legal brief, prices, maker emails, spec confirmation, production checks

Verified against `Zero-State-LLC/Patch-Hive` main (`9dba804`, 2026-11-02), read-only. Nothing was sent, changed or run. Outside facts from web searches are marked "search result"; check them on the linked page before you rely on them.

Order of sections, by what each unblocks:

1. Spec confirmation (T001): unlocks plan.md for four specs.
2. The seven provisional Jev decisions, plus the steps for the one that needs an operator action.
3. Maker outreach: unlocks closing 003 T039 (17 HP values).
4. Production sign-up test and VirusTotal reanalysis.
5. Legal brief for a lawyer.
6. Prices (not urgent: sales are deferred).

---

### 1. T001 spec confirmations (specs 001, 002, 003, 004)

**What and why.** Each of the four specs was drafted by a model from repo docs and code. Every claim is tagged `[OBSERVED: file]` (read from a source) or `[INFERRED]` (a rule derived it). "Confirm the spec" means you read the `[INFERRED]` claims and say, per claim, "yes, that is how the product should work" or "no, change it to X". You are not checking code. Your answers let Claude write `plan.md` (T002), which in turn unlocks T010 (the transitions-table tests are already written, but each tasks.md says T010 "stays open until T002").

**Current state (verified).**
- `specs/00{1,2,3,4}-*/tasks.md` line 5: `T001 Confirm the spec with the operator` is unchecked in all four. T002 depends on T001; T010 depends on T002.
- `[INFERRED]` lines in spec.md: 001 about 45, 002 about 51, 003 about 50, 004 about 78 (grep count of lines).
- Spec 003 already has owner decisions D1 to D8 (lines 5 to 30) that override INFERRED text where they differ, so its sitting is the shortest. 003 OQ-8 (Jev, 0.94) says walk the rest in one sitting; research 003 R6 says one sitting per spec, starting with 003.
- Many INFERRED rows are already implemented and tested, so you mostly confirm intent, not facts.

**Steps.**
1. Open the spec: `specs/003-catalog-dataset-pipeline/spec.md` first, then 001, 002, 004.
2. For each checklist group below, read the cited lines and reply in chat to Claude with "confirm" or the correction. "Confirm all of section X" is enough.
3. Claude then ticks T001 in that tasks.md and writes plan.md (T002).

Checklists (claims to confirm or correct; line numbers are spec.md lines):

**001 rig-intelligence**
- [ ] A run selects a rig revision, loads its confirmed inventory only, and fails closed with a `NOT_COMPUTABLE` receipt (no queued run) when readiness fails (lines 80 to 81, 113 to 119, FR-022, SC-006).
- [ ] Patch pages and the Patch Book are out of scope here (line 96).
- [ ] Confirming a module creates a new rig revision, never edits the old one (line 161). Rollback means selecting an earlier revision, never deleting (line 266).
- [ ] Run lifecycle `IDLE, RIG_LOADED, QUEUED, RUNNING, SUCCEEDED, FAILED, NOT_COMPUTABLE` and the illegal moves in lines 338 to 343 (FAILED never becomes SUCCEEDED; a new revision starts again from IDLE).
- [ ] Module evidence lifecycle `PROPOSED, CONFIRMED, REJECTED`; evidence never skips the proposal step (lines 361 to 391).
- [ ] A module matching two classes (VCO and LFO) may serve in more than one role (line 425); whether it may fill two roles in one patch is still open.
- [ ] Photos and overlays "may be personal" (line 264), the assumption behind the retention decision (2.1).

**002 patch-book-publishing**
- [ ] With the flag off, every publishing request fails closed and changes no state (lines 138, 244, SC-006).
- [ ] A publish needs an export bound to a validated book (lines 139, 260, FR-048). Today it always refuses (OQ-6 `keep_off`).
- [ ] Draft or hidden publications are invisible to non-owners; the gallery shows only `published` and `public` (lines 151, 255).
- [ ] A removed publication refuses every transition; `draft` to `hidden` and `draft` to `removed` stay illegal (lines 173, 345 to 347).
- [ ] Reports on draft, hidden or removed publications are rejected (lines 353, 511).
- [ ] No model or decision-layer component may change publication status or moderate (lines 261, 354).
- [ ] Page and book compile machines: states `queued`, `remediating`, `collecting`, `emitted`, `failed`; deterministic remediation order; "no accepted pages means the book fails" (lines 379 to 476). Not implemented yet.
- [ ] Out of scope: multi-page profiles, Style Studio and Design Engine, patch generation (lines 89 to 92).
- [ ] Concurrent owner and admin acts: admin wins (line 510; built in #197).

**003 catalog-dataset-pipeline** (read the "Owner decisions" block first; it overrides)
- [ ] Batch lifecycle states and illegal moves (lines 242 to 280): BLOCKED, RETRY_QUEUED, FILTERED, OVERLAY, REJECTED. These exist only as scripts today.
- [ ] FR-003: a paid fetch never starts without a recorded approval (built in #196, `receipts/fetch-approvals.json`, empty).
- [ ] FR-017, FR-018, FR-020, FR-031, FR-032: residual targets file, versioned content-hashed overlays, admission needs approval of a receipt binding the current overlay, per-run rollback, no model output moves a row past evidence-only.
- [ ] Case catalog uses the same pipeline (FR-029, line 215).
- [ ] Edge cases (lines 419 to 436): wrong HP on a page is evidence only; private source stays out of the repo; ADVERSARY reviews untrusted page content.
- [ ] Line 426 slug collision: checked 2026-11-01, slugs are brand plus name and globally unique, so only the wording needs fixing (OQ-6).
- [ ] Sealed seed path (line 304): Jev chose a separate SEEDED/SEALED state (OQ-4, 0.68). Confirm; the seed is a scrape-derived discovery lead (D1).

**004 commerce**
- [ ] Commerce never influences patch generation or visibility (lines 83, 223 FR-035, SC-006).
- [ ] Refund, tax, invoicing and legal terms are not defined here (lines 86 to 87) and stay NOT_COMPUTABLE until counsel.
- [ ] Unlimited is an explicit entitlement flag, not 999999 (FR-004). The ledger is append-only (FR-008). Every provider event is verified first; unverifiable ones end `Unresolved` with zero credits (FR-013, FR-014).
- [ ] Subscription credits are granted once per billing period (FR-016). Cancelling keeps granted credits; credits do not expire (line 149).
- [ ] Every provider-confirmed purchase, one-time or subscription, goes through the single path that evaluates referrals (FR-028, FR-032, FR-033).
- [ ] A referral code must not reveal an email address (FR-036).
- [ ] Machine B (checkout) and Machine C (subscription) tables (lines 300 to 375), including "Unresolved exits only through operator action".
- [ ] Payments off by default; flag off leaves the ledger unchanged (lines 151 to 159, SC-007).
- [ ] Edge cases EC-1 to EC-13 (lines 421 to 434), notably EC-13: a referrer who later deletes their account.

**Check it worked.** `grep -n "T001" specs/00{1,2,3,4}-*/tasks.md` shows `[x]` for each confirmed spec.

**Unblocks.** T002 plan.md for each spec, then closing T010, then T090 (converge code against spec).

**Time.** About 45 to 90 minutes per spec (003 shortest, 004 longest). Four sittings.

**Risk / notes.** Nothing is deployed by this. If you correct an INFERRED claim that code already implements, Claude will list the drift and propose a follow-up.

---

### 2. The seven provisional Jev decisions

Source: `docs/evidence/JEV_DECISIONS_2026-11-01.md` and `jev-decisions-2026-11-01.json`. "Provisional" means Jev confidence below 0.5. Merged PRs checked with `gh pr view`: #193, #194, #195, #196, #197, #198, #200 are all MERGED.

#### 2.1 001 OQ-10: retention for rig photos, OCR, overlays (0.29; lawyer must confirm)
- **Question.** How long are photos, OCR output and user overlays kept, and who can see them?
- **Jev's pick.** `minimal_images_only` (0.47): keep the 30-day default, cap at 90, schedule expiry, add user delete; leave overlays, ledger and account deletion for later.
- **Alternatives.** `adopt_proposed_table` (0.45, the repo's earlier recommendation: 1 year exports, 7 year ledger, 30 day logs); `shorter_images_strict` (0.03: 7 day default, 30 max); `status_quo_document` (0.05).
- **Built on it.** #193 (merged): a requested retention above 90 days is refused (`RETENTION_DAYS_INVALID`); owner delete soft-deletes the row and removes the stored file. Not built: scheduling `evidence.expire` (waits for 006 T101b/T101c). Existing images keep their stored retention (up to 365 days) until they expire or are deleted. #194 later added overlay and evidence deletion on account closure.
- **Recommendation.** Confirm. The two top options were 0.47 vs 0.45 and the code now covers most of the other. Two follow-ups for you: decide whether old 365-day images should be shortened (a data fix), and do 2.8 so the expiry job can be scheduled.

#### 2.2 002 OQ-12: licence for published patch books, CC BY-NC and `allow_remix` (0.39; lawyer must confirm)
- **Question.** What is the legal effect of the hard-coded CC BY-NC 4.0 default, and what should `allow_remix` mean?
- **Jev's pick.** `owner_picks_license` (0.54): add a licence choice mapped from `allow_remix` (remix false means a NoDerivatives variant).
- **Alternatives.** `keep_ccbync_default` (0.33: `allow_remix` becomes a UI hint); `all_rights_reserved` (0.03); `no_public_sharing` (0.10: defer while the flag is off).
- **Built on it.** Nothing. Publishing is off and draft-to-publish always answers 409 `PUBLICATION_BOOK_NOT_VALIDATED`. No licence schema change was made.
- **Recommendation.** Change to `no_public_sharing` (defer): publishing is off and the JSON marks this "hard" to reverse once a licence is granted. Revisit after counsel answers (section 5, question 4).

#### 2.3 002 OQ-13: report rate limits, anonymous reports, retention (0.34; lawyer must confirm)
- **Question.** Rate limits, whether anonymous reports are allowed, how long reports and audit logs are kept.
- **Jev's pick.** `limit_and_require_dedupe` (0.56): keep anonymous, rate-limit, dedupe; retention undecided.
- **Alternatives.** `auth_only_with_retention` (0.42: login required, reports kept 1 year after resolution, audit 7 years); `as_built` (0.02).
- **Built on it.** #197 (merged): `POST /p/{slug}/report` limited to 10 per hour per client address (429 `REPORT_RATE_LIMIT`); a signed-in reporter who repeats a report gets `already_reported`; anonymous reports are rate-limited but not deduped; no schema change; retention not decided. Spec 002 T037.
- **Recommendation.** Confirm for now (publishing is off, the change is cheap and reversible). Take retention to counsel (section 5, question 5); reporter ids are personal data.

#### 2.4 002 OQ-15: threat model for public publishing surfaces (0.43)
- **Question.** Write the ADVERSARY threat model for `/p/{slug}`, download, gallery and report now, or only when the flag returns?
- **Jev's pick.** `threat_model_now` (0.62).
- **Alternatives.** `when_flag_returns` (0.37, the repo's earlier recommendation); `skip` (0.01).
- **Built on it.** #195 (merged, docs only): a threat model in spec 002 (and one for the evidence boundary in spec 001). It names a likely stored XSS: `backend/export/visualization.py` puts rack, case and module names into SVG without escaping and `/p/{slug}/download/svg` serves it (found in code, not confirmed by a test). Other gaps: uploads read fully into memory before the size check; no production image scanner chosen; no rate limit on public publishing routes other than reports.
- **Recommendation.** Confirm. The document exists and found a real gap. Ask Claude to open a task for the SVG escaping before publishing is ever enabled.

#### 2.5 003 OQ-1: the 17 legacy HP values with no maker source (0.49)
- **Question.** What to do with the 17 modules whose HP only the old v1 list states (`legacy_unsourced`) so `UNSOURCED_HP_OVERLAYS` can be retired.
- **Jev's pick.** `ask_makers` (0.62).
- **Alternatives.** `accept_marked_and_close` (0.21: keep labelled permanently, close T039); `flag_unresolved` (0.15: block placement of the 17); `owner_correct_from_retailer` (0.02: against FR-027).
- **Built on it.** #180 (retailer evidence for the 57: 40 agree and read `retailer_observed`, 6 disagree, 11 not found); #200 (eight hand-checked maker HP values, 003 OQ-2). No code depends on the pick; T039 stays open.
- **Recommendation.** Confirm and send the emails in section 3. If there is no reply in about 4 weeks, fall back to `accept_marked_and_close` for the rest.

#### 2.6 006 OQ-1: protecting the GitHub `production` environment (0.36)
- **Question.** How is `production` protected for `db-migrate`, `db-load`, `edge-secrets` (T101b)?
- **Jev's pick.** `owner_reviewer_main_only` (0.52): you as required reviewer, deployment branch `main` only, admin bypass off, "Prevent self-review" OFF while solo, prod secrets moved into the environment.
- **Alternatives.** `two_reviewers` (0.46: four-eyes, needs a second person with repo access; the research note says two admin collaborators exist); `main_only_no_reviewer` (0.01); `leave_as_is` (0.01).
- **Built on it.** #160: the three workflows already set `environment:` (verified: `db-load.yml:49`, `edge-secrets.yml:33`, `db-migrate.yml:25`). Verified with `gh api repos/Zero-State-LLC/Patch-Hive/environments`: environments `production` and `staging` exist with NO protection rules and no branch policy. Only T101c (daily evidence expiry) depends on it.
- **Recommendation.** Confirm, and do the steps in 2.8.

#### 2.7 004 OQ-1: tier prices and credit quantities (0.29; lawyer must confirm)
- **Question.** Ratify $4.99/$14.99/$29.99, 25/100/unlimited credits, $0.20 per credit, $5 minimum, USD only?
- **Jev's pick.** `A_ratify_as_is` (0.47).
- **Alternatives.** `B_adjust_ladder` (0.19), `C_credits_first` (0.17), `D_regional_tax` (0.17).
- **Built on it.** Nothing charges. Sales are deferred (004 OQ-13 `D_defer_sales`, 0.95); Machines B and C (T046, T049) and resolve (T048b) are not built. (Correction 2026-11-06: they were built on 2026-11-02 behind flags that stay off.) #184 (admin reject of unresolved events) and #183 (referrals need a verified purchase) do not depend on prices.
- **Recommendation.** Change the record to "not ratified; revisit when counsel has drafted terms". When you do ratify, use the sheet recommended in section 6 (not A).

#### 2.8 Operator steps for 2.6 (GitHub `production` environment)
Source: `specs/006-cloudflare-edge-clef/DEPLOY_NOTES.md`, "Production protection for the manual workflows (T101)".

**What and why.** Stops any dispatched branch workflow from reaching production DB and Cloudflare secrets, and adds an approval click before each production run.

**Current state.** Environments exist with no rules (read via API). Repo-level secrets still hold `PATCHHIVE_DATABASE_URL_PROD` and `CLOUDFLARE_API_TOKEN`, and the repo variable `CLOUDFLARE_ACCOUNT_ID`, per DEPLOY_NOTES; I did not read secret names.

**Steps** (repo admin, GitHub UI):
1. Repo `Zero-State-LLC/Patch-Hive`, Settings, Environments, `production`.
2. Tick Required reviewers, add yourself. Leave "Prevent self-review" OFF. Untick "Allow administrators to bypass configured protection rules".
3. Deployment branches and tags: Selected branches and tags, add rule `main`.
4. Optionally open `staging` (no reviewers) for the staging secrets.
5. Add the environment secret `PATCHHIVE_DATABASE_URL_PROD` to `production`.
6. In Cloudflare, issue a second, staging-scoped API token (DEPLOY_NOTES: Account API Tokens Edit, Workers Scripts Edit). Put the production token in `production` and the staging token in `staging`, both as `CLOUDFLARE_API_TOKEN`, and add `CLOUDFLARE_ACCOUNT_ID` as an environment variable in each.
7. Check the workflow's inputs, then dispatch one test run from `main`:
```bash
gh workflow view edge-secrets.yml -R Zero-State-LLC/Patch-Hive --yaml
```
```bash
gh workflow run edge-secrets.yml -R Zero-State-LLC/Patch-Hive --ref main -f env=staging
```
   (The job selects `production` when input `env == 'production'`, so `env=staging` is the safe test; confirm the input name in the first command's output before running the second.) For `production` runs, approve the prompt on the Actions run page.
8. Only after step 7 works, delete the repo-level copies of `PATCHHIVE_DATABASE_URL_PROD`, `CLOUDFLARE_API_TOKEN` and the variable `CLOUDFLARE_ACCOUNT_ID`.

**Check it worked.**
```bash
gh api repos/Zero-State-LLC/Patch-Hive/environments --jq '.environments[]|{name,protection_rules,deployment_branch_policy}'
```
`production` now shows a required-reviewers rule and a branch policy; a production run waits for your approval.

**Unblocks.** 006 T101b, then T101c (daily `evidence.expire`).

**Time.** 30 to 45 minutes.

**Risk / notes.** Do step 7 before step 8 or a run can lose its secrets. If you add a second reviewer later, turn "Prevent self-review" on only then, or runs deadlock.

---

### 3. Maker outreach for the 17 unsourced HP values (003 T039, OQ-1)

**What and why.** 17 modules carry an HP width from an old list with no maker source (`hp_source = legacy_unsourced`). Racks use HP for placement, so a wrong width matters. A maker-provided width is the route to retire `UNSOURCED_HP_OVERLAYS`. You send the emails; I contacted no one.

**Current state (verified in `data/synth-catalog/overlays/module-catalog-hp-retailer-v1.json` and `specs/003-.../tasks.md` T039).** Of the 57 rows, 46 have a retailer HP (40 agree with the stored value, 6 disagree) and 11 were not found on an allowed retailer: 6 + 11 = 17 stay `legacy_unsourced`. The table below lists exactly those 17. The Make Noise 1hp, 4hp, 6hp blanks are not among them (retailer pages agree with stored widths), so they need no email. Akemie's Castle (ALM Busy Circuits) is separate (003 OQ-2): `module_catalog` holds 18, `modules` holds 38, and the manual host showed a bot check.

**Modules per maker.**

| Maker | Module | Stored HP vs retailer |
|---|---|---|
| ADDAC System (8) | ADDAC200PI | 2 vs 4 |
| | ADDAC200S Size Matter (black) | 2 vs 4 |
| | ADDAC501B Complex Random Expansion | 8 vs 4 |
| | ADDAC001 VCC, ADDAC003 VCC Manual Inputs, ADDAC005 VCC Gate Outputs, ADDAC101 .WAV Player | no retailer page |
| | ADDAC203 CV Mapping | retailer lists only the 203 REV.02 (6 HP); unclear if it is our version |
| Befaco (2) | Mixer | 5 vs 4 |
| | Dual Atenuverter | no retailer page |
| Instruo (1) | dàil | 4 vs 6 (page bundles a 2 HP expander) |
| Cwejman (1) | D-LFO | 12 vs 14 |
| Doepfer (1) | A-101-4 | no page found |
| Intellijel (2) | μAtt, Quadra Expander | no page; Quadra manual gives one width without naming the module |
| Make Noise (2) | Mysteron, Strega | no page; Strega's page gives inches only |
| ALM Busy Circuits (extra) | Akemie's Castle | catalog 18, modules 38 |

**Contact routes.** "GET" means I fetched it myself with a plain GET (identified user agent, robots.txt read first). "Search" means a web-search summary I could not fetch myself (the site blocked or timed out), so confirm on the page before sending. I did not work around any block.

| Maker | Contact | How found |
|---|---|---|
| ALM Busy Circuits | help@busycircuits.com, from `https://busycircuits.com/policies/contact-information`; support page `https://busycircuits.com/pages/support` | GET (WebFetch for the address); robots.txt (Shopify defaults) does not disallow these pages |
| Intellijel | support@intellijel.com, from `https://intellijel.com/support/` | GET; robots.txt does not disallow it |
| Cwejman | Use the contact form at `https://www.cwejmanmusic.com/contact` (200; Squarespace robots.txt does not disallow it; no address shown in page text; the form was not inspected). `cwejman.net` redirects to an unrelated site and `cwejman.com` is not the maker's current shop | GET |
| ADDAC System | Use the contact form at `https://www.addacsystem.com/en/support`; a search result gives addac@addacsystem.com. My GET got a JavaScript challenge | Search |
| Befaco | Use the contact form at `https://shop.befaco.org/contact-us`; search result gives support@befaco.org (technical) and shop@befaco.org (orders). `www.befaco.org` returned 403 to my GET | Search |
| Instruo | Use the contact form at `https://www.instruomodular.com/contact/`; its terms page names info@instruomodular.com. `www.instruomodular.com` returned 403 to my GET | Search |
| Make Noise | technical@makenoisemusic.com per `https://www.makenoisemusic.com/support/`. The host timed out for me (curl and WebFetch); check in a browser | Search |
| Doepfer | No contact page found: `/contact.htm` and `/contact_e.htm` returned 404; robots.txt returns 404 (no rules). Search results show sales@doepfer.de in a 2024 manual and hardware@doepfer.de in a 2007 press release. Use the contact link on `https://www.doepfer.de/` and confirm the address | Search, low confidence |

**Email drafts** (replace `[Name]`; one per maker, from your own address):

*ADDAC System.* Subject: Module width (HP) for a few ADDAC modules
> Hello ADDAC team,
> I am building PatchHive, a free tool that documents Eurorack racks and checks that modules fit before people buy a case. I list your modules and want the widths to be right, from you rather than a retailer.
> Could you tell me the panel width in HP of: ADDAC001 VCC, ADDAC003 VCC Manual Inputs, ADDAC005 VCC Gate Outputs, ADDAC101 .WAV Player, ADDAC200PI Pedal Integrator, ADDAC200S Size Matter (black), ADDAC203 CV Mapping (original and REV.02 if both exist), and ADDAC501B Complex Random Expansion?
> A link to a spec sheet or manual stating the width is ideal. I would cite it and credit ADDAC. Thank you for your time.
> Best, [Name], PatchHive

*Befaco.* Subject: HP width for Befaco Mixer and Dual Atenuverter
> Hello Befaco team,
> I am building PatchHive, a free tool that documents Eurorack racks. Could you confirm the panel width in HP of the Mixer and the Dual Atenuverter? Retailers list the Mixer at 4 HP while an older list says 5. A link to a manual or spec page would let me cite Befaco directly. Thank you, [Name], PatchHive

*Instruo.* Subject: Width of the dàil module
> Hello Instruo team,
> I am building PatchHive, a free tool that documents Eurorack racks. What is the panel width in HP of the dàil on its own? A retailer page shows 6 HP but seems to include a 2 HP expander. A link to a spec page or manual would let me cite Instruo. Thank you, [Name], PatchHive

*Cwejman.* Subject: HP width of the D-LFO
> Hello Cwejman team,
> I am building PatchHive, a free tool that documents Eurorack racks. Could you tell me the panel width of the D-LFO in HP? Retailers show 14 HP. A link to a spec page or manual would let me cite Cwejman. Thank you, [Name], PatchHive

*Doepfer.* Subject: Width (TE) of the A-101-4
> Hello Doepfer team,
> I am building PatchHive, a free tool that documents Eurorack racks. I cannot find a page for the A-101-4. Could you tell me its panel width in TE/HP and, if possible, link a data sheet? Thank you, [Name], PatchHive

*Intellijel.* Subject: Panel width for μAtt and Quadra Expander
> Hello Intellijel team,
> I am building PatchHive, a free tool that documents Eurorack racks. Could you give me the panel width in HP of the μAtt and the Quadra Expander? The Quadra manual gives one width without saying which module it belongs to. A link to a spec page would let me cite Intellijel. Thank you, [Name], PatchHive

*Make Noise.* Subject: Width of Mysteron and Strega
> Hello Make Noise team,
> I am building PatchHive, a free tool that documents Eurorack racks. I cannot find product pages with a panel width for Mysteron, and Strega's page gives inches only. Could you tell me the HP of each? Thank you, [Name], PatchHive

*ALM Busy Circuits.* Subject: Akemie's Castle width
> Hello ALM team,
> I am building PatchHive, a free tool that documents Eurorack racks. Is the Akemie's Castle 18 HP? One automated read of a listing gave 38, which looks wrong. A link to the manual would let me cite ALM. Thank you, [Name], PatchHive

**Check it worked.** Replies logged. Send Claude each maker's words and URL; Claude adds the next HP overlay version (after `module-catalog-hp-v7`) with a quote, loads it through the db-load workflow, and the marker clears.

**Unblocks.** 003 T039 and removal of `UNSOURCED_HP_OVERLAYS`.

**Time.** 20 minutes to send; replies take days or weeks.

**Risk / notes.** Do not paste retailer data as if it were the maker's. Do not use ModularGrid. Without a reply, 003 OQ-1's fallback is `accept_marked_and_close`.

---

### 4. Production sign-up test and VirusTotal reanalysis

Source: `CURRENT_STATE.md` ("real sign-up on production", "VirusTotal reanalysis") and `docs/KANBAN.md:59` ("VirusTotal reanalysis and the nine vendor false-positive reports (frontend is deployed)").

#### 4.1 Production sign-up test
**What and why.** Confirms a new person can create an account and sign in on the live site. CURRENT_STATE says no account exists on production and sign-up has not been tried.

**Current state.** Sign-in is open (#113). The form is in `frontend/src/pages/Login.tsx` (tabs Sign in and Create account; fields username, email, password of 8 to 128 characters). Backend `backend/community/auth_routes.py` returns 429 `TOO_MANY_SIGNUPS` for repeated sign-ups from one address and 400 `USERNAME_OR_EMAIL_TAKEN` for duplicates. Referrals are off by default, so leave any referral code empty. `DELETE /api/me` (#194, self-delete) is on main; production ran `9dbb5ba` per CURRENT_STATE, so assume it is not deployed (check `/health`).

**Steps.**
1. Check the live API and its version:
```bash
curl -s https://api.patch-hive.com/health/ready
```
2. In a private browser window open `https://patch-hive.com/login` and click Create account.
3. Use an address you control, a unique username and a fresh password from your password manager (not one you use elsewhere).
4. Submit and confirm you land signed in.
5. Create one rack, reload, and confirm you are still signed in and the rack is listed.
6. Sign out, then sign in again with the same credentials.
7. Optional: in dev tools, Application, Cookies, confirm the refresh cookie is `HttpOnly` and `Secure`.

**Check it worked.** Account created, sign-in works after sign-out, the rack persists, and the console shows no errors (watch for Content-Security-Policy violations; CSP is enforced).

**Unblocks.** First real production account; confidence that sign-up works; shows whether the rate limits get in a normal user's way.

**Time.** 10 minutes.

**Risk / notes.** This writes a real user row in production. Until #194 is deployed you cannot self-delete via the API; keep it as your test user or ask Claude to propose an approved removal. Never test payments here (test mode only).

#### 4.2 VirusTotal reanalysis
**What and why.** The repo records nine security vendors flagging the site as false positives. A reanalysis refreshes the verdict and a vendor report asks the vendor to clear it.

**Current state.** Open on `docs/KANBAN.md:59`. The repo does not store which vendors flagged it, so that list is unknown to me.

**Steps.**
1. Go to `https://www.virustotal.com`, tab URL, enter `https://patch-hive.com`.
2. If a previous result shows, click Reanalyze, wait, and note which vendors still flag it.
3. Repeat for `https://api.patch-hive.com`.
4. For each vendor still flagging, find that vendor's false-positive or site-review form on its own website and submit the URL with one line: "owner-operated Eurorack documentation web app, no downloads".
5. Re-run in a few days.

**Check it worked.** Detections drop to 0, or only vendors with open reviews remain. Keep vendor names and report dates in a private note (tell Claude if you want them recorded in `docs/KANBAN.md`).

**Unblocks.** Users behind those vendors' products can reach the site.

**Time.** 15 minutes now, plus a follow-up.

**Risk / notes.** Vendor reports go to third parties under your name; send them yourself and include nothing secret.

---

### 5. Legal brief for counsel (facts and questions only; no legal conclusions)

You can hand this section to a lawyer as it is. It covers every item marked "a lawyer must confirm" in `docs/evidence/JEV_DECISIONS_2026-11-01.md` (001 OQ-10, 002 OQ-6/12/13, 003 OQ-4, 004 OQ-1/2/12/13) plus the NVIDIA and Cloudflare model terms. Confirm the legal entity name and jurisdiction (the repo organisation is Zero-State-LLC).

**Product.** PatchHive (patch-hive.com): a web app where users photograph and describe a Eurorack synthesizer rig, the system proposes module identification, a person confirms it, and the app generates patch documentation. Runs on Cloudflare Workers/Containers; database on Neon (region not stated in the repo; owner to supply); files in a Cloudflare R2 bucket (`patchhive-prod-files`). Stripe is in test mode and no sales are enabled. Publishing to a public gallery is off.

**Data held (as built on main).**

| Data | Where | Kept |
|---|---|---|
| Account: email, username, display name, password hash, refresh tokens | Neon | Until the user deletes the account. `DELETE /api/me` (#194) replaces PII, revokes sessions, deletes comments, votes, overlays, annotations and style recipes, soft-deletes racks and clears their text, sets publications to removed, writes one audit row with counts only |
| Rig photos (re-encoded JPEG, metadata stripped) | R2 | 30 days default, 90 max for new uploads; older images up to 365 days; the owner can delete; the expiry job exists but is not scheduled yet |
| Provider/OCR output linked to a photo | Neon | Append-only classification evidence and receipts remain after the image is deleted (hashes, lineage); raw-text policy not decided |
| Rigs, runs, patches, receipts | Neon | Append-only; kept after anonymization |
| Credit ledger, referral rows, canonical exports | Neon, R2 | Kept after anonymization; no period decided (earlier proposal: 7 years for financial records, "confirm with an accountant") |
| Stripe event records | Neon | Payload hash, status and reason code only |
| Publication reports (reason; reporter id if signed in; anonymous allowed) | Neon | Indefinitely; no policy |
| Admin audit events | Neon | Append-only; no period decided |
| Application logs | Cloudflare observability | Not documented (proposal 30 days) |
| Backups, logs, provider-side data | Neon, Cloudflare, providers | Not covered by the deletion routine (a listed gap in spec 004) |

**Questions for counsel.**

1. **Terms, refunds, consumer protection (004 OQ-13; also OQ-1 and OQ-2).** If the app sells monthly credit subscriptions and one-time credit packs through Stripe: (a) what terms of service, refund policy and withdrawal-right notices are required in the places of sale? (b) Do non-expiring credits and an "unlimited" tier carry specific rules? (c) Who is the seller of record, and what tax and VAT duties arise (US-only launch versus EU buyers)? (d) May a refund reverse only unspent credits and leave any remainder unresolved (004 OQ-2 as decided), and what about chargebacks? (e) What must be disclosed about Stripe receiving email and display name? Prices themselves (004 OQ-1) are provisional.
2. **Retention after account deletion (004 OQ-12).** The system anonymizes the user but keeps the ledger, referral rows, exports and runs. Is that adequate where erasure rights apply, and what retention period applies to financial records, referral rows and the admin audit trail? Do free-text fields inside kept rows (rig or patch names, notes) matter?
3. **Photo retention (001 OQ-10).** Photos may show homes, serial numbers or people. Are 30 days default and 90 days maximum acceptable, and is a privacy notice, DPIA or consent text needed? What about older images (up to 365 days) and derived OCR text, hashes and receipts that remain after the image is deleted? How are backups treated?
4. **Licence (002 OQ-12) and the book/publish rule (OQ-6).** The default licence on a published patch book is CC BY-NC 4.0 and `allow_remix` is stored. (a) Is CC BY-NC suitable for user-submitted content, and who grants it? (b) What should `allow_remix=false` map to (for example CC BY-NC-ND or all-rights-reserved)? (c) Is "NonCommercial" too ambiguous, given CC licences are irrevocable once granted? (d) What licence should users grant the service so it can host and serve their work?
5. **Reports and audit retention (002 OQ-13).** Anonymous reports are accepted (10 per hour per address); signed-in reporters are recorded. Should anonymous reports remain, how long should reports and moderation audit be kept, and is a reporter notice needed? What takedown process should accompany a public gallery?
6. **Third-party data provenance (003 OQ-4, decision D1).** The catalog seed `seed-phase2-v1.json` came from a browser scrape of a third-party site (703 brand names, 376 module identities); its spec values were archived or nulled and its descriptions removed, and rows carry `access_basis = unknown` and are never bulk-published. Retailer values are recorded only from one-off manual lookups and never treated as canonical. Is keeping the brand and module names acceptable, and do manufacturer facts (HP, power, depth) taken from maker pages need attribution? The state-machine wording in 003 OQ-4 follows the answer.
7. **NVIDIA API (`backend/intelligence/nvidia_provider.py`, host `integrate.api.nvidia.com`).** Rig photos can be sent there when enabled; today only staging holds the credentials (`edge/api/wrangler.jsonc`). Search results (not read in full): NVIDIA's API Trial Terms describe the service as for testing and evaluation and restrict use of outputs; one forum quote says prompts and outputs may be used to improve products, which I could not resolve; each model is also under the NVIDIA Open Model License Agreement. Questions: may the service be used in production? Does NVIDIA retain or use rig photos and prompts? What is the licence and notice position for each pinned model (`nvidia/nemotron-3.5-super-vl-120b-a12b`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`)? Start from each model page on `https://build.nvidia.com` and its linked trial terms.
8. **Cloudflare Workers AI / Clef (`@cf/cloudflare/...`).** Rig photos go to Workers AI when enabled. Search result of Cloudflare docs: Cloudflare says it does not use Customer Content to train Workers AI models or improve services without explicit consent, and may store content only if you pair it with a storage product; no zero-retention guarantee was found. Read `https://developers.cloudflare.com/workers-ai/platform/data-usage/` and Cloudflare's agreements and DPA. Questions: do they cover the photos, are the Clef model licences satisfied, and must users be told photos go to third-party models?

**Check it worked.** Counsel's written answers. Claude records each as the answer to the matching OQ and removes the "lawyer must confirm" tag.

**Unblocks.** 004 OQ-13 (sales and Machines B/C), 004 OQ-12 sign-off, 001 OQ-10 sign-off, 002 OQ-12/13 and any return of publishing, and NVIDIA provider use outside staging.

**Time.** 1 to 2 hours to send; counsel's turnaround varies.

**Risk / notes.** Facts only; nothing here is legal advice. Until answered: sales stay off, publishing stays off, and the NVIDIA provider stays off outside staging.

---

### 6. Prices (004 OQ-1, provisionally ratified at 0.29)

**What and why.** Decide what the plans cost and what they include. Not urgent: sales are deferred (004 OQ-13 `D_defer_sales`, 0.95), so nothing charges today.

**Current state.** From `docs/evidence/jev-decisions-2026-11-01.json`, 004 OQ-1 evidence, fetched by the research pass on 2026-11-01. I did not re-fetch these pages.
- Stripe card fee: 2.9% plus $0.30 domestic; +1.5% international; +1% currency conversion; Stripe Tax Basic 0.5% or $0.50 per transaction via API; Billing 0.7% pay-as-you-go; dispute $15; refunds are free but original fees are not returned (`https://stripe.com/pricing`).
- Comparable tools: Splice Creator $4.99 first month then $19.99 per month, about 200 credit-based downloads (`https://www.splice.com/plans`); Notion Plus $10 and Business $20 per member per month (`https://www.notion.com/pricing`); Canva Pro $144 per year (`https://www.canva.com/pricing/`).
- One Patch Book export costs 3 credits (`backend/core/config.py`, `patchbook_export_cost=3`), so $0.60 at $0.20 per credit.
- Stripe fee on each sale (2.9% + $0.30; "with Billing" adds 0.7%): $4.99 is $0.445 (8.9%), with Billing $0.480 (9.6%); $14.99 is $0.735 (4.9%), $0.840 (5.6%); $29.99 is $1.170 (3.9%), $1.380 (4.6%); a $5.00 pack is $0.445 (8.9%).
- CORE versus pay-as-you-go: CORE is 25 credits for $4.99 ($0.1996 each), essentially the $0.20 pack price, so it gives no discount and no reason to subscribe. PRO is 100 credits for $14.99 ($0.15 each, 25% off packs). STUDIO "unlimited" has open-ended cost; the decided OQ-8 answer is an explicit flag with an owner-set fair-use cap.

**Three price sheets** (per export = 3 credits; USD; quantities in B and C are my illustrations, edit freely).

| | Sheet A: as proposed | Sheet B: adjusted ladder | Sheet C: credits first |
|---|---|---|---|
| Packs | $0.20 per credit, $5 minimum | $0.20 per credit, $10 minimum | $10 = 50 credits; $25 = 135; $50 = 300 |
| CORE | $4.99, 25 credits | $4.99, 30 credits | none |
| PRO | $14.99, 100 credits | $14.99, 100 credits | none |
| STUDIO | $29.99, unlimited | $29.99, 250 credits (or fair-use cap) | none |
| Price per export | pack $0.60, CORE $0.60, PRO $0.45 | pack $0.60, CORE $0.50, PRO $0.45, STUDIO $0.36 | $0.60, $0.56, $0.50 |
| Fee per sale | $5 pack 8.9%; CORE 8.9% (9.6% with Billing); PRO 4.9%; STUDIO 3.9% | $10 pack 5.9%; CORE 8.9%; PRO 4.9%; STUDIO 3.9% | $10 pack $0.59 (5.9%); $25 $1.03 (4.1%); $50 $1.75 (3.5%); no Billing fee |
| Weakness | CORE has no discount; unlimited cost unbounded | CORE fee still 8.9%; you pick the numbers | no recurring revenue |
| Jev option | A (0.47) | B (0.19) | C (0.17) |

**Recommendation.** Sheet C to launch: fewest open questions (no subscription machine, no proration or status handling), fees about 6% or less, smallest legal surface. Add Sheet B's ladder when subscriptions are built. Do not ratify A as written: CORE costs the same as buying credits. USD only; tax and VAT go to counsel (section 5).

**Steps.**
1. Tell Claude "price sheet C" (or B or A) with the quantities you want. Claude records it as the answer to 004 OQ-1 and updates the spec.
2. No code changes until sales are enabled.

**Check it worked.** 004 OQ-1 in `specs/004-commerce/spec.md` shows your decision.

**Unblocks.** T046 (Machine B), T049, T050; those also need T001 and counsel's answers.

**Time.** 10 minutes.

**Risk / notes.** Fee figures are as Stripe published them on 2026-11-01 and may change. Payments stay `STRIPE_TEST_MODE=true` and `ALLOW_PRODUCTION_PAYMENTS=false` until a separate activation review.
