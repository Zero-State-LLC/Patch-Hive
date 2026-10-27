# PatchHive Kanban (mirror)

Mirror of [org Project #8 "Patch-Hive"](https://github.com/orgs/Zero-State-LLC/projects/8). The project is the source of truth. Regenerate this file with `gh project item-list 8 --owner Zero-State-LLC`.

Columns (Status): Backlog → Ready → In progress → In review → Done. Spec tasks are titled `[NNN Txxx]`; Ready means every `depends_on` is done (`just spec-dag`).

Snapshot: 2026-10-26 PT, 56 items.

## Backlog

- [#21](https://github.com/Zero-State-LLC/Patch-Hive/issues/21) Advance v0.3 alpha toward closed staging beta
- [008 T040b] Run Design Engine walkthrough on staging (test payments) and capture receipt
- [008 T050b] Pin readiness matrix + cutover checklist to walkthrough SHA
- [alpha exit] No P0 regressions on main CI (blocked: Actions billing)
- [beta] Operator staging host pick
- [beta] Secrets, CORS, fail-closed payment flags
- [beta] Design Engine staging enablement
- [beta] Acceptance suite against staging Postgres
- [beta] Backup/restore + ledger reconcile drill receipts
- [beta] Manual accessibility protocol
- [beta] Dual-path F2/F4/F5 thinning
- [beta] Playwright against staging
- [005 T061 = 007 T030b+T040b] Propose and approve thresholds from baseline
- [005 T062 = 007 T060b] Pin and retain SHA-pinned evaluation receipt
- [005 T070 = 007 T050b] Enable provider in staging after approval
- [005] Close Spec Kit gaps (Workflows section, transitions table)
- [ops] Fix org Actions billing/spending limit (admin)
- [ops] Add required status checks backend/frontend/Analyze once green
- [release] Tag v0.4.0-alpha.1 after versioning PR merges
- [data] Next catalog enrichment batch (needs budget approval)
- [triage] Review personal-only branches with unmerged work
- [001 T002] Write plan.md (rig intelligence)
- [001 T010] Encode transitions table as tests (rig intelligence)
- [001 T090] Converge code against spec (rig intelligence)
- [002 T002] Write plan.md (patch-book publishing)
- [002 T010] Encode transitions table as tests (patch-book publishing)
- [002 T090] Converge code against spec (patch-book publishing)
- [003 T002] Write plan.md (catalog dataset pipeline)
- [003 T010] Encode transitions table as tests (catalog dataset pipeline)
- [003 T090] Converge code against spec (catalog dataset pipeline)
- [004 T002] Write plan.md (commerce)
- [004 T010] Encode transitions table as tests (commerce)
- [004 T090] Converge code against spec (commerce)
- [006 T040] Publish API hostname; restrict CORS to exact origin
- [006 T050] Bind Hyperdrive to Neon staging branch
- [006 T060b] Verify Clef resolution path on Hyperdrive-bound staging
- [007 T020b = 005 T061d] Run baseline vs provider-assisted evaluation on frozen corpus

## Ready

- [008 T030b] Verify seeded demo auth on the staging host
- [001 T001] Confirm rig intelligence spec
- [002 T001] Confirm patch-book publishing spec
- [003 T001] Confirm catalog dataset pipeline spec
- [004 T001] Confirm commerce spec
- [007 T010b = 005 T061c] Promote rights-cleared cases and freeze corpus SHA

## In progress

- [006 T030] Edge frontend on Cloudflare (Pages in spec; Workers in #55)

## In review

- [#55](https://github.com/Zero-State-LLC/Patch-Hive/pull/55) ops(frontend): ship SPA on Cloudflare Workers (patch-hive.com) and gate dev-only copy
- [#56](https://github.com/Zero-State-LLC/Patch-Hive/pull/56) style(frontend): Hallmark polish to clear the Floor (cyber-hive DESIGN.md)
- [#57](https://github.com/Zero-State-LLC/Patch-Hive/pull/57) spec: Spec Kit + DAG compliance audit for 001-008; add spec DAG checker

## Done

- [#4](https://github.com/Zero-State-LLC/Patch-Hive/pull/4) ci: free security scanning to replace CodeQL
- [#22](https://github.com/Zero-State-LLC/Patch-Hive/pull/22) Clarify PatchHive next milestone in roadmap
- [#24](https://github.com/Zero-State-LLC/Patch-Hive/pull/24) chore(deps-dev): bump source-map-js from 1.2.1 to 1.2.2 in /frontend
- [#25](https://github.com/Zero-State-LLC/Patch-Hive/pull/25) sync: bring personal repo main (964ce18) into org
- [#26](https://github.com/Zero-State-LLC/Patch-Hive/pull/26) ci: real backend+frontend CI; fix project automation target
- [#27](https://github.com/Zero-State-LLC/Patch-Hive/pull/27) specs: draft skeletons 001-004 + 005 gap list (stacked on #25)
- [#28](https://github.com/Zero-State-LLC/Patch-Hive/pull/28) release: align versions to 0.3.0-alpha.2 + release workflow (stacked on #25)
- [#29](https://github.com/Zero-State-LLC/Patch-Hive/pull/29) docs: KANBAN.md mirror of Project #8 (stacked on #25)
- [#30](https://github.com/Zero-State-LLC/Patch-Hive/pull/30) data: catalog batch 7 via scrape-router (overlay v5 + new-brand candidates + dry-run receipt)
