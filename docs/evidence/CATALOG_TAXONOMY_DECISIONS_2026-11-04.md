# Catalog taxonomy decisions applied (2026-11-04)

This applies the owner's catalog calls from committed data: decisions 5, 6, 7, 14 and 17 in `docs/evidence/OWNER_DECISIONS_2026-11-04.md` ([#278](https://github.com/Zero-State-LLC/Patch-Hive/pull/278), open when this was written). No maker page, feed or listing was fetched, nothing was paid for, and nothing was loaded to a deployed database.

OBSERVED means read in this checkout or measured on a throwaway load. INFERRED means reasoned from it, including the reviewer's own knowledge of a module. Counts are for a load from the committed inputs. Production also holds 137 database-only rows that this checkout cannot see.

## Result

| Live rows (OBSERVED) | Before | After |
|---|---:|---:|
| All | 3,599 | 3,598 |
| Without a category | 619 | 557 |
| VIDEO | 0 | 27 |
| SYSTEM | 0 | 12 |

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
| Mutable-derived table | 17 | see [below](#mutable-derived-table) | 12 | `overlays/module-catalog-category-v5.json` |
| Empty Mutable rows whose maker wording is committed | 17 | VCF, LFO | 2 | v5 |
| **Rows filled** | | | **62** | fill-null |
| Corrections: the 3 video rows v1 filed elsewhere | 5 | VIDEO | 3 | `provenance/category-corrections-v1.json` |
| Corrections: Mutable rows backed by committed wording | 17 | VCF, LFO | 2 | same |
| Retired: `jolin-getrekt-touch-waveshaper` (`jolin-getrekt` kept) | 7 | | 1 | `overlays/catalog-retirements-v3.json` |

Noise A4 (noise next to another function) leaves Nekyia Ouija empty, as the option says. The other A rows are Wildsync NOISE (A1), Steady State Fate Quantum Rainbow 2 (A2), and Nonlinearcircuits PSEUDO and 1u Reverse Sigmoid (A3). No NOISE category was added.

| Left empty, by reason (OBSERVED) | Rows | What settles it |
|---|---:|---|
| No tags | 423 | Feed re-crawl (281) or product pages (142) |
| Generic tags only | 58 | Maker page |
| No maker-crawl page (seed-only rows) | 50 | Not T031: there is no crawl page to read |
| Firmware platforms | 10 | Stay empty (decision 17) |
| Tags point to two categories | 8 | [Maker page](#needs-a-maker-page-in-the-free-reads-pr) |
| "Probably not modules" | 8 | [Maker page](#the-nine-probably-not-modules-rows) |

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
- The rest is FR-038 unchanged: the entry names the wrong value and the page, the old value is archived first, and a value changed since review is left alone.

Category corrections run **after** the overlays, in their own `CATEGORY_CORRECTION_MANIFESTS`. The existing `PROVENANCE_MANIFESTS` run first, when a fresh database's catalog is still empty: they would record the row as processed and find nothing to correct, and overlay v1's fill-null would then store the wrong value for good. Overlay v1 can't be edited instead, because a loaded database already holds its values. OBSERVED: a load from empty and a load over main's data end with the same category and tombstone on every `module_catalog` row.

## Mutable Instruments rows

All 35 rows, checked against committed data and the reviewer's knowledge. Committed maker wording exists for 8 products: `module-catalog-hp-v4.json` (Ripples, Tides; "maker-page-checked-2026-10-30") and `hermes-research/unmatched-pass.json` (Braids, Clouds, Marbles, Plaits, Rings, Stages). For the rest, committed data holds only a width, such as "Width 12HP" in `module-catalog-hp-v3.json`.

| Row | Stored | Committed maker wording | Outcome |
|---|---|---|---|
| Ripples | VCO | "Key data Liquid filter" | **Corrected to VCF** |
| Tides (2014 version) | VCO | "Key data Tidal modulator" | **Corrected to LFO.** The catalog's own rule sends `modulat` to LFO. |
| Ripples_Original | empty | "Key data Liquid filter" | **Filled VCF** |
| Tides_Original | empty | "Key data Tidal modulator" | **Filled LFO** |
| Yarns | VCO | none | **Deferred.** INFERRED: a MIDI interface, as the owner says, and VCO is almost certainly wrong. The only committed hint is the seed's research label, which D1 keeps as a discovery lead, not evidence. One page read settles it. |
| Rings | VCO | "Key data Resonator" | **Deferred.** The wording isn't "oscillator", but committed data doesn't name a better category. `resonat` in a name means FX, yet rows tagged resonator are split (FX 3, VCF 2, ENV 1, SEQ 1), Rings sounds on its own when triggered, and plucked-string voices are VCO. |
| Frames | VCA | none | **Deferred.** INFERRED: four VCAs and a mixer, so VCA is defensible. The page decides VCA or MIX. |
| Edges | SEQ | none | **Deferred.** INFERRED: a chiptune oscillator, so SEQ looks wrong. |
| Links | MIX | none | Kept. INFERRED: a multiple and mixer. The page confirms. |
| Grids | SEQ | none | Kept. INFERRED: a drum sequencer. |
| Marbles | SEQ | "Random sampler" | Kept. The wording doesn't contradict SEQ. Its clones disagree (TLM RANDS is LFO, MSW Pachinko is SAMP). |
| Stages | ENV | "Segment generator" | Confirmed |
| Braids, Plaits | VCO | "Macro-oscillator" | Confirmed |
| Clouds | FX | "Texture synthesizer" | Kept. T031 sends `clouds` to FX, and the Clouds derivatives that hold a category hold FX. |
| Braids (old version) | VCO | none for this row | Kept, same product as Braids |
| Anushri (Eurorack), anushri exp | VCO, MIDI | none | Kept. The page confirms. |
| 17 more, empty | | none | [Listed below](#needs-a-maker-page-in-the-free-reads-pr) |

## Mutable-derived table

`does_source` says where the description comes from. `maker_wording` rows quote Mutable from committed data, and a test checks the quote is verbatim in the cited file. `reviewer_knowledge` rows are INFERRED: the name, URL and tags show which Mutable module it derives from, but no committed text says what that module does. The free-reads PR confirms those seven.

| Row | Derived from | What it does | Source | Category |
|---|---|---|---|---|
| Michigan Synth Works MicroStreams | Streams | Dynamics gate | reviewer_knowledge | VCA |
| Michigan Synth Works MicroTides | Tides | "Tidal modulator" | maker_wording | LFO |
| Michigan Synth Works NanoRings | Rings | "Resonator" | maker_wording | VCO |
| Tall Dog µRings SE | Rings | "Resonator" | maker_wording | VCO |
| TLM Audio PHYSC | Rings | "Resonator" | maker_wording | VCO |
| Michigan Synth Works Plancks II | Frames | Keyframer of four VCAs | reviewer_knowledge | VCA |
| Michigan Synth Works Quarks | Elements | Modal synthesis voice | reviewer_knowledge | VCO |
| TLM Audio MODAX | Elements | Modal synthesis voice | reviewer_knowledge | VCO |
| Michigan Synth Works Twiigs | Branches | Bernoulli gate | reviewer_knowledge | UTIL |
| Michigan Synth Works Twist | Warps | Meta-modulator | reviewer_knowledge | FX |
| Plum Audio Apex | Peaks | Dual function generator | reviewer_knowledge | ENV |
| Tall Dog µPlaits SE | Plaits | "Macro-oscillator" | maker_wording | VCO |

The Rings and Frames rows follow the catalog's own Rings (VCO) and Frames (VCA) rows. If the free-reads PR moves either, these rows need `correct` entries to match.

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
- **Mutable-derived, to confirm (7):** the `reviewer_knowledge` rows above.
- **"Probably not modules" (8):** the rows above.
- **Two categories (8):** BLM DDK, Erogenous Tones BLIP, Laine Vole, Nekyia Ouija, Nonlinearcircuits Coupled Comparators and SPASM, Selestium OSCULATRIX, Tsyklon Chaos Divider HV.

## Dry run

The target was a throwaway Postgres 15.13 container: migrated to alembic head, then loaded by `import_catalog_population.py --apply` from main at 007b437 (the baseline), then dry-run from this branch. Receipt: [`receipts/taxonomy-2026-11-04.dry-run.json`](../../data/synth-catalog/receipts/taxonomy-2026-11-04.dry-run.json).

| | |
|---|---|
| inserts | `catalog_value_archive`: 8 old values, and markers for the 10 manifest rows |
| updates | `category_overlay`: 62; `module_catalog_correct`: 5; `modules_correct`: 3; `catalog_retire`: 1; `module_retire`: 1 |
| conflicts | 0 |
| unmatched | same as the baseline (hp 31, power_depth 38, retire 1 + 1) |
| plan_hash | `377081ebdfb2a8bac4fdf0d60a32b7addc6ccb2c747c799228f3f8865d096eec` |
| inputs_hash | `a7d66f17d8e32be3ef1fa7a0913431041c587dd664ceaaf4642afb270cbbfe42` |

The plan hash depends on the target database, so the operator applies with the hash from db-load.yml's own dry run, on staging first (decision 20). The inputs hash covers the committed catalog inputs.

Also OBSERVED on throwaway copies:

- An apply bound to those two hashes wrote exactly this plan and deleted no row. A second dry run planned nothing.
- A load from empty applied the same corrections and retirement. A second dry run planned nothing.
- The two end with the same category and tombstone on every `module_catalog` row.

## Found along the way, not changed

These are outside the owner's calls, so nothing here was touched:

1. **35 more video rows hold another category.** The T031 pass listed 3, but OBSERVED: 23 more are tagged video, such as Foxing Hour SHUTTER (UTIL), LZX Pendulum (VCO) and Syntonie Ondes (VCO), and 12 more come from a majority-video brand, such as Syntonie Animate (VCO), whose expander now reads VIDEO. Two empty LZX rows with no crawl page (Cadet II RGB Encoder, Keychain) are also outside the 24. `build_maker_overlays.CATEGORY` still files a newly crawled video row by its function, so this list can grow. Does the owner want these moved to VIDEO?
2. **More rack infrastructure outside the 11.** Tagged power and holding UTIL: David Haillant USB Power Output, LZX DC Distro 3A and 5A, Manikk Analog8, Sonoclast Zero, WGD tofu. By name only: Make Noise Din Power (UTIL); and, empty, Endorphin.es 2HP POWER, Intellijel Power Entry and USB Extender, DPW P2 Pedal Power, Synthrotek USB Power.
3. **A fill never reaches `modules.module_type` on a loaded database.** OBSERVED: after the apply over main's data, the 62 filled rows keep `module_type = UNKNOWN`, while a load from empty gives them their category. VIDEO and SYSTEM are unaffected in practice, since neither joins a patch. A rectifier or a Mutable derivative stays out of generated patches on that database until something copies the category across. Every earlier fill overlay has the same gap. NOT_COMPUTABLE offline: how many rows this is on staging or production.
4. **Other Mutable derivatives look misfiled.** Left alone: MSW mBrane 6HP Yarns (VCO), MSW Pachinko (SAMP), After Later uTides v2 (VCO), TLM SEGS (LFO, while Stages is ENV), TLM METAX (VCO). Seven more are empty and outside the 12: After Later Atom, Cara, Knit, nRings, Peaks, Pique and uGrids.
5. **Decision 15 isn't built here.** An in-rack supply's output is still not handled specially, and the builder has no warning that it isn't counted.
6. **Jolin ROSA stays undecided.** The same duplicate pattern as GETREKT, but decision 7 names only GETREKT.
7. NOT_COMPUTABLE offline: whether any production rack places the `modules` row being retired. FR-036 warns such a rack and doesn't change it.

T031 stays open: its text needs the page cache rebuilt and the untagged rows classified from their pages.
