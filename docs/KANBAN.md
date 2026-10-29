# PatchHive Kanban (mirror)

Mirror of [org Project #8 "Patch-Hive"](https://github.com/orgs/Zero-State-LLC/projects/8). The project is the source of truth. Regenerate this file with `gh project item-list 8 --owner Zero-State-LLC`.

Columns (Status): Backlog → Ready → In progress → In review → Done. Spec tasks are titled `[NNN Txxx]`; Ready means every `depends_on` is done (`just spec-dag`). Slices A1–A5 and C1–C6 are described in [docs/evidence/NEXT_SLICES_2026-10-28.md](evidence/NEXT_SLICES_2026-10-28.md).

Snapshot: 2026-10-28 PT (evening), 139 items.

## Backlog

- [#21](https://github.com/Zero-State-LLC/Patch-Hive/issues/21) Advance v0.3 alpha toward closed staging beta
- [008 T040b] Run Design Engine walkthrough on staging (test payments) and capture receipt
- [008 T050b] Pin readiness matrix + cutover checklist to walkthrough SHA
- [beta] Operator staging host pick
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
- [ops] Org Actions budget or spending limit (needed before making the repo private again)
- [ops] Add required status checks backend/frontend/Analyze once green
- [release] Tag v0.4.0-alpha.1 after versioning PR merges
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
- [006 T050] Bind Hyperdrive to Neon staging branch
- [006 T060b] Verify Clef resolution path on Hyperdrive-bound staging
- [007 T020b = 005 T061d] Run baseline vs provider-assisted evaluation on frozen corpus
- [003 T026] Frap Tools listing adapter
- [decision] HP correction for NOT NULL modules.hp (Sovage CHICANE 14 -> 4)
- [decision] seed_catalog_from_synth.py: delete, port registry slug fill
- [decision] Maker permission metadata and stealth proxy sign-off
- [decision] Model jumper-dependent power (power_configs)
- [beta] Open accounts (VITE_ACCOUNTS_OPEN=true) once the API is live
- [003 T031] Rebuild the maker-crawl cache and classify 644 untagged rows (paid cap)
- [catalog] Review 24 rows whose tags point to two categories

## Ready

- [008 T030b] Verify seeded demo auth on the staging host
- [001 T001] Confirm rig intelligence spec
- [002 T001] Confirm patch-book publishing spec
- [003 T001] Confirm catalog dataset pipeline spec
- [004 T001] Confirm commerce spec
- [007 T010b = 005 T061c] Promote rights-cleared cases and freeze corpus SHA
- [ops] VirusTotal reanalysis and the nine vendor false-positive reports (frontend is deployed)
- [ops] Rotate context.dev and OpenRouter API keys
- [ops] Add RELEASE_PLEASE_TOKEN secret
- [ops] Add PROJECT_TOKEN so new PRs reach Project #8
- [api] Count unknown module power per rail in rack budgets (slice A1)
- [catalog] Seven new crawl rows -> catalog-additions-v6 + power v14
- [003 T030] Refuse shared homepages at crawl time (slice A2)
- [api] Rack warning for tombstoned placements (slice A4)
- [frontend] Skip the refresh call when signed out (slice A5)
- [ops] Real sign-up on production (operator)
- [ops] Decide repo visibility vs the Actions budget
- [ops] Review open PRs #106, #109, #110, #111

## In progress

_None._

## In review

- [#106](https://github.com/Zero-State-LLC/Patch-Hive/pull/106) chore(deps-dev): bump zod from 4.4.3 to 4.6.7 in /frontend
- [#109](https://github.com/Zero-State-LLC/Patch-Hive/pull/109) chore(main): release 0.3.0-alpha.4
- [#110](https://github.com/Zero-State-LLC/Patch-Hive/pull/110) fix(api): make container startup migrations opt-in
- [#111](https://github.com/Zero-State-LLC/Patch-Hive/pull/111) chore(codeowners): replace partner-agents team with @scrimshawlife-ctrl

## Done

- [alpha exit] No P0 regressions on main CI — green on main 2026-10-28 (repo public)
- [beta] Secrets, CORS, fail-closed payment flags — edge-secrets workflow, exact-origin CORS, test-mode payments
- [data] Next catalog enrichment batch (needs budget approval)
- [006 T030] Edge frontend on Cloudflare (Pages in spec; Workers in #55)
- [006 T040] Publish API hostname; restrict CORS to exact origin — api.patch-hive.com live, other origins 400
- [003 T027] Load maker-crawl overlays to prod (operator) — done 2026-10-28, #112
- [api] Verify registry snapshot ships in the API image — it didn't; registry reads module_catalog (#114)
- [decision] Retire bogus catalog rows (TLM ST MODULAR) — tombstones, #116
- [003 T028] Fill missing categories from crawl tags
- [003 T029] Tombstone misattributed rows; re-add the 7 only they held
- [ops] Production deploy: API and frontend from main
- [ops] Rotate the Cloudflare token pasted in chat
- [#116](https://github.com/Zero-State-LLC/Patch-Hive/pull/116) feat(catalog): tombstone misattributed rows and re-add what only they held
- [#115](https://github.com/Zero-State-LLC/Patch-Hive/pull/115) feat(catalog): fill missing categories from maker crawl tags
- [#114](https://github.com/Zero-State-LLC/Patch-Hive/pull/114) fix(registry): read a manufacturer's models from the module catalog
- [#113](https://github.com/Zero-State-LLC/Patch-Hive/pull/113) feat(frontend): enforce the CSP and open sign-in
- [#112](https://github.com/Zero-State-LLC/Patch-Hive/pull/112) docs(003): mark the prod catalog load (T027) done
- [#107](https://github.com/Zero-State-LLC/Patch-Hive/pull/107) fix(ci): edge-secrets writes production secrets to the production Worker
- [#105](https://github.com/Zero-State-LLC/Patch-Hive/pull/105) fix(intelligence): a failed provider resolves UNRESOLVED or ESCALATE, never REJECT
- [#104](https://github.com/Zero-State-LLC/Patch-Hive/pull/104) fix(intelligence): bound choice answers to the request's candidates (spec 005 FR-003)
- [#103](https://github.com/Zero-State-LLC/Patch-Hive/pull/103) fix(003): bounded downloads, identified receipts, and apply bound to the reviewed plan
- [#102](https://github.com/Zero-State-LLC/Patch-Hive/pull/102) fix(002): draw body text, steps and cables at the profile's font floor
- [#101](https://github.com/Zero-State-LLC/Patch-Hive/pull/101) fix(002): patch pages wrap instead of cutting, overflow fails with a code; guard publication lifecycle
- [#100](https://github.com/Zero-State-LLC/Patch-Hive/pull/100) fix(frontend): allow Cloudflare's analytics beacon in the report-only CSP
- [#99](https://github.com/Zero-State-LLC/Patch-Hive/pull/99) feat(auth): short in-memory access tokens, rotating refresh cookie, report-only CSP
- [#98](https://github.com/Zero-State-LLC/Patch-Hive/pull/98) fix(security): P1 hardening from the gap analysis
- [#97](https://github.com/Zero-State-LLC/Patch-Hive/pull/97) feat(001): resolve generic jacks to declared ones, and fail runs on contradictions
- [#96](https://github.com/Zero-State-LLC/Patch-Hive/pull/96) feat(engine): six more patch rules, and a demo rig that shows real patches
- [#94](https://github.com/Zero-State-LLC/Patch-Hive/pull/94) fix(001): five canonical categories, and no invented study patches
- [#93](https://github.com/Zero-State-LLC/Patch-Hive/pull/93) fix(001): soft-delete racks so deletion keeps run and patch history
- [#92](https://github.com/Zero-State-LLC/Patch-Hive/pull/92) fix(001): keep runs and generated patches append-only
- [#90](https://github.com/Zero-State-LLC/Patch-Hive/pull/90) chore(main): release 0.3.0-alpha.3
- [#89](https://github.com/Zero-State-LLC/Patch-Hive/pull/89) chore: ignore trail's local code-map cache
- [#88](https://github.com/Zero-State-LLC/Patch-Hive/pull/88) fix(001): gate readiness before writing, record the run lifecycle and real provenance
- [#87](https://github.com/Zero-State-LLC/Patch-Hive/pull/87) fix(edge): keep the container label name under Cloudflare's 16-byte limit
- [#86](https://github.com/Zero-State-LLC/Patch-Hive/pull/86) fix(edge): forward the https scheme to the API and restart on config changes
- [#85](https://github.com/Zero-State-LLC/Patch-Hive/pull/85) ops: add a workflow that writes edge API secrets without exposing them
- [#84](https://github.com/Zero-State-LLC/Patch-Hive/pull/84) ops(edge): run the API container under the durable_object scheduling policy
- [#83](https://github.com/Zero-State-LLC/Patch-Hive/pull/83) ops: make the public pair production and add a separate staging pair
- [#82](https://github.com/Zero-State-LLC/Patch-Hive/pull/82) fix(api): close the P0 security gaps from the gap analysis
- [#81](https://github.com/Zero-State-LLC/Patch-Hive/pull/81) docs: refresh state, board mirror and open decisions after #80
- [#80](https://github.com/Zero-State-LLC/Patch-Hive/pull/80) feat(api): users own their racks
- [#79](https://github.com/Zero-State-LLC/Patch-Hive/pull/79) fix(api): require an admin for module and case writes, and audit them
- [#78](https://github.com/Zero-State-LLC/Patch-Hive/pull/78) test: restore env and settings after the acceptance suite
- [#77](https://github.com/Zero-State-LLC/Patch-Hive/pull/77) chore: 003 fill empty catalog categories; close T025, add T027 for prod
- [#76](https://github.com/Zero-State-LLC/Patch-Hive/pull/76) fix: 003 keep parsed draws the model left empty; fill feed rows from pages
- [#75](https://github.com/Zero-State-LLC/Patch-Hive/pull/75) fix: 003 read Erica's unlabelled signed draws (+59mA, -30mA)
- [#74](https://github.com/Zero-State-LLC/Patch-Hive/pull/74) feat: 003 T026 overlays: catalog-additions-v4 and module-power-depth-v12
- [#73](https://github.com/Zero-State-LLC/Patch-Hive/pull/73) feat: 003 T026 paid pass: 4ms, Pittsburgh and Erica merged into the v2 crawl
- [#72](https://github.com/Zero-State-LLC/Patch-Hive/pull/72) feat: 003 T026 free adapter fixes for 4ms, Pittsburgh, Erica; Tiptop excluded
- [#71](https://github.com/Zero-State-LLC/Patch-Hive/pull/71) fix: 003 resolve the five staging conflicts by product identity
- [#70](https://github.com/Zero-State-LLC/Patch-Hive/pull/70) fix: 003 loader false conflicts from integer columns and unverified sources
- [#69](https://github.com/Zero-State-LLC/Patch-Hive/pull/69) fix(frontend): remove phishing-scanner triggers from patch-hive.com
- [#68](https://github.com/Zero-State-LLC/Patch-Hive/pull/68) fix: 003 rail parser misread -12V draws; correct the v2 overlays and staging
- [#67](https://github.com/Zero-State-LLC/Patch-Hive/pull/67) feat: 003 T025 loader overlays from the v2 maker crawl (+2,721 catalog rows)
- [#66](https://github.com/Zero-State-LLC/Patch-Hive/pull/66) feat: 003 T023 manufacturer crawl v2 (shared router, curated homepages, adapters, dry run)
- [#65](https://github.com/Zero-State-LLC/Patch-Hive/pull/65) feat: 003 T020–T022 source scope + Firecrawl proxy tier
- [#64](https://github.com/Zero-State-LLC/Patch-Hive/pull/64) spec(003): record owner decisions on ModularGrid leads and source scope
- [#63](https://github.com/Zero-State-LLC/Patch-Hive/pull/63) feat(storage): mirror evidence, exports and design packs to R2 (006 T055a)
- [#62](https://github.com/Zero-State-LLC/Patch-Hive/pull/62) ops(api): serve FastAPI on Cloudflare Containers at api.patch-hive.com (006 T040a, T050a)
- [#61](https://github.com/Zero-State-LLC/Patch-Hive/pull/61) spec: add missing depends_on edges and a --ready view to the spec DAG checker
- [#60](https://github.com/Zero-State-LLC/Patch-Hive/pull/60) ci(release): pass RELEASE_PLEASE_TOKEN to release-please
- [#59](https://github.com/Zero-State-LLC/Patch-Hive/pull/59) fix(github): drop case-colliding PULL_REQUEST_TEMPLATE.md
- [#58](https://github.com/Zero-State-LLC/Patch-Hive/pull/58) ci: release-please + Conventional Commit PR titles; board Status Backlog
- [#57](https://github.com/Zero-State-LLC/Patch-Hive/pull/57) spec: Spec Kit + DAG compliance audit for 001-008; add spec DAG checker
- [#56](https://github.com/Zero-State-LLC/Patch-Hive/pull/56) style(frontend): Hallmark polish to clear the Floor (cyber-hive DESIGN.md)
- [#55](https://github.com/Zero-State-LLC/Patch-Hive/pull/55) ops(frontend): ship SPA on Cloudflare Workers (patch-hive.com) and gate dev-only copy
- [#30](https://github.com/Zero-State-LLC/Patch-Hive/pull/30) data: catalog batch 7 via scrape-router (overlay v5 + new-brand candidates + dry-run receipt)
- [#29](https://github.com/Zero-State-LLC/Patch-Hive/pull/29) docs: KANBAN.md mirror of Project #8 (stacked on #25)
- [#28](https://github.com/Zero-State-LLC/Patch-Hive/pull/28) release: align versions to 0.3.0-alpha.2 + release workflow (stacked on #25)
- [#27](https://github.com/Zero-State-LLC/Patch-Hive/pull/27) specs: draft skeletons 001-004 + 005 gap list (stacked on #25)
- [#26](https://github.com/Zero-State-LLC/Patch-Hive/pull/26) ci: real backend+frontend CI; fix project automation target
- [#25](https://github.com/Zero-State-LLC/Patch-Hive/pull/25) sync: bring personal repo main (964ce18) into org
- [#24](https://github.com/Zero-State-LLC/Patch-Hive/pull/24) chore(deps-dev): bump source-map-js from 1.2.1 to 1.2.2 in /frontend
- [#22](https://github.com/Zero-State-LLC/Patch-Hive/pull/22) Clarify PatchHive next milestone in roadmap
- [#4](https://github.com/Zero-State-LLC/Patch-Hive/pull/4) ci: free security scanning to replace CodeQL
