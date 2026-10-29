# Tasks

- [x] T001 Add PatchHive constitution.
- [x] T002 Add SpecKit feature 005 specification chain.
- [x] T003 Add specification authority/index documentation.
- [x] T010 Implement DecisionProvider protocol and schemas.
- [x] T011 Implement deterministic DecisionPolicy and reason codes.
- [x] T012 Add contract/property tests for malformed and adversarial packets.
- [x] T020 Add append-only persistence migration.
- [x] T021 Add telemetry without raw sensitive evidence.
- [x] T030 Implement fixture DecisionProvider.
- [x] T031 Implement Jev adapter behind default-off feature flag.
- [x] T040 Implement module candidate ranking service.
- [x] T041 Implement hierarchical function/capability decisions.
- [x] T042 Implement port-semantic decisions.
- [x] T043 Implement evidence-conflict decisions.
- [x] T050 Integrate proposals into existing confirmation UI.
  - [x] T050a Project retained receipts into confirmation UI without canonical authority.
  - [x] T050b Bind advisory projection to exact candidate + evidence identity.
  - [x] T050c Invoke DecisionProvider from an evidence-resolution command path and persist append-only DecisionReceipt records.
    - [x] T050c1 Add idempotent append-only proposal persistence service.
    - [x] T050c2 Add flag-gated evidence-resolution orchestration using exact evidence + bounded candidates.
    - [x] T050c3 Expose the bounded resolution command/API and test it end-to-end. Service tests cover flag-off, exact binding, provider failure, idempotency, advisory persistence, and zero canonical mutation; API test covers request → receipt → advisory projection.
- [x] T060 Build evaluation harness and synthetic CI corpus contract.
- [x] T060a Harden provider production boundary: pinned Jev model, idempotency propagation, stable transport errors, malformed-candidate rejection, immutable receipt collision guard.
- [x] T060b Reject cross-partition image-hash leakage before pilot admission.
- [ ] T061 Define operator-approved thresholds from baseline results.
  - [x] T061a Add governed real-world pilot intake/schema/validator.
  - [x] T061b Add GrokBot/Firecrawl acquisition brief and coverage reporter.
  - [x] T061b2 Define evidence-to-case promotion workflow and harden admission checks.
  - [ ] T061c Promote rights-cleared evidence into a representative reviewed pilot and freeze corpus SHA. Tracked as 007 T010b.
    - depends_on: [T061b2, 007:T010b]
  - [ ] T061d Run baseline vs Jev-assisted evaluation and propose thresholds for operator approval. Tracked as 007 T020b and T030b.
    - depends_on: [T061c, 007:T020b, 007:T030b]
- [ ] T062 Retain SHA-pinned evaluation receipt. Tracked as 007 T060b.
  - depends_on: [T061, 007:T060b]
- [ ] T070 Staging enablement only after gate passes. Tracked as 007 T050b.
  - depends_on: [T061, 007:T050b]

## Gap closure (2026-10-29)

From [research.md](research.md). Effort in brackets.

- [x] T081 Treat an unsupported or invalid packet as a provider failure: ESCALATE with a routing target, else UNRESOLVED, keeping the reason codes; fix the "fail closed (REJECT)" docstring in `evidence/routes.py` (R3) [S]. Done 2026-10-29 (#135): `UNSUPPORTED_SCHEMA` and an invalid PROVIDER_SUCCESS packet go to ESCALATE when a routing target exists, else UNRESOLVED (`PACKET_SCHEMA_INVALID`); the docstring is fixed.
  - depends_on: [T060a]
- [x] T082 Route every provider through `resolve_module_identity_guarded` and use `settings.decision_policy_version`; drop the hardcoded `decision-policy-v1` (R2) [S]. Done 2026-10-29 (#135): `resolve_rack_evidence_decision` always takes the guarded flow, with `settings.decision_policy_version`; the hardcoded path is gone.
  - depends_on: [T050c3, T081]
- [ ] T083 Check idempotency before the provider call: store `idempotency_key` with a unique `(request_id, idempotency_key)` index, and set `evidence_hash` to a SHA-256 of the retained evidence packet and image (R5) [M].
  - depends_on: [T082]
- [x] T084 Pass the choice request into evaluation so the candidate check runs, and replace the hardcoded `false_canonicalization_count = 0` with the structural count (R4) [S–M]. Done 2026-10-29: cases carry optional `candidate_ids`; `evaluate` builds the request and counts the resolution-machine replay. Cases without `candidate_ids` skip the candidate check.
  - depends_on: [T060]
- [ ] T085 Name one bounded routing target (human review) in settings and pass it to the guarded resolution (R6) [S].
  - depends_on: [T082]
- [ ] T080 Gate the runtime on a verified 007 receipt: outside development, refuse to start (and answer 409 `ENABLEMENT_RECEIPT_REQUIRED`) unless a signed receipt names the configured provider and policy version (R1) [M].
  - depends_on: [T082, 007:T081]
