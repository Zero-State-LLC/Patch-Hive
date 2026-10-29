# Intent

## Problem

Six modules in the committed maker crawl (`maker-crawl-v2.json`) are in no overlay, so the catalog lacks them: 2hp Mix, Bastl Aikido, Bastl Citadel Alchemist, FX Wizard and Wave Bard, and Tubbutec USB bridge A. The planning note said seven; the seventh, Doepfer "A-100 Kofferversionen", is a case ("Koffer" is German for case).

## Proposed outcome

- `catalog-additions-v6` (6 rows) and `module-power-depth-v14` (6 entries), built with `build_maker_overlays.py --brands "2hp,Bastl Instruments,Tubbutec,Doepfer" --only-new`.
- `--only-new` emits only modules no catalog row or earlier overlay holds, and no power entries for matched rows (a partial pass otherwise repeats every brand's earlier entries).
- `NOT_MODULE_NAME` excludes "Kofferversion(en)".
- The pages state no power draws, so the draws stay unknown (spec 003 FR-022) and rack budgets show them per rail (#118). Depth is filled where stated.
- `build_reattribution.py` moves its v2 output numbers to 7/15 (v2 wrote none), so 6/14 belong to these rows.

## Affected users / systems

- `module_catalog` and `modules` (+6 each) on staging and prod; the overlay builder.

## Constraints / non-goals

Maker pages only; insert-if-absent and fill-null; no fetches. Dry run, then apply with the reviewed `plan_hash`.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| No earlier overlay or seed holds the six | `OBSERVED` | offline plan comparison; `test_a3_overlays_hold_only_the_new_crawl_rows` |
| The overlays build byte-identically twice | `OBSERVED` | two runs, `cmp` |
| A fresh load holds them | `OBSERVED` | Postgres 15 population test, then a query |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-28
