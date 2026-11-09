# Doepfer A-138m and Analogue Systems types, 2026-11-08

Labelling photos for spec 009's evaluation set turned up two faults in the public catalog. Both are fixed through reviewed correction manifests (spec 003 D4, FR-038), checked against the makers' own pages. No value comes from ModularGrid. **Nothing has been loaded to staging or production.**

OBSERVED means read from a maker's page, this checkout or a deployed public API on 2026-11-08. INFERRED means reasoned from those.

| Fault | Rows | Change | File |
|---|---:|---|---|
| A-138m's width in `modules` | 1 | 8 HP to 20 HP | `provenance/maker-corrections-v8.json` |
| Analogue Systems Module Category, in `module_catalog` and `modules` | 6 | See [below](#the-six-corrected-rows) | `provenance/category-corrections-v8.json` |

## Doepfer A-138m

Doepfer's page states a 4×4 matrix mixer, with `Breite/Width: 20 TE/HP, 101.3 mm` ([A138m.htm](https://doepfer.de/A138m.htm)).

OBSERVED on both deployed databases, by public API:

| Table | Row | HP |
|---|---|---:|
| `module_catalog` | `doepfer-a-138m` | 20 |
| `modules` | id 320, created 2026-10-17 | 8 |

`maker-corrections-v4` corrected `module_catalog` on 2026-10-30, and recorded that `modules` held no row for this module. The deployed databases did hold one, so the row Rigs are validated against kept the wrong width. This change corrects that row only.

### Not merged

The old A-138 is a four-channel mixer sold as A-138a and A-138b, on [its own page](https://doepfer.de/A138.htm). The A-138m is a different module. The catalog holds one A-138 row, the A-138m, so nothing merges and no row is added or retired. A test keeps it that way.

## Analogue Systems

Each of the 44 public rows was read against its own page on `analoguesystems.co.uk`, and against the maker's [archived module list](https://www.analoguesystems.co.uk/previous_site/modules.htm) where that lists the module.

A row is corrected only when all three of these hold:

1. The maker's page says what the module is.
2. The stored category isn't that.
3. What it is maps to one category under the catalog's existing rules.

All 44 stored widths match the pages.

### The six corrected rows

| Row | Stored | Now | The maker's page | Rule |
|---|---|---|---|---|
| [RS-20](https://www.analoguesystems.co.uk/index.php/as-modules/rs20) | LFO | FX | A ring modulator and a four-way multiple | `ring modulator` is FX |
| [RS-610N](https://www.analoguesystems.co.uk/index.php/as-modules/rs-610n) | LFO | FX | Two ring modulators | `ring modulator` is FX |
| [RS-85](https://www.analoguesystems.co.uk/index.php/as-modules/rs85) | VCO | LFO | "VC-LFO" | LFO |
| [RS-380](https://www.analoguesystems.co.uk/index.php/as-modules/rs380) | SAMP | LFO | "Modulator": LFO first, then sample and hold, noise and VCA | LFO; `s&h` is LFO |
| [RS-380N](https://www.analoguesystems.co.uk/index.php/as-modules/rs380n) | SAMP | LFO | The same module on a dual-bus panel | LFO; `s&h` is LFO |
| [RS-70](https://www.analoguesystems.co.uk/index.php/as-modules/rs70) | ENV | UTIL | An inverter and a pre-amp, with a slew limiter built into the inverter | `inverter` and `preamp` are UTIL |

The rules are `TAG_CATEGORY` in `scripts/build_category_overlay.py`.

OBSERVED: running `category()` from `scripts/build_maker_overlays.py` on each row's committed tags gives the stored value. It takes the first keyword that matches: `modulat` caught "ring modulator", `sampl` caught "sample and hold", `oscillat` caught RS-85's `oscillator` tag, and `slew` caught RS-70.

The maker lists RS-20's multiple second, and a multiple only splits a signal, so the ring modulator decides it. LFO matches neither half.

### Left for the owner

The page says what these are, but not which one category that is. A correction here would be my reading rather than the maker's, so none is included.

| Row | Stored | The maker's page | Why it isn't settled | Suggestion |
|---|---|---|---|---|
| RS-35, RS-35N | SEQ | Derives control voltages from audio: pitch, level and triggers | Not a sequencer. `converter` is UTIL, but the catalog files envelope followers under ENV (5 of 6) | UTIL |
| RS-420 | ENV | Octave controller for up to three VCOs, with slew and a CV buffer | The rule sends `controller` to SEQ, yet the page describes a CV stage, not a hand controller | UTIL |
| RS-250 | none | Trunk lines to the rear panel | No rule. UTIL, or SYSTEM as rack infrastructure (decision 14) | UTIL |
| RS-260 | none | Voltage quantiser | No rule, and the catalog's two named quantisers split SEQ and UTIL | UTIL |

### Stored value matches part of the page

These stay as they are.

| Row | Stored | The maker's page |
|---|---|---|
| RS-510e, RS-510N | VCA | What the maker calls two modules in one: a trapezoid envelope generator and a VCA |
| RS-600 | LFO | Performance wheels with a built-in LFO |
| RS-295 | FX | Expander for the RS-290 delay and sampler, adding MIDI |

### The other 29 rows agree with their pages

| Category | Rows |
|---|---|
| VCF | RS-100N Low Pass, RS-100S, RS-110, RS-110N, RS-120, RS-215, RS-360, RS-500e, RS-500N |
| FX | RS-240, RS-310, RS-390 Echo, RS-430, RS-440, RS-650, RS-650 Echo Reverb |
| MIX | RS-160, RS-165 |
| VCA | RS-180, RS-180N |
| UTIL | RS-220, RS-270 |
| SEQ | RS-280, RS-340 |
| ENV | RS-350, RS-60N Envelope |
| VCO | RS-95e, RS-95N |
| SAMP | RS-290 |

Three pages carry an editing slip that doesn't change the outcome. RS-360's description repeats the RS-370's, while its title and the archived list say filter bank. RS-160's title says audio mixer while its text says CV mixer. RS-420's title says external processor while the site's menu says octave controller.

## How the pages were read

Every page went through `CatalogScraper`: robots.txt, the deny list, the per-host delay and the cache, with the paid cap at 0 (owner decisions 1 and 18). `receipts/free-reads-2026-11-08.json` lists each URL's outcome and SHA-256, with no page text.

`www.analoguesystems.co.uk` serves `robots.txt` as `application/octet-stream`, which the shared transport reports as no answer, so the scraper first refused the whole site. This isn't a refusal by the maker: the file answers 200, and its rules allow every path read here. For this one file, the MIME filter was widened through `CatalogScraper`'s `transport` argument so the scraper could parse it. Pages kept the filter, and no committed code changed.

| Page | SHA-256 |
|---|---|
| `doepfer.de/A138m.htm` | `9d1fd0f51cbeb68575254f406e7aa425b1700b184b7c95a1bd37de0fcd73b0e3` |
| `doepfer.de/A138.htm` | `4396a5deb97d0a7bd10fd044cc5e4c7ad8e861fd6622c1b99401a2f369575c19` |
| `previous_site/modules.htm` | `75602da161167afb892c44eef8b91fcdc7e5c1b47f108ee2304ddeeb6cd7b16d` |
| `as-modules/rs20` | `d4add492c90a98d11aa30a9d753a4ec5046a0d903d2b5fc7ed66b3bbd0aee328` |
| `as-modules/rs-610n` | `3850acd3be90e17baeca5d8a2fff66ab2e7cbd20e2374ef6326a7a7d2fd76e8e` |
| `as-modules/rs85` | `d4dc0d13ce78910d85ec6497c4c494bde20c971c4bdb1fc90e879de5a2b795df` |
| `as-modules/rs380` | `d4d0fae78093eb53c2728c9e95e2eaf1bfa58f65696003447ce491ab1de1b74c` |
| `as-modules/rs380n` | `59656a0196c2cbbec244482105fac42e12f9107fba5d14636affde2d040f456c` |
| `as-modules/rs70` | `9d98c06349be1a75e869d3ff24558ce1b3c17f03f415a6a2a1422e2fe92bd526` |

## What a Rig sees

- **Width.** Validation reads `modules.hp`, so a Rig that placed an A-138m at 8 HP may report an overlap or an out-of-row error until the placement is fixed. The loader counts Rigs only for retirements, so how many hold this module is NOT_COMPUTABLE here.
- **Category.** The revision hash omits `module_type`, as decision 56 records, so a Rig holding one of the six rows can get different patches from the same revision and seed. Old runs don't change.

## Local check

On a throwaway Postgres, loaded with everything except these two manifests and with a `modules` row seeded at 8 HP:

| Step | Result |
|---|---|
| Dry run | 13 values to archive and correct (1 width, 12 category), 0 conflicts |
| Apply | All 13 written, each old value archived |
| Second dry run | Plans nothing |
| Load from empty | The same six categories, and the A-138m catalog row at 20 HP |

## Dry run

Run through `db-load.yml` from branch `claude/catalog-a138m-analogue-systems`. **None of these runs wrote anything.** The loads came after, under [Loads](#loads).

| Environment | Run | Commit | Result |
|---|---|---|---|
| Staging | [42537413747](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42537413747) | `2dbeb7f` | 13 values to archive and correct (7 in `modules`, 6 in `module_catalog`), 0 conflicts, no destructive SQL, table counts unchanged |
| Production | [42537569004](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42537569004) | `2dbeb7f` | Refused before planning: the database was at `20261106_commerce_append_only`, one migration behind this code's `20261107_photo_readings` |
| Production, after its migration | [42540690340](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42540690340) | `cd0df87` | The same as staging, with the same hashes |

The owner chose the production dry run on 2026-11-08. Staging and production gave the same two hashes, for the owner's yes on each load:

- `plan_hash`: `479df9425d7cc67ef3db87ac80f06c9f8a224a7134a45848f34f148a916c84f1`
- `inputs_hash`: `8c69037d063cf57a61e97d1d07842475d9c505970b749d640ac157b0c1a7cb23`

The plan hash covers every statement and its parameters, so both databases would receive the same writes. The local check gave the same two hashes. An apply refuses if the plan or the committed inputs have changed since, and this record isn't an input.

`cd0df87` only adds this record to `2dbeb7f`. The commits on `main` after this branch was cut (`a9594f2`, `5cecd49`) touch no catalog input, loader code or migration.

The one difference between the databases is outside this plan: `catalog_value_archive` holds 6,209 rows on production and 6,325 on staging.

## Loads

The owner approved both hashes on 2026-11-08. #379 merged as `50467ef`, and both loads ran from that commit in `apply` mode, staging first, with `plan_hash` `479df9425d7cc67ef3db87ac80f06c9f8a224a7134a45848f34f148a916c84f1` and `inputs_hash` `8c69037d063cf57a61e97d1d07842475d9c505970b749d640ac157b0c1a7cb23`.

| Database | Run | Result | `catalog_value_archive` |
|---|---|---|---|
| Staging | [42542529212](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42542529212) | 13 corrections, 0 conflicts, no destructive SQL | 6,325 to 6,351 |
| Production | [42542863263](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42542863263) | 13 corrections, 0 conflicts, no destructive SQL | 6,209 to 6,235 |

Each load corrected 7 `modules` rows and 6 `module_catalog` rows. The archive grew by 26 on each host: the 13 old values, and one marker for each of the 13 rows processed. The receipt's `catalog_value_archive_markers: 2` counts the insert statements, one per manifest.

These are the first loads with a lasting record on either host: `catalog_load_runs` went from 0 to 1 and `catalog_load_changes` from 0 to 39. No other table's row count changed.

Reading each host's public API afterwards, A-138m is 20 HP, RS-20 and RS-610N are FX, RS-85, RS-380 and RS-380N are LFO, and RS-70 is UTIL. `/api/modules` still has 3,379 rows on both. Production's public catalog still has 3,383 rows, and none of them mentions ModularGrid.

## Not changed here

- 12 other rows hold different widths in `modules` and `module_catalog`, the same shape of fault as A-138m:
  1V/Oct The Centre, Abyss Devices aMix, After Later Audio G&T, Allen Synthesis Kompari, Cwejman ADSR-VC2 and MMF-1, Doepfer A-106-1 and A-137-2, Erica Synths Fusion Ring modulator, Fusion VCA and Sequential Switch, and Expert Sleepers ES-6. Each needs its own maker check to say which table is right.
- 8 other ring modulators, from 6 makers, are filed as LFO. The keyword above is the likely cause, but those rows weren't traced.
- A-138m's depth and current are on Doepfer's page, but `modules` holds neither. This change only corrects the width.
- RS-650 and RS-650 Echo Reverb point at one page, so one may need retiring.
- The robots.txt reading above may affect other makers, which would show as `robots_unavailable`. That hasn't been measured.
