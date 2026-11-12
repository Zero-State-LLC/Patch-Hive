# Intent

## Problem

224 Modules have jack lists on both databases, but a Module with no category can't be used by any patch rule. 19 of the 224 have no category, including Make Noise Bruxa and Mutable Warps. Four drums filed as VCO also get pitch cables.

## Proposed outcome

- `overlays/module-catalog-category-v11.json` fills a category for each row whose maker's document settles it, by the catalog's existing rules.
- `docs/evidence/CATALOG_JACK_LIST_CATEGORIES_2026-11-10.md` names each row, its category and its source document, and lists every row left out and why.

Out of scope: applying a load, and any dry run before the owner's go-ahead. Also out of scope: a new category, a change to the engine, and rewriting a stored jack list.

## Affected users / systems

The catalog loader. Once a load is applied, patch generation can use these Modules, because the loader's sync copies a category onto `modules.module_type` over the placeholder.

## Constraints / non-goals

- Existing categories only. A row that needs a new one, or whose document doesn't settle it, stays out and goes on the owner's list.
- ModularGrid is never a source (spec 003 D1).
- Quotes from makers' documents stay out of the repo.
- Fill-null only. Nothing spends money on any provider.

## Open questions

The owner decides:

- Which category quantisers take, which settles Analogue Systems RS-260 and Intellijel Scales.
- What to do about the four drums. The brief asked for a correction manifest, but the catalog's rules send drums to VCO and there is no drum category, so none is included. The evidence record gives three options.
- A category for each of the other 8 rows left out, if a suggestion there is accepted.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| 19 of the 224 rows have no category on production | `OBSERVED` | `overlays/module-jacks-v1.json` joined with the public API, 2026-11-10 |
| Each of the 9 categories follows from the maker's document | `OBSERVED` | Read by hand; `backend/tests/test_jack_list_categories.py` checks the rule |
| A dry run plans 9 fills and 9 `module_type` updates with 0 conflicts | `OBSERVED` | Throwaway Postgres loaded without the overlay |
| Both deployed databases get the same plan | `OBSERVED` | Dry runs 42926869828 (staging) and 42926874415 (production), same `plan_hash` and `inputs_hash` |
| Mosaic Bass Drum's jack list is incomplete | `INFERRED` | The document describes CV control the list doesn't have; no physical panel was checked |

## Author / date

- Author: Claude Opus 5.5, for the owner
- Date: 2026-11-10
