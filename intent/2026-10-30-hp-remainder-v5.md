# Intent

## Problem

61 module_catalog HP values were still `legacy_unsourced` after #172 (v1 values with no maker citation). The owner asked for all of them to be handled.

## Proposed outcome

Every one of the 61 was checked against maker sources reachable with plain GETs (robots.txt honoured, 2 s spacing, a host dropped at its first block; maker manuals on the maker's domain and the maker's GitHub count). `module-catalog-hp-v5.json` re-sources the 4 that a maker source states (each quoted); `maker-corrections-v6.json` corrects Dixie II 8 to 6. The other 57 stay marked with the reason recorded in tasks.md T039. Out of scope: any route around a block, retailer data, paid fetches.

## Affected users / systems

Catalog loader overlays and provenance manifests; module_catalog and modules HP for 4 rows; rack placement for Dixie II.

## Constraints / non-goals

No retailer or third-party database values, no ModularGrid, no route around bot challenges or CAPTCHAs, no mm-to-HP conversion.

## Open questions

The 57 left need either a maker answer (ADDAC, Befaco, Instruō, Dreadbox, Cwejman, Intellijel, Make Noise could be asked for spec sheets) or an owner decision to keep them marked.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Dixie II manual (rev 2018.09.13) states "Width 6 hp" | `OBSERVED` | intellijel.com/downloads/manuals/dixie-2_manual_2018.09.13.pdf |
| Metropolis manual v1.30 states 34 hp; Mutamix manual 18 hp | `OBSERVED` | intellijel.com manuals |
| endorphin.es COCKPIT MK1 page (BLACK / GOLDEN) states "Dimensions: 6 HP" | `OBSERVED` | endorphin.es/discontinued/p/cockpit |
| On a database shaped like prod the plan corrects Dixie II in both tables, clears 4 markers, 0 conflicts; a rerun plans nothing | `OBSERVED` | local Postgres 15 simulation |

## Author / date

- Author: Claude (for Daniel Meyer)
- Date: 2026-10-30
