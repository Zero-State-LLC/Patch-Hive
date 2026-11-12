# Intent

## Problem

Only 226 of the 3,379 public Modules declare jacks. The 2026-11-09 readings, already paid for, hold more lists that both readings gave jack for jack, but only one reading called the document complete. Spec 003 FR-041 kept them out, because the engine then sent a cable to the first free jack of the right type, so a list missing a jack could misroute a cable.

## Proposed outcome

- `scripts/read_module_jacks.py decide --one-full` accepts a list when the two readings list the same jacks and at least one calls the document complete. Every other gate stays.
- `overlay --earlier` leaves out Modules an earlier overlay holds, and `--reviews` with `--reviewed-only` keeps only lists a hand check found complete.
- Two new gates refuse a name that stands for several jacks and a list holding one channel of a multi-channel Module.
- FR-041 is amended to match: a list only one reading called complete also needs a hand check. Two samples of 25 found 20 and 18 complete, so `overlays/module-jacks-v2.json` holds only the 38 confirmed lists.

Out of scope: new model readings, which need a working key and a cap, and loading. Each load needs the owner's yes on its hashes.

## Affected users / systems

Patch generation and Patch Books for the Modules in v2, once loaded.

## Constraints / non-goals

- The loader fills `io_ports` only while empty, and a different stored list is a conflict that stays as it is (FR-041).
- Quotes from makers' documents stay in the private proposal.
- No model spend: the gate reruns over kept readings.

## Open questions

None for this slice.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| v2 holds 38 lists, 234 jacks, 29 makers, none in v1, each hand-checked complete | `OBSERVED` | `overlays/module-jacks-v2.json`, `jack-list-reviews.json`, `backend/tests/test_module_jacks_load.py` |
| About one in four lists only one reading called complete is incomplete | `OBSERVED` | Two samples of 25, `docs/evidence/CATALOG_MODULE_JACKS_V2_2026-11-12.md` |
| A list matches the physical panel | `NOT_COMPUTABLE` | Lists were checked against documents only |
| Two readings by one model catch slips, not a mistake both make | `INFERRED` | Same model, two prompts |

## Author / date

- Author: Claude Opus 5.5, for the owner
- Date: 2026-11-12
