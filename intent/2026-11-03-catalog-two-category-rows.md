# Intent

## Problem

`scripts/build_category_overlay.py` leaves a row empty when its maker tags point to two categories. In a load from the committed inputs, 24 such rows (20 live) have no category, and nobody has checked which category is right.

## Proposed outcome

List the rows reproducibly (`--list-ambiguous`), settle the ones committed data settles in a hand-reviewed fill-null overlay (`module-catalog-category-v2`, every entry citing its source), and write down the rest: a retirement proposal for the duplicate Jolin GETREKT, a noise-versus-random convention proposal, and the rows that need a maker page. Evidence: [CATALOG_TWO_CATEGORY_ROWS_2026-11-03.md](../docs/evidence/CATALOG_TWO_CATEGORY_ROWS_2026-11-03.md).

Out of scope: any fetch (catalog work is offline until the owner signs off the maker-permission basis), any load to a deployed database, retiring rows, and new categories.

## Affected users / systems

Catalog inputs only. `inputs_hash` changes, and the next db-load dry run plans 9 `category_overlay` updates. No schema change.

## Constraints / non-goals

Fill-null only. A row the committed data does not settle stays empty (unknown stays null). No ModularGrid.

## Open questions

- Retire `jolin-getrekt-touch-waveshaper` (and the ROSA twin)? Owner.
- Noise versus random: option A, B or C? Owner.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| 24 rows (20 live) are ambiguous before v2, 15 (11 live) after | `OBSERVED` | `build_category_overlay.py --list-ambiguous` |
| Each v2 category is one of its row's tag categories, and the loader fills it | `OBSERVED` | `backend/tests/test_build_category_overlay.py` |
| A catalog noise module filed under VCO is not a noise source for the patch engine | `INFERRED` | `catalog_routes.py:279` sets `module_type = category`; `engine.py:136` matches NOISE |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-03
