# Intent

## Problem

Before #152 the unsourced `overlays/module-catalog-hp-v1.json` filled empty HP ahead of the maker-cited v2. #152 fixed the order for fresh loads, but the loader never overwrites a stored value, so databases loaded earlier (staging, prod) most likely still hold the v1 values: Acid Rain Technology Junction 6 (maker: 4), Doepfer A-101-3 10 (maker: 30), Doepfer A-137-2 10 (maker: 14). A wrong HP misplaces a module in a rack.

## Proposed outcome

- `provenance/maker-corrections-v2.json` with reviewed `correct` entries (spec 003 D4, FR-038) for every table that holds a v1 value: `module_catalog` for all three, and `modules` for Junction and A-101-3 (their `modules` rows copied the catalog HP). A-137-2 has no `modules` row.
- The loader reads the manifest after `maker-corrections-v1`.
- Out of scope: ALM Busy Circuits Akemie's Castle. A replay of the pre-#152 load stores 38 (the maker value, from `catalog-additions-v3`), not v1's 18, so no correction is written. Also out of scope: the wider HP triage (spec 003 T039).

## Affected users / systems

`module_catalog` and `modules` on staging and prod (five values), the catalog loader's manifest list.

## Constraints / non-goals

Values only from a cited maker page. Each entry fires only while the stored value is the v1 value; any other value is left alone. Dry run, then apply with the reviewed `plan_hash`. No ModularGrid.

## Open questions

- Does staging hold 18 for Akemie's Castle anyway (a history the replay does not reproduce)? The db-load dry run shows only the planned corrections; a read-only query of the row answers it. If it does, a later manifest corrects it.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The maker pages state 4, 30, 14 and 38 HP | `OBSERVED` | plain GET 2026-10-29, PR #152 body |
| A pre-#152 fresh load stores 6/10/10 in `module_catalog`, 6/10 in `modules`, and 38 for Akemie's Castle | `OBSERVED` | replica replay of 4d5bfe9 on Postgres 15.13 |
| The branch apply writes only the five corrections; a rerun changes nothing; no other slug's HP changes | `OBSERVED` | replica replay, slug:hp digests before and after |
| Staging and prod hold the same values as the replay | `INFERRED` | they were loaded before #152; confirm with the staging dry run |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-30
