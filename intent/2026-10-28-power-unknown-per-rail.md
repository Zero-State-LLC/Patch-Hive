# Intent

## Problem

Unknown module power counted as 0 mA (decision note §1), so a rack could pass a power budget it may not meet:
- `racks/validation.py` added a NULL draw as 0 with no warning.
- `cases/compatibility.py` warned only when all three rails were NULL, and treated a NULL +5V as "needs no +5V" (wrong for a jumper-set 4ms module).
- Rack Builder marked a module unknown when +12V was NULL, then dropped its known -12V and +5V.
- The power overlay script truncated 3.5 mA to 3; the loader rounds to 4.

In prod, 1,568 live modules have no +12V, 1,651 no -12V, and 3,320 no +5V.

## Proposed outcome

- A module rail that is NULL is unknown on that rail only; known rails still add (spec 003 FR-022).
- Rack validation: a rail whose known draws fit but which has unknowns is a `POWER_RAIL_INCOMPLETE` warning ("at least X mA of C mA, plus N modules with unknown draw"). Known draws over capacity stay a hard error. `POWER_UNSPECIFIED` also fires when every draw is unknown.
- Compatibility: each rail result carries `unknown_draw_count` and `unknown_modules`; such a rail is `incomplete` with a lower-bound message. A NULL +5V is unknown (`POS5_UNKNOWN`, `POS5_INCOMPLETE`), never `POS5_NOT_REQUIRED`.
- Rack Builder: per-rail totals and unknown counts (`lib/powerBudget.ts`); meters warn on unknowns and say "at least … at most … headroom".
- One rounding rule: the overlay script rounds half away from zero like the loader.

Out of scope: jumper-dependent power configs (decision note §1, later).

## Affected users / systems

- Rack validation, case compatibility API, Rack Builder and Racks pages, the power overlay script.

## Constraints / non-goals

Never invent a draw. Unknown is a warning, not an error; only known draws over capacity block.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| NULL counts per rail in prod | `OBSERVED` | read-only prod query |
| Known rails add when another is NULL; unknowns warn per rail | `OBSERVED` | `tests/unit/test_rack_case_validation.py`, `tests/test_case_catalog_compatibility.py`, `src/lib/powerBudget.test.ts` |
| Overlay script and loader round alike | `OBSERVED` | `tests/test_power_rounding.py` |
| Most racks will show a +5V lower bound | `INFERRED` | 3,320 of 3,886 live modules state no +5V |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-28
