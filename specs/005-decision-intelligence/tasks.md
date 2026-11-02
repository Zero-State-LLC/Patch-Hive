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
- [x] T083 Check idempotency before the provider call: store `idempotency_key` with a unique `(request_id, idempotency_key)` index, and set `evidence_hash` to a SHA-256 of the retained evidence packet and image (R5) [M]. Done 2026-10-29: `resolve_module_identity_guarded` looks up `(request_id, idempotency_key)` before the provider call and answers a repeat from the stored receipt; the same key with different evidence is 409 `IDEMPOTENCY_KEY_CONFLICT`. Migration `20261029_decision_receipt_idempotency` adds the column and unique index; `evidence_hash` is `stable_sha256` of the evidence packet plus image SHA.
  - depends_on: [T082]
- [x] T084 Pass the choice request into evaluation so the candidate check runs, and replace the hardcoded `false_canonicalization_count = 0` with the structural count (R4) [S–M]. Done 2026-10-29: cases carry optional `candidate_ids`; `evaluate` builds the request and counts the resolution-machine replay. Cases without `candidate_ids` skip the candidate check.
  - depends_on: [T060]
- [x] T085 Name one bounded routing target (human review) in settings and pass it to the guarded resolution (R6) [S]. Done 2026-10-29: `settings.decision_routing_target` (default empty until something consumes ESCALATE, so failed decisions end UNRESOLVED with `ESCALATE_NO_ROUTING_TARGET`; set `human_review` once a review queue exists) is passed as `routing_targets` from the route, so `routing_target_exists` is true when configured.
  - depends_on: [T082]
- [x] T086 Add an NVIDIA vision provider beside Clef (owner direction 2026-11-01: NVIDIA models wherever a vision model is needed, Clef kept for image classification). Done 2026-11-01: `intelligence/nvidia_provider.py` (`NvidiaVisionProvider`, pinned `NVIDIA_MODELS`, JSON-schema answers limited to the candidates) on the Clef adapter machine with `NVIDIA_*` codes; `DECISION_PROVIDER=nvidia`, `ENABLE_NVIDIA_PROVIDER` (default off, refused in production, gated by the 007 receipt), `NVIDIA_API_KEY` as a staging secret; `nvidia` is an enableable 007 provider. Tests in `tests/unit/test_nvidia_provider.py`. Before enabling: a 007 evaluation run with `nvidia` as the assisted provider.
- [x] T080 Gate the runtime on a verified 007 receipt: outside development, refuse to start (and answer 409 `ENABLEMENT_RECEIPT_REQUIRED`) unless a signed receipt names the configured provider and policy version (R1) [M]. Done 2026-11-01: `intelligence/enablement_gate.py`; with any decision flag on or a provider selected outside development and test, startup (`main.py` lifespan) refuses and `POST /racks/{id}/evidence/decision-resolution` answers 409 `ENABLEMENT_RECEIPT_REQUIRED` with failure codes, unless the receipt and signature JSON at `DECISION_ENABLEMENT_RECEIPT_PATH` and `DECISION_ENABLEMENT_SIGNATURE_PATH` verify against the approver allowlist (007 T081) and name `DECISION_PROVIDER` and `DECISION_POLICY_VERSION`. The edge Worker forwards both paths in staging only. Tests in `tests/unit/test_decision_enablement_gate.py`. Usable once 007 T082 and T083 produce a real key and signature.
  - depends_on: [T082, 007:T081]
