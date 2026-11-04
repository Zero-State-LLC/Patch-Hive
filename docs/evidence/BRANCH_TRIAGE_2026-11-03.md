# Branch triage, 2026-11-03

Project #8 card "[triage] Review personal-only branches with unmerged work".

The data comes from `git fetch org` against `main` at 3688037, and `gh pr list --state all` (242 PRs). For each branch:
- "commits outside main" is `git rev-list --count main..<branch>`;
- "patches not in main" is the number of `+` lines from `git cherry main <branch>`, which drops commits whose patch already landed under another hash.

## Counts (265 branches besides `main`)

| Group | Branches | Action |
|---|---|---|
| A PR was merged | 197 | Left in place; their work is in `main` |
| A PR is open | 7 | Left in place |
| Only closed, unmerged PRs | 4 | Listed below |
| No PR, nothing outside `main` | 24 | **Deleted 2026-11-03** (owner's decision) |
| No PR, with commits of their own | 33 | Listed below |

The merged-PR branches could also go. GitHub's "Automatically delete head branches" setting would stop new ones from piling up; that is an owner setting.

## Deleted (24)

Each tip was an ancestor of `main` and had no open PR, and both were re-checked just before deletion. No commit was lost; only the branch names went.

- `claude/abx-core-1.3-upgrade-01AfV6jcMku78T7sratZyRX3`
- `claude/add-patchhive-overlay-RLAL6`
- `claude/beautify-readme-fM0BD`
- `claude/create-replit-export-zip-MhUsd`
- `claude/patchhive-analysis-prompt-NO4MI`
- `claude/stripe-integration-prompt-eze7U`
- `codex/add-proprietary-jack-function-detection`
- `codex/add-pruning-and-interactive-pdf-index`
- `codex/add-structure-aware-naming-to-patches`
- `codex/expand-vl2-style-patch-book-generator`
- `codex/finalize-schemas-and-add-round-trip-test`
- `codex/fix-screenshots-and-demo-in-readme`
- `codex/implement-abx-runes-compliance-in-patch-hive`
- `codex/implement-automated-acceptance-tests`
- `codex/implement-automated-acceptance-tests-ppvfbm`
- `codex/implement-patchhive-ingestion-and-pipeline`
- `codex/implement-patchhive-system-as-a-subsystem`
- `codex/implement-publishing-layer-for-patchhive`
- `codex/implement-rig-workspace-with-contextual-tabs`
- `codex/implement-user-dashboard-and-leaderboards`
- `codex/sync-patchhive-codebase-with-notion-canon`
- `codex/upgrade-patch-book-export-and-define-monetization-tiers`
- `feat/multi-photo-reconcile-ui`
- `personal-archive-2026-10-09`

## Patches already in `main` (12)

Every patch on these branches is already in `main`, under another hash. They are safe to delete on the owner's word.

| Branch | Commits outside main | Patches not in main | Last commit |
| --- | --- | --- | --- |
| `copilot/fix-codeql-security-vulnerabilities` (closed PR #16) | 1 | 0 | 2026-09-17 Initial plan |
| `docs/staging-smoke-receipt-20260726` | 1 | 0 | 2026-07-26 docs(evidence): record local staging compose smoke PASS (alembic head |
| `feat/automate-testing` | 1 | 0 | 2026-07-26 feat(test): unified test runner + CI acceptance gate |
| `feat/design-engine-staging-walkthrough` | 1 | 0 | 2026-07-26 feat(staging): Design Engine enablement overlay + API walkthrough |
| `feat/docker-staging-suite` | 1 | 0 | 2026-07-26 feat(staging): Docker-native suite with in-network acceptance |
| `feat/pdb-p0-registry-catalog-explorer-20260723` | 1 | 0 | 2026-07-23 feat(pdb): Device Registry + catalog seeding + public explorer + modu |
| `feat/staging-acceptance-suite` | 1 | 0 | 2026-07-26 feat(staging): acceptance suite against compose Postgres |
| `feat/staging-smoke-backup-drill` | 1 | 0 | 2026-07-26 feat(staging): smoke scripts with health, alembic, backup/restore dri |
| `fix/entrypoint-wait-for-db` | 1 | 0 | 2026-07-26 fix(ops): wait for DATABASE_URL before alembic in entrypoint |
| `fix/registry-admin-auth-156` | 1 | 0 | 2026-07-29 fix(registry): authorize admin mutations (#156) |
| `ops/beta-staging-migrations-health` | 1 | 0 | 2026-07-26 feat(ops): Alembic-on-deploy, /health/ready, beta-staging evidence re |
| `personal-archive/fix/spec-005-postmerge-verification` | 1 | 0 | 2026-09-25 test(intelligence): exercise malformed bounded candidate validation |

## Work believed to have landed under other commits (20)

Most of these are the 2026-09-25/26 `personal-archive/*` snapshots and July staging work. That work reached `main` through the personal repository sync (#25) and later squash merges, so `git cherry` cannot match it commit by commit. **Check each one before deleting it.**

| Branch | Commits outside main | Patches not in main | Last commit |
| --- | --- | --- | --- |
| `codex/modular-case-catalog-foundation` | 18 | 18 | 2026-07-21 fix: register complete backend model graph for integration CLIs |
| `cursor/fix-case-materialize-null-rails-d529` | 2 | 2 | 2026-07-25 docs: record open bugfix PR #138 in MEMORIES.md |
| `cursor/harden-codebase-index-305c` | 3 | 3 | 2026-07-26 chore(ai): refresh codebase-memory artifact at HEAD |
| `feat/001-port-resolution-validation` | 2 | 1 | 2026-10-28 feat(001): resolve generic jacks to declared ones, and fail runs on c |
| `feat/f2-canon-rigs-list` | 2 | 2 | 2026-07-26 style(canon): black-format routes.py for CI |
| `feat/f4-canon-evidence-aliases` | 2 | 2 | 2026-07-26 test(e2e): mock canon evidence paths after F4 FE switch |
| `feature/008-impl-f5-cutover` (closed PR #52) | 2 | 1 | 2026-10-24 feat: 008 implement Dual-Path F5 Cutover + Design Engine Staging Rece |
| `fix/demo-credentials-login` | 2 | 2 | 2026-07-26 fix(auth): use admin_demo for staging admin (avoid acceptance conflic |
| `fix/shadow-fe-seed-type-safety` | 5 | 5 | 2026-07-26 fix(db): migrate modules/module_catalog registry slug columns |
| `fix/workflow-invalid-projects-permission` (closed PR #2) | 3 | 3 | 2026-08-15 perf(ci): cut billed Actions minutes (#3) |
| `personal-archive/feat/spec-005-decision-intelligence` | 67 | 63 | 2026-09-25 docs(spec): reconcile logical decision records with MVP receipt persi |
| `personal-archive/feat/t061-corpus-promotion-workbench` | 4 | 4 | 2026-09-25 docs(corpus): define retained-bundle and operator-shot intake |
| `personal-archive/fix/decision-intelligence-verification` | 17 | 17 | 2026-09-25 docs(spec): define v1 evidence identity semantics |
| `personal-archive/fix/spec-005-production-boundaries` | 22 | 21 | 2026-09-25 test(intelligence): use schema-invalid bounded candidate fixture |
| `personal-archive/fix/t061c-queue-auditability` | 2 | 2 | 2026-09-26 test: cover strict kind filtering and discovery traceability |
| `personal-archive/fix/t061c-retained-corpus-contract` | 2 | 2 | 2026-09-25 test: cover retained pilot promotion contract |
| `personal-archive/ops/jev-t070-preflight` | 1 | 1 | 2026-09-25 ci: add manual Jev T070 preflight |
| `personal-archive/ops/t070-jev-preflight` | 4 | 4 | 2026-09-25 docs(evidence): record successful pinned-model Jev preflight |
| `personal-archive/style/frontend-prettier-baseline` | 4 | 3 | 2026-09-25 ci(frontend): enforce Prettier after baseline |
| `security/free-scanner-stack` (closed PR #4) | 2 | 2 | 2026-08-15 fix(ci): run gitleaks binary instead of the licensed action |

## Not landed (5)

| Branch | What it holds |
|---|---|
| `codex/case-catalog-normalization` | a case-catalog normalization doc and an import contract schema |
| `claude/audit-export-tests-za0Lt`, `claude/generate-vl2-pack-kbY4K`, `claude/patchbook-computed-tiers-Dzu7u` | December 2025 experiments, from before the canon rewrite |
| `archive/local-pdb-readiness-20260723` | a deliberate archive snapshot of the local PDB readiness work |

| Branch | Commits outside main | Patches not in main | Last commit |
| --- | --- | --- | --- |
| `archive/local-pdb-readiness-20260723` | 5 | 3 | 2026-07-29 chore(archive): preserve local PDB readiness workspace |
| `claude/audit-export-tests-za0Lt` | 1 | 1 | 2025-12-23 Audit: Harden Patch Book export with determinism + tests |
| `claude/generate-vl2-pack-kbY4K` | 1 | 1 | 2025-12-23 Add FastAPI/Pydantic backend integration for system packs |
| `claude/patchbook-computed-tiers-Dzu7u` | 1 | 1 | 2025-12-23 Upgrade PatchBook to v1.1 with computed intelligence and monetization |
| `codex/case-catalog-normalization` | 2 | 2 | 2026-07-21 feat(cases): add normalized import contract schema |
