# Intent

## Problem

The v1 crawl gave seven brands another maker's homepage, so the v2 crawl filed that maker's modules under the wrong name. In prod, 262 rows in each of `module_catalog` and `modules` are affected:
- Phase Engineering (69), British Noise Electronics (68) and Epicycloid Engineering (67) hold Noise Engineering's range.
- Mental Noise (48) holds Make Noise's.
- Endangered Audio Research (6) holds ARC's, d:Machinery (3) Infinite Machinery's, and Winter Plankton (1) Winter Modular's.

Separately, the TLM "ST MODULAR" row is not a module (owner review). The loader never deletes, so none of these could be removed.

## Proposed outcome

- `module_catalog.tombstoned_at` and `tombstone_reason` (migration `20261028_catalog_tombstones`). `modules` uses its existing `status = 'tombstoned'`.
- The loader reads `overlays/catalog-retirements-v*.json` and tombstones each named row, last in the plan, once. Retirements are covered by `plan_hash`, and the tombstone clock is excluded from it.
- Browse, brands, categories, stats, registry search and counts, and batch materialize skip tombstoned rows. A slug lookup still answers; materializing a tombstoned row is 409 `CATALOG_ROW_TOMBSTONED`.
- `scripts/build_reattribution.py` writes the manifest: 262 misattributed rows plus TLM, each with the real maker's page as evidence. 255 already have a twin under the real maker. The 7 that do not (five Noise Engineering Legio and Basimilus Iteritas modules, and Infinite Machinery PMBP and Stereo Mixer) are re-added under their maker in `catalog-additions-v5` and `module-power-depth-v13`, from the same pages.
- `build_maker_overlays.shared_homepage_skips` stops future overlay builds from filing a shared homepage under a brand whose name is not in the host.

Out of scope: fixing the crawler's homepage resolution itself; un-tombstoning; rack placements (none reference these rows in prod).

## Affected users / systems

- `module_catalog`, `modules`, catalog and registry read paths, the loader, overlay builders.

## Constraints / non-goals

Never delete. Fill-null and insert-if-absent only for the re-adds. No fetches. No ModularGrid. Dry run, then apply with the reviewed `plan_hash`.

## Open questions

None. Owner chose "retire all, re-add 7" on 2026-10-28.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| All 262 rows are crawl-sourced and link to the other maker's site | `OBSERVED` | read-only prod query; manifest test checks each evidence URL host |
| Fresh load tombstones 262 + 262 and adds the 7 | `OBSERVED` | `test_catalog_population` on Postgres 15, then a direct count |
| Read paths hide tombstoned rows | `OBSERVED` | `tests/test_catalog_tombstones.py` |
| Manifest and re-add overlays build byte-identically twice | `OBSERVED` | two runs, `cmp` |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-28
