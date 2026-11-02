# Intent

## Problem

Specs 001–004 each carry a transitions table that their T010 says to encode as tests. None was, so code could drift from the tables without CI noticing.

## Proposed outcome

One table-driven test file per spec (`backend/tests/unit/test_spec_00N_transitions.py`) that asserts every row the code implements: listed transitions reach the listed state, listed illegal pairs are rejected with no state change. Rows the code does not implement are left out and recorded as drift in each spec's T010 note, not encoded as passing tests. T010 stays open because its dependency T002 (plan.md) waits on the owner's T001.

Out of scope: changing production code to close the drift, and the missing machines (001 evidence disposition, 002 page and book compilation, 003 batch pipeline, 004 Machines B and C).

## Affected users / systems

CI backend tests only.

## Constraints / non-goals

No production code, spec, fixture or existing-test edits. No assertion weakened to pass. Payments stay in test mode; no provider called.

## Open questions

- 004: `record_purchase(payment_verified=False)` still writes the legacy Grant and a Rewarded referral; the spec lists a client-submitted purchase reward as illegal. Fix or amend the spec (owner).
- Whether each missing machine should be built or cut from its spec.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The four files pass and are lint-clean | `OBSERVED` | local pytest and ruff |
| The drift rows listed in each T010 note have no implementation | `OBSERVED` | code search, file:line in the notes |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-01
