# CURRENT_STATE

**Authoritative as of:** 2026-10-28  
**Branch pin:** `main` on `Zero-State-LLC/Patch-Hive`  
**HEAD:** `433bb76` (#80, users own their racks)  
**Recent work:** maker-crawl catalog pipeline (spec 003 T020–T027, #64–#77) loaded to staging; API write auth (#79) and rack ownership (#80); phishing-scanner fixes for patch-hive.com (#69).  
**Open PRs:** [#78](https://github.com/Zero-State-LLC/Patch-Hive/pull/78) acceptance-suite env isolation.  
**Board:** [Project #8](https://github.com/orgs/Zero-State-LLC/projects/8), mirrored in [docs/KANBAN.md](docs/KANBAN.md).  
**Open owner decisions:** [docs/evidence/OPEN_DESIGN_DECISIONS_2026-10-28.md](docs/evidence/OPEN_DESIGN_DECISIONS_2026-10-28.md).  

**Alpha tag lineage:** `v0.3.0-alpha` (late alpha — **not** production)

### Recent merges (OBSERVED)

| PR | Result |
|----|--------|
| [#62](https://github.com/Zero-State-LLC/Patch-Hive/pull/62) | FastAPI on Cloudflare Containers for `api.patch-hive.com` (merged; not deployed) |
| [#63](https://github.com/Zero-State-LLC/Patch-Hive/pull/63) | Evidence, exports and design packs mirrored to R2 |
| [#64](https://github.com/Zero-State-LLC/Patch-Hive/pull/64)–[#65](https://github.com/Zero-State-LLC/Patch-Hive/pull/65) | Spec 003 owner decisions D1/D2; ModularGrid rows tagged as leads; maker-only source scope |
| [#66](https://github.com/Zero-State-LLC/Patch-Hive/pull/66)–[#67](https://github.com/Zero-State-LLC/Patch-Hive/pull/67) | Maker crawl v2 (shared router, adapters, paid run) and loader overlays |
| [#68](https://github.com/Zero-State-LLC/Patch-Hive/pull/68), [#70](https://github.com/Zero-State-LLC/Patch-Hive/pull/70), [#71](https://github.com/Zero-State-LLC/Patch-Hive/pull/71) | Rail-parser fix, false-conflict fix, product-identity review: staging at 0 conflicts |
| [#72](https://github.com/Zero-State-LLC/Patch-Hive/pull/72)–[#77](https://github.com/Zero-State-LLC/Patch-Hive/pull/77) | T026 pass (4ms, Pittsburgh, Erica), coverage fixes, categories; T025 done, T027 (prod) added |
| [#69](https://github.com/Zero-State-LLC/Patch-Hive/pull/69) | patch-hive.com: no sign-in until the API is live, real 404s, favicon, robots/sitemap |
| [#79](https://github.com/Zero-State-LLC/Patch-Hive/pull/79) | Module and case writes admin-only and audited |
| [#80](https://github.com/Zero-State-LLC/Patch-Hive/pull/80) | Users own their racks; patches, runs and exports follow the rack |

## OBSERVED product posture

| Area | State |
|------|--------|
| Product identity | Deterministic Eurorack **rig + patch documentation** |
| Canonical domain | `backend/canon/` (+ design recipes, export fulfillment) |
| Design Engine flags | **Default off** — staging overlay + walkthrough PASS (#147) |
| Alembic | Single head through `20261027_catalog_lead_tags`; staging migrated 2026-10-27, prod not yet |
| Health | `/health` liveness; `/health/ready` includes DB |
| Local Compose staging | `docker-compose.staging.yml` + `scripts/staging/*` + `scripts/test/run.*` |
| Test automation | `scripts/test/run.sh\|ps1` · CI `acceptance-tests.yml` · 11 acceptance PASS |
| Dual-path inventory | F0/F1/F3/F2 done; F4/F5 residual; Z deferred |
| Named staging host | Plan only — **NOT_PERFORMED** |
| Payments | Test-mode only |
| Module catalog (staging) | 4,172 catalog rows, 4,142 modules, 0 conflicts; sources: Phase 2 seed (ModularGrid leads, tagged `unknown`/`CATALOG_OBSERVED`) plus maker pages (`official_publication`). Prod not loaded (T027) |
| API access | Module and case writes admin-only (#79). Racks owner-scoped (#80): owner reads/writes, admin read roles read all, public racks readable by anyone, others 404. Catalog materialize and stateless layout recommendation stay public |
| Accounts | Sign-in hidden in production builds until `VITE_ACCOUNTS_OPEN=true` (after the API is live) |
| Production deploy | Frontend live on Cloudflare Workers (`patch-hive.com`) from a build before #69/#80; API (`api.patch-hive.com`) **not deployed** |
| Production readiness | **Not ready** (beta-staging engineering) — [assessment](docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md) · [matrix](docs/evidence/PRODUCTION_READINESS_MATRIX.md) · [delta](docs/evidence/PRODUCTION_READINESS_DELTA_2026-07-26.md) |

## Decision Intelligence specification campaign (2026-09-25)

**OBSERVED:** provider-neutral Decision Intelligence is now specified under `specs/005-decision-intelligence/`; implementation remains pending and Jev is not enabled. The constitution makes evidence non-canonical and forbids probabilistic direct-to-canon writes.

**Next implementation gate:** contracts + deterministic policy + fixture provider before any Jev adapter.

## Immediate continuation priorities

1. Operator: deploy the frontend (#69, #80) and request a VirusTotal reanalysis; rotate the context.dev and OpenRouter keys; add `RELEASE_PLEASE_TOKEN` and `PROJECT_TOKEN`.
2. Operator: deploy the API (`api.patch-hive.com`), then open accounts (`VITE_ACCOUNTS_OPEN=true`).
3. Operator: load the catalog to prod (T027: `db-migrate.yml` prod, `db-load.yml` dry run, then apply).
4. Engineering, no decision needed: count unknown module power per rail in rack budgets; seven new crawl rows as overlays v5/v13; verify the registry snapshot ships in the API image.
5. Owner decisions: see [OPEN_DESIGN_DECISIONS_2026-10-28.md](docs/evidence/OPEN_DESIGN_DECISIONS_2026-10-28.md).

**Local test automation:**
`cd backend && pytest tests --ignore=tests/acceptance -q` (CI form; 871 passed on #80) · acceptance suite separately (11 passed; #78 lets it run in the same invocation)

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
