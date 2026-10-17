# Workflows

## WF-001 Module identity

`EvidenceBundle -> CandidateSet -> DecisionRequest -> DecisionPacket -> DecisionPolicy -> ResolutionProposal -> Confirmation -> InventoryRevision`

Guards:
- no candidates => UNRESOLVED;
- stale/unknown candidate IDs => REJECT;
- provider failure => ESCALATE or UNRESOLVED according to policy, never confirm;
- `none_of_above` => UNRESOLVED/retrieval route.

## WF-002 Capability classification

`EvidenceBundle -> bounded capability questions -> DecisionPackets -> policy -> capability proposals`

Each capability is independent. Absence of evidence is not evidence of absence.

## WF-003 Port semantics

`confirmed/proposed module context + normalized labels/geometry/manual evidence -> bounded port roles -> policy -> proposals`

Electrical values require authoritative evidence or explicit confirmation; probabilistic inference alone cannot canonize them.

## WF-004 Evidence conflict

`claims -> normalize -> compare -> conflict decision -> deterministic source-authority policy -> resolve/escalate`

No source is deleted during resolution.

## WF-005 Provider escalation

`attempt -> packet/failure -> policy -> next bounded route`

Maximum attempts and allowed routes are configuration/policy, not model output.
