# 005 — Decision Intelligence & Evidence Resolution

**Status:** IMPLEMENTED (T001–T060b) / evaluation gate open (T061, T062, T070; continued in Spec 007)  
**Date:** 2026-09-25  
**Acceptance:** [acceptance.md](acceptance.md) is the acceptance checklist for every FR below.  
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

Implemented 2026-10-28 (#104). An out-of-set answer escalates. The evaluation harness does not yet pass the request, so the check does not run there (research R4).

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

Provider failure handling implemented 2026-10-28 (#105): a failed provider is UNRESOLVED or ESCALATE, never REJECT. An unsupported packet schema still returns REJECT (research R3).

### FR-010 Evaluation gate
Jev MUST remain behind a feature flag until a retained labeled evaluation corpus demonstrates approved thresholds for candidate ranking, calibration, abstention/review behavior, and false-canonicalization protection.

Production refuses to start with a decision provider on, implemented 2026-10-29 (#132). Staging still enables on flags alone; no runtime code checks the 007 receipt (research R1, R2).

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

## Implementation status (2026-10-29)

Checked against `main` at 95ca9ee. Decision research is in [research.md](research.md).

| FR | Status | Evidence |
| --- | --- | --- |
| FR-001 Provider-neutral decisions | Implemented | `DecisionProvider` protocol and contracts; Jev and Clef types stay in their adapters [OBSERVED: backend/intelligence/provider.py, contracts.py, jev_provider.py, clef_provider.py] |
| FR-002 Immutable DecisionPacket | Partial | Frozen packet and append-only receipt exist [OBSERVED: contracts.py, persistence.py]. `evidence_hash` is the raw evidence id, and the provider runs before the idempotency check (R5) |
| FR-003 Bounded candidate identity | Implemented | `check_choice_packet` in `DecisionPolicy.evaluate` (#104) [OBSERVED: policy.py]. Not applied in evaluation (R4) |
| FR-004 Hierarchical classification | Implemented | `classify_family`, `classify_capability`, `classify_port` [OBSERVED: backend/intelligence/module_service.py] |
| FR-005 Deterministic disposition | Implemented | Pure `DecisionPolicy` with versioned thresholds [OBSERVED: policy.py] |
| FR-006 Explicit confirmation | Implemented | Canon write only from CONFIRMED in the resolution machine [OBSERVED: resolution_machine.py]; confirmations record the signed-in user (#130) [OBSERVED: backend/evidence/routes.py] |
| FR-007 Conflict detection | Implemented | `detect_conflict` probability decision (T043) [OBSERVED: module_service.py]. Source preservation was not re-checked here [INFERRED from T043] |
| FR-008 Routing | Partial | ESCALATE exists, but the route never sets `routing_targets` and no router exists (R6) [OBSERVED: evidence/routes.py, clef_resolution.py] |
| FR-009 Failure semantics | Partial | Provider failures fail closed to UNRESOLVED/ESCALATE (#105). Unsupported schema and invalid packets return REJECT (R3) [OBSERVED: policy.py, resolution_machine.py] |
| FR-010 Evaluation gate | Partial | Flags default off; production refuses providers (#132) [OBSERVED: backend/core/startup_policy.py]. No runtime receipt check; the Jev path bypasses the guarded machine and hardcodes `decision-policy-v1` (R1, R2) |

Counts: 6 Implemented, 4 Partial, 0 Missing.

## Open questions (2026-10-29)

This spec had no open-questions list. The questions raised by research are below.

- **Should an unsupported packet schema REJECT?** Open for the owner. Recommendation: no, treat it as a provider failure (R3, T081).
- **Does the Jev path have to use the guarded machine?** Open for the owner. Recommendation: yes, one path for every provider (R2, T082).
- **Is `false_canonicalization_count = 0` measured?** RESOLVED: no. `evaluation.py` hardcodes it; 007 adds a structural replay count on top [OBSERVED: evaluation.py, evaluation_enablement.py]. T084 replaces the constant.
