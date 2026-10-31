# Intent

## Problem

Three owner decisions were open after #170: two T034 power settings the loader skipped (SMR base setting unlabelled on the page; VCA Matrix "80 max" with no unit), the Doepfer A-155 stored at 4 HP while its maker page says 50 HP (FR-038 only allowed corrections inside the 1-42 band), and whether to schedule `evidence.expire`.

## Proposed outcome

The owner adopted the recommendations in docs/evidence/OPEN_DECISIONS_2026-10-30_RESEARCH.md §5-7:
- `receipts/t034-owner-decisions.json`: SMR base labelled "jumper not set to +12V"; VCA Matrix external-5V +12V stored as unknown. 21 settings for 11 modules load, none skipped.
- FR-038: reviewed corrections may run from 1 to 84 HP; extraction (FR-007) keeps 1-42. `provenance/maker-corrections-v5.json` corrects A-155 4 to 50 in `module_catalog` and `modules`.
- `evidence.expire`: not scheduled now; spec 006 T101c follows T101b.
Out of scope: other legacy_unsourced rows, deploying.

## Affected users / systems

Catalog loader, `power_configs`, `module_catalog` / `modules` HP, rack placement for the A-155, spec 003 FR-038, spec 006 tasks.

## Constraints / non-goals

No number added that a page does not state; a correction still needs `only_if_value`, a maker page and archive-first; fill-only elsewhere.

## Open questions

None for this change.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| doepfer.de/a155.htm states "50 TE / 50 HP / 253.7 mm" | `OBSERVED` | plain GET 2026-10-30 |
| Prod stores A-155 at 4 HP in both tables | `OBSERVED` | prod API (catalog id 169, modules id 324) |
| On a database holding 4 HP the plan corrects it to 50 and clears its marker (61 left); a rerun plans nothing | `OBSERVED` | local Postgres 15 simulation |
| No API, schema or frontend check caps module HP at 42 | `OBSERVED` | grep of backend and frontend |

## Author / date

- Author: Claude (for Daniel Meyer)
- Date: 2026-10-30
