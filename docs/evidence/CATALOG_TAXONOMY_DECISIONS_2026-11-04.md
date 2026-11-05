# Catalog taxonomy decisions applied (2026-11-04)

This applies the owner's catalog calls from committed data: decisions 5, 6, 7, 14, 17, 49, 50, 51, 54, 55 and 56 in `docs/evidence/OWNER_DECISIONS_2026-11-04.md` ([#278](https://github.com/Zero-State-LLC/Patch-Hive/pull/278), open when this was written). No maker page, feed or listing was fetched, nothing was paid for, and nothing was loaded to a deployed database.

OBSERVED means read in this checkout or measured on a throwaway load. INFERRED means reasoned from it. Counts are for a load from the committed inputs over main's data, unless a row says otherwise. Production also holds 137 database-only rows that this checkout cannot see.

## Result

| Live rows (OBSERVED) | Before | After |
|---|---:|---:|
| All | 3,599 | 3,598 |
| Without a category | 619 | 567 |
| VIDEO | 0 | 51 |
| SYSTEM | 0 | 14 |

| Rule | Decision | Category | Rows | File |
|---|---|---|---:|---|
| Held video rows | 5 | VIDEO | 24 | `overlays/module-catalog-category-v4.json` |
| Held power rows (not retired) | 14 | SYSTEM | 11 | v4 |
| Whole tag `fan` | 14 | SYSTEM | 1 | v4 |
| Whole tag `rectifier` | 17 | UTIL | 5 | v4 |
| Whole tag `crossfader` | 17 | MIX | 3 | v4 |
| Noise A1: the name names one function | 6 | VCO | 1 | v4 |
| Noise A2: tagged noise and random only | 6 | VCO | 1 | v4 |
| Noise A3: noise among modulation tags | 6 | LFO | 2 | v4 |
| Mutable-derived rows whose quote gives the category | 17, 50, 55 | LFO, VCO | 2 | `overlays/module-catalog-category-v5.json` |
| Empty Mutable rows quoted from their own page | 17, 50 | VCF, LFO | 2 | v5 |
| **Rows filled** | | | **52** | fill-null |
| Corrections: the 3 video rows v1 filed elsewhere | 5 | VIDEO | 3 | `provenance/category-corrections-v1.json` |
| Corrections: Mutable rows backed by committed wording | 17 | VCF, LFO | 2 | same |
| Corrections: further video rows | 49 | VIDEO | 24 | `provenance/category-corrections-v2.json` |
| Corrections: LZX DC Distro 3A and 5A | 54 | SYSTEM | 2 | `provenance/category-corrections-v3.json` |
| **Rows corrected** | | | **31** | |
| Retired: `jolin-getrekt-touch-waveshaper` (`jolin-getrekt` kept) | 7 | | 1 | `overlays/catalog-retirements-v3.json` |
| `modules.module_type` set from the catalog category | 51 | see [below](#decision-51-a-category-now-reaches-modulesmodule_type) | 52 | loader |

Noise A4 (noise next to another function) leaves Nekyia Ouija empty, as the option says. The other A rows are Wildsync NOISE (A1), Steady State Fate Quantum Rainbow 2 (A2), and Nonlinearcircuits PSEUDO and 1u Reverse Sigmoid (A3). No NOISE category was added.

| Left empty, by reason (OBSERVED) | Rows | What settles it |
|---|---:|---|
| No tags | 423 | Feed re-crawl (281) or product pages (142) |
| Generic tags only | 58 | Maker page |
| No maker-crawl page (seed-only rows) | 50 | Not T031: there is no crawl page to read |
| Firmware platforms | 10 | Stay empty (decision 17) |
| Tags point to two categories | 8 | [Maker page](#needs-a-maker-page-in-the-free-reads-pr) |
| "Probably not modules" | 8 | [Maker page](#the-nine-probably-not-modules-rows) |
| Mutable-derived, no committed source | 7 | [Maker page](#decisions-50-and-55-no-category-without-a-cited-source) |
| Rings-derived: the quote names no category | 3 | [Maker page](#decisions-50-and-55-no-category-without-a-cited-source) |

## Decisions 49 and 54: the further video rows

Of the 35, 24 moved to VIDEO, 2 moved to SYSTEM, and 9 stay as they are. The test: does the row's **own** maker page say video, or is the only link its brand? OBSERVED, from `hermes-research/maker-crawl-v2.json`.

| Outcome | Rows | Evidence |
|---|---:|---|
| Moved to VIDEO | 23 | The row's own page carries the whole tag `video` |
| Moved to VIDEO | 1 | Syntonie Formes: the page's tags include RGB, a video signal, and 12 of Syntonie's 23 crawled modules are tagged video |
| Moved to SYSTEM (decision 54) | 2 | LZX DC Distro 3A and 5A: tagged power, distributor and utility. They're rack power, not video. |
| **Stay as they are, listed for a maker page** | **9** | The brand only, and the row's tags name another function |

Moved to VIDEO, by old category: MIX 6, VCO 5, UTIL 4, VCF 3, VCA 3, FX 2, LFO 1. The 2 DC Distro rows were UTIL. Each is corrected in both `module_catalog` and `modules`.

The 9 keep their stored category until a maker page says otherwise (decision 54):

| Row | Stored | Own tags | Note |
|---|---|---|---|
| LZX Cyclops | UTIL | interface, ILDA, laser, display | A laser output. Nothing says video. |
| LZX Sensory Translator | VCF | microphone, filter, envelope, trigger | |
| Afterlife Castle Circuits #2 | UTIL | flip-flops, multi-gate, quad-gate | The brand is 2 of 3, a small sample. |
| Syntonie Animate | VCO | quadrature, oscillator, CV | Its expander is VIDEO by decision 5, so the pair now differ. |
| Syntonie VU006 | VCO | oscillator, quadrature, sine | Shares the VU prefix with video rows, but nothing committed says what VU means. |
| Syntonie Cadrans | VCA | VCA, crossfader, multiplier | |
| Syntonie Matrice | VCA | matrix mixer, VCA, mixer | |
| Syntonie Seuils | UTIL | comparator, logic, ramp shifter | |
| Syntonie Solaire | MIX | rectifier, mixer | |

The same weakness applies to three of the original 24, which decision 5 settled as a group: LZX P (slide pot), Syntonie Courbes (shaper, expo, log, triple) and Syntonie VU008 (phase shifter, ramp, dual). They stay VIDEO.

Outside the 35 and not moved: LZX TBC2 Expander (UTIL, no crawl page, though TBC2 itself is VIDEO), Foxing Hour LUMA (UTIL, tagged RGB and greyscale), and two empty LZX rows with no crawl page (Cadet II RGB Encoder, Keychain). `build_maker_overlays.CATEGORY` still files a newly crawled video row by its function, so this list can grow.

## Decisions 50 and 55: no category without a cited source

Overlay v5 now holds only rows whose maker quote gives their category by the catalog's own rule. It hadn't been loaded anywhere but a throwaway database, so it was edited rather than versioned. These 10 rows stay empty until a maker page settles each:

| Row | Points to, by its committed name, URL or tags | Why it's out |
|---|---|---|
| Michigan Synth Works MicroStreams | Streams | Decision 50: no committed wording |
| Michigan Synth Works Plancks II | Frames | Decision 50 |
| Michigan Synth Works Quarks | Elements | Decision 50 |
| TLM Audio MODAX | Elements | Decision 50 |
| Michigan Synth Works Twiigs | a Bernoulli gate (Branches) | Decision 50 |
| Michigan Synth Works Twist | Warps | Decision 50 |
| Plum Audio Apex | Peaks | Decision 50 |
| Michigan Synth Works NanoRings | Rings | Decision 55: "Key data Resonator" names no category |
| Tall Dog µRings SE | Rings | Decision 55 |
| TLM Audio PHYSC | Rings | Decision 55 |

Re-checking everything else this PR adds:

| Row | Source | Outcome |
|---|---|---|
| Ripples_Original | "Key data Liquid filter", on this row's own page (`module-catalog-hp-v4.json` cites that URL). The catalog's rule sends `filter` to VCF. | Stays VCF |
| Tides_Original | "Key data Tidal modulator", likewise. The catalog's rule sends `modulat` to LFO. | Stays LFO |
| Tall Dog µPlaits SE | "Key data Macro-oscillator". The catalog's rule sends `oscillat` to VCO. | Stays VCO |
| Michigan Synth Works MicroTides | "Key data Tidal modulator". The wording is from the page for the first Tides, and this is a Tides 2 derivative. | Stays LFO |
| Ripples and Tides (2014 version) corrections | The same quotes, on the pages they cite | Unchanged |
| Overlay v4 | Whole tags, the owner's conventions and the brand test decision 5 names | Unchanged: no model knowledge |

I also removed what went beyond the sources in the rows that stay: `does` now holds the maker's word and nothing added. Tests check that each quote is verbatim in its cited file, that `does` is part of it, and that the category follows from it by the catalog's own rule.

## Decision 51: a category now reaches `modules.module_type`

**Finding, confirmed.** The patch engine reads `modules.module_type`, not the catalog's category. The loader inserts a module row whose catalog row has no category with the placeholder `UNKNOWN`, and no fill ever updated it. So on a database already loaded, a filled row stayed out of generated patches, while a load from empty gave it the category. `test_a_category_reaches_module_type_on_a_loaded_database` runs on a throwaway Postgres. Before the fix, OBSERVED:

```
{'M/S-MATRIX': 'UNKNOWN'} != {'M/S-MATRIX': 'UTIL'}
{'Video Gate 1U 10HP': 'UNKNOWN'} != {'Video Gate 1U 10HP': 'VIDEO'}
```

**Fix.** A new last step in the loader's plan, `_schedule_module_type_sync`, copies a live catalog row's category onto its module row, over the placeholder only. It reads each row's final state after every fill, correction and retirement. It also reaches rows filled by earlier loads.

**It writes a module row only when all of these hold**, and the `UPDATE` re-checks the placeholder, source and status when it runs:

- `module_type` is exactly `UNKNOWN`.
- `source` is `SynthCatalogResearch` or `CatalogCandidate`, the sources the loader itself writes.
- The row isn't tombstoned, and neither is its catalog row.
- Exactly one live catalog category matches its brand and name, and that category is in the vocabulary.

**It never touches** any other value. That covers a reviewed correction, an admin edit, and the `UTIL` default that materializing a catalog row or the admin importer writes. Rows it leaves alone are counted, not hidden. One known limit: a row materialized from an empty catalog row holds that default `UTIL`, which can't be told apart from a deliberate value, so it stays `UTIL` even once the catalog has a better category.

### What this does to existing rows

These counts are what the owner approves from. A load from empty needs no sync, because its inserts already take the category.

| Database | Rows set from `UNKNOWN` | By category | Can now join patches |
|---|---:|---|---:|
| Loaded from main today (OBSERVED) | 52 | VIDEO 24, SYSTEM 12, UTIL 5, LFO 4, MIX 3, VCO 3, VCF 1 | 16 |
| First loaded at `ada8949`, the newest commit the [2026-11-02 operator receipts](OPERATOR_RECEIPTS_2026-11-02.md) record for `db-load.yml` (OBSERVED on a replay) | 134 | UTIL 40, VIDEO 24, VCO 16, FX 14, SYSTEM 12, MIX 10, SEQ 8, LFO 5, ENV 3, VCF 1, VCA 1 | 98 |
| Worst case: every row older than category overlays v1 to v3 (OBSERVED on a scratch copy) | 302 | UTIL 85, FX 37, SEQ 35, LFO 34, VCO 28, VIDEO 27, MIX 17, VCA 16, SYSTEM 12, ENV 5, VCF 5, SAMP 1 | 263 |

**Production's count is NOT_COMPUTABLE offline.** Its load history isn't fully recorded here, and its 137 database-only rows can't be seen. INFERRED: if the `ada8949` runs were applies, between 134 and about 302, and any database-only rows the guards allow would add to that. The `db-load.yml` dry run on production prints the exact count and categories in its job summary, so the go-ahead can name them.

For the same load over main's data, the corrections also move 29 module rows **out** of generated patches: 27 into VIDEO (UTIL 6, MIX 6, VCO 5, VCF 3, VCA 3, FX 2, LFO 1, MIDI 1) and the 2 LZX DC Distro rows from UTIL into SYSTEM. For example, LZX Pendulum stops counting as an oscillator. One module row, the Jolin duplicate, is tombstoned.

What a Rig sees after the load:

- **Next generation:** a Rig holding one of these modules may get different patches. A filled module can now be wired in, and a corrected video module no longer can.
- **Stored runs and patches:** unchanged. OBSERVED: the plan writes only `module_catalog` (84 statements), `modules` (82) and `catalog_value_archive` (115).
- **Same revision, different result:** the rig revision hash doesn't include `module_type`, so the same revision and seed can produce a different patch set before and after the load. Decision 56 accepts this for this load, and old runs don't change. The hash gap is its own bug, [#295](https://github.com/Zero-State-LLC/Patch-Hive/issues/295), because changing the hash would invalidate every existing revision.
- **Placement and power:** unchanged. `racks/validation.py` doesn't read `module_type`.
- **Rig metrics:** new packets count these modules under their new category instead of `UNKNOWN`.

**Left alone over main's data:** 1 row, Make Noise Maths, with `module_type` UTIL and catalog category ENV.

**Reversal.** The old value of every synced row is archived first, under batch `module-type-sync-v1`, so a manual `UPDATE` can undo it. There's no automatic rollback yet (FR-031, decision 40), and `db-load.yml`'s pre-apply dump doesn't leave the runner.

## VIDEO and SYSTEM in the vocabulary

OBSERVED, by consumer:

- **Loader.** It had no vocabulary. `population.MODULE_CATEGORIES` now holds the 13 names, and a category overlay or correction naming anything else is a conflict that writes nothing.
- **Tests.** The `CATEGORIES` sets in `test_build_category_overlay.py` and `test_category_t031.py` gain both names.
- **Frontend filter.** There is no hard-coded list. `Modules.tsx` lists whatever `/modules/catalog/categories` returns, so the code needs no change, and a new test proves both appear and can be selected.
- **TypeScript contract.** There is no category union to extend: `category` and `module_type` are `string`.
- **Module plate color.** `catalog.css` maps some categories to a color. Both new ones take the default `--module-controller`, as UTIL, MIX and MIDI do.
- **Patch engine.** `engine.py` matches substrings of `module_type`, and no keyword is a substring of VIDEO or SYSTEM. Tests read the keywords out of the source and check that a rack holding only these generates nothing, and that adding them to a full rack changes no connection.
- **Other readers.** `core/naming.py`, `derive_patch_semantics.py`, `patching_order.py` and `get_module_color` give both no role.

One thing the engine doesn't ignore: a placed module changes the generated *names* of patches it isn't part of, because `name_patch_v2` hashes how many modules the rack holds. This is true of every module type and isn't new.

## How a category correction works

The loader's `correct` action covered HP, power and verification fields. It now also takes `module_catalog.category` and `modules.module_type`:

- Each row is corrected in both tables, because the patch engine reads `modules.module_type`. A `modules` entry whose row doesn't exist is counted as `rows_missing` and writes nothing: Ripples and Tides (2014 version) have no `modules` row in a load from the committed inputs.
- `correct` is the only action these fields accept. `null`, `flag`, `keep` and `relabel` are conflicts.
- A category correction never clears a `needs_reverify` flag, which is about HP or power.
- The rest is FR-038 unchanged: the entry names the wrong value and the page, the old value is archived first, and a value changed since review is left alone. If the module row still holds `UNKNOWN`, the correction leaves it, and decision 51's sync then writes the corrected category.

Category corrections run **after** the overlays, in their own `CATEGORY_CORRECTION_MANIFESTS`. The existing `PROVENANCE_MANIFESTS` run first, when a fresh database's catalog is still empty: they would record the row as processed and find nothing to correct, and overlay v1's fill-null would then store the wrong value for good. Overlay v1 can't be edited instead, because a loaded database already holds its values. OBSERVED: a load from empty and a load over main's data end with the same category and tombstone on every `module_catalog` row, and the same `module_type` and status on every `modules` row.

## Mutable Instruments rows

All 35 rows, checked against committed data. Committed maker wording exists for 8 products: `module-catalog-hp-v4.json` (Ripples, Tides; "maker-page-checked-2026-10-30") and `hermes-research/unmatched-pass.json` (Braids, Clouds, Marbles, Plaits, Rings, Stages). For the rest, committed data holds only a width, such as "Width 12HP" in `module-catalog-hp-v3.json`. Notes marked INFERRED explain why a row is listed for a page. No category rests on them.

| Row | Stored | Committed maker wording | Outcome |
|---|---|---|---|
| Ripples | VCO | "Key data Liquid filter" | **Corrected to VCF** |
| Tides (2014 version) | VCO | "Key data Tidal modulator" | **Corrected to LFO.** The catalog's own rule sends `modulat` to LFO. |
| Ripples_Original | empty | "Key data Liquid filter" | **Filled VCF** |
| Tides_Original | empty | "Key data Tidal modulator" | **Filled LFO** |
| Yarns | VCO | none | **Deferred.** INFERRED: a MIDI interface, as the owner says, and VCO is almost certainly wrong. The only committed hint is the seed's research label, which D1 keeps as a discovery lead, not evidence. One page read settles it. |
| Rings | VCO | "Key data Resonator" | **Deferred.** The wording isn't "oscillator", but committed data doesn't name a better category: rows tagged resonator are split (FX 3, VCF 2, ENV 1, SEQ 1). Its 3 derivatives wait with it (decision 55). |
| Frames | VCA | none | **Deferred.** INFERRED: VCA is defensible. The page decides VCA or MIX. |
| Edges | SEQ | none | **Deferred.** INFERRED: an oscillator, so SEQ looks wrong. |
| Links | MIX | none | Kept. The page confirms. |
| Grids | SEQ | none | Kept. The page confirms. |
| Marbles | SEQ | "Random sampler" | Kept. The wording doesn't contradict SEQ. Its clones disagree (TLM RANDS is LFO, MSW Pachinko is SAMP). |
| Stages | ENV | "Segment generator" | Confirmed |
| Braids, Plaits | VCO | "Macro-oscillator" | Confirmed |
| Clouds | FX | "Texture synthesizer" | Kept. T031 sends `clouds` to FX, and the Clouds derivatives that hold a category hold FX. |
| Braids (old version) | VCO | none for this row | Kept, same product as Braids |
| Anushri (Eurorack), anushri exp | VCO, MIDI | none | Kept. The page confirms. |
| 17 more, empty | | none | [Listed below](#needs-a-maker-page-in-the-free-reads-pr) |

## The nine "probably not modules" rows

Only the fan is settled by committed data. None of the nine is a USB power panel: that row (Mörk Modules USB Power 1U black panel) is among the 11 power rows already.

| Row | Tags | Outcome |
|---|---|---|
| Alyseum EOLE | ventilation, temperature, fan, monitor | **SYSTEM** |
| Hive Mind USBee | USB, port, blank | Maker page. The URL says "usb-port-moving-module": it moves a USB port, and nothing says it supplies power. |
| Avalon Harmonics Alcove (Printed Blank) | blank, storage | Maker page |
| Ethereal Electronics Starlight 8HP, 16HP | blank, panel, light | Maker page. Crawled at 85 mA and 150 mA, so lit panels may be working units. |
| Morph Modular Wormhole Portal | blank, 1U, Intellijel | Maker page |
| Nozoïd Nozori expansion panel | expansion, panel, jumpers | Maker page |
| WGD Modular ramen | connector, RJ45, case | Maker page |
| Plankton NUTONE PCB only | feedback, send, pcb | Maker page |

Decision 14 retires whatever never occupies HP, and a Blank Panel isn't a Module. So the page check decides SYSTEM, retire or another category for each.

## Needs a maker page in the free-reads PR

- **Mutable rows stored but unconfirmed (8):** Yarns, Rings, Frames, Edges, Links, Grids, Anushri (Eurorack), anushri exp.
- **Mutable rows empty (17):** Beads, Blades, Blinds, Branches, Ears, Elements, Kinks, Peaks, Ripples_2020, Shades_2020, Shades_Original, Shelves, Streams, Tides_2018, Veils_2020, Veils_Original, Warps.
- **Mutable-derived, left empty (10):** [listed above](#decisions-50-and-55-no-category-without-a-cited-source).
- **Rows linked to video only by brand (9):** [listed above](#decisions-49-and-54-the-further-video-rows).
- **"Probably not modules" (8):** the rows above.
- **Two categories (8):** BLM DDK, Erogenous Tones BLIP, Laine Vole, Nekyia Ouija, Nonlinearcircuits Coupled Comparators and SPASM, Selestium OSCULATRIX, Tsyklon Chaos Divider HV.

## Dry run

The target was a throwaway Postgres 15.13 container: migrated to alembic head, then loaded by `import_catalog_population.py --apply` from main at 504bbc1 (the baseline), then dry-run from this branch. Receipt: [`receipts/taxonomy-2026-11-04.dry-run.json`](../../data/synth-catalog/receipts/taxonomy-2026-11-04.dry-run.json).

| | |
|---|---|
| inserts | `catalog_value_archive`: 112 old values (60 corrected, 52 synced), and markers for the manifest rows |
| updates | `category_overlay`: 52; `module_catalog_correct`: 31; `modules_correct`: 29; `module_type_from_category`: 52; `catalog_retire`: 1; `module_retire`: 1 |
| conflicts | 0 |
| unmatched | same as the baseline (hp 31, power_depth 38, retire 1 + 1) |
| plan_hash | `2269b9c72b8b35daf4e9cc0ef7f964991f15b1b06e8d9244db309b4bfeb407aa` |
| inputs_hash | `eaeca0636e151009a6ab1b85639d789eb93e0aa16239adab909735a45b4acddb` |

The plan hash depends on the target database, so the operator applies with the hash from db-load.yml's own dry run, on staging first (decision 20). The inputs hash covers the committed catalog inputs.

Also OBSERVED on throwaway copies:

- An apply bound to those two hashes wrote exactly this plan and deleted no row. A second dry run planned nothing.
- A load from empty applied the same corrections and retirement and needed no sync. A second dry run planned nothing.
- The two end with the same category and tombstone on every `module_catalog` row, and the same `module_type` and status on every `modules` row. No live module row holds `UNKNOWN` while its catalog row has a category.

## Found along the way, not changed

These are outside the owner's calls, so nothing here was touched:

1. **More rack infrastructure outside SYSTEM.** Tagged power and holding UTIL: David Haillant USB Power Output, Manikk Analog8, Sonoclast Zero, WGD tofu. By name only: Make Noise Din Power (UTIL); and, empty, Endorphin.es 2HP POWER, Intellijel Power Entry and USB Extender, DPW P2 Pedal Power, Synthrotek USB Power.
2. **Other Mutable derivatives look misfiled.** Left alone: MSW mBrane 6HP Yarns (VCO), MSW Pachinko (SAMP), After Later uTides v2 (VCO), TLM SEGS (LFO, while Stages is ENV), TLM METAX (VCO). Seven more are empty and outside the owner's 12: After Later Atom, Cara, Knit, nRings, Peaks, Pique and uGrids.
3. **Decision 15 isn't built here.** An in-rack supply's output is still not handled specially, and the builder has no warning that it isn't counted.
4. **Jolin ROSA stays undecided.** The same duplicate pattern as GETREKT, but decision 7 names only GETREKT.
5. NOT_COMPUTABLE offline: whether any production rack places the `modules` row being retired. FR-036 warns such a rack and doesn't change it.

T031 stays open: its text needs the page cache rebuilt and the untagged rows classified from their pages.
