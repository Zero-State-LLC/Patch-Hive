# Contract — DecisionProvider

Provider-neutral interface:

```python
class DecisionProvider(Protocol):
    def choose(self, request: ChoiceRequest) -> DecisionPacket: ...
    def score(self, request: ScoreRequest) -> DecisionPacket: ...
    def probability(self, request: ProbabilityRequest) -> DecisionPacket: ...
```

## ChoiceRequest
- request_id
- contract_version
- purpose
- evidence_hash + evidence_refs
- choices: stable IDs + concise descriptions
- context: normalized JSON only
- timeout budget

## DecisionPacket
- decision_id
- request_id
- contract_version
- provider
- provider_version
- evidence_hash
- candidate_set_hash / rubric_hash
- result
- probabilities or score where supported
- provider_status
- created_at
- raw_payload_hash (optional)
- no canonical mutation fields

## Rules

1. Adapter output MUST validate before policy sees it.
2. Unknown fields do not acquire authority.
3. Provider-specific metadata stays in adapter/diagnostic storage.
4. Request and packet schemas are versioned.
5. Identical packet + policy version yields identical disposition.

## Evidence identity semantics (v1)

The field name `evidence_hash` is retained for schema compatibility in `patchhive.decision.v1`, but its normative value is the immutable `ClassificationEvidenceRecord.id` for the exact evidence record being resolved.

- It is an **evidence identity binding**, not a cryptographic content digest.
- Providers and policy MUST echo the value unchanged.
- Receipt lookup MUST bind advisory results to this evidence identity in addition to candidate identity.
- Callers MUST NOT use `evidence_hash` as proof of byte integrity, packet integrity, or content equality.
- Cryptographic integrity uses dedicated hashes such as image/content SHA, candidate-set hash, request/result hash, and raw-payload hash.
- A future schema version MAY rename this field to `evidence_id`; such a rename MUST be versioned rather than silently changing v1 semantics.
