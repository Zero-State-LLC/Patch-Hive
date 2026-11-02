# Intent

## Problem

Spec 005 FR-010 requires an approved, receipt-bound evaluation before a decision provider runs. Production refuses providers outright (#132), but staging could turn one on with flags alone; no runtime code read the signed 007 receipt (research R1).

## Proposed outcome

Outside development and test, with any decision flag on or a provider selected, startup refuses and the decision route answers 409 `ENABLEMENT_RECEIPT_REQUIRED`, unless a signed `EvaluationEnablementReceipt` verifies against the committed approver allowlist and names the configured provider and policy version. Receipt and signature are JSON files named by two new settings, forwarded by the edge Worker in staging only.

Out of scope: generating the key (007 T082) and signing a real receipt (007 T083), both operator steps.

## Affected users / systems

API startup, `POST /racks/{id}/evidence/decision-resolution`, `edge/api` env forwarding. Staging sets no decision flags today, so nothing that runs now changes.

## Constraints / non-goals

Fail closed: any unreadable, invalid, unsigned, wrongly signed, revoked, or mismatched receipt refuses. Development and test stay ungated so local work and CI are unaffected. Production's blanket refusal is unchanged.

## Open questions

- Where the operator keeps the receipt in the container (committed file or a mounted path) is the operator's choice; the settings take any readable path.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Staging sets no decision flags today | `OBSERVED` | `edge/api/wrangler.jsonc` staging vars |
| The gate refuses every failure mode and passes a valid signed receipt | `OBSERVED` | `tests/unit/test_decision_enablement_gate.py` |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-01
