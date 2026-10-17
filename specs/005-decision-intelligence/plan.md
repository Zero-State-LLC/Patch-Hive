# Implementation plan

## WP-00 SpecKit normalization
- Establish constitution and this feature tree.
- Add specification index and authority map.
- Do not bulk-move historical docs; link and classify them to avoid breaking references.

## WP-01 Contracts
- Add provider-neutral schemas/protocol.
- Add deterministic policy interface and reason codes.
- Add schema/hash/idempotency tests.

## WP-02 Persistence + telemetry
- Append-only request/attempt/packet/disposition persistence.
- Structured metrics for latency, failures, confidence bands, escalation.

## WP-03 Jev adapter
- Implement Jev only behind `DecisionProvider`.
- No Jev types outside adapter.
- Feature flag default OFF.
- Fixture provider remains authoritative for deterministic tests.

## WP-04 Module intelligence
- Candidate ranking.
- Function-family classification.
- Capability classification.
- Port-semantic classification.
- Conflict detection.

## WP-05 UI confirmation
- Show candidate, confidence band, evidence provenance, reason for review.
- Confirm/reject/defer through existing inventory confirmation authority.

## WP-06 Evaluation
- Versioned labeled corpus.
- Baseline vs Jev.
- Calibration, top-k, abstention/review, escalation, latency/cost.
- Retained evaluation receipt pinned to source SHA.

## WP-07 Controlled enablement
- Enable only in non-production/staging after evaluation gate.
- No automatic canonicalization.
