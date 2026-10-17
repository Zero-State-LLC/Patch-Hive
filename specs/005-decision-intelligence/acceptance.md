# Acceptance

## Contract
- [x] Provider-specific response types cannot enter canon package contracts.
- [x] Candidate result outside server-authored set is rejected.
- [x] Packet hashes and idempotency are deterministic.
- [x] Unsupported schema/policy versions fail closed.

## Authority
- [x] No DecisionPacket can directly create/update SystemInventoryRevision.
- [x] Provider failure cannot transition to CONFIRMED/CANONICALIZED.
- [x] Low confidence cannot be converted to a fabricated negative fact.
- [x] Existing user confirmation remains required for probabilistic identity/capability proposals.

## Evaluation
- [ ] Versioned labeled corpus exists with provenance/licensing notes.
- [ ] Baseline and Jev results are retained.
- [ ] Top-1/top-k, calibration, review/abstention, escalation, latency/cost are reported.
- [ ] False canonicalization = 0.
- [ ] Thresholds are selected after observing baseline; no invented target is treated as evidence.

## Operations
- [x] Jev flag defaults OFF.
- [ ] Provider timeout/retry caps tested.
- [ ] Provider outage leaves canonical generation safe.
- [ ] Rollback disables Jev without schema/data loss.

## Documentation
- [x] README/current state/roadmap link the feature spec.
- [x] Architecture marks decision intelligence as evidence-side, not canonical authority.
- [x] Legacy/historical docs are not silently promoted to authority.
