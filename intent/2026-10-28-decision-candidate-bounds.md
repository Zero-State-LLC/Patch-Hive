# Intent

## Problem

Spec 005 FR-003 says exact module identification works only over the catalog candidates in the request, plus `none_of_above`, and that a provider must not create a catalog identity. Nothing enforced it. `DecisionPolicy.evaluate` saw only the packet, so a provider that answered with a choice outside the request's candidates (or put probability on one, or reported a different candidate set hash) could reach `AUTO_PROPOSE`.

## Proposed outcome

- `check_choice_packet(packet, request)` in `intelligence/contracts.py` checks a succeeded choice packet against the request: the selected choice and every probability key must be a request candidate or an abstain choice (`none_of_above`, `unknown`), and a reported candidate set hash must match the request's.
- `DecisionPolicy.evaluate(packet, request)` returns `ESCALATE` with the violation as the reason (`CHOICE_NOT_IN_CANDIDATE_SET`, `PROBABILITY_OUTSIDE_CANDIDATE_SET`, `CANDIDATE_SET_MISMATCH`).
- The module decision service and Clef resolution pass the request to the policy.

Out of scope:
- Provider-failure disposition. Spec 005 implies a failed provider is not a rejection; spec 006's resolution machine maps it to `REJECT` and 13 tests encode that. Changing it needs a decision (see Open questions).

## Affected users / systems

- `backend/intelligence/` policy, contracts, module service, Clef resolution.
- Any provider (Clef, OpenRouter, local) answering choice requests.

## Constraints / non-goals

- Fail closed: an out-of-set answer escalates; it is never repaired into an in-set one.
- Vision cannot self-confirm; `AUTO_PROPOSE` remains a proposal.
- No change to packet schema or stored packets.

## Open questions

- Should a provider failure resolve to `UNRESOLVED` (or `ESCALATE` when a routing target exists) instead of `REJECT`? Owner decides; it changes the spec 006 contract and its tests.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| An out-of-set choice now escalates in the policy and the service | `OBSERVED` | `tests/unit/test_decision_adversarial.py`, `tests/unit/test_module_decision_service.py` |
| In-set answers still auto-propose; abstain stays unresolved | `OBSERVED` | same tests |
| Full backend suite passes | `OBSERVED` | local run, 947 passed |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-28
