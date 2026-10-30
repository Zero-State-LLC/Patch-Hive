# Intent

## Problem

The 2026-10-29 gap analysis left decisions open across specs 001–008. Specs 001, 002 and 004 had stub research files, and 005, 007 and 008 had none. No spec said which requirements the merged fixes (#82–#133) implement. The specs no longer matched the code.

## Proposed outcome

- Each spec has a research.md with one R-item per open decision: evidence, options, a recommendation and its effort.
- Each spec has an "Implementation status (2026-10-29)" table mapping every FR to Implemented, Partial or Missing, with evidence.
- Open questions the code now answers are marked RESOLVED.
- Gap-closure tasks have `depends_on` edges.
- `scripts/check_spec_dag.py --strict` passes.

Out of scope: code changes, adopting recommendations the owner has not approved, and any paid fetch or deploy.

## Affected users / systems

Specs 001–008, CURRENT_STATE.md and docs/KANBAN.md. No runtime system changes.

## Constraints / non-goals

- Docs only.
- Recommendations stay recommendations until the owner adopts them.
- Spending (T035), legal and business questions stay with the owner.

## Open questions

The owner decides each R-item marked "awaits the owner". The main ones:

- receipt signing (007/008);
- the provider purchase machines (004);
- the 221 v1 HP values (003 R7).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| `_correct_row` never clears `needs_reverify` | `OBSERVED` | data/synth-catalog/population.py:585 |
| Archive, correct and reverify statements don't check tombstones | `OBSERVED` | population.py:525 (`_row_where`) |
| Of the 221 v1 HP values, 45 agree with a maker page, 7 disagree and 169 are unmatched | `OBSERVED` | local comparison with hermes-research/maker-crawl-v2.json |
| The Akemie's Castle crawl value (38 HP) is an extraction error | `INFERRED` | widely listed at 18 HP; not checked on the maker page |
| FR status tables match the code | `OBSERVED` | per-spec evidence columns; spot-checked in review |

## Author / date

- Author: Claude Code (for Daniel Meyer)
- Date: 2026-10-29
