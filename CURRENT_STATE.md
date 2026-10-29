# CURRENT_STATE

**Authoritative as of:** 2026-10-28  
**Branch pin:** `main` on `Zero-State-LLC/Patch-Hive`  
**HEAD:** `c59b2db` (#116, catalog tombstones)  
**Recent work (2026-10-28):** gap-analysis fixes for specs 001–005 and P0/P1 security (#82–#105); Cloudflare edge for staging and production (#83–#87, #107); short-lived tokens, refresh cookie and an enforced CSP (#99, #100, #113); prod catalog load, Products page, category fill and catalog tombstones (#112–#116). Staging and production both run main.  
**Open PRs:** [#110](https://github.com/Zero-State-LLC/Patch-Hive/pull/110) opt-in container startup migrations, [#111](https://github.com/Zero-State-LLC/Patch-Hive/pull/111) CODEOWNERS, [#109](https://github.com/Zero-State-LLC/Patch-Hive/pull/109) release 0.3.0-alpha.4, [#106](https://github.com/Zero-State-LLC/Patch-Hive/pull/106) zod bump.  
**Board:** [Project #8](https://github.com/orgs/Zero-State-LLC/projects/8), mirrored in [docs/KANBAN.md](docs/KANBAN.md).  
**Open owner decisions:** [docs/evidence/OPEN_DESIGN_DECISIONS_2026-10-28.md](docs/evidence/OPEN_DESIGN_DECISIONS_2026-10-28.md).  
**Next slices:** [docs/evidence/NEXT_SLICES_2026-10-28.md](docs/evidence/NEXT_SLICES_2026-10-28.md).  

**Alpha tag lineage:** `v0.3.0-alpha` (late alpha — **not** production)

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

## OBSERVED product posture

| Area | State |
|------|--------|
| Product identity | Deterministic Eurorack **rig + patch documentation** |
| Canonical domain | `backend/canon/` (+ design recipes, export fulfillment) |
| Design Engine flags | **Default off** — staging overlay + walkthrough PASS (#147) |
| Alembic | Single head through `20261028_catalog_tombstones`; staging and prod migrated 2026-10-28 |
| Health | `/health` liveness; `/health/ready` includes DB |
| Local Compose staging | `docker-compose.staging.yml` + `scripts/staging/*` + `scripts/test/run.*` |
| Test automation | `scripts/test/run.sh\|ps1` · CI `acceptance-tests.yml` · 11 acceptance PASS |
| Dual-path inventory | F0/F1/F3/F2 done; F4/F5 residual; Z deferred |
| Named staging host | Plan only — **NOT_PERFORMED** |
| Payments | Test-mode only |
| Module catalog (staging = prod) | 4,179 catalog rows and 4,149 modules, of which 263 each are tombstoned; 3,916 visible from 364 brands, 0 conflicts. 855 rows have no category. Sources: Phase 2 seed (ModularGrid leads, tagged `unknown`/`CATALOG_OBSERVED`) plus maker pages (`official_publication`). Maker-crawl page cache deleted 2026-10-28; committed crawl results intact |
| API access | Module and case writes admin-only (#79). Racks owner-scoped (#80): owner reads/writes, admin read roles read all, public racks readable by anyone, others 404. Catalog materialize and stateless layout recommendation stay public |
| Accounts | Sign-in open on staging and production (#113). No account yet created on production; a real sign-up is still to be tried |
| Production deploy | Frontend (`patch-hive.com`) and API (`api.patch-hive.com`) on Cloudflare, both from main; CSP enforced; CORS limited to the exact origin |
| CI | Repo is public so GitHub Actions runs on free minutes; with the repo private the Actions budget blocks every job |
| Production readiness | **Not ready** (beta-staging engineering) — [assessment](docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md) · [matrix](docs/evidence/PRODUCTION_READINESS_MATRIX.md) · [delta](docs/evidence/PRODUCTION_READINESS_DELTA_2026-07-26.md) |

## Decision Intelligence specification campaign (2026-09-25)

**OBSERVED:** provider-neutral Decision Intelligence is now specified under `specs/005-decision-intelligence/`; implementation remains pending and Jev is not enabled. The constitution makes evidence non-canonical and forbids probabilistic direct-to-canon writes.

**Next implementation gate:** contracts + deterministic policy + fixture provider before any Jev adapter.

## Immediate continuation priorities

See [docs/evidence/NEXT_SLICES_2026-10-28.md](docs/evidence/NEXT_SLICES_2026-10-28.md). In short:

1. Engineering, no decision needed: per-rail unknown power in rack budgets; refuse shared homepages at crawl time (003 T030); seven new crawl rows as `catalog-additions-v6` + power v14.
2. Operator: try a real sign-up on production; verify seeded demo auth on staging (008 T030b); VirusTotal reanalysis; rotate the context.dev and OpenRouter keys; add `PROJECT_TOKEN` and `RELEASE_PLEASE_TOKEN`; decide repo visibility versus the Actions budget.
3. Owner decisions: HP correction action (Sovage CHICANE), deleting the seed scripts, paid caps for Frap and the cache rebuild; review #109–#111.

**Local test automation:**
`cd backend && pytest tests -q` with a local Postgres 15 for the population tests (999 passed, 4 skipped on #116) · acceptance suite separately (11 passed; #78 lets it run in the same invocation)

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
