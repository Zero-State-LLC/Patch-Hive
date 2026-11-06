# Catalog lead promotion (FR-034), 2026-11-05

Spec 003 FR-034 says a ModularGrid-derived row becomes canonical only through manufacturer or manual confirmation, recorded with its source URL. Until now nothing did that, so a real module stayed hidden from anonymous readers even when its maker's page confirmed it. This change adds that path and uses it on the rows a free read could confirm.

Every read was a plain GET through `data/synth-catalog/catalog_scrape.py`: robots.txt honoured, the paid cap at 0, and the paid-service keys unset. ModularGrid wasn't fetched. A site that refused stays refused. This is an engineering policy under [ADR 0002](../adr/0002-maker-permission-basis.md), not legal advice, and the [owner decisions](OWNER_DECISIONS_2026-11-04.md) send the wider question to counsel (decision 39).

## Result

| Leads hidden from anonymous reads | Rows |
|---|---:|
| Before | 564 |
| Confirmed by the maker's page, and promoted | 220 |
| **Still hidden** | **344** |

The full list is `data/synth-catalog/overlays/lead-promotions-v1.json`: each row's slug, maker page, content hash and a short quote.

| Promoted, by maker | Rows |
|---|---:|
| Doepfer | 47 |
| Bastl Instruments | 27 |
| Make Noise | 15 |
| Intellijel | 13 |
| Endorphin.es, Erica Synths | 11 each |
| Cwejman | 10 |
| Expert Sleepers | 9 |
| ADDAC System | 8 |
| Acid Rain Technology, After Later Audio, Mutable Instruments | 7 each |
| AniModule | 6 |
| 2hp, ACL, Alyseum | 5 each |
| Abyss Devices, ALM Busy Circuits, Alright Devices | 4 each |
| 4ms Company, Animal Factory Amplification | 3 each |
| 1010 Music, Allen Synthesis | 2 each |
| 1V/Oct, Afterlife Laboratories, Aircraft Designs, AJH Synth, Anti-Kulture | 1 each |

## What a row needs

- A page on the maker's own site, by the same checks as the [access-basis record](CATALOG_ACCESS_BASIS_2026-11-05.md), read by plain GET.
- The page has to name that module. A row was held when the page named another product, was a list of products, or was a holding page.
- The stored category has to survive the page. Where the maker's words name a different function, the category was corrected. Where they name none, the stored one stays only if they don't contradict it.
- Only facts are published. No description is copied. Module rows for these leads hold none.

## How the loader does it

`_schedule_lead_promotions` is the only path that changes a basis, and only from `unknown` on a lead row. It:

- refuses an entry with no https maker page, or one that points at ModularGrid, as a conflict;
- archives the old `access_basis` and `evidence_status` first, under batch `lead-promotions-v1`;
- sets `official_publication` and `MANUFACTURER_CONFIRMED`, and records the page as `manufacturer_url` without replacing a stored URL;
- leaves retired rows alone, and writes nothing on a second run.

## Other changes in this load

| Change | Rows | File |
|---|---:|---|
| Category corrected, in both tables | 37 | `provenance/category-corrections-v5.json` |
| Category filled | 12 | `overlays/module-catalog-category-v7.json` |
| Width misread as 104 HP, corrected in both tables | 15 | `provenance/hp-footer-corrections-v1.json` |
| Width filled from the maker's page (ESX-8CV, ESX-8GT) | 2 | `overlays/module-catalog-hp-v9.json` |

These corrections show why a lead's stored category can't be trusted without the page:

| Row | Stored | Corrected | Maker's words |
|---|---|---|---|
| Bastl Pizza | UTIL | VCO | "compact digital oscillator" |
| Doepfer A-106-6 | VCO | VCF | "XP Filter" |
| Doepfer A-112 | VCO | SAMP | "Sampler / Wavetable Module" |
| Make Noise Erbe-Verb | UTIL | FX | "reverb algorithms" |
| Make Noise FXDf | UTIL | VCF | "6 Band Fixed Filter" |
| Endorphin.es Milky Way 1U (silver) | UTIL | FX | "16 Algorithm Stereo FX Processor" |
| Alright Devices T-Wrex | SAMP | FX | "analog bitcrusher and decimator" |

### 15 rows stored 104 HP

After Later Audio's pages mention 104 HP elsewhere, and the crawl read that as each module's width. 9 of these rows are public on production, and a rack can't place a module that wide. Each page states the real width as "Width: Nhp".

| Row | Width | Row | Width | Row | Width |
|---|---:|---|---:|---|---:|
| Sum+Inv | 2 | Flip | 14 | Brooks | 4 |
| Enigma Expander | 4 | Threads 1U | 24 | Cloverleaf | 14 |
| bOSC | 6 | Typhoon | 16 | G&T | 10 |
| ENVy | 6 | uO_C | 8 | Quarks | 22 |
| uTides v2 | 8 | Scenes | 14 | Valley | 8 |

### A correction: Doepfer A-101-4

The [free-reads record](CATALOG_FREE_READS_2026-11-05.md) listed A-101-4's width as confirmed, and that was wrong. `doepfer.de/a1014.htm` is the page for the A-110-4 Thru Zero Quadrature VCO, and it never mentions A-101-4. This load removes that entry, so the row goes back to `legacy_unsourced`. 9 widths, not 8, wait on the owner's emails. The 8 ADDAC confirmations were rechecked, and each page does name its module.

## Still hidden: 344 rows

| Why | Rows |
|---|---:|
| No maker page on record (Dreadbox 35, Befaco 29, Erica Synths 25, ADDAC 19, Cwejman 19, Expert Sleepers 19, others 33, and 104 rows from 32 smaller makers) | 283 |
| Page read, but it doesn't confirm the row | 38 |
| robots.txt refused (Befaco 6, AMSynths 3) | 9 |
| robots.txt didn't answer (Instruo 5, Analogue Systems 5) | 10 |
| The fetch failed or was refused (Acid Rain Technology 2, Befaco 1, AJH Synth 1) | 4 |

Rows held after a read include Intellijel's legacy rows, where the page is a list and the text next to a name can belong to the next product. They also include a row named "μAtt" whose page was for Triplatt, 333modules and AI Synthesis, whose pages answered with a holding page, and Tiliqua, a firmware platform (decision 17).

ADDAC's site began answering with a holding page during this work. Its 8 promotions rest on full pages read earlier the same day, and the other 19 ADDAC rows wait.

## Staging

Loaded from branch `catalog/lead-promotion`, before merge, on the owner's yes after seeing this list.

| Step | Run | Result |
|---|---|---|
| Dry run | [42135080338](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42135080338) | 0 conflicts, no destructive SQL |
| Apply | [42135961226](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42135961226) | 220 promoted. Leads went from 564 to 344, and the archive from 5,424 to 6,077 rows |
| Second dry run | [42136505803](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42136505803) | Plans nothing |
| Smoke | [42136528548](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42136528548) | 10/10 |

Reading staging's public API afterwards: the catalog total went from 3,160 to 3,380, and none of those rows mentions ModularGrid. No row is `unknown`, and none stores a width over 84. A spot check of promoted rows shows the new basis, evidence status, category, width and maker URL. Rows checked as still hidden stay hidden: Befaco ADSR, μAtt and A-101-4.

`/api/modules` reports 3,375 rows, and a read through its pages saw only 3,184 of them, because the list has no fixed order. That is a separate bug, fixed in its own PR.

## Production

Loaded from `main` at `6826c36`, after [#308](https://github.com/Zero-State-LLC/Patch-Hive/pull/308) merged, on the owner's yes with these hashes. That yes also accepted that the same revision and seed can give different patches ([#295](https://github.com/Zero-State-LLC/Patch-Hive/issues/295)), and that these rows return to public reads while decision 39's wider question is with counsel.

- `plan_hash`: `319ed5ddbecafcf4ef6ab7654e24f9d14ad3034359218a9d00645e1376c801e2`
- `inputs_hash`: `0de24a57473e35893acef24d0a5ac00654e16853ec76c5bcea8d26daed5309fa`
- 0 conflicts, no destructive SQL.

| Step | Run | Result |
|---|---|---|
| Dry run, branch | [42136940478](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42136940478) | Wrote nothing |
| Dry run, `main` | [42139037435](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42139037435) | Same hashes |
| Apply | [42139434261](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42139434261) | 220 promoted. Leads went from 564 to 344, and the archive from 5,308 to 5,961 rows |
| Second dry run | [42139855482](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42139855482) | Plans nothing |
| Smoke | [42139878429](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42139878429) | 10/10 |

Reading production's public API afterwards: the catalog total went from 3,160 to 3,380, and none of those rows mentions ModularGrid. No public row is `unknown`, none stores a width over 84, and 285 have no category. Every public catalog row matches staging's. Rows checked as still hidden stay hidden: Befaco ADSR, μAtt, A-101-4 and A-170-2.

## Not in this change

- A search for maker pages for the 283 rows with none.
- A guard against a width over the band at the crawl. The corrections fix these rows, but the crawl code that read them hasn't changed.

T031 and T039 stay open.
