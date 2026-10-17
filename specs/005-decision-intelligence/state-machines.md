# State machines

## Resolution state

```text
CAPTURED
  -> EVIDENCE_EXTRACTED
  -> CANDIDATES_READY
  -> DECISION_PENDING
  -> DECISION_RECORDED
       -> PROPOSED
       -> REVIEW_REQUIRED
       -> UNRESOLVED
       -> ESCALATION_REQUIRED
       -> REJECTED
PROPOSED/REVIEW_REQUIRED
  -> CONFIRMED
  -> REJECTED
  -> DEFERRED
CONFIRMED
  -> CANONICALIZED
```

### Forbidden transitions

- DECISION_RECORDED -> CANONICALIZED
- provider failure -> CONFIRMED
- UNRESOLVED -> CANONICALIZED
- DEFERRED -> CANONICALIZED
- candidate not in CandidateSet -> PROPOSED

## Provider request state

`CREATED -> SENT -> SUCCEEDED | FAILED | TIMED_OUT`

Retry creates a new attempt bound to the same idempotent logical request; attempts are retained.
