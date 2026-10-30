# Intent

## Problem

The 007 evaluation receipt is self-consistent only (007 research R1). `verify_enablement_receipt`
accepts a bare mapping that carries only `schema_version`, `approved_by` and a matching unkeyed
SHA, and anyone who edits a field can reseal it. `OperatorApproval.approved_by` is free text, so a
receipt never says who approved it. The 006 `gates_pass` guard accepts any 64-hex string as the
evaluation receipt SHA and never sees the receipt (006 research R1).

## Proposed outcome

- 007 T080: `verify_enablement_receipt` validates the full `EvaluationEnablementReceipt` model
  (a mapping must validate and round-trip exactly) and, when given the chain records, rebuilds the
  receipt with `pin_receipt` and compares.
- 007 T081: an Ed25519 signature over `receipt_sha256`, kept beside the receipt, is checked against a
  committed approver allowlist (`key_id`, public key, `valid_from`, `revoked_at`). The signing key id
  must equal the receipt's `approved_by`. Unknown, revoked or not-yet-valid keys, bad signatures and
  mismatched hashes all refuse. The committed allowlist ships with no keys.
- 006 T100: `ReadinessEvidence` carries the receipt and its signature; `gates_pass` calls the signed
  verifier against the committed allowlist and requires the receipt SHA to match the evidence SHA.

Out of scope: generating or committing a real approver key (007 T082), signing the pinned receipt
(007 T083), signing the 008 `ReadinessPin` (008 T071/T072), and the runtime gate (005 T080).

## Affected users / systems

Backend `intelligence/evaluation_enablement.py`, new `intelligence/receipt_signing.py`,
`core/ops/edge_readiness.py`, their tests, and the backend dependency set (`cryptography`).

## Constraints / non-goals

Fail closed. No private key in the tree; tests generate throwaway keys in memory. No secrets in logs
or error details. The allowlist path is a committed file, not an environment override. Until an
operator commits a reviewed public key, `gates_pass` cannot pass; that is intended.

## Open questions

- Revocation semantics: research R1 says "reject a key revoked before the receipt's `approved_at`".
  `approved_at` is inside the signed content, so a holder of a lost key can backdate it. This change
  also refuses any key whose `revoked_at` is at or before verification time, matching "a lost key is
  revoked and the receipt re-signed with a new key". Operator to confirm.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| `cryptography` was not installed in the backend venv | `OBSERVED` | venv import, 2026-10-29 |
| `cryptography==50.0.2` is the newest release on the index | `OBSERVED` | `pip index versions cryptography`, 2026-10-29 |
| A bare mapping with a matching SHA passed the old verifier | `OBSERVED` | 007 research R1 |
| No other runtime caller relies on `gates_pass` accepting a bare SHA | `OBSERVED` | grep of backend/ and scripts/ |

## Author / date

- Author: Claude (lane high) for Daniel Meyer
- Date: 2026-10-29
