# Intent

## Problem

The crawl-time guard (#119, spec 003 T030) found ten more brands on another maker's host, still live in prod after #116:
- **busycircuits.com:** Barcode, FKMG, Swizzle and Warped Circuits hold ALM Busy Circuits' range.
- **instruomodular.com:** Instruō duplicates Instruo.
- **jasmineandolivetrees.com:** In The Trees duplicates Jasmine & Olive Trees.
- **modularsynthlab.com:** a retailer gave Mad Rooster Lab, Olitronik_lab and Vintage Synth Lab a Meng Qi module.

## Proposed outcome

- `overlays/catalog-retirements-v2.json`: 185 rows tombstoned in each of `module_catalog` and `modules`, through the loader path #116 added.
  - 178 have a twin under the real maker.
  - 5 sit on the retailer host, which no maker owns, so nothing is re-added.
  - 2 are a v1-crawl "QUAID GIGASLOPE" stored at 52 HP: outside FR-007, and there is no current page for it.
- `build_reattribution.py` builds the next version and leaves out rows earlier manifests retire. It refuses to rewrite an existing manifest, so v1 stays as applied.
- `build_maker_overlays.misattributed_brands`: the crawler's owner rule (named in the host, else the one adapter- or curated-resolved brand). Name matching now reads "&" as "and" and drops accents.

## Affected users / systems

- `module_catalog`, `modules` (staging, prod), the reattribution and overlay builders.

## Constraints / non-goals

Never delete. No re-adds from retailer pages. No fetches. Dry run, then apply with the reviewed `plan_hash`.

## Open questions

None. Owner said "Retire them" on 2026-10-28.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The ten brands are live in prod | `OBSERVED` | read-only prod query |
| Every v2 row cites the owner's (or the retailer's) page and renders as safe SQL | `OBSERVED` | `tests/test_catalog_tombstones.py` |
| A fresh load tombstones 447 rows per table (v1 + v2) | `OBSERVED` | Postgres 15 population test, then a count |
| v2 builds byte-identically twice; v1 is unchanged | `OBSERVED` | two runs, `cmp` |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-28
