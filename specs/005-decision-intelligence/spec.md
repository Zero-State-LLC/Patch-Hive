# 005 — Decision Intelligence & Evidence Resolution

**Status:** SPECIFIED / implementation not authorized by this document alone  
**Date:** 2026-09-25  
**Depends on:** VSI evidence contracts, canonical inventory, module registry, deterministic patch compiler

## Problem

PatchHive can collect photo/manual/hybrid evidence and represent candidate module matches, but repeated ambiguous decisions still require provider-specific logic or manual resolution. The product needs a provider-neutral decision layer that can classify and rank bounded possibilities without giving probabilistic systems canonical authority.

## Objective

Introduce a `DecisionProvider` abstraction and deterministic `DecisionPolicy` so Jev can be used for bounded classification, scoring, conflict detection, and routing while canon remains deterministic and user/authority confirmed.

## User outcomes

- A user photographs or imports a rig and receives useful ranked module candidates rather than an opaque model answer.
- A partially identified module can still acquire bounded capability hypotheses without inventing exact identity.
- Ambiguous evidence is routed to the cheapest safe next resolution step.
- A user can see why confirmation is required.
- Confirmed inventory remains the only inventory eligible for canonical generation.

## Functional requirements

### FR-001 Provider-neutral decisions
The system MUST expose provider-neutral decision primitives for bounded choice, bounded score, and boolean probability. Canonical code MUST NOT import a Jev response type.

### FR-002 Immutable DecisionPacket
Every completed decision MUST emit an immutable DecisionPacket containing decision ID, contract version, provider + provider version, evidence references/hash, bounded answer space, result probabilities/score, policy version, timestamps, and disposition.

### FR-003 Bounded candidate identity
Exact module identification MUST operate only over catalog candidates supplied in the request plus `none_of_above`. The decision provider MUST NOT create a new catalog identity.

### FR-004 Hierarchical classification
The system SHOULD support function-family, subtype, capability, and port-semantic classification independently of exact module identity.

### FR-005 Deterministic disposition
Provider confidence MUST NOT directly determine canon. A deterministic versioned policy maps DecisionPacket + evidence authority to `AUTO_PROPOSE`, `USER_REVIEW`, `UNRESOLVED`, `ESCALATE`, or `REJECT`.

### FR-006 Explicit confirmation
`AUTO_PROPOSE` means proposal only. Canonical inventory mutation requires an existing trusted/manual confirmation path unless an explicitly versioned authoritative-source rule applies.

### FR-007 Conflict detection
Contradictory evidence MUST be represented explicitly. Conflict disposition MUST preserve every source and MUST NOT silently choose a winner.

### FR-008 Routing
The policy MAY route unresolved work to catalog lookup, manufacturer-document retrieval, vision retry, stronger model, or human review. Routing MUST be bounded and auditable.

### FR-009 Failure semantics
Provider unavailable, malformed response, unsupported contract version, missing evidence, and insufficient confidence MUST fail closed. No failure may be interpreted as confirmation.

### FR-010 Evaluation gate
Jev MUST remain behind a feature flag until a retained labeled evaluation corpus demonstrates approved thresholds for candidate ranking, calibration, abstention/review behavior, and false-canonicalization protection.

## Non-functional requirements

- Deterministic policy for identical DecisionPacket + policy version.
- Idempotent decision request handling for stable request IDs.
- No raw secrets or unnecessary image bytes in DecisionPacket.
- Structured telemetry MUST distinguish provider failure from low-confidence result.
- Decision artifacts MUST be schema-versioned and hashable.
- Provider timeout/retry behavior MUST be bounded.

## Out of scope

- Jev as a vision/OCR model.
- Automatic electrical-safety certification.
- Model-authored canonical module specifications.
- Autonomous hardware control.
- Replacing existing canonical validators.
- Direct model-to-canon writes.

## Success measures

The evaluation harness reports:
- top-1 and top-k module candidate accuracy;
- calibration error / reliability by confidence band;
- abstention + human-review rate;
- escalation rate and provider cost/latency;
- false-canonicalization count (**must remain zero by architecture**);
- unresolved cases preserved without fabricated facts.

## Acceptance summary

The feature is not eligible for normal VSI traffic until all contracts, policy tests, failure tests, provenance tests, and evaluation gates in `acceptance.md` pass.
