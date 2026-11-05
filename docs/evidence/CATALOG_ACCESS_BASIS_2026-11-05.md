# Catalog access basis and ModularGrid URLs, 2026-11-05

This records the data step for [owner decisions](OWNER_DECISIONS_2026-11-04.md) 52 and 53. The load does it: `_schedule_access_basis` in `data/synth-catalog/population.py`, with the checked rows in `data/synth-catalog/overlays/access-basis-v1.json`.

## What the load changes

| Rows | Before | After | How they're picked |
|---|---|---|---|
| Maker rows that pass the checks | no basis | `official_publication` | Listed in the overlay, row by row |
| `CatalogCandidate` | no basis | `unknown`, `CATALOG_OBSERVED` | By source, so the repo doesn't name ModularGrid-derived rows |
| `SynthCatalogResearch` | no basis | `unknown`, `CATALOG_OBSERVED` | By source |
| `module_catalog.modulargrid_url` | 179 URLs | none | Any row holding one |
| `modules.source_reference` | 523 URLs | none | Any row holding a ModularGrid URL |

The load only fills an empty basis, and it leaves retired rows alone. Each cleared URL goes to `catalog_value_archive` first, under batch `modulargrid-clear-v1`, and no API serves that table.

## A correction: alpha.10 still served ModularGrid URLs

[#294](https://github.com/Zero-State-LLC/Patch-Hive/pull/294) removed `modulargrid_url` and `modulargrid_id` from the API, and the agent's report to the owner after the alpha.10 deploy said the URLs were no longer served. That was incomplete. `/api/modules` kept returning the same URLs in `source_reference`.

- Staging served 186 of them to anonymous readers. Of those, 179 were `CatalogCandidate` rows and 7 were Instruo rows.
- Across all rows, including those anonymous reads leave out, 523 held one on staging and on production.

Decision 52 named the first two fields only. This step treats `source_reference` the same way, because it holds the same URL. `ModuleResponse` also drops such a value, so a restore or an import can't bring it back into a response.

## How each maker row was checked

Decision 53 expected 721 maker rows. Both databases now hold 724: 703 `ManufacturerCrawl` and 21 `ManufacturerVerified`, the same slugs on each.

[ADR 0002](../adr/0002-maker-permission-basis.md) sets the conditions: a maker-owned site, robots.txt honoured, and no opt-out. `scripts/build_access_basis_overlay.py` applies them to each row's `manufacturer_url`.

A row must pass at least one of these to count as the maker's own site:

| Check | Rows passing | Meaning |
|---|---|---|
| `brand_in_host` | 661 | The brand's name is in the site's name. The 140 rows that rest on this alone were read by brand and host, 47 pairs in all |
| `official_rows` | 546 | Rows already `official_publication` for this brand use the same site |
| `maker_sources` | 75 | `maker-sources.json` lists the site for this brand |
| `reviewed` | 7 | Read by hand: 6 on Mutable Instruments' documentation site, 1 on BÈSIA Modular's store |

The row's page must also be allowed by robots.txt, read once per site with the crawler's own user agent, under the crawler's rule: only a 200 or a 404 counts as an answer.

**694 rows passed. 30 rows failed and stay with no basis:**

| Rows | Maker | Site | Why |
|---|---|---|---|
| 8 | AMSynths | amsynths.co.uk | robots.txt answered 403 |
| 6 | Pulp Logic | pulplogic.com | robots.txt answered 403 |
| 2 | SSSR Labs | sssrlabs.com | robots.txt answered 403 |
| 1 | Befaco | befaco.org | robots.txt answered 403 |
| 4 | Fruku | fruku.club | robots.txt didn't answer |
| 2 | FlatSix Modular | flatsixmodular.com | robots.txt didn't answer |
| 1 | Encore Electronics | encoreelectronics.com | robots.txt didn't answer |
| 1 | Frap Tools | frap.tools | robots.txt didn't answer |
| 1 | Raw Analogue Sound | rawanaloguesound.com | robots.txt didn't answer |
| 1 | Tin Man Synths | tinmansynths.cn | robots.txt didn't answer |
| 1 | Noise Engineering | manualslib.com | Not the maker's site: a manuals archive |
| 1 | Synthetic Sound Labs | steamsynth.com | Not confirmed as the maker's site |
| 1 | Unknown Devices | unwn.dev | Not confirmed as the maker's site |

These rows stay visible, as they are today. Rebuilding the overlay picks up any site that answers later, and a read from the maker's own page can replace the Noise Engineering row. Sites that didn't answer can vary between runs, so this list is what the 2026-11-05 run saw.

## What readers see

Anonymous reads leave out `unknown` rows and their `modules` rows ([FR-033](../../specs/003-catalog-dataset-pipeline/spec.md)), so these 188 rows leave the public catalog. Signed-in readers still see them, marked "Unverified lead". All 9 `SynthCatalogResearch` rows are Instruo, which leaves 2 Instruo rows public until maker pages confirm the rest (FR-034).

A placed module stays in its rack, because a rack reads its modules directly.

## Staging

Loaded from branch `catalog/access-basis-backfill`, before merge, on data that already held the taxonomy load.

| Step | Run | Result |
|---|---|---|
| Dry run | [42014932903](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42014932903) | 0 conflicts, no destructive SQL |
| Apply | [42015174470](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42015174470) | 694 + 188 tagged, 179 + 523 cleared, 702 values archived |
| Second dry run | [42016039691](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42016039691) | Plans nothing |
| Design walkthrough | [42016568620](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42016568620) | Passed, run from the #298 branch |
| Smoke | [42016577708](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42016577708) | Passed |

Reading staging's public API afterwards: the catalog total went from 3,359 to 3,171, and none of the 3,171 module rows mentions ModularGrid. Rows with no basis fell from 961 to 79: the 30 above and 49 retired rows.

## Production

Loaded from `main` at `5efa122`, after [#297](https://github.com/Zero-State-LLC/Patch-Hive/pull/297), [#298](https://github.com/Zero-State-LLC/Patch-Hive/pull/298) and [#299](https://github.com/Zero-State-LLC/Patch-Hive/pull/299) merged. The dry runs from the branch and from `main` gave the same hashes, and the apply used them:

- `plan_hash`: `265bb085a3cf0fcc3cdc3094680bc809420804b134cded0fc366559007983fb2`
- `inputs_hash`: `373ed6ead83d4b2d66ef7841858fc063bc900ab1ce3975a196d031f1c0a5544f`
- 0 conflicts, no destructive SQL.

| Step | Run | Result |
|---|---|---|
| Dry run, branch | [42016573161](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42016573161) | First production database read through the named secrets from [#273](https://github.com/Zero-State-LLC/Patch-Hive/pull/273); wrote nothing |
| Dry run, `main` | [42100987495](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42100987495) | Same hashes |
| Apply | [42101357989](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42101357989) | Counts below |
| Second dry run | [42102464437](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42102464437) | Plans nothing |
| Smoke | [42102457775](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42102457775) | Passed |

This load also carried the taxonomy that staging already had:

| Update | Rows |
|---|---|
| `category_overlay` | 134 |
| `module_catalog_correct` | 31 |
| `modules_correct` | 27 |
| `catalog_retire` | 1 |
| `module_retire` | 1 |
| `module_type_from_category` | 336 |
| `access_basis_official` | 694 |
| `access_basis_lead` | 188 |
| `modulargrid_url_clear` | 179 |
| `modules_source_reference_clear` | 523 |

`catalog_value_archive` grew from 3,820 to 4,978 rows, 1,158 against 1,099 planned statements (1,096 values and 3 markers). The plan counts statements, and one statement can archive several fields of a row. Staging's taxonomy load shows the same gap of 59: 523 rows against 464 statements.

Reading production's public API afterwards: the catalog total went from 3,360 to 3,171, and none of the 3,171 rows on `/api/modules/catalog` or `/api/modules` mentions ModularGrid. Rows with no basis fell from 961 to 79. The public rows match staging's: catalog rows on every field, module rows on everything but `imported_at`. Rows anonymous reads leave out weren't compared.

The two databases didn't start the same. Before these loads their archives held 3,869 and 3,820 rows, and `module_type_from_category` updated 403 rows on staging and 336 here. The cause wasn't traced.

## Retry of the 30 left-out rows

Run the same day, after the free reads. Robots.txt was read again for each site, and the 3 unconfirmed sites were read by plain GET, with nothing paid. 5 rows now pass, which takes the overlay to 699 rows and leaves 25 out.

| Row | Why it now passes |
|---|---|
| FlatSix Modular Shroud of Turing, Slight of Hand | robots.txt answered and allows the pages |
| Synthetic Sound Labs V-Gates Euro | steamsynth.com is titled "Analog Synthesizers \| Synthetic Sound Labs" |
| Unknown Devices Eisei | unwn.dev is titled "unknown devices – modular instruments" |
| Noise Engineering Basimilus Iteritas Alter | The maker has its own page, so `provenance/catalog-url-corrections-v1.json` replaces the third-party manual link. The old URL is archived first |

| Still left out | Rows | Why |
|---|---:|---|
| AMSynths 8, Pulp Logic 6, SSSR Labs 2, Befaco 1 | 17 | robots.txt answers 403, a refusal under decision 3 |
| Fruku 4, Encore Electronics 1, Frap Tools 1, Raw Analogue Sound 1, Tin Man Synths 1 | 8 | The connection timed out from this machine, and curl timed out the same way. A read from another network might get an answer |

These 25 stay public with no basis. They aren't leads, so tagging them `unknown` would hide real maker rows.

A correction now accepts `module_catalog.manufacturer_url`. It must cite an https page, and it never clears a `needs_reverify` flag, because a flag is about HP or power.
