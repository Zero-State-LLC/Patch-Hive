# PatchHive continuation plan

**Status date:** 2026-07-21  
**main HEAD:** `de1fbcf` (Login #95; Design Engine #90–#94 on main)  
**Open:** [#96](https://github.com/scrimshawlife-ctrl/Patch-Hive/pull/96) Cyber Hive pages  
**Tracking:** Issue #46 closed · PR #47–#95 on main  
**Readiness:** [evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md](evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md)  
**Roadmap:** [ROADMAP.md](ROADMAP.md)  
**Plan:** [evidence/CONTINUATION_PLAN_POST_75.md](evidence/CONTINUATION_PLAN_POST_75.md)

## Where we are

Phases 0–8 of `PATCHHIVE_ONESHOT_CANON_ALIGNMENT_001` are on `main` (`a162f85` via PR #47).  
P1 dual-path slices A–E and Visual System Intelligence **specifications** are on `main`.  
This campaign implements VSI **P0 contracts** (evidence adapter, inventory, patch gates) without production vision models.

### Done (OBSERVED)

- [x] Canonical contracts, compiler, runes, immutable hierarchy (ADR 0001)
- [x] Alembic chain through `20240928_fix_schema_gaps` (single head)
- [x] Canonical workspace UI + PatchGraph a11y pair + theme tokens
- [x] Photo evidence resolution path (untrusted evidence only)
- [x] Atomic credits/exports, download tokens, Stripe webhook adapter (test mode)
- [x] Feature flags default-off for legacy social/publish/leaderboards/referrals
- [x] Security workflow (audit, Bandit, Gitleaks, SBOM)
- [x] Docs spine: CANON_ALIGNMENT, FEATURE_FLAGS, SECURITY, OPERATIONS, VALIDATION_EVIDENCE, ACCESSIBILITY
- [x] HTTP `/api/canon/*` for credits, exports, downloads, webhooks
- [x] Merge PR #47 to `main` — `a162f85` @ 2026-07-20T23:46:29Z
- [x] **P1 client wiring (PR #49):** `canonApi` + Account/RigDetail use `/api/canon` for balance, summary, list/create exports, download tokens; `monetizationApi.balance` aliases canon; `exportApi.patchbookExport` deprecated; Playwright mocks canon balance; gitignore allows `frontend/src/lib/`
- [x] Main CI green on merge commit of #49 (`71a4dfa`)

### Explicitly not done

- [ ] Production or staging deploy
- [ ] Live Stripe / `ALLOW_PRODUCTION_PAYMENTS=true`
- [ ] Full retirement of legacy rack/patch/export dual paths
- [x] Move acceptance credits path off legacy debit POST (PR #51)
- [x] Run DTOs with server-authored bridge fields (PR #54; namespace still legacy-*)
- [ ] Deletion of historical top-level/`backend/patchhive` package and unrouted page modules
- [x] Cases/Patches list pages beyond stubs (PR #69)
- [ ] Hardware, DSP, MIDI/CV, or ModularGrid live provider implementation
- [x] Provider-neutral vision adapter + mock/fixture (VSI campaign WP-02)
- [x] SystemInventoryRevision + confirmed-inventory patch gate (WP-03)
- [x] Wire inventory gate into generate path (WP-05 / C2 — rack placements as manual USER_CONFIRMED)
- [x] Persist inventory revisions via Alembic (WP-06 — `20240929_visual_inventory_evidence`)
- [x] Native canon bridge IDs (`rig-rev-*` / `gen-run-*`; legacy helpers deprecated)
- [x] Multi-image evidence upload + retention soft-delete
- [ ] Live vision provider behind adapter (ops secret + evaluation dataset)

## 2026-09-25 Decision Intelligence campaign

SpecKit normalization and feature 005 are specified on the campaign branch. Implementation order is contract-first: DecisionProvider schemas -> deterministic DecisionPolicy -> fixture provider -> persistence/telemetry -> Jev adapter (flag off) -> module/capability/port intelligence -> evaluation -> staging enablement. Do not wire Jev directly into legacy modules/racks or canonical mutation paths. See [`../specs/005-decision-intelligence/tasks.md`](../specs/005-decision-intelligence/tasks.md).

## Recommended work order

### P0 — Ship gate (post-#47 / #49)

1. ~~Human review of PR #47~~ **DONE**
2. ~~Human review of PR #49~~ **DONE**
3. [x] Confirm `alembic heads` == `20240928_fix_schema_gaps` on clean `main` checkout
4. [x] Confirm flags in `.env.example`: all `ENABLE_LEGACY_*` false; `STRIPE_TEST_MODE=true`; `ALLOW_PRODUCTION_PAYMENTS=false`
5. [x] Main CI green @ `71a4dfa`
6. Optional: tag `v0.2.1-canon-p1-client` (or `v0.2.0-canon-mvp` if not tagged) and cut release notes

### P1 — Dual-path reduction (ACTIVE residual)

**Completed slices:**
- **PR #49:** FE debit/list/balance → canon only.
- **PR #51:** acceptance debit → `/api/canon/exports`; admin grant dual-writes canonical ledger; legacy debit gateable via `ENABLE_LEGACY_PATCHBOOK_DEBIT`.
- **PR #54:** run list/get DTO exposes server-authored export bridge; RigDetail uses DTO fields only; `runs.bridge` ensures canon FK targets.

**Progress checklist:**
- [x] Acceptance debit tests use `POST /api/canon/exports` + canonical ledger
- [x] Admin credit grant dual-writes `canonical_credit_ledger`
- [x] Legacy PatchBook debit: `deprecated` JSON markers + `ENABLE_LEGACY_PATCHBOOK_DEBIT` (default **false** → 410)
- [x] Run DTOs carry `rig_revision_id`, `source_run_id`, `artifact_manifest_hash`, `export_bridge_ready` (server-authored via `runs.bridge`)
- [x] RigDetail export uses server bridge fields (no client `legacyRunManifestHash` invent)
- [x] Default `ENABLE_LEGACY_PATCHBOOK_DEBIT=false` once remaining non-MVP callers cleared
- [ ] Full retirement of legacy rack/patch list dual path (still needed for inventory UI)
- [x] Promote bridge IDs to native `rig-rev-*` / `gen-run-*` (PR #66)

**Next slices (ordered):**

1. ~~**Acceptance → canon credits path**~~ **DONE** (PR #51)  
2. ~~**Deprecate / feature-gate legacy debit POST**~~ **DONE** (PR #51; default **false** after caller audit — slice E)  
3. ~~**Run / revision bridge honesty**~~ **DONE** (PR #54 — server DTO + ensure canon rows; namespace still legacy-* until native generator)  

4. ~~**Inventory dual-path plan (design-first, then thin PR)**~~ **DESIGN DONE** — matrix in [CANON_ALIGNMENT.md](CANON_ALIGNMENT.md#inventory-dual-path-matrix-design-first)  
   - Slices **A–E** **DONE** (optional alias B + content hash C included).  
   - Do **not** big-bang delete racks routers.  
   - **Exit (design):** matrix merged. **Exit (code):** slice A green on CI.
### P2 — Package and dead-UI hygiene

1. ~~**Unrouted frontend pages**~~ **DONE**  
   - Moved to `frontend/src/legacy/pages/`; clients in `frontend/src/legacy/apiClients.ts`.  
   - See `frontend/src/legacy/README.md`.  
   - **Exit:** `rg` for those page names only under `legacy/`; App routes unchanged.
2. ~~**Import telemetry for `patchhive` package**~~ **DONE** (Wave 4)  
   - Telemetry: [engineering/PATCHHIVE_IMPORT_TELEMETRY.md](engineering/PATCHHIVE_IMPORT_TELEMETRY.md)  
   - Marker `legacy_pipeline` on residual unit importers; `patchhive/tests` quarantined  
   - CI guard: `scripts/ai/check_no_canon_patchhive_imports.sh`  
   - **Exit met:** documented graph + no canon/evidence → package imports

3. Worktree hygiene: ignore accidental Finder duplicates (`frontend/src/lib/hash 2.ts` etc.) — do not commit.

### P3 — Staging operations

1. ~~Staging host plan + Compose staging profile~~ **DONE** (design + `docker-compose.staging.yml`; named host still operator pick)
2. ~~Local Docker staging stack~~ **DONE** ([STAGING_LOCAL_DOCKER_RECEIPT.md](evidence/STAGING_LOCAL_DOCKER_RECEIPT.md)); named public domain still optional ([DOMAIN_CUTOVER_CHECKLIST.md](evidence/DOMAIN_CUTOVER_CHECKLIST.md)).
3. Run acceptance suite against staging Postgres.
4. Backup/restore drill; ledger `reconcile` job if present.
5. Manual accessibility protocol on staging (see ACCESSIBILITY.md).
6. Expand Playwright beyond mocked MVP when staging exists.

### P4 — Product depth (still MVP-scoped)

1. ~~**Cases / Patches list pages**~~ **DONE** (PR #69)
2. ~~Deeper rig revision UX~~ **DONE** (revision picker + overlay notes/favorite/tried).
3. ~~Stronger empty/loading/error parity on Modules list~~ **DONE** (PR #77 + prior)  
4. ~~Expand golden fixtures / property tests for compiler edge cases~~ **DONE** (this PR)  

5. Real image scanner implementation behind `ImageScanner` (ops secret + service).

### P4b — Visual System Intelligence (ACTIVE residual)

See [VISUAL_SYSTEM_INTELLIGENCE_ROADMAP.md](VISUAL_SYSTEM_INTELLIGENCE_ROADMAP.md), [evidence/WORK_PACKAGES.md](evidence/WORK_PACKAGES.md), and [evidence/CONTINUATION_EXECUTION_2026-07-21.md](evidence/CONTINUATION_EXECUTION_2026-07-21.md).

1. ~~**WP-05:** inventory gate on generate~~ **DONE**
2. ~~**WP-06:** Alembic inventory + image assets~~ **DONE** (`20240929_visual_inventory_evidence`)
3. ~~Native bridge IDs~~ **DONE** (`rig-rev-*` / `gen-run-*`)
4. ~~Multi-image upload + retention~~ **DONE** (`POST/GET/DELETE /api/racks/{id}/evidence/images`)
5. ~~Ranked candidate confirmation API + multi-candidate RackBuilder~~ **DONE**
6. ~~Evaluation + cloud adapter~~ **DONE** (PR #67)
7. ~~AI engineering foundation~~ **DONE** (PR #70)
8. ~~Land PR #66~~ **DONE**
9. ~~Wire RackBuilder live evidence APIs~~ **DONE** (PR #69)
10. ~~Cases/Patches list pages~~ **DONE** (PR #69)
11. ~~Post-foundation reaudit + telemetry + ast-grep~~ **DONE** (PR #71)
12. ~~Rig revision picker + personal overlays~~ **DONE** (this branch; Alembic `20240930_patch_user_overlays`)
13. ~~Multi-photo reconciliation (VSI P1)~~ **PARTIAL** (fuse API + PR #74 UI + PR #75 confirm; accuracy NOT_COMPUTABLE)
14. ~~Staging Compose drill (ops)~~ **DONE** (local OBSERVED — `docs/evidence/STAGING_COMPOSE_RECEIPT.md`; not production)
15. ~~Fusion panel confirm/reject/defer + confirm-all non-conflict~~ **DONE** (PR #75)
16. ~~Playwright multi-photo + fusion panel~~ **DONE** (this PR / Wave 1)
17. ~~RigDetail inventory-revision receipt surface~~ **DONE** (`GET .../evidence/inventory` + overview panel)
18. ~~Modules catalog polish~~ **DONE** (search/filter/sort + place-on-rig entry; Racks list loading/empty/retry)
19. ~~`patchhive` import telemetry quarantine~~ **DONE** (Wave 4 — telemetry, markers, CI guard)
20. ~~Compiler validation edge-case suite expansion~~ **DONE** (signal/direction/feedback/attenuation/empty)
21. ~~Migrate one `legacy_pipeline` suite onto canon contracts~~ **DONE** (`test_schema_roundtrip` → canon `RigMetricsPacket`)
22. ~~Gallery append-only revisions on canon~~ **DONE** (`canon.gallery_revisions`; patchhive shim)
23. ~~All residual `legacy_pipeline` unit tests off patchhive~~ **DONE** (function_registry, query_surface, pipeline, export_pack)
24. ~~Staging host plan + compose.staging~~ **DONE** (named host NOT_PERFORMED)
25. ~~Dual-path retirement design F0~~ **DONE** ([DUAL_PATH_RETIREMENT_DESIGN.md](evidence/DUAL_PATH_RETIREMENT_DESIGN.md))
26. Optional: cut `v0.3.0-alpha.1` release tag after this docs/ops PR
27. ~~Dual-path F3 generate dual-write audit~~ **DONE** ([F3_GENERATE_DUAL_WRITE_AUDIT.md](evidence/F3_GENERATE_DUAL_WRITE_AUDIT.md))
28. ~~RigDetail inventory→generate UX loop~~ **DONE** (PR #85)
29. ~~Next dual-path: F2 thin `GET /api/canon/rigs`~~ **DONE** · ~~F4 evidence aliases~~ **DONE** — next: F5 FE inventory list cutover, or operator staging host

### P5 — Explicitly deferred

- Community feed, profiles, comments, votes, following  
- Public publishing gallery as product surface  
- Leaderboards, contests, marketplace, curriculum  
- Live payments and customer charging  
- Next.js rewrite (forbidden by campaign: keep React/Vite + FastAPI)  
- Abraxas bridge productization beyond existing `docs/CANON.md` interface notes (RigMetricsPacket etc.) — separate campaign

## Repo continuation analysis (2026-07-21)

**Method:** github continuation recipe + live `main` @ `71a4dfa` evidence packet (no open campaign PR).

### OBSERVED

| Fact | Evidence |
|------|----------|
| HEAD == origin/main | `71a4dfaab7aefe1d4cb920dd9f83abcb7757fea7` |
| No open PRs/issues | `gh pr/issue list` empty open set |
| Alembic single head | `20240928_fix_schema_gaps` |
| Canon routers mounted | `backend/main.py` includes `/api/canon` |
| Legacy routers still mounted | racks, patches, runs, export, monetization, me |
| FE debit path | `RigDetail` → `canonApi.createExport` only |
| FE inventory path | `rackApi` / `runApi` / `patchApi` still primary |
| Acceptance debit path | still `/api/export/runs/{id}/patchbook` |
| Unrouted social/publish pages | on disk, not in `App.tsx` Routes |
| CI green on #49 merge push | Backend / Quality / Security success |
| Docs drift pre-this-pass | README/CURRENT_STATE still claimed HEAD `a162f85` (PR #47 only) |

### INFERRED

- Safest next engineering PR is **acceptance + legacy debit deprecation**, not rack rewrite (smaller blast radius, clears dual-debit residual).
- Cases/Patches stubs are product depth (P4), not blockers for “canon MVP on main.”
- `patchhive` package removal is blocked on test corpus rewrite — quarantine before delete.

### SPECULATIVE (do not promote)

- Staging host choice (Render vs Compose vs Azure) without operator pick.
- Whether racks remain forever as CANON_SUPPORTING vs full rename to “rigs” HTTP.

### Recommended next operator action

1. Merge this docs PR (status truth).  
2. Open `feat/p1-acceptance-canon-exports` implementing CONTINUATION P1 items 1–2.  
3. Hold production deploy and live Stripe.

## Verification commands (copy/paste)

```bash
# main
git fetch origin && git checkout main && git pull --ff-only
git rev-parse HEAD   # expect 296fc3b… or later

cd backend
# prefer project venv; scrub Hermes PYTHONPATH if present
env -u PYTHONPATH python -m pip install -e '.[dev]'
alembic heads        # expect 20240928_fix_schema_gaps
env -u PYTHONPATH python -m pytest tests --ignore=tests/acceptance -q
env -u PYTHONPATH python -m pytest tests/api/test_canon_export_api.py -q

cd ../frontend
npm ci
env -u PYTHONPATH npm test -- --run
env -u PYTHONPATH npm run type-check
env -u PYTHONPATH npm run test:e2e
```

CI authoritative when local Docker/Postgres missing. Full `make test` requires Docker Compose plugin.

## Drift watchlist

| Item | Risk |
|------|------|
| Root `DEPLOY_STATUS.md` (2025-11-26 “ready for Render”) | Stale — do not treat as ship authority |
| Root `CANON_DIFF.md` / `CANON_SYNC.md` | Pre-campaign audits — superseded by CANON_ALIGNMENT |
| `docs/OPERATIONS.md` Alembic head | Must match **20240928_fix_schema_gaps** |
| Social pages still on disk | Dead UI surface if re-linked accidentally |
| Dual export debit paths | Double-debit risk if both live without shared ledger — prefer canon only; acceptance still on legacy POST |
| README “checkout campaign branch” | Stale until this docs pass — main is default |
| Finder `* 2.ts` duplicates under `frontend/src/lib/` | Noise; never commit |

## Exit criteria for “canon MVP on main”

1. ~~PR #47 merged~~ **DONE**  
2. ~~Main CI green on merge~~ **DONE** (also #49 @ `71a4dfa`)  
3. Docs on main: README + CURRENT_STATE + CONTINUATION agree on merged HEAD — **this pass**  
4. No production payment flags enabled — **true in `.env.example`**  
5. Staging optional but recommended before any public traffic claim  
6. **Stretch (P1 complete):** acceptance + UI share one debit ledger path (canon)

**Active engineering starts at P1 inventory dual-path plan / P2 dead-UI hygiene.**
