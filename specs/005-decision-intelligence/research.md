# Research: 005-decision-intelligence

Decision research for the open decision-intelligence gaps (2026-10-29). Each item gives the evidence, the options and the recommendation. Labels: `[OBSERVED: <source>]` or `[INFERRED]`. Effort: S (under a day), M (one to three days), L (more).

Already fixed and reconciled in [spec.md](spec.md): answers bounded to the request's candidates (#104); a failed provider is UNRESOLVED or ESCALATE, never REJECT (#105); production refuses to start with a decision provider on (#132); evidence confirmations record the signed-in user (#130).

## R1. The runtime gate is only flags (FR-010)

**Evidence**

- `POST /racks/{rack_id}/evidence/decision-resolution` checks `enable_decision_intelligence`, then runs a provider. No receipt is read [OBSERVED: backend/evidence/routes.py `resolve_rack_evidence_decision`].
- Nothing outside the 007 and 008 modules calls `staging_enabled` or `verify_enablement_receipt` [OBSERVED: grep of backend/ and scripts/, 2026-10-29].
- Production refuses to start with `enable_decision_intelligence`, `enable_clef_provider` or a `decision_provider` other than `disabled` (#132) [OBSERVED: backend/core/startup_policy.py]. Staging can still turn a provider on with no receipt.
- The receipt itself is forgeable today ([007 research R1](../007-evaluation-staging-enablement/research.md)).

**Options**

1. Keep flags only and rely on the operator. That is the current gap.
2. Load a signed 007 receipt at startup (path or R2 key in settings). Refuse to start, or answer 409, unless it verifies and names the configured provider and `decision_policy_version`.
3. Check the receipt on every request. Same guarantee as 2, more cost, no extra safety.

**Recommendation:** option 2. Startup check in `core/startup_policy.py` for every non-development environment, plus a 409 `ENABLEMENT_RECEIPT_REQUIRED` in the route as defence in depth. Depends on 007 signing. Effort M.

## R2. The Jev path bypasses the guarded machine (FR-010, FR-006 of 006)

**Evidence:** only `decision_provider == "clef"` goes through `_resolve_with_guarded_flow` and the 006 resolution machine. The Jev path calls `resolve_module_identity` directly and hardcodes `policy_version="decision-policy-v1"` instead of `settings.decision_policy_version` [OBSERVED: backend/evidence/routes.py]. On Jev transport errors it answers 502/504 and the machine never records the failure [OBSERVED: routes.py].

**Options:** (1) route every provider through `resolve_module_identity_guarded`; (2) keep two paths and copy the guards.

**Recommendation:** option 1. One path, one pinned policy version, one failure mapping. Effort S.

## R3. Unsupported packet schema returns REJECT (FR-009)

**Evidence**

- `DecisionPolicy.evaluate` returns `REJECT / UNSUPPORTED_SCHEMA` when `schema_version` is not `patchhive.decision.v1`. Every other provider-side failure escalates [OBSERVED: backend/intelligence/policy.py].
- The 006 resolution machine sends `PROVIDER_SUCCESS` with an invalid packet to `REJECT / PACKET_SCHEMA_INVALID` [OBSERVED: backend/intelligence/resolution_machine.py].
- The `_resolve_with_guarded_flow` docstring still says "Provider failures fail closed (REJECT)". The code maps them to UNRESOLVED or ESCALATE (#105) [OBSERVED: routes.py].
- `acceptance.md` asks only that unsupported versions "fail closed" [OBSERVED: acceptance.md].

**Options:** (1) keep REJECT; (2) treat an unsupported or invalid packet as a provider failure: ESCALATE when a routing target exists, else UNRESOLVED.

**Recommendation:** option 2. A packet the system cannot read says nothing about the evidence, the same reasoning as #105. Keep the reason codes. Fix the docstring. Effort S.

## R4. Evaluation ignores the request (Success measures, FR-003)

**Evidence**

- `evaluation.evaluate` and `structural_false_canonicalizations` call `policy.evaluate(packet)` with no request, so the candidate check (#104) never runs in evaluation [OBSERVED: backend/intelligence/evaluation.py, backend/intelligence/evaluation_enablement.py].
- `EvaluationCase` carries no candidate set [OBSERVED: evaluation.py].
- `false_canonicalization_count` is hardcoded `0` in `evaluation.py`. 007 adds the structural replay count on top [OBSERVED: evaluation.py, evaluation_enablement.py `_condition_metrics`].

**Options:** (1) add the candidate set to each case and build a `ChoiceRequest` for `evaluate`; (2) leave it and document.

**Recommendation:** option 1. Add `candidate_ids` to the case schema, pass the request, and count an out-of-set answer as an escalation. Replace the hardcoded `0` with the structural count so the base harness cannot report zero by construction. Effort S–M (fixture schema change).

## R5. Evidence hash and idempotency order (FR-002, NFR idempotency)

**Evidence**

- `evidence_hash` is set to the raw `evidence_id`, not a hash of the evidence [OBSERVED: backend/intelligence/evidence_resolution.py, backend/intelligence/clef_resolution.py].
- The provider is called before any receipt lookup. `persist_decision_proposal` dedupes only on `packet_hash` or `decision_id` [OBSERVED: backend/intelligence/persistence.py].
- `decision_id` is derived from the request id and the raw response hash, so a repeat call with the same request and a different answer writes a second receipt [OBSERVED: backend/intelligence/jev_provider.py, backend/intelligence/clef_provider.py `_decision_id`].
- `DecisionReceiptRecord` has no `idempotency_key` column [OBSERVED: backend/intelligence/models.py].

**Options:** (1) look up by `(request_id, idempotency_key)` before the provider call, with a new column and unique index; (2) keep dedupe by packet hash.

**Recommendation:** option 1. Also set `evidence_hash = stable_sha256` of the retained evidence packet plus the image asset SHA. Needs an Alembic migration. Effort M.

## R6. Routing targets are never set (FR-008)

**Evidence:** the route never passes `routing_targets`, so a failed provider always lands in UNRESOLVED and a policy ESCALATE has no named target [OBSERVED: evidence/routes.py, clef_resolution.py]. There is no catalog-lookup, document-retrieval or human-review router [OBSERVED: grep of backend/intelligence/].

**Recommendation:** start with one target, human review (the existing confirmation UI), configured in settings. Add others only with their own spec. Effort S.
