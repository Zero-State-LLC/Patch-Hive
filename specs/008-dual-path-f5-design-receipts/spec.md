# 008 — Dual-Path F5 Cutover & Design Engine Staging Receipts

**Status:** DRAFT spec, reconstructed 2026-10-26 from `tasks.md` and `OPERATOR_NOTES.md` after implementation (#53). Code IMPLEMENTED; staging walkthrough and pin open. The operator must confirm every `[INFERRED]` item.  
**Date:** 2026-10-26  
**Depends on:** Spec 007 (enablement receipt pinned), dual-path design F0–F4, Design Engine foundation.

## Problem

The frontend inventory list still reads the legacy path, the demo credentials drift from the seed, and readiness docs are not pinned to a walkthrough receipt, so no beta claim can be backed by evidence [OBSERVED: tasks.md, docs/KANBAN.md alpha-exit items].

## Objective

Move the frontend list to the canonical alias without a dual-write regression, align demo auth with the seed, capture a Design Engine walkthrough receipt under test payments, and pin the readiness docs to it [OBSERVED: tasks.md].

## User scenarios and testing

### User story 1 — Read rigs from the canonical alias (Priority: P1)

As a rig owner, I want the rig list served from the canonical alias so that the UI shows the authoritative set.

**Acceptance scenarios:**

1. **Given** the legacy and canonical list routes, **when** parity evidence is collected, **then** the full id sets match [OBSERVED: OPERATOR_NOTES.md T010].
2. **Given** every canon write route, **when** the write-surface audit runs, **then** each has a `/api/racks` twin and no new write route exists [OBSERVED: OPERATOR_NOTES.md T010].
3. **Given** the switched list pages, **when** a generate runs, **then** the F3 audit finds native `gen-run-*`/`rig-rev-*`/`inv-rev-*` ids and no `legacy-*` ids [OBSERVED: OPERATOR_NOTES.md T020].

### User story 2 — Capture a walkthrough receipt in test mode (Priority: P1)

As the operator, I want a receipt for preview → credit grant → export debit → fulfillment → download so that beta eligibility rests on a recorded run.

**Acceptance scenarios:**

1. **Given** seeded auth that does not match the seed, **when** the walkthrough starts, **then** it exits non-zero and writes no receipt [OBSERVED: OPERATOR_NOTES.md].
2. **Given** server flags that are unreadable, not test mode, or changed during the run, **when** the walkthrough runs, **then** it fails closed (`SERVER_FLAGS_UNVERIFIABLE`, `FLAGS_NOT_TEST_MODE`, `SERVER_ENVIRONMENT_MISMATCH`, `SERVER_FLAGS_CHANGED`) [OBSERVED: OPERATOR_NOTES.md].
3. **Given** a passing run, **when** the receipt is sealed, **then** it holds source SHA, server-reported flags, step outcomes, and the pack SHA-256 only [OBSERVED: OPERATOR_NOTES.md].

### User story 3 — Pin readiness docs (Priority: P2)

As the operator, I want the readiness matrix and cutover checklist pinned to the receipt so that the docs cannot claim more than the evidence.

**Acceptance scenarios:**

1. **Given** a doc without the exact receipt SHA, an open P0, or an unverified Spec 007 receipt, **when** `pin_readiness_docs` runs, **then** it fails closed [OBSERVED: OPERATOR_NOTES.md].
2. **Given** no `RECEIPT_CAPTURED` state, **when** `operator_pin` is replayed, **then** the machine does not reach `BETA_ELIGIBLE` [OBSERVED: tasks.md].

### Edge cases

- The canon list orders by id descending while the legacy list is unordered, so pages of a paginated list can differ even when full sets match [OBSERVED: OPERATOR_NOTES.md].
- A server without `GET /api/admin/ops/runtime-flags` (HTTP 404) fails closed [OBSERVED: OPERATOR_NOTES.md].

## Requirements

### Functional requirements

- **FR-001** The FE list pages MUST read `canonApi.listRigs`/`getRig`; all writes MUST stay on their existing endpoints [OBSERVED: OPERATOR_NOTES.md T020].
- **FR-002** `scripts/seed_golden_demo.py` MUST be the single source of demo credentials; the walkthrough MUST NOT rewrite a password hash [OBSERVED: OPERATOR_NOTES.md T030].
- **FR-003** Walkthrough flags MUST come from the running server's read-only `GET /api/admin/ops/runtime-flags`, which returns `schema_version`, `environment`, and six booleans only [OBSERVED: OPERATOR_NOTES.md T040].
- **FR-004** Every artifact MUST be sealed by `record_sha256` and carry its predecessor's SHA; `BETA_ELIGIBLE` is terminal [OBSERVED: OPERATOR_NOTES.md].
- **FR-005** Pinning MUST require a verified Spec 007 enablement receipt [OBSERVED: OPERATOR_NOTES.md T050].
- **FR-006** Production payments MUST remain disabled; reaching `BETA_ELIGIBLE` MUST NOT flip any flag [OBSERVED: tasks.md, OPERATOR_NOTES.md].

### Key entities

`AliasParityEvidence`, `FeCutoverEvidence`, `SeedAuthCheck`, `WalkthroughStart`, `WalkthroughReceipt`, `ReadinessPin` (schema ids `patchhive.*.v1`) [OBSERVED: OPERATOR_NOTES.md].

## Authority, data, security, observability, rollback

- **Authority:** existing confirmation and generate gates are unchanged [OBSERVED: tasks.md T020].
- **Data:** no route added or changed for T010; no schema change [OBSERVED: OPERATOR_NOTES.md].
- **Security/privacy:** records never hold passwords, tokens, database URLs, or pack bytes [OBSERVED: OPERATOR_NOTES.md]. The runtime-flags endpoint is admin-only and read-only [OBSERVED].
- **Observability:** rejected events are recorded and leave state unchanged [OBSERVED: OPERATOR_NOTES.md].
- **Rollback:** revert the two FE list pages to the legacy endpoints; the canonical alias routes predate this feature [INFERRED].

## Success criteria

- **SC-001** A staging walkthrough receipt exists for one exact source SHA [OBSERVED: tasks.md T040].
- **SC-002** `PRODUCTION_READINESS_MATRIX.md` and `DOMAIN_CUTOVER_CHECKLIST.md` carry no `PENDING_OPERATOR_WALKTHROUGH` placeholder [OBSERVED: OPERATOR_NOTES.md].
- **SC-003** `beta_eligible(machine)` is true on replay of the five events [OBSERVED: OPERATOR_NOTES.md].

## Out of scope

Enabling payments, changing runtime config, routing, or DNS, and the unrouted `frontend/src/legacy/pages/Publish.tsx` [OBSERVED: OPERATOR_NOTES.md].
