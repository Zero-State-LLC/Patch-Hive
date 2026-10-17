# Domain model — Decision Intelligence

## Entities

### EvidenceBundle
Immutable references to normalized observations. Contains no canonical conclusion.

### CandidateSet
A bounded set of allowed answers derived from catalog/search state. Exact identity candidate sets MUST include `none_of_above`.

### DecisionRequest
Versioned request containing purpose, evidence bundle reference/hash, candidate set or score rubric, and idempotency key.

### DecisionPacket
Immutable provider-neutral result. It records provider provenance and probabilities/scores but has no canonical authority.

### DecisionPolicy
Pure, versioned rules that map a DecisionPacket plus evidence-authority metadata to a disposition.

### ResolutionProposal
A non-canonical proposal for module identity, capability, port semantics, conflict, or next action.

### Confirmation
Existing user/authoritative confirmation event that can permit canonical inventory revision.

## Invariants

- EvidenceBundle -> DecisionPacket is many-to-many and append-only.
- DecisionPacket never owns a CanonicalRig or SystemInventoryRevision mutation.
- Provider-specific payloads may be retained as diagnostic evidence but are not domain contracts.
- Candidate IDs must resolve to registry records at request time or the request fails closed.
- A `none_of_above` identity result never creates a module.
