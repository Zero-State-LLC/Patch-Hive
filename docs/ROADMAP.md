# PatchHive roadmap

## Roadmap rules

This roadmap is capability- and evidence-based. Dates are not commitments unless separately approved. A phase advances only when its exit criteria are satisfied on an identified source SHA.

Status vocabulary:

- `COMPLETE` — merged and validated with retained evidence.
- `ACTIVE` — currently authorized work.
- `PLANNED` — sequenced but not started.
- `DEFERRED` — intentionally outside the current release line.
- `NOT_COMPUTABLE` — evidence is unavailable or insufficient.

**Live posture:** [CURRENT_STATE.md](../CURRENT_STATE.md)  
**Production readiness:** [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) · [evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md](evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md)  
**Ordered engineering backlog:** [CONTINUATION.md](CONTINUATION.md)

## Retroactive release map

| Line | Maturity | Scope | Current classification |
|---|---|---|---|
| `0.1.x` | historical prototype | early rig, patch, publishing, experimental surfaces | superseded / compatibility-only |
| `0.2.x` | canon-aligned MVP | immutable rigs/runs, deterministic compiler, validation, canonical export/credit boundary | **COMPLETE on main** (not production released) |
| `0.3.0-alpha` | Patch Book + VSI + Design Engine | one-page contracts, VSI P0, Style Studio / design packs (flags off) | **ACTIVE / late alpha** (`v0.3.0-alpha.1` lineage) |
| `0.3.0-beta` | closed staging beta | named staging, Design Engine E2E, a11y protocol, dual-path thinning | **PLANNED** |
| `0.3.0-rc` | Patch Book release candidate | freeze SHA, full export matrix, concurrency/debit evidence | **PLANNED** |
| `0.4.x` | production hardening | ops maturity, scanner, SLOs, support, payment readiness (still off) | **PLANNED** |
| `1.0.0` | production-supported release | stable public workflow + authority decision | **not eligible** |

## `0.2.x` — Canon-aligned MVP — COMPLETE

**Objective:** one truthful runtime and fail-closed dual-path monetization.

### Delivered (COMPLETE)

- Canonical `/api/canon/*` credits, exports, download tokens, test-mode Stripe webhook
- Legacy debit `ENABLE_LEGACY_PATCHBOOK_DEBIT=false` → 410 by default
- Server-authored run bridge identities (`rig-rev-*` / `gen-run-*`)
- Legacy social / publishing / leaderboards / referrals default off
- FE quarantine of unrouted community/publish pages under `frontend/src/legacy/`
- VSI P0: secure image evidence, mock vision adapter, inventory gate, multi-photo fusion (user confirm only)
- CI: backend + quality + security workflows

### Residual (not blocking 0.2 classification)

- Inventory HTTP still primarily `/api/racks` (CANON_SUPPORTING; dual-path F2–F5 planned)
- Named multi-tenant staging host **NOT_PERFORMED**
- Production deploy and live payments **NOT_GRANTED**

## `0.3.0-alpha` — Patch Books, Design Engine, product shell — ACTIVE

**Objective:** make publication and presentation pipelines real under fail-closed flags.

### COMPLETE on main (PRs #66–#95 lineage)

| Capability | Status |
|------------|--------|
| Patch page / book contracts + Design Engine foundation | COMPLETE (#90) |
| Families, a11y preflight, preview rate limit | COMPLETE (#91) |
| Deterministic SVG diagrams + influence library | COMPLETE (#92) |
| Server style recipe library + staging enablement docs | COMPLETE (#93) |
| Pack artifact download, share toggle, zip export | COMPLETE (#94) |
| Cyber Hive Login gate | COMPLETE (#95) |
| Zero State × PatchHive brand / design system | COMPLETE (#88–#89) |
| Local Docker staging receipts + domain cutover checklist | COMPLETE (#87) |
| F3 generate dual-write audit | COMPLETE (#86) |
| Cyber Hive product page visual upgrade | ACTIVE (#96 open) |

### Exit criteria for closing alpha

- [ ] Demo credentials aligned with seed data
- [ ] Design Engine walkthrough receipt with flags on (test payments only)
- [ ] Docs / readiness matrix pinned to post-#96 SHA
- [ ] No P0 integrity regressions on main CI

## `0.3.0-beta` — Closed staging beta — PLANNED

**Objective:** prove the product on a durable non-prod environment.

### Required work

1. Operator host pick (Compose VPS / Render / Fly / Azure) — [STAGING_HOST_PLAN.md](evidence/STAGING_HOST_PLAN.md)
2. Secrets, CORS, fail-closed payment flags
3. Design Engine staging enablement — [PATCHBOOK_STAGING_ENABLEMENT.md](design/PATCHBOOK_STAGING_ENABLEMENT.md)
4. Acceptance suite against staging Postgres
5. Backup/restore + ledger reconcile drill receipts
6. Manual accessibility protocol — [ACCESSIBILITY.md](ACCESSIBILITY.md)
7. Dual-path F2/F4/F5 thinning (no big-bang rack delete)
8. Playwright against staging or staging-like stack

### Exit criteria

- Named staging URL (or private IP) with health + migrate head verified
- Debit → fulfillment → download pack succeeds under test mode
- A11y protocol logged; known defects severity-classified
- Production payments still **disabled**

## `0.3.0-rc` — Release candidate — PLANNED

**Objective:** freeze scope and prove release behavior on one SHA.

### Required evidence

- Clean candidate tag + release receipt
- Full supported-format export matrix
- Dense-book performance budgets
- Corrupted artifact, retry, reversal, idempotency tests
- No unresolved P0/P1 defects
- SHA-pinned [PRODUCTION_READINESS](PRODUCTION_READINESS.md) checklist filled

Any release-blocking fix produces a **new** RC tag.

## `0.4.x` — Production hardening — PLANNED

**Objective:** remove operational uncertainty before public production use.

### Workstreams

- Production malware/AV scanner behind `ImageScanner`
- SLOs, alerts, dead-letter handling, reconciliation jobs
- Backup restoration drills and disaster recovery
- Rate limiting, abuse controls, privacy retention, support tooling
- Payment readiness (webhooks, concurrency) **without** activation by default
- Customer-facing help, methodology, and failure recovery
- Threat model sign-off; SBOM retained per release

## `1.0.0` — Production-supported release

PatchHive reaches `1.0.0` only when:

- canonical core workflows are stable and supportable;
- compatibility policy is enforced;
- migrations and backup recovery are proven;
- production security and privacy review has no unresolved critical/high findings;
- accessibility acceptance passes;
- deterministic export and manifest behavior is demonstrated;
- operational ownership and incident response exist;
- legal, billing, licensing, and support surfaces are approved;
- an explicit operator decision authorizes production deployment.

Live customer charging requires a **separate** payment-activation decision (`ALLOW_PRODUCTION_PAYMENTS`).

## Visual System Intelligence (cross-cutting)

Authoritative contracts: [VISUAL_SYSTEM_INTELLIGENCE.md](VISUAL_SYSTEM_INTELLIGENCE.md), ADR-005, [VISUAL_SYSTEM_INTELLIGENCE_ROADMAP.md](VISUAL_SYSTEM_INTELLIGENCE_ROADMAP.md).

| Priority | Capability | Status |
|----------|------------|--------|
| P0 | Secure image re-encode + local quality | COMPLETE |
| P0 | Provider-neutral vision adapter + mock/fixture | COMPLETE |
| P0 | Classification candidates cannot self-confirm | COMPLETE |
| P0 | Confirmation → inventory revision + generate gate | COMPLETE |
| P0 | Multi-photo fusion UI (user confirm only) | COMPLETE |
| P1 | Port/control/cable reconstruction | STUB |
| P1 | Photo-derived Patch Books | SPEC / Design Engine presentation only |
| P1 | Live vision provider + eval accuracy | NOT_COMPUTABLE without dataset |
| P2 | Live camera guidance, marketplace match | DEFERRED |

**Out of scope forever unless product canon changes:** audio recording as ground truth, DSP engines, MIDI/CV hardware activation, DAW/plugin hosting.

## Dual-path inventory (cross-cutting)

Design: [evidence/DUAL_PATH_RETIREMENT_DESIGN.md](evidence/DUAL_PATH_RETIREMENT_DESIGN.md)

| Slice | Status |
|-------|--------|
| F0 design | COMPLETE |
| F3 generate dual-write audit | COMPLETE |
| F2 thin `GET /api/canon/rigs` | COMPLETE |
| F4 evidence canon aliases | COMPLETE |
| F5 FE inventory list cutover | PLANNED |
| Z delete `backend/racks` | DEFERRED (operator-only campaign) |

## Near-term sequence (next 2 weeks)

1. Land Cyber Hive UI pages (#96); pin readiness docs  
2. Align demo auth with seed  
3. Design Engine local/staging walkthrough receipt  
4. Operator staging host pick  
5. Dual-path F2 **or** export concurrency hardening (one primary track)  
6. Optional tag `v0.3.1-alpha` / `v0.4.0-beta.1` only after staging receipts  

## Deferred beyond 1.0

Unless separately authorized:

- community social graph;
- marketplace and public publishing network;
- leaderboards and contests;
- multiplayer or collaboration;
- hardware control, MIDI/CV activation, or DSP;
- automatic electrical-safety certification;
- arbitrary plugin execution;
- audio simulation presented as ground truth.


## Decision Intelligence (cross-cutting) — SPECIFIED

Authoritative spec: [`specs/005-decision-intelligence/`](../specs/005-decision-intelligence/spec.md). The provider-neutral decision layer sits between normalized evidence and deterministic policy. Jev is a planned default-off adapter for bounded classification/scoring/routing; it is not a vision provider and has no canonical write authority.

Sequence: contracts/policy -> persistence/telemetry -> fixture provider -> Jev adapter -> module/capability/port decisions -> confirmation UI -> labeled evaluation -> controlled staging enablement.
