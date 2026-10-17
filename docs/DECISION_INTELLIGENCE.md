# Decision Intelligence

**Status:** specification campaign; implementation pending.

PatchHive's Decision Intelligence layer resolves bounded ambiguity between untrusted evidence and deterministic canon. Jev is the first planned provider adapter, not a canonical dependency.

```text
image/manual/import
      |
      v
evidence providers (vision/OCR/retrieval)
      |
      v
normalized EvidenceBundle
      |
      v
DecisionProvider (Jev or fixture/other)
      |
      v
DecisionPacket
      |
      v
deterministic DecisionPolicy
      |
      v
proposal / review / unresolved / escalation
      |
      v
existing confirmation authority
      |
      v
canonical inventory revision
```

High-value use cases: module candidate ranking, function-family classification, capability hypotheses, port semantics, evidence-conflict detection, and cheap-to-expensive routing.

**Hard boundary:** probabilistic decisions never directly write canonical inventory.

Authoritative feature specification: [`specs/005-decision-intelligence/`](../specs/005-decision-intelligence/spec.md).
