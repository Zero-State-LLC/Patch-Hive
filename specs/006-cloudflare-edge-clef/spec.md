# 006 — Cloudflare Edge Deploy with Clef Classifier

**Status:** IMPLEMENTED in code (#50); operator deploy tasks T030–T050 and T060b DEFERRED (see DEPLOY_NOTES.md)  
**Date:** 2026-10-24  
**Depends on:** Spec 005 (DecisionProvider + DecisionPolicy + DecisionPacket), constitution authority boundaries, Neon staging branch, existing Vite frontend + FastAPI backend.

## Problem

PatchHive is late-alpha. The domain `patch-hive.com` is now on Cloudflare. Production deploy has not been performed. A public beta requires an edge frontend, a reachable API hostname, continued use of Neon, and a vision-capable classifier that stays inside the Spec 005 authority boundary.

## Objective

Deploy the Vite frontend to Cloudflare Pages, expose a public API hostname (Tunnel or Containers), bind Hyperdrive to the Neon staging branch, and add Clef (`@cf/cloudflare/clef` and `clef-flash`) as a DecisionProvider adapter. No canon mutation outside existing confirmation paths. No live payments. No D1 migration.

## User outcomes

- Users reach the app at a Cloudflare-hosted hostname.
- Module-candidate ranking and hierarchical classification can use Clef vision when the feature flag is on.
- Evidence resolution still surfaces exact candidate + evidence identity for confirmation.
- Operators can see readiness state before any beta claim.

## Functional requirements

### FR-001 Edge frontend
The Vite build MUST deploy to Cloudflare Pages. Custom domain MUST be attached. `VITE_API_BASE_URL` MUST point at the public API hostname.

Amended 2026-10-27: the SPA ships on Workers static assets (PR #55), not Pages. Two frontend Workers exist: `patch-hive.com` (production) and `staging.patch-hive.com` (staging, `noindex`). Each build points `VITE_API_BASE_URL` at its own API.

### FR-002 Public API surface
A hostname (`api.patch-hive.com` or operator-chosen) MUST serve the existing FastAPI surface. CORS MUST be restricted to the exact frontend origin. `ALLOW_PRODUCTION_PAYMENTS` MUST remain false.

Amended 2026-10-27: `api.patch-hive.com` is production (`ENVIRONMENT=production`, no feature flags). `api-staging.patch-hive.com` is staging (`ENVIRONMENT=staging`), where the 007 enablement and 008 walkthrough run. Each allows only its own frontend origin.

Exact-origin CORS and an enforced CSP implemented 2026-10-28 (#113). Production refuses to start with a decision provider on, implemented 2026-10-29 (#132). API security headers implemented 2026-10-29 (#130).

### FR-003 Database continuity
The API MUST use the Neon staging branch through its pooled connection string. No D1 schema migration.

Amended 2026-10-27: this requirement applies to the staging API (`api-staging.patch-hive.com`). The production API uses Neon `main` through its pooled endpoint.

Amended 2026-10-26, approved by the operator 2026-10-26: this previously required Hyperdrive. Hyperdrive's connection string is only reachable from the Workers runtime, and the FastAPI container's Postgres driver connects over TCP from inside the container, so Hyperdrive cannot serve it. Hyperdrive stays available for any future Worker-side database client.

### FR-004 Clef as DecisionProvider
Clef MUST implement the Spec 005 DecisionProvider protocol. System One responses (choice / noul / score + optional images) MUST map to DecisionPacket. Clef types MUST NOT leak outside the adapter. Feature flag default off. Fail-closed on timeout, malformed response, or unavailable.

### FR-005 Policy ownership unchanged
Disposition remains the deterministic Spec 005 DecisionPolicy. Clef confidence does not write canon. Confirmation path is unchanged.

### FR-006 State machines
Decision/evidence resolution, Clef adapter invocation, and edge deployment readiness MUST be implemented as explicit guarded state machines (defined in tasks.md). Transitions are pure functions of (state, event, guard). Every path is auditable and ends in a terminal state or ARCHIVED.

### FR-007 Evaluation gate
Clef remains flagged off until a retained labeled corpus (text + vision cases) meets operator-approved thresholds for top-1/top-k, calibration, abstention, and zero false-canonicalization.

## Non-functional requirements

- Idempotent decision requests.
- Structured telemetry distinguishing provider failure from low confidence.
- SHA-pinned evaluation receipt.
- No raw image bytes or secrets in DecisionPacket.

## Out of scope

- Live payments.
- D1 migration.
- Clef RL fine-tuning.
- Production-readiness claim before gates pass.
- Automatic electrical-safety certification.

## Success measures

- Pages build and custom domain resolve.
- `/health/ready` returns database ok.
- DecisionPacket shape validated end-to-end.
- Evaluation receipt retained and SHA-pinned.
- Readiness state machine reaches GATES_PASSED only after operator approval.

## Acceptance traceability

| Requirement | Task | Acceptance |
| --- | --- | --- |
| FR-001 Edge frontend | T030 | build succeeds, custom domain attached, `VITE_API_BASE_URL` set |
| FR-002 Public API surface | T040 | exact CORS origin, `ALLOW_PRODUCTION_PAYMENTS=false`, `/health/ready` ok |
| FR-003 Database continuity | T050, T060b | API container on the Neon staging pooled endpoint; no D1 migration |
| FR-004 Clef as DecisionProvider | T020, T060a | only SUCCESS emits a DecisionPacket; no type leakage; flag default off |
| FR-005 Policy ownership | T060a | disposition policy-owned; idempotent receipts |
| FR-006 State machines | T010, T020, T070, T090 | every path terminal or ARCHIVED; GATES_PASSED → BETA_READY only on operator approval |
| FR-007 Evaluation gate | T080, Spec 007 | receipt SHA-pinned; thresholds operator-approved |

## Acceptance summary

Feature is not eligible for normal traffic until Pages, API hostname, Hyperdrive, Clef adapter, policy tests, evaluation gate, and DOMAIN_CUTOVER_CHECKLIST receipts all pass.

Amended 2026-10-29: per the FR-001 and FR-003 amendments, read "Pages" as the Workers static-assets frontend and "Hyperdrive" as Neon's pooled endpoint (research R6).

## Implementation status (2026-10-29)

Checked against `main` at 95ca9ee. Decision research is in [research.md](research.md).

| FR | Status | Evidence |
| --- | --- | --- |
| FR-001 Edge frontend | Implemented | SPA on Workers static assets (#55), production and staging pairs live [OBSERVED: CURRENT_STATE.md]; CSP enforced (#113) [OBSERVED: frontend/worker/headers.ts] |
| FR-002 Public API surface | Implemented | Exact-origin `CORS_ORIGINS` and `ALLOW_PRODUCTION_PAYMENTS=false` per Worker env [OBSERVED: edge/api/wrangler.jsonc]; security headers (#130) [OBSERVED: edge/api/src/index.ts]; production refuses providers (#132) [OBSERVED: backend/core/startup_policy.py] |
| FR-003 Database continuity | Implemented | Staging and production migrated 2026-10-28 [OBSERVED: CURRENT_STATE.md]; startup migrations opt-in (#110) [OBSERVED: backend/docker-entrypoint.sh]. T050b stays open: no receipt in the tree |
| FR-004 Clef as DecisionProvider | Implemented | Adapter state machine, flag default off (T020) [OBSERVED: backend/intelligence/clef_provider.py, core/config.py] |
| FR-005 Policy ownership unchanged | Implemented | Guarded resolution applies `DecisionPolicy` (T060a) [OBSERVED: backend/intelligence/clef_resolution.py] |
| FR-006 State machines | Partial | All three machines exist and pass tests [OBSERVED: tests/integration/test_006_edge_clef_state_machines.py, 2026-10-29 run]. `gates_pass` accepts any 64-hex SHA (R1); the Jev path skips the resolution machine (005 research R2) |
| FR-007 Evaluation gate | Partial | Clef flag off by default and refused in production (#132). Corpus has 0 cases (007 T010b); the receipt is forgeable (007 research R1) |
| Ops: deploy workflows (no FR) | Partial | No environment protection on production targets, a foreign workflow, an extra `actions: write`, an unrevoked R2 token on failure (R2–R5) [OBSERVED: .github/workflows/] |

Counts: 5 Implemented, 2 Partial, 0 Missing.

## Open questions (2026-10-29)

This spec had no open-questions list. Questions raised by research:

- **Does the acceptance summary still require Pages and Hyperdrive?** RESOLVED: no. FR-001 and FR-003 were amended (R6); the summary is amended above.
- **Can production run a decision provider before BETA_READY?** RESOLVED: no. Startup refuses it (#132) [OBSERVED: backend/core/startup_policy.py].
- **Who creates the GitHub `production` environment?** RESOLVED: a repo admin, in the repo settings; it cannot be created from the tree (R2, T101b).
