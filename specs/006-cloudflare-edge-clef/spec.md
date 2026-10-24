# 006 — Cloudflare Edge Deploy with Clef Classifier

**Status:** SPECIFIED  
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

### FR-002 Public API surface
A hostname (`api.patch-hive.com` or operator-chosen) MUST serve the existing FastAPI surface. CORS MUST be restricted to the exact frontend origin. `ALLOW_PRODUCTION_PAYMENTS` MUST remain false.

### FR-003 Database continuity
Hyperdrive MUST point at the Neon staging branch connection string. No D1 schema migration.

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

## Acceptance summary

Feature is not eligible for normal traffic until Pages, API hostname, Hyperdrive, Clef adapter, policy tests, evaluation gate, and DOMAIN_CUTOVER_CHECKLIST receipts all pass.
