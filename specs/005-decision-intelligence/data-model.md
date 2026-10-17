# Data model

Initial implementation SHOULD prefer append-only decision records.

## decision_requests
- id (stable UUID/string)
- contract_version
- purpose
- evidence_hash
- candidate_set_hash/rubric_hash
- idempotency_key (unique)
- created_at

## decision_attempts
- id
- request_id FK
- provider
- provider_version
- attempt_number
- status
- latency_ms
- error_code nullable
- raw_payload_hash nullable
- created_at

## decision_packets
- id
- request_id FK
- attempt_id FK
- schema_version
- result_json
- result_hash
- created_at

## decision_dispositions
- id
- decision_packet_id FK
- policy_version
- disposition
- reason_codes JSON
- created_at

No table above may directly update canonical inventory. Existing confirmation/application services own that transition.


## MVP persistence reconciliation

The runtime currently persists a consolidated append-only `decision_receipts` projection rather than four normalized tables. This is an intentional MVP implementation of the logical records above, not a change in authority.

The receipt retains request/provider/result/policy/disposition provenance required for audit while keeping the decision subsystem noncanonical. Normalized `decision_requests`, `decision_attempts`, `decision_packets`, and `decision_dispositions` tables are reserved for a later phase if multi-attempt retry history, provider cost accounting, or independent disposition replay requires them.

Any future normalization MUST preserve append-only semantics and MUST NOT introduce a direct canonical-inventory write path.
