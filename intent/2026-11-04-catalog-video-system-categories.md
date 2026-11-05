# Intent

## Problem

The spec 003 T031 offline pass left catalog rows waiting on owner calls: 24 video rows, 11 power rows, 4 rows tagged both noise and random, rectifiers, crossfaders, and Mutable-derived rows. A duplicate Jolin row was also waiting, and the catalog's own Mutable Instruments rows looked wrong. The owner decided these on 2026-11-04 (decisions 5, 6, 7, 14 and 17, recorded in #278).

## Proposed outcome

One PR that applies those calls from committed data:

- VIDEO and SYSTEM wherever the Module Category vocabulary is enforced, with a test that the patch engine ignores both.
- A generated overlay for the rule-based rows and a hand-reviewed overlay for the Mutable table, fill-null.
- `correct` entries for the 3 video rows v1 filed elsewhere, and for the Mutable rows committed data backs.
- A retirement of `jolin-getrekt-touch-waveshaper`.
- A dated evidence doc with observed counts, and a dry run against a throwaway database.

Evidence: [CATALOG_TAXONOMY_DECISIONS_2026-11-04.md](../docs/evidence/CATALOG_TAXONOMY_DECISIONS_2026-11-04.md).

Out of scope: any fetch, any load to a deployed database, a NOISE category, firmware platforms, decision 15's builder warning, and ticking T031.

## Affected users / systems

Catalog inputs and the loader. `inputs_hash` changes, and the next db-load dry run plans 62 category fills, 8 corrected values and 2 retirement updates. A rack holding a corrected row sees its new category. No schema change.

## Constraints / non-goals

No maker page, feed or listing is fetched. A category outside the vocabulary is a conflict. Anything committed data doesn't back is listed for the free-reads PR, not corrected, and that includes Yarns. Retirements tombstone, never delete.

## Open questions

- Should the 35 other video rows that hold another category move to VIDEO? Owner.
- Should a category fill reach `modules.module_type` on a loaded database? Owner, later.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The dry run over main's data plans 62 fills, 5 + 3 corrections, 1 + 1 retirements, 0 conflicts | `OBSERVED` | `receipts/taxonomy-2026-11-04.dry-run.json` |
| A load from empty and a load over main's data agree on every category and tombstone | `OBSERVED` | throwaway Postgres, same receipt |
| No patch engine keyword matches VIDEO or SYSTEM | `OBSERVED` | `tests/unit/test_patch_engine.py` |
| What 7 of the 12 Mutable-derived modules do | `INFERRED` | reviewer's knowledge; no committed maker wording |
| Whether a production rack places the retired row | `NOT_COMPUTABLE` | offline |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-04
