# Intent

## Problem

57 catalog HP values still carry `hp_source = legacy_unsourced` (spec 003 T039). Their makers' sites block plain requests (ADDAC System, Befaco, Instruō, Dreadbox), are gone (cwejman.net now redirects to an unrelated site), or have no page that states the width. No maker route is left that we may use.

## Proposed outcome

One-off manual retailer lookups for those 57 rows (spec 003 D2, FR-006), recorded in `data/synth-catalog/overlays/module-catalog-hp-retailer-v1.json` with URL, verbatim quote, fetch time and page hash. Owner decision 2026-11-01 (new FR-039): where the retailer states the stored HP, the loader moves the marker to `hp_source = retailer_observed`; where it disagrees, the row stays `legacy_unsourced` for the owner. HP is never filled or changed from a retailer page.

Out of scope: correcting the 6 disagreeing values (each needs a maker source or an owner decision), the 11 rows no allowed retailer lists, and any automated retailer crawler (still forbidden by D2).

## Affected users / systems

Catalog loader (`population.py` marker step), `module_catalog.hp_source` on staging and prod, the catalog API field `hp_source`.

## Constraints / non-goals

Plain GETs only, robots.txt read first, 2 s spacing (10 s where robots asks). Hosts that answered 403 (Perfect Circuit, Signal Sounds, Juno) were not used and not worked around. No maker site, community catalog (ModularGrid) or archive fetched. `retailer_observed` is not maker confirmation (FR-027).

## Open questions

- The 6 disagreements (ADDAC200PI 2/4, ADDAC200S black 2/4, ADDAC501B 8/4, Befaco Mixer 5/4, Cwejman D-LFO 12/14, Instruō dàil 4/6) need a maker source or an owner correction. dàil's 6 HP page includes a 2 HP expander.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| 46 of 57 rows have a retailer page stating HP; 40 agree with the stored value | `OBSERVED` | saved pages; every quote matched verbatim against its page |
| A replica loaded with main's code moves 40 markers and plans nothing on rerun, 0 conflicts | `OBSERVED` | local Postgres 15 simulation |
| Staging and prod hold 57 marked rows, so they will end with 17 `legacy_unsourced` | `INFERRED` | replica has 58 (fresh load leaves A-155 at v1's 4) |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-01
