# Intent

## Problem

1,038 of 4,172 `module_catalog` rows have no category. Of the 901 rows the loader builds, 851 have a crawled maker page, and most of those pages list tags the overlay builder's category rules never read (for example "low pass gate", "random", "attenuverter", "compressor").

## Proposed outcome

- `scripts/build_category_overlay.py` writes `overlays/module-catalog-category-v1.json` from the committed crawl (`hermes-research/maker-crawl-v2.json`), with no fetches.
- For each catalog row the loader would hold with no category, in order:
  1. the existing builder rules over tags and name;
  2. the source URL's path words;
  3. new whole-tag rules (`TAG_CATEGORY`) mapped onto the existing 11 categories. A row whose tags point to two categories stays empty.
- The loader reads `module-catalog-category-v*.json` and fills a category only where it is null. A mismatched identity is a conflict; a missing slug is counted as unmatched.
- Result: 183 rows filled (152 whole-tag, 26 existing rules, 5 URL path). 24 ambiguous and 644 untagged rows stay empty.

Out of scope: the 137 older database rows the loader does not build, and the 644 untagged rows (they would need the maker pages read again).

## Affected users / systems

- `data/synth-catalog/population.py`, the new overlay and builder, `module_catalog.category` on staging and prod.

## Constraints / non-goals

Fill-null only; no stored category changes. No ModularGrid. No paid fetches. Loads go dry run, then apply with the reviewed `plan_hash`.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The overlay builds byte-identically twice | `OBSERVED` | two local runs, `cmp` |
| The loader fills nulls only and flags identity mismatches | `OBSERVED` | `tests/test_build_category_overlay.py` |
| Population dry run, apply and rerun stay idempotent with the overlay | `OBSERVED` | `tests/test_catalog_population.py` on Postgres 15 |
| Tag-to-category mappings are correct for each row | `INFERRED` | whole-tag rules; ambiguous rows excluded |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-28
