# Spec 003 T031 offline pass (2026-11-03)

T031 classifies the catalog rows that have no category. This pass is offline: committed data only, no maker-page, feed or listing fetch, no paid fetch, no load to a deployed database. The owner holds catalog fetching until the maker-permission basis is signed off ([EXTERNAL_SOURCE_POLICY.md](../EXTERNAL_SOURCE_POLICY.md)).

OBSERVED means read in this checkout or measured on a scratch load; INFERRED means reasoned from it. Counts are for a load from the committed inputs. Production also holds 137 database-only rows that this checkout cannot see.

## Result

| Live rows without a category (load from committed inputs) | Rows |
|---|---:|
| Before this pass | 702 |
| Classified by `overlays/module-catalog-category-v3.json` | 74 |
| Left | 628 |

| Left, by reason | Rows | What settles it |
|---|---:|---|
| No tags (feed and listing adapters kept none) | 425 | A re-crawl that keeps the store taxonomy (281 rows), or product pages (144) |
| Tags that no rule settles | 98 | See [Tagged rows still empty](#tagged-rows-still-empty) |
| Held: video modules | 24 | Owner decision 1 |
| Held: power supplies | 11 | Owner decision 2 |
| Tags that point to two categories | 20 | [#250](https://github.com/Zero-State-LLC/Patch-Hive/pull/250) settles 9; 11 need the convention or a maker page |
| No maker-crawl page (seed-only rows) | 50 | Not T031: there is no crawl page to read |

With #250 merged as well, 619 live rows remain without a category.

## New whole-tag rules (`scripts/build_category_overlay.py`)

The rules match whole tags only, never the name or free text. A row whose tags point to two categories stays empty. Every rule was spot-checked on every row it classifies. OBSERVED: each row's tags and name come from `hermes-research/maker-crawl-v2.json`.

| Rule (whole tag → category) | Rows it classifies | Check |
|---|---|---|
| glide → ENV | AvonSynth AVS-GLIDE-1 (glide, quad, voltage controlled) | A quad glide is a slew processor; slew is ENV (`CATEGORY`). |
| integrator → ENV | Tokyo Tape Music Center Dual Integrator 155 | A Buchla-style integrator is a lag (slew) processor. INFERRED from the name and the Buchla series. |
| trapezoid → ENV | Signs Modular trp (trapezoid, decay, CV) | A trapezoid generator is an envelope; the brand's fg1 and bbFG are function generators. |
| dual decay → ENV | none on its own | Added so BLM DDK (percussion, dual decay) stays empty rather than becoming a voice. |
| drive, clipper → FX | Sovage CHICANE (drive, clipper, stereo) | A stereo drive. |
| clouds → FX | Michigan Synth Works Microburst and Monsoon | Clouds derivatives. Mutable Clouds is FX in the catalog, as are the 4 rows already tagged clouds. |
| dry/wet → FX | Atonal Circuits K7 (encoder, high frequencies, dry/wet) | A dry/wet control marks an effect. |
| frequency shifter → FX | ARC Klangumwandler; TTMC Frequency Shifter 185 | Both names say so. |
| phase shifter, phaser → FX | TTMC Phase Shifter 196; NLC The Suppository of all Wisdom; NLC Encephalo Adjuster | Phasers. |
| pitch shifter → FX | gregsbrain xVox pitch shifter DIY kit | The name says so. |
| saturator → FX | Aircraft Designs Ember Mid/Side Saturator | The name says so. |
| aux send, pan, panning → MIX | ST Modular SEND, PAE, CV Pan; Pusherman CV PAN; AJH Triple Cross Xfader; WGD Lemon | Panners and send/return. `panner` is already MIX (`CATEGORY`); 7 tagged rows hold MIX. |
| summing → MIX | selestium COMBINER | A summing mixer; 7 tagged rows hold MIX. |
| cv controller → SEQ | BeepBoop Samsara (URL `samsara-bipolar-cv-controller`) | Controllers are SEQ (`TAG_CATEGORY`). |
| groovebox, pattern → SEQ | Melawati Oddity; NLC BEAT FREQS; NLC Cellular Automata | Gate-pattern generators. Oddity is a groovebox: a sequencer with voices, filed by its sequencer. |
| manual gate → SEQ | Fully Wired Quad Manual Gate | A performance controller. |
| rhythmic → SEQ | Sonoclast Heartbeat (rhythmic, gate, loop) | A rhythm generator. |
| shift register → SEQ | Larix RITOURNELLE SHIFT-R | 6 of 11 categorized rows with this tag are SEQ. |
| adapter → UTIL | Something Modular PAL (pedal adapter); ST Modular Emoo (MOOER pedal adapter) | The effect is the pedal; the module adapts it. |
| inverter, adder → UTIL | TTMC CV Inverter 157; Rides in the Storm IPT Dual Inverter & Precision Adder | CV maths; `precision adder` is already UTIL. |
| dac → UTIL | StudioKAT R2R DAC v1, v2 | Converters; `converter` is already UTIL. |
| display, visualizer → UTIL | apf.audio tiliqua-screen; Atonal SEE; BeepBoop Eurostack Sound System V2; Motley Disting EX Flush External Display; Motley Dual Disting Display; Vaski Lights Stereo Visualizer (2) | Displays and meters. |
| headphones, headphone amp, monitoring → UTIL | BeepBoop 1U Headphones; Feedback PhoneZ; Skull & Circuits SCM-A01 | Output utilities. BeepBoop 2hp Headphones is UTIL. Singular `headphone` is left out: Jolin OCELOT (electroacoustic, feedback, headphone) is an instrument. |
| indicator → UTIL | Hive Mind IND (indicator, LED, signal) | A signal indicator. |
| line-in, microphone, preamp → UTIL | Pindsvik LIHO; BeepBoop 2hp Intercom MIC; Ginko PHONO PREAMP | Input interfaces; `input` and `interface` are already UTIL. |
| matrix, router → UTIL | ACL M/S-MATRIX; Hinton Signal Matrix; Ult-Sound MSM-4x4; Divergent Waves Dice; Vostok Path | Routing; 7 of 12 categorized rows with `router` are UTIL. |
| meter, oscilloscope, vu meter → UTIL | Dave Jones Otool; BeepBoop 1U VU Meter; Olivia Artz LEDVU; Thawney LEDVU | Meters. |
| splitter → UTIL | Der Mann mit der Maschine TRS Split; vpme.de TRS Split | Splitters. |
| tester → UTIL | Jolin NEXUM (tester, cable) | A cable tester. |
| voltage scaler → UTIL | Omiindustriies Curtail | A scaler. |
| braids, plaits → VCO | Michigan Synth Works MicroBraids II and Beehive (8HP Plaits) | Derivatives. Mutable Braids and Plaits are VCO in the catalog. |
| chiptune → VCO | BitByBit WaveBoy DIY (Chiptune, GameBoy) | A sound source. |
| cowbell, kick, percussion → VCO | NLC MORE; WGD kaoya; Manikk DRM7 | Drum voices. `drum` is VCO (`CATEGORY`); 12 categorized percussion rows are VCO. |
| drone, plucked string → VCO | NLC FOURIER; selestium QUIVERER (M5); NLC Is Carp Lust Wrong? | Sound sources; 7 drone rows are VCO. |
| speech, synthesizer → VCO | Polaxis Talko 1 (assembled, DIY); Pusherman KLANGMASCHINE; TLM KLANGMASCHINE | Voices. ST Modular's KLANGMASCHINE is VCO in v1. |

Total: 74 rows. By category: UTIL 33, VCO 13, FX 11, SEQ 7, MIX 7, ENV 3.

**Dropped after the spot-check.** `rectifier → UTIL` would have classified NLC 1u Difference Rectifier, GENiE, Let's Splosh and SPLISH. GENiE is tagged "neuron", and NLC's own Neuron and 4HP Neuron are FX. Across makers, categorized rectifier rows are split between FX, MIX and UTIL. Rectifiers need a convention, not a rule.

**Retired rows are skipped.** A retired row needs no category. Phase Engineering's Variatic Erumption (retired by `catalog-retirements-v1`) would otherwise have taken VCO.

**Two rows the new rules make two-category:** BLM DDK (VCO or ENV) and Rides in the Storm CLI (FX from clipper, UTIL from matrix). Both stay empty.

**No conflict with #250.** OBSERVED: none of the nine rows #250 settles changes its pair of tag categories under these rules.

## Feed adapters keep the store taxonomy (`scripts/maker_adapters.py`)

Until now the Shopify adapter used `product_type` only to drop merchandise, the WooCommerce adapter used `categories` only to pick which products to keep, and neither kept a store's tags. Now each feed candidate carries `store_tags`, holding the store's own product type, categories and tags as published (HTML-unescaped and de-duplicated). This covers:

- Shopify: `product_type` and `tags`
- Squarespace: `categories` and `tags`
- WooCommerce: category and tag names

`crawl_adapter` writes them on the crawl row as `store_tags`, separate from the page's own `tags`. `build_category_overlay.py` reads both.

This changes no committed data: nothing was re-crawled. OBSERVED, the 425 rows with no tags break down as:

| Source | Rows |
|---|---:|
| Shopify feed | 206 |
| Squarespace feed | 42 |
| WooCommerce feed | 33 |
| Listing adapters | 140 |
| Generic crawl | 4 |

The 281 feed rows would carry their store's taxonomy after a feed re-crawl. That is one free JSON GET per store page (`products.json`, `?format=json`, the WooCommerce Store API), but it is still a fetch, so it waits for the permission decision. The 144 listing and generic rows need product pages.

## Dry run

No staging or production replica was available offline. The target was a scratch Postgres 15 database in the local container: migrated to alembic head, loaded by `import_catalog_population.py --apply` from main's catalog inputs (this branch without v3), then dry-run with v3. Receipt: [`receipts/t031-category-v3.dry-run.json`](../../data/synth-catalog/receipts/t031-category-v3.dry-run.json).

| | |
|---|---|
| inserts | none |
| updates | `category_overlay`: 74 |
| conflicts | 0 |
| unmatched | same as main's baseline (hp 31, power_depth 38, retire 1 + 1) |
| plan_hash | `5960fd8e83fc7fe2c5ca7fb43ff8eda9fe10a76ec0909e317ae1548c98660af7` |
| inputs_hash | `f17caec2d923f6ae9c51be5aa614eebb56414f02655f316d69da9be9d19c4043` |

The plan hash depends on the target database, so the operator applies with the hash from db-load.yml's own dry run on staging or prod. The inputs hash is the hash of this commit's catalog inputs. Merging #250 changes both.

## Tagged rows still empty

98 live rows have tags that no rule settles. INFERRED groups:

| Group | Rows | Why no rule |
|---|---:|---|
| Mutable Instruments derivatives (Streams, Tides, Rings, Frames, Elements, Branches, Warps, Peaks, Plaits, plus clones) | 12 | The catalog's own Mutable rows cannot anchor them: Ripples, Yarns, Tides and Rings are VCO, and Frames is VCA. A reviewed name-to-category table is a separate decision. |
| Programmable DSP and firmware platforms (apf.audio pmod, Bela Pepper, Rebel Genius and OWL, Gracious Host, PIKOCOREURO, Patching Panda, Carciofo) | 10 | The function depends on the firmware loaded. |
| Probably not modules (fan, printed and lit blank panels, USB port blank, expansion panel, connector, bare PCB) | 9 | Retirement candidates, like the power supplies. |
| Rectifiers (NLC ×4, Rides in the Storm CLI) | 5 | FX or UTIL: a convention is needed (see above). |
| Crossfaders (Modulaire Maritime R / K and VC Crossfader, Sonocurrent M C3A) | 3 | Categorized crossfaders are split: VCA 9, UTIL 4, VCF 2, and one each of FX, VCO and MIX. |
| Generic tags only (cv, gate, stereo, analog, sync, generator, …) | 59 | Need the maker page, including BLM DDK. |

## Owner decisions needed

1. **Video modules (24 rows held).** OBSERVED list:
   - Afterlife Laboratories: Video Keyer
   - LZX Industries (13): Doorway, ESG3, Liquid TV, Marble Index, Navigator, P, PAB, Polar Fringe, PRM, Shapechanger, SumDist, Swatch, TBC2
   - Nonlinearcircuits: LDRama
   - Syntonie (9): Combines, Courbes, Entrée, Isohélie, Rampes, Sortie, VU003B, VU007, VU008

   A row is held when it is tagged `video` or when it comes from a brand most of whose crawled modules are tagged video (Afterlife Laboratories, LZX Industries, Melted Electronics, Syntonie). That second test catches Syntonie VU008, whose own tags say only "phase shifter".

   | Option | Effect |
   |---|---|
   | A. A new VIDEO category | Honest. The rack builder and the patch engine have no VIDEO handling, so these modules would not join audio patches, which is correct. Costs: the frontend category filter, the tests' category sets, and `correct` entries for three video rows already categorized by v1 (Hive Mind Video Gate as UTIL, Melted Electronics Glitch Boy as MIDI, Syntonie Animate Exp as UTIL). |
   | B. UTIL | No vocabulary change, but it puts video processors among audio utilities, and the patch engine counts UTIL modules as utilities. |

   **Recommendation: A**, or leave the rows empty until the owner wants video in the catalog at all.
2. **Power supplies (11 rows held): retire them?** OBSERVED list:
   - Aircraft Designs DC High-Quality Power Supply
   - Eowave SOURCE D'ENERGIE and SOURCE MK3
   - Feed me Synthesis parasitic power
   - Feedback RESET
   - Mörk Modules USB Power 1U black panel
   - Soundmachines SILTA
   - ST Modular POW! and USB
   - vpme.de UPWR
   - WGD Modular STV

   `build_maker_overlays.NOT_MODULE_NAME` already treats power supplies as "not a module" by name, so these slipped past it. **Recommendation: retire them** with a `catalog-retirements-v3` entry each, citing the maker page. They are rack power, not modules a patch uses. The 9 "probably not modules" rows above could go in the same manifest after a maker-page check.
3. **The maker-permission basis.** The feed re-crawl (281 rows) and the maker pages (59 or more rows) both wait on it.
