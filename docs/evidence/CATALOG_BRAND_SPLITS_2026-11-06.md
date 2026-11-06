# Brand splits in the public catalog, 2026-11-06

The [second-name review](CATALOG_SECOND_NAMES_2026-11-05.md) found two makers listed under two brands. A scan of all 338 public brands by letters and by maker site found only these two.

| Maker | Before | After |
|---|---|---|
| Mutable Instruments | "Mutable Instruments" 13 rows, "Mutable instruments" 19 | "Mutable Instruments" 30 |
| Joranalogue Audio Design | "Joranalogue" 2 rows, "Joranalogue Audio Design" 27 | "Joranalogue Audio Design" 27 |

The change also retires 5 rows, which takes the public catalog from 3,388 to 3,383 rows. Nothing is deleted.

## Mutable Instruments: one spelling

Both spellings share one slug for each module, so no row changes its address. The 19 rows stored as "Mutable instruments" move to "Mutable Instruments" in both tables, along with any hidden or retired row stored that way.

Committed files aren't rewritten. They stay as reviewed, and the loader reads them under the one spelling (`BRAND_RENAMES` in `population.py`).

The move has three safeguards:

- **It runs first in the plan,** so everything after it matches rows the way the files now read.
- **The old value is archived first,** under batch `brand-renames-v1`.
- **A module's archived values follow it.** They're keyed by brand, so without this a manifest that module already passed through would run on it again and could clear a value twice. A test on Postgres covers this.

If a module already exists under the new spelling, the plan reports a conflict and doesn't move it.

## Joranalogue: the 2 rows that stay under one brand

"Joranalogue Audio Design" is the maker's name and holds the other 25 modules, so its rows stay. The 2 "Joranalogue" rows repeat the same pages, and they retire.

Those 2 rows were added by hand on 2026-10-17, so they differ slightly from the rows that stay. Generate 3 had the category and the row that stays didn't, so it takes VCO from the maker's "voltage controlled oscillator (VCO)".

## What retires

| Retires | Stays | Why |
|---|---|---|
| Joranalogue Filter 8 | Joranalogue Audio Design Filter 8 | Same page |
| Joranalogue Generate 3 | Joranalogue Audio Design Generate 3 | Same page |
| Mutable Instruments Ripples | Ripples_Original | Same page |
| Mutable Instruments Tides (2014 version) | Tides_Original | Same page |
| Endorphin.es Milky Way 1U (silver) | MILKY WAY 1U | Its own page sells one module in silver and black |

## A correction: Milky Way 1U

The second-name review said this row was a separate format with a wrong width, and proposed correcting its 6 HP to 22. That was wrong, and so was my report to the owner. A public MILKY WAY 1U row already holds 22 HP on `endorphin.es/modules/p/milky-way-1u`, which states "22 HP". The first review missed it because the silver row pointed at the 3U page. So the row retires, and no width changes.

A scan of the other public rows named after a finish found none in the same position. Dnipro Metamorph (black panel), System80 860 MK2 (grey) and Vaski Lights Stereo Visualizer each have their own product pages, so they stay.

## What a Rig sees

A placed module stays placed, and every read of that Rig warns that it's retired, with the reason. Patches generated for a Rig holding a retired row can change.

Renaming a brand doesn't touch `rack_modules`, which refers to a module by id. Stored revisions keep the brand they were saved with.

The dry-run receipt counts Rigs holding a retired module (`retired_on_racks`).

## Not changed here

- The names `Ripples_Original`, `Tides_Original` and similar come from the maker's documentation addresses. They read oddly, and they stay.
- `maker-sources.json` still lists "Mutable instruments". A future crawl under that spelling is read under the one spelling at load.
- `backend/integrations/synth_catalog_importer.py` reads the seed by its own path, not through this loader. Its seed lists both spellings as brand names, but has no module row under the old one.

## Staging

Loaded from branch `catalog/brand-splits`, before merge, on the owner's yes after seeing this list.

- `plan_hash`: `701516504aa7b6d82b8d865f227f93b6bd74372c80aabc112b01813e66ec8b7a`
- `inputs_hash`: `134df64ffd51c83bea0628cc73fe27ca63133c0c1a7b36860c16551b27cbc882`

| Step | Run | Result |
|---|---|---|
| Dry run | [42190351455](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42190351455) | 0 conflicts, no destructive SQL, 0 Rigs |
| Apply | [42191721314](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42191721314) | 19 rows moved in each table, 5 retired in each |
| Second dry run | [42191990957](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42191990957) | Plans nothing |
| Smoke | [42192149946](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42192149946) | 10/10 |

Reading staging's public API afterwards and comparing every row with the read before the load:

- The catalog went from 3,388 to 3,383 rows, and `/api/modules` from 3,384 to 3,379. None of those rows mentions ModularGrid.
- Public brands went from 338 to 336. The brand list shows Mutable Instruments with 30 and Joranalogue Audio Design with 27. Filtering by the old spelling returns nothing.
- Only the expected rows changed: the 5 retired rows are gone, 19 rows changed brand and nothing else, and Generate 3 gained VCO. No module's width, power, depth or id changed.
- Rows with no category went from 281 to 280.
- MILKY WAY 1U reads 22 HP.

The production dry run ([42190602658](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42190602658)) gave the same hashes and counted 0 Rigs.
