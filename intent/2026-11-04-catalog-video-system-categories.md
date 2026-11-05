# Intent

## Problem

The spec 003 T031 offline pass left catalog rows waiting on owner calls: 24 video rows, 11 power rows, 4 rows tagged both noise and random, rectifiers, crossfaders, and Mutable-derived rows. A duplicate Jolin row was also waiting, and the catalog's own Mutable Instruments rows looked wrong. The owner decided these on 2026-11-04 (decisions 5, 6, 7, 14 and 17, recorded in #278).

Reviewing that work raised more calls (decisions 49, 50, 51, 54, 55 and 56): 35 further video rows held other categories, 10 Mutable-derived rows had no source that gave their category, and a filled category never reached `modules.module_type` on a loaded database.

## Proposed outcome

One PR that applies those calls from committed data:

- VIDEO and SYSTEM wherever the Module Category vocabulary is enforced, with a test that the patch engine ignores both.
- A generated overlay for the rule-based rows and a hand-reviewed overlay for the rows that quote the maker, fill-null.
- `correct` entries for the 3 video rows v1 filed elsewhere, for the further video rows whose own page says video, for the 2 LZX DC Distro rows, and for the Mutable rows committed data backs.
- A retirement of `jolin-getrekt-touch-waveshaper`.
- A loader step that copies a category onto a module row holding the loader's own placeholder, and nothing else.
- A dated evidence doc with observed counts, and a dry run against a throwaway database.

Evidence: [CATALOG_TAXONOMY_DECISIONS_2026-11-04.md](../docs/evidence/CATALOG_TAXONOMY_DECISIONS_2026-11-04.md).

Out of scope: any fetch, any load to a deployed database, a NOISE category, firmware platforms, decision 52's clearing of ModularGrid URLs, and ticking T031.

## Affected users / systems

Catalog inputs, the loader, and `db-load.yml`'s summary. `inputs_hash` changes. Over main's data, the next db-load dry run plans 52 category fills, 60 corrected values, 52 `module_type` fills and 2 retirement updates. A deployed database has more `module_type` fills, because earlier fills never reached those rows. On a Rig holding an affected module, the next generation may differ, and a Rig holding a SYSTEM module gets #291's warning. No schema change.

## Constraints / non-goals

No maker page, feed or listing is fetched. A category outside the vocabulary is a conflict. No category without a cited source: anything committed data doesn't back is listed for the free-reads PR, not filled or corrected. A `module_type` someone set is never overwritten. Retirements tombstone, never delete.

## Open questions

- Module rows that hold the materialize default `UTIL` can't be told apart from a deliberate value, so they stay. Owner, later.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The dry run over main's data plans 52 fills, 31 + 29 corrections, 52 `module_type` fills, 1 + 1 retirements, 0 conflicts | `OBSERVED` | `receipts/taxonomy-2026-11-04.dry-run.json` |
| A load from empty and a load over main's data agree on every category, tombstone, `module_type` and status | `OBSERVED` | throwaway Postgres, same receipt |
| Before the fix, a filled category left `module_type` as `UNKNOWN` on a loaded database | `OBSERVED` | `test_a_category_reaches_module_type_on_a_loaded_database` failed, then passed |
| No patch engine keyword matches VIDEO or SYSTEM | `OBSERVED` | `tests/unit/test_patch_engine.py` |
| The same rig revision and seed can give different patches after the load, accepted by decision 56 and filed as #295 | `OBSERVED` | `runs/bridge.py` doesn't read `module_type` |
| How many `module_type` rows production would change | `NOT_COMPUTABLE` | offline; `db-load.yml`'s dry run prints it |
| Whether a production rack places the retired row | `NOT_COMPUTABLE` | offline |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-04
