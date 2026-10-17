# CURRENT_STATE

**Authoritative as of:** 2026-07-26  
**Branch pin:** `origin/main`  
**HEAD:** re-pin after merge of this campaign (see recent merges)  
**Recent work:** beta staging ops train #141–#148; Design Engine staging walkthrough; unified test runner + CI acceptance; dual-path F2 canon rigs list.  
**Open issues:** #68 P0 Product Database residual; #58 P1 residual + P2 hygiene; #96 UI pages (**open**).

**Alpha tag lineage:** `v0.3.0-alpha` (late alpha — **not** production)

### Recent merges (OBSERVED)

| PR | Result |
|----|--------|
| [#141](https://github.com/scrimshawlife-ctrl/Patch-Hive/pull/141) | FE/seed type-safety + registry slug Alembic + CI green-path |
| [#142](https://github.com/scrimshawlife-ctrl/Patch-Hive/pull/142) | Alembic-on-deploy + `/health/ready` + evidence re-pin |
| [#143](https://github.com/scrimshawlife-ctrl/Patch-Hive/pull/143) | Local staging compose smoke receipt |
| [#144](https://github.com/scrimshawlife-ctrl/Patch-Hive/pull/144) | Entrypoint wait on DATABASE_URL before alembic |
| [#145](https://github.com/scrimshawlife-ctrl/Patch-Hive/pull/145) | Smoke scripts + backup/restore drill + FE API env fix |
| [#146](https://github.com/scrimshawlife-ctrl/Patch-Hive/pull/146) | Acceptance suite against compose Postgres |
| [#147](https://github.com/scrimshawlife-ctrl/Patch-Hive/pull/147) | Design Engine staging enablement + walkthrough |
| [#148](https://github.com/scrimshawlife-ctrl/Patch-Hive/pull/148) | Unified test runner + CI acceptance gate |
| [#96](https://github.com/scrimshawlife-ctrl/Patch-Hive/pull/96) | Full product pages visual upgrade (**open**) |

**Campaign issue lineage:** [#46](https://github.com/scrimshawlife-ctrl/Patch-Hive/issues/46) — closed

## OBSERVED product posture

| Area | State |
|------|--------|
| Product identity | Deterministic Eurorack **rig + patch documentation** |
| Canonical domain | `backend/canon/` (+ design recipes, export fulfillment) |
| Design Engine flags | **Default off** — staging overlay + walkthrough PASS (#147) |
| Alembic | Single head through `20260726_module_registry_slugs`; entrypoint waits for DB then upgrades |
| Health | `/health` liveness; `/health/ready` includes DB |
| Local Compose staging | `docker-compose.staging.yml` + `scripts/staging/*` + `scripts/test/run.*` |
| Test automation | `scripts/test/run.sh\|ps1` · CI `acceptance-tests.yml` · 11 acceptance PASS |
| Dual-path inventory | F0/F1/F3/F2 done; F4/F5 residual; Z deferred |
| Named staging host | Plan only — **NOT_PERFORMED** |
| Payments | Test-mode only |
| Production deploy | **Not performed** |
| Production readiness | **Not ready** (beta-staging engineering) — [assessment](docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md) · [matrix](docs/evidence/PRODUCTION_READINESS_MATRIX.md) · [delta](docs/evidence/PRODUCTION_READINESS_DELTA_2026-07-26.md) |

## Decision Intelligence specification campaign (2026-09-25)

**OBSERVED:** provider-neutral Decision Intelligence is now specified under `specs/005-decision-intelligence/`; implementation remains pending and Jev is not enabled. The constitution makes evidence non-canonical and forbids probabilistic direct-to-canon writes.

**Next implementation gate:** contracts + deterministic policy + fixture provider before any Jev adapter.

## Immediate continuation priorities

1. Operator: pick named staging host; optional domain cutover ([DOMAIN_CUTOVER_CHECKLIST.md](docs/evidence/DOMAIN_CUTOVER_CHECKLIST.md)).
2. Dual-path F4 (evidence alias) / F5 (FE inventory reads prefer canon DTO).
3. P1/P2 hygiene per CONTINUATION; #96 UI polish when ready.

**Local staging automation:**  
`scripts/test/run.ps1 ci` · `staging` · smoke · acceptance (11 PASS) · design-engine (export succeeded)

## Authority boundary

**Do not:** deploy production, enable live Stripe, charge users, or activate hardware without separate operator authorization.

## Doc index

| Doc | Use |
|-----|-----|
| [docs/ROADMAP.md](docs/ROADMAP.md) | Capability roadmap |
| [docs/CONTINUATION.md](docs/CONTINUATION.md) | Engineering backlog |
| [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md) | Gate framework |
| [docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md](docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md) | Latest readiness narrative |
| [docs/FEATURE_FLAGS.md](docs/FEATURE_FLAGS.md) | Flags |
| [brand/README.md](brand/README.md) | Brand kit |
| [.specify/memory/constitution.md](.specify/memory/constitution.md) | SpecKit constitution |
| [specs/005-decision-intelligence/spec.md](specs/005-decision-intelligence/spec.md) | Decision Intelligence requirements |
