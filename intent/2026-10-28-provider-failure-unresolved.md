# Intent

## Problem

Spec 006's resolution machine sent a provider failure or timeout to `REJECT`. Spec 005 treats `REJECT` as a judgment on the evidence, and a provider that did not answer made none. A rejected resolution reads as "this evidence is bad" when the truth is "nobody looked".

## Proposed outcome

- `CLASSIFYING` + `provider_fail` / `timeout` goes to `ESCALATE` when a routing target exists, else `UNRESOLVED`. The reason stays `PROVIDER_FAIL` / `PROVIDER_TIMEOUT`.
- Clef resolution passes its routing targets on every failure event (exception, malformed output, failed packet).
- Unchanged: no proposal, no decision receipt, no canon write; neither state accepts a confirmation. An invalid packet schema still goes to `REJECT`.
- Spec 006 tasks.md and DEPLOY_NOTES updated to match.

Out of scope: retry scheduling for unresolved resolutions.

## Affected users / systems

- `backend/intelligence/resolution_machine.py`, `clef_resolution.py`.
- Spec 006 state-machine tests and docs.

## Constraints / non-goals

Fail closed: both target states block canon writes. No change to the policy's packet-level `ESCALATE` for failed packets.

## Open questions

None. Owner chose UNRESOLVED / ESCALATE on 2026-10-28.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Failure goes UNRESOLVED without a route, ESCALATE with one | `OBSERVED` | `tests/unit/test_resolution_machine.py`, `test_clef_provider_failure_escalates_when_a_routing_target_exists` |
| Neither state permits a canon write or confirmation | `OBSERVED` | same tests; `test_failed_provider_resolution_cannot_be_confirmed_and_can_be_archived` |
| Full backend suite passes | `OBSERVED` | local run, 955 passed |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-28
