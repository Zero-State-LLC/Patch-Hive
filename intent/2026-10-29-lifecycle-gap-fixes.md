# Intent

## Problem

The 2026-10-29 spec reconciliation (#134) found four places where the code breaks what the specs already say:

- A catalog correction leaves `needs_reverify` set, so a fixed row stays FLAGGED (003 R8).
- Manifest statements can archive, correct or flag a tombstoned row (003 R9).
- The Jev decision path skips the guarded resolution machine and hardcodes `decision-policy-v1` (005 R2).
- An unsupported or invalid decision packet ends REJECT, unlike every other provider failure (005 R3).

## Proposed outcome

- The loader clears `needs_reverify` once every flagged field on a corrected row is fixed. A flag or relabel is fixed by a later `correct`; a null is fixed once the field holds a value again.
- Every manifest statement skips retired rows, and the receipt counts each as `refused_row_tombstoned`.
- Every decision provider runs through `_resolve_with_guarded_flow`, using `settings.decision_policy_version`.
- An unreadable packet ends UNRESOLVED, or ESCALATE when there is a review route.

Out of scope:

- routing targets (005 R6);
- the idempotency-before-provider order (005 R5);
- receipt signing (007 R1).

## Affected users / systems

- Catalog loader (`data/synth-catalog/population.py`): the next db-load plan adds one `clear_reverify` update for CHICANE.
- Decision Intelligence route (off in production by startup policy).

## Constraints / non-goals

- Fail closed.
- No prod data load without a reviewed `plan_hash` and the owner's OK.
- Tests change only where the specified behavior changed (REJECT to UNRESOLVED).

## Open questions

None. Each fix follows the spec text.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| `clear_reverify` clears only when nothing flagged stays open, and a rerun is a no-op | `OBSERVED` | three scenarios on a local Postgres 15 (filled, empty nulled field, open flag) |
| Full backend suite passes | `OBSERVED` | 1104 passed, 9 skipped |
| CHICANE's flag clears on the next load | `INFERRED` | its only open items are the hp flag (corrected) and depth_mm, refilled to 12 mm |

## Author / date

- Author: Claude Code (for Daniel Meyer)
- Date: 2026-10-29
