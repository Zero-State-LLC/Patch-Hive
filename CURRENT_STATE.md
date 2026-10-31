# CURRENT_STATE

**Authoritative as of:** 2026-10-30  
**Branch pin:** `main` on `Zero-State-LLC/Patch-Hive`  
**HEAD:** `414d96a` (#172); #134–#172 plus the 0.3.0-alpha.4 release (#109) and the zod bump (#106) merged 2026-10-29/30. Database migrations (head `20261030_power_configs`) and catalog loads are applied to staging and production. **Staging and production both run `9dbb5ba`** (0.3.0-alpha.5; #168–#172 changed only docs and catalog data, loaded 2026-10-30) (API and frontend redeployed and smoke-tested 2026-10-30: staging API Worker `6cf8458e` and frontend `ea6b2239`, production API `604091fa` and frontend `2b7c6bcb`). Payments stay in test mode on both.  
**Recent work (2026-10-28):** gap-analysis fixes for specs 001–005 and P0/P1 security (#82–#105); Cloudflare edge for staging and production (#83–#87, #107); short-lived tokens, refresh cookie and an enforced CSP (#99, #100, #113); prod catalog load, Products page, category fill and catalog tombstones (#112–#116). 2026-10-29: slices A1–A5 (#118, #119, #121–#123) and a second retirement (#120); spec research (#134); lifecycle and decision fixes (#135); slices B1–B5 (#136–#140) and C1–C5 (#142–#146).  
**Open PRs:** none.  
**Board:** [Project #8](https://github.com/orgs/Zero-State-LLC/projects/8), mirrored in [docs/KANBAN.md](docs/KANBAN.md).  
**Open owner decisions:** [docs/evidence/OPEN_DECISIONS_2026-10-30.md](docs/evidence/OPEN_DECISIONS_2026-10-30.md) (13 decisions with recommendations, plus [follow-up research](docs/evidence/OPEN_DECISIONS_2026-10-30_RESEARCH.md); supersedes [the 2026-10-28 note](docs/evidence/OPEN_DESIGN_DECISIONS_2026-10-28.md)). Decided and done 2026-10-30: legacy purchase route deleted (#150), routing target empty by default (#151), strict key revocation kept (#149), HP overlay precedence fixed (#152), prod workflows given a `production` environment (#160; moving the secrets is the owner's step T101b), two rig scores defined with the other four NOT_COMPUTABLE (#161), T035 jumper pages fetched free (#163), unsourced HP values triaged (#164), jumper-dependent power loaded as `power_configs` (#166), 26 more legacy HP values re-sourced (#167), Otool's jumper settings labelled from its maker manual (#170), the SMR and VCA Matrix settings and the A-155 width decided and loaded (#172; reviewed HP corrections may now run to 84 HP), `evidence.expire` scheduling deferred to 006 T101c after T101b.  
**Next slices:** [docs/evidence/NEXT_SLICES_2026-10-28.md](docs/evidence/NEXT_SLICES_2026-10-28.md) (A1–A5 done; status updated 2026-10-29).  
**Decision research (2026-10-29):** one `research.md` per spec, 001–008, each with an "Implementation status (2026-10-29)" table in its `spec.md` and gap-closure tasks in its `tasks.md`. Receipt signing (007 R1) is built (#144); the approver key is an operator step (007 T082). The decisions awaiting the owner: the provider purchase machines (004 R1), the 221 unsourced v1 HP values (003 R7), deleting the legacy purchase route (004 R5, OQ-11), whether publishing comes back (002 OQ-6, T033), the rig score formulas (001 OQ-11) and GitHub environment protection for prod workflows (006 R2).  

**Alpha tag lineage:** `v0.3.0-alpha` (late alpha — **not** production); latest pre-release `v0.3.0-alpha.5` (2026-10-30)

### Recent merges (OBSERVED, 2026-10-30)

| PR | Result |
|----|--------|
| [#160](https://github.com/Zero-State-LLC/Patch-Hive/pull/160) | `db-migrate`, `db-load` and `edge-secrets` jobs run in a `production` or `staging` environment (006 T101a); nothing changes until the owner moves the secrets (T101b, steps in `specs/006-cloudflare-edge-clef/DEPLOY_NOTES.md`) |
| [#161](https://github.com/Zero-State-LLC/Patch-Hive/pull/161) | `routing_flex_score` and `performance_density_index` defined (`canon-metrics.1.2.0`); NOT_COMPUTABLE whenever a module lacks `io_ports`, which today is almost every real rig |
| [#162](https://github.com/Zero-State-LLC/Patch-Hive/pull/162) | `/health` reports the release version from `backend/pyproject.toml`; `python -m evidence.expire` (dry run unless `--apply`) retires expired evidence images; not scheduled |
| [#163](https://github.com/Zero-State-LLC/Patch-Hive/pull/163) | T035: 42 jumper-dependent maker pages fetched free into `receipts/t035-jumper-power.json` (11 with per-jumper draws); no catalog value changed; T034 consumes it |
| [#164](https://github.com/Zero-State-LLC/Patch-Hive/pull/164) | T038 triage: 106 v1 HP values re-sourced against their own maker pages (`module-catalog-hp-v3`), 4 corrected (`maker-corrections-v3`), 88 marked `hp_source = legacy_unsourced` (migration `20261030_catalog_hp_source`); loaded to staging and prod |
| [#172](https://github.com/Zero-State-LLC/Patch-Hive/pull/172) | Owner decisions applied: `receipts/t034-owner-decisions.json` labels the SMR base setting "jumper not set to +12V" and stores the VCA Matrix's unit-less "80 max" as an unknown +12V draw (all 21 settings load); FR-038 lets reviewed HP corrections run to 84 HP and `maker-corrections-v5` sets the Doepfer A-155 4 → 50 in both tables; spec 006 T101c (daily `evidence.expire`) follows T101b. Loaded to staging and prod |
| [#171](https://github.com/Zero-State-LLC/Patch-Hive/pull/171) | State record for #168, #170 and the Otool load |
| [#170](https://github.com/Zero-State-LLC/Patch-Hive/pull/170) | T034: `receipts/t034-manual-labels.json` names a setting the product page leaves unlabelled, only from the maker's own manual; Dave Jones Otool's Internal 5v / External 5v settings loaded to staging and prod (19 settings for 11 modules). Research on the remaining decisions in `OPEN_DECISIONS_2026-10-30_RESEARCH.md` §5–7 |
| [#168](https://github.com/Zero-State-LLC/Patch-Hive/pull/168) | State record for #159, #166, #167 and the `9dbb5ba` redeploy |
| [#166](https://github.com/Zero-State-LLC/Patch-Hive/pull/166) | T034: `power_configs` table and `rack_modules.power_config_id` (migration `20261030_power_configs`); 17 per-jumper draws for 11 modules loaded from the T035 receipt and served at `/api/modules/{id}/power-configs`; settings whose unit or base the page leaves unstated were skipped for the owner |
| [#167](https://github.com/Zero-State-LLC/Patch-Hive/pull/167) | T039: 26 more legacy HP values confirmed on maker pages (`module-catalog-hp-v4`), Doepfer A-106-1 8→14 and A-138m 8→20 corrected (`maker-corrections-v4`); 62 values stay `legacy_unsourced` |
| [#159](https://github.com/Zero-State-LLC/Patch-Hive/pull/159), [#165](https://github.com/Zero-State-LLC/Patch-Hive/pull/165) | Release 0.3.0-alpha.5; state record for #160–#164 |
| [#147](https://github.com/Zero-State-LLC/Patch-Hive/pull/147), [#148](https://github.com/Zero-State-LLC/Patch-Hive/pull/148) | State refresh; decision brief for the 13 open owner decisions |
| [#111](https://github.com/Zero-State-LLC/Patch-Hive/pull/111) | CODEOWNERS names `@scrimshawlife-ctrl`; the `partner-agents` team no longer had repo access |
| [#149](https://github.com/Zero-State-LLC/Patch-Hive/pull/149) | Spec 007 research R1 describes the strict key revocation the verifier enforces |
| [#150](https://github.com/Zero-State-LLC/Patch-Hive/pull/150) | Legacy `POST /api/monetization/purchases` deleted (004 T043); referrals behind `ENABLE_REFERRALS`; the old `ENABLE_LEGACY_REFERRALS` key is accepted and ignored with a warning |
| [#151](https://github.com/Zero-State-LLC/Patch-Hive/pull/151) | `decision_routing_target` defaults to empty: failed decisions end UNRESOLVED until a review queue consumes ESCALATE |
| [#152](https://github.com/Zero-State-LLC/Patch-Hive/pull/152) | Maker-cited HP overlays fill before the unsourced v1 overlay |
| [#153](https://github.com/Zero-State-LLC/Patch-Hive/pull/153) | Reviewed HP corrections from maker pages: Acid Rain Junction 6→4, Doepfer A-101-3 10→30, A-137-2 10→14; loaded to staging and prod |
| [#154](https://github.com/Zero-State-LLC/Patch-Hive/pull/154) | The loader plans a `needs_reverify` clear only when the database would apply it, so a rerun plans nothing |

### Recent merges (OBSERVED, 2026-10-29)

| PR | Result |
|----|--------|
| [#134](https://github.com/Zero-State-LLC/Patch-Hive/pull/134) | Research for every open decision; specs 001–008 reconciled with the code; gap-closure tasks added |
| [#135](https://github.com/Zero-State-LLC/Patch-Hive/pull/135) | Catalog lifecycle: tombstoned rows refused, `needs_reverify` cleared once every flagged field is corrected (CHICANE cleared on staging and prod). Decisions: invalid packets escalate or stay unresolved; every provider goes through the guarded flow |
| [#136](https://github.com/Zero-State-LLC/Patch-Hive/pull/136) | Workflows: foreign pin-PR workflow removed, `actions: write` dropped, orphan R2 token revoked on failure |
| [#137](https://github.com/Zero-State-LLC/Patch-Hive/pull/137) | Rig: `allow_feedback` and `prefer_simple` honoured; the full IR is hashed |
| [#138](https://github.com/Zero-State-LLC/Patch-Hive/pull/138) | Book: unlisted by default, bounded gallery filter, wrapped cover disclaimer, manifest warnings |
| [#139](https://github.com/Zero-State-LLC/Patch-Hive/pull/139) | Commerce: append-only credit ledger (database trigger), live-mode gate, webhook secret rotation and race handling |
| [#140](https://github.com/Zero-State-LLC/Patch-Hive/pull/140) | Decision evaluation runs the candidate check; the walkthrough accepts staging only |
| [#141](https://github.com/Zero-State-LLC/Patch-Hive/pull/141) | Spec ticks for work shipped in #135 (003 T036/T037, 005 T081/T082) |
| [#142](https://github.com/Zero-State-LLC/Patch-Hive/pull/142) | Rig: the canon compiler runs on the generation path; one `RigMetricsPacket` per rig revision (scores `NOT_COMPUTABLE` until OQ-11) |
| [#143](https://github.com/Zero-State-LLC/Patch-Hive/pull/143) | Book: `validate_book` stage, plate page-count check, warnings in the stage receipt; publishing a draft refused until it is bound to a validated book |
| [#144](https://github.com/Zero-State-LLC/Patch-Hive/pull/144) | Evaluation receipts verified by replay and signed (Ed25519, committed allowlist, empty until the operator adds a key); readiness gates verify the receipt |
| [#145](https://github.com/Zero-State-LLC/Patch-Hive/pull/145) | Commerce: legacy balance route removed; every webhook event ends `processed`, `duplicate`, `unresolved` or `ignored` |
| [#146](https://github.com/Zero-State-LLC/Patch-Hive/pull/146) | Decisions: idempotency checked before the provider call (advisory lock, key bindings that replay their own outcome); `human_review` routing target |

### Recent merges (OBSERVED, 2026-10-28)

| PR | Result |
|----|--------|
| [#82](https://github.com/Zero-State-LLC/Patch-Hive/pull/82), [#98](https://github.com/Zero-State-LLC/Patch-Hive/pull/98) | P0 and P1 security fixes from the gap analysis: export idempotency per user, admin-only role grants, sign-in lockout and per-IP limits, Argon2 with rehash, one referral reward |
| [#83](https://github.com/Zero-State-LLC/Patch-Hive/pull/83)–[#87](https://github.com/Zero-State-LLC/Patch-Hive/pull/87), [#107](https://github.com/Zero-State-LLC/Patch-Hive/pull/107) | Edge: production and staging pairs on Cloudflare, container scheduling, secrets workflow (production secrets now reach the production Worker), https forwarding |
| [#88](https://github.com/Zero-State-LLC/Patch-Hive/pull/88), [#92](https://github.com/Zero-State-LLC/Patch-Hive/pull/92)–[#97](https://github.com/Zero-State-LLC/Patch-Hive/pull/97) | Spec 001: gated run lifecycle, append-only runs and patches, rack soft-delete, five categories, six engine rules, port resolution and validation |
| [#99](https://github.com/Zero-State-LLC/Patch-Hive/pull/99), [#100](https://github.com/Zero-State-LLC/Patch-Hive/pull/100), [#113](https://github.com/Zero-State-LLC/Patch-Hive/pull/113) | 15-minute in-memory access tokens, rotating refresh cookie, CSP enforced, sign-in open |
| [#101](https://github.com/Zero-State-LLC/Patch-Hive/pull/101), [#102](https://github.com/Zero-State-LLC/Patch-Hive/pull/102) | Spec 002: patch pages wrap or fail with a code, font floors, publication lifecycle |
| [#103](https://github.com/Zero-State-LLC/Patch-Hive/pull/103) | Spec 003: bounded downloads, identified receipts, apply bound to the reviewed `plan_hash` (case writes included) |
| [#104](https://github.com/Zero-State-LLC/Patch-Hive/pull/104), [#105](https://github.com/Zero-State-LLC/Patch-Hive/pull/105) | Spec 005: answers bounded to the request's candidates; a failed provider is UNRESOLVED or ESCALATE, never REJECT |
| [#112](https://github.com/Zero-State-LLC/Patch-Hive/pull/112) | Catalog loaded to prod (T027) |
| [#114](https://github.com/Zero-State-LLC/Patch-Hive/pull/114) | Products page reads the module catalog (was empty in production) |
| [#115](https://github.com/Zero-State-LLC/Patch-Hive/pull/115) | 183 missing categories filled from crawl tags (T028) |
| [#116](https://github.com/Zero-State-LLC/Patch-Hive/pull/116) | 263 misattributed or bogus rows tombstoned, 7 modules re-added under their makers (T029) |
| [#117](https://github.com/Zero-State-LLC/Patch-Hive/pull/117) | Docs, board mirror and the next-slices plan |
| [#118](https://github.com/Zero-State-LLC/Patch-Hive/pull/118) | A1: unknown module power counted per rail, not as 0 mA; one rounding rule |
| [#119](https://github.com/Zero-State-LLC/Patch-Hive/pull/119) | A2: the crawler refuses a homepage another brand owns (T030) |
| [#120](https://github.com/Zero-State-LLC/Patch-Hive/pull/120) | Second retirement: 185 more misattributed rows (ALM Busy Circuits copies and others) |
| [#121](https://github.com/Zero-State-LLC/Patch-Hive/pull/121) | A3: six crawled modules no overlay held |
| [#122](https://github.com/Zero-State-LLC/Patch-Hive/pull/122) | A4: racks warn when they hold a retired module |
| [#123](https://github.com/Zero-State-LLC/Patch-Hive/pull/123) | A5: signed-out page loads skip the refresh call |

## OBSERVED product posture

| Area | State |
|------|--------|
| Product identity | Deterministic Eurorack **rig + patch documentation** |
| Canonical domain | `backend/canon/` (+ design recipes, export fulfillment) |
| Design Engine flags | **Default off** — staging overlay + walkthrough PASS (#147) |
| Alembic | Single head through `20261030_catalog_hp_source`; staging and prod migrated 2026-10-30 |
| Rig validation | Unknown draws are per rail (`POWER_RAIL_INCOMPLETE`, lower bounds); retired placements warn (`MODULE_TOMBSTONED`) on every rack read |
| Health | `/health` liveness; `/health/ready` includes DB |
| Local Compose staging | `docker-compose.staging.yml` + `scripts/staging/*` + `scripts/test/run.*` |
| Test automation | `scripts/test/run.sh\|ps1` · CI `acceptance-tests.yml` · 11 acceptance PASS |
| Dual-path inventory | F0/F1/F3/F2 done; F4/F5 residual; Z deferred |
| Named staging host | Plan only — **NOT_PERFORMED** |
| Payments | Test-mode only. Payment webhook events are recorded `unresolved` (`HANDLER_NOT_IMPLEMENTED`) until 004 T046/T049 |
| Publishing | Drafts cannot be published (`PUBLICATION_BOOK_NOT_VALIDATED`) until the owner decides OQ-6 (002 T033) |
| Readiness gates | Refuse every evaluation receipt (`APPROVER_KEY_UNKNOWN`) until the operator commits an approver public key (007 T082) |
| Module catalog (staging = prod) | 4,184 catalog rows and 4,154 modules, of which 448 each are tombstoned; 3,736 visible from 356 brands, 0 conflicts. 855 rows have no category. Sovage CHICANE corrected to 4 HP (#125) and unflagged (#135, loads of 2026-10-29). HP corrected for Acid Rain Junction, Doepfer A-101-3 and A-137-2 (#153, loads of 2026-10-30); A-101-3's module stays flagged because its +5V draw is unstated: doepfer.de gives +12V 50 mA, -12V 50 mA and 65 mm depth (already loaded from `module-power-depth-v10`), but neither the product page nor either manual states +5V. HP corrected for Make Noise DPO (28) and Morphagene (20), Bastl Knit Rider (16) and Intellijel MEMS Mic 1U (10) (#164); A-106-1 (14) and A-138m (20) corrected (#167), A-155 (50) corrected (#172), loads of 2026-10-30; 61 HP values carry `hp_source = legacy_unsourced` until a maker page confirms them (mostly ADDAC and Befaco, whose sites block automated reads; T039 open). 21 jumper settings for 11 modules are in `power_configs` (#166, #170, #172), every setting the T035 receipt recorded. The older duplicate row "QCD: Quad Clock Distributor" has none; they sit on "4ms QCD"). Sources: Phase 2 seed (ModularGrid leads, tagged `unknown`/`CATALOG_OBSERVED`) plus maker pages (`official_publication`). Maker-crawl page cache deleted 2026-10-28; committed crawl results intact |
| API access | Module and case writes admin-only (#79). Racks owner-scoped (#80): owner reads/writes, admin read roles read all, public racks readable by anyone, others 404. Catalog materialize and stateless layout recommendation stay public |
| Accounts | Sign-in open on staging and production (#113). No account yet created on production; a real sign-up is still to be tried |
| Production deploy | Frontend (`patch-hive.com`) and API (`api.patch-hive.com`) on Cloudflare, deployed manually with `wrangler deploy` from a checkout of main (no deploy workflow); API and frontend last deployed at `9dbb5ba` on 2026-10-30. CSP enforced; CORS limited to the exact origin. `/health` reports the release version (0.3.0-alpha.5) |
| CI | Repo is public so GitHub Actions runs on free minutes; with the repo private the Actions budget blocks every job |
| Production readiness | **Not ready** (beta-staging engineering) — [assessment](docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md) · [matrix](docs/evidence/PRODUCTION_READINESS_MATRIX.md) · [delta](docs/evidence/PRODUCTION_READINESS_DELTA_2026-07-26.md) |

## Decision Intelligence specification campaign (2026-09-25)

**OBSERVED:** provider-neutral Decision Intelligence is now specified under `specs/005-decision-intelligence/`; implementation remains pending and Jev is not enabled. The constitution makes evidence non-canonical and forbids probabilistic direct-to-canon writes.

**Next implementation gate:** contracts + deterministic policy + fixture provider before any Jev adapter.

## Immediate continuation priorities

1. **Review #110 first.** Today `edge/api/src/index.ts` sends `RUN_MIGRATIONS: "true"`, so every API container cold start runs `alembic upgrade head` on its database, production included. Deploying a branch with a new migration migrates that database without `db-migrate.yml`. #110 makes startup migrations opt-in and warns when the schema is behind. Its CI is green, but it needs updating with main (it is behind), and that is the owner's branch.
2. Catalog: 61 HP values stay `legacy_unsourced` (ADDAC System and Befaco block plain requests; 21 others need another maker source), T039. `evidence.expire` gets a daily job once T101b is done (006 T101c; 0 evidence images today). T035 needed no paid pass (#163); Frap needs none either (D7).
3. Operator:
   - real sign-up on production;
   - verify seeded demo auth on staging (008 T030b);
   - VirusTotal reanalysis;
   - rotate the context.dev and OpenRouter keys;
   - add `PROJECT_TOKEN` and `RELEASE_PLEASE_TOKEN`;
   - decide repo visibility versus the Actions budget;
   - #106 (zod; its CodeQL failures came from the private-repo period, so rerun it), #109 (release), #111 (CODEOWNERS);
   - confirm specs 001–004 (R6).

**Local test automation:**
`cd backend && pytest tests -q` with a local Postgres 15 for the population tests (1,045 passed, 2 skipped on #125) · acceptance suite separately (11 passed; #78 lets it run in the same invocation)

## Authority boundary

**Do not:** deploy production, enable live Stripe, charge users, or activate hardware without separate operator authorization.

## Doc index

| Doc | Use |
|-----|-----|
| [docs/ROADMAP.md](docs/ROADMAP.md) | Capability roadmap |
| [docs/KANBAN.md](docs/KANBAN.md) | Board mirror (Project #8 is the source of truth) |
| [docs/evidence/OPEN_DESIGN_DECISIONS_2026-10-28.md](docs/evidence/OPEN_DESIGN_DECISIONS_2026-10-28.md) | Open owner decisions with research |
| [docs/CONTINUATION.md](docs/CONTINUATION.md) | Engineering backlog (dated 2026-07-21; see the board for current work) |
| [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md) | Gate framework |
| [docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md](docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md) | Latest readiness narrative |
| [docs/FEATURE_FLAGS.md](docs/FEATURE_FLAGS.md) | Flags |
| [brand/README.md](brand/README.md) | Brand kit |
| [.specify/memory/constitution.md](.specify/memory/constitution.md) | SpecKit constitution |
| [specs/005-decision-intelligence/spec.md](specs/005-decision-intelligence/spec.md) | Decision Intelligence requirements |

## Database (Neon, provisioned 2026-10-16)

OBSERVED:

- Provider: Neon, project `patchhive` (id `polished-night-86976142`), region `aws-us-west-2`, Postgres 15, database `patchhive`.
- Branches: `main` is **prod** (default); `staging` was branched from `main`.
- Compute: 0.25 CU fixed, scale-to-zero after 5 min.
- Hard project quota (the project suspends instead of overbilling): `compute_time_seconds` 180000 (about 50 CU-hours per month) and `logical_size_bytes` 1 GiB. The org is on the Neon Launch plan (usage-billed).
- Connection strings: GitHub Actions secrets `PATCHHIVE_DATABASE_URL_STAGING` and `PATCHHIVE_DATABASE_URL_PROD`. Never commit them.
- Migrations: run the manual workflow `.github/workflows/db-migrate.yml` (choose `staging` or `prod`). The agent box cannot reach Postgres port 5432 directly.
- Data load: manual workflow `.github/workflows/db-load.yml` (`env` staging or prod, `mode` dry-run by default or apply). Apply dumps the affected tables first; the dump stays on the runner (only its size and sha256 go to the job summary) and the uploaded receipt is counts only, because this repo's artifacts are public. The agent box cannot open port 5432, so the load runs in Actions. Run `db-migrate.yml` on the same ref first; the load refuses to start unless the database is at that checkout's alembic head. Operator yes is still required before apply.
