# Catalog free reads, 2026-11-05

This records the free reads under [owner decisions](OWNER_DECISIONS_2026-11-04.md) 18, 30, 41, 50 and 54, plus the page checks decisions 13, 14 and 17 asked for. Every read was a plain GET through `data/synth-catalog/catalog_scrape.py`: robots.txt honoured, the deny list and per-host delay on, and the paid cap at 0. The paid-service keys were also unset for the run. Nothing was paid for, and ModularGrid wasn't fetched. A site that refused stays refused.

`scripts/catalog_free_reads.py` does the reads. Each URL's outcome is in [`receipts/free-reads-2026-11-05.json`](../../data/synth-catalog/receipts/free-reads-2026-11-05.json). Page text isn't committed: only the few words an overlay rests on are.

OBSERVED means read on a maker's page or measured in this checkout. Counts are for a load from the committed inputs unless a row says otherwise.

## Result

| Live rows (OBSERVED) | Before | After |
|---|---:|---:|
| All | 3,598 | 3,587 |
| Without a category | 567 | 280 |
| HP marked `legacy_unsourced` | 18 | 9 |

| Reads | Rows |
|---|---:|
| Page read | 517 |
| No page known (seed-only rows, and named rows the crawl never reached) | 63 |
| robots.txt refused with a 403 (Befaco 14, SSSR Labs 1, X Audio Systems 1) | 16 |
| robots.txt didn't answer (Analogue Systems) | 2 |
| Page failed or missing (Modulaire Maritime, 2 Mutable Anushri pages) | 3 |
| **Rows** | **601** |

The feeds of 11 makers gave 547 products with their stores' own taxonomy. A further 19 named pages are listed in the receipt under `named_pages`.

## What changes

| Change | Rows | File |
|---|---:|---|
| Category filled | 276 | `overlays/module-catalog-category-v6.json` |
| Category corrected | 5 | `provenance/category-corrections-v4.json` |
| Retired | 11 | `overlays/catalog-retirements-v4.json` |
| A supply's output cleared from its draw fields | 5 | `provenance/maker-corrections-v7.json` |
| Width corrected | 3 | `provenance/maker-corrections-v7.json`, `overlays/module-catalog-hp-v8.json` |
| Width confirmed by the maker | 6 | `overlays/module-catalog-hp-v8.json` |

Filled, by category: UTIL 65, VCO 50, FX 38, SEQ 34, VCF 19, MIX 19, LFO 18, ENV 12, VCA 9, SYSTEM 4, MIDI 4, SAMP 4.

### How a category was filled

A keyword match alone gets too many of these wrong, so every row was reviewed by hand. Each entry holds the maker's words (`does`), a short quote around them, and the rule they follow from: the catalog's own rule, or a named owner decision. Tests check that the words are in the quote and that the category follows.

These rows show what the review caught:

| Row | Keyword match | Outcome |
|---|---|---|
| Noise Engineering Soleo Vero, "stroboscope tuner for up to three oscillators" | VCO | Left empty |
| Endorphin.es AUTOPILOT, "autotuner of oscillators" | VCO | Left empty |
| Joranalogue Collide 4, "lock-in amplifier" | VCA | Left empty |
| Joranalogue Pivot 2, "variable router" for effects | FX | UTIL |
| 2hp Arp, "arpeggiator" | UTIL | SEQ |

A row stays empty when its words name two functions (Make Noise DXG, Noise Engineering Sinclastic Empulatrix, Plankton Nutone), or name no category. Decision 17's firmware platforms stay empty, as do rows like Noise Engineering Versio and Legio that the maker calls a platform.

### Category corrections

Each is corrected in both `module_catalog` and `modules`.

| Row | Stored | Corrected | Maker's words |
|---|---|---|---|
| Mutable Yarns | VCO | MIDI | "4-channel MIDI interface" |
| Mutable Frames | VCA | MIX | "Keyframer/mixer" |
| Mutable Edges | SEQ | VCO | "Quad chiptune audio generator" |
| LZX Sensory Translator | VCF | UTIL | "5-channel input acquisition" |
| Syntonie Animate | VCO | LFO | "quadrature low frequency oscillator" |

The other Mutable rows the [taxonomy record](CATALOG_TAXONOMY_DECISIONS_2026-11-04.md) listed:

| Row | Page says | Outcome |
|---|---|---|
| Blades, Ripples_2020, Shelves | "Dual multimode filter", "Liquid filter", "EQ filter" | VCF |
| Veils_2020, Veils_Original | "Quad VCAr" | VCA |
| Tides_2018 | "Tidal modulator" | LFO, as Tides is |
| Ears | "Contact microphone" | UTIL |
| Grids, Links | "Topographic drum sequencer", "Multiples and mixing" | Kept as SEQ and MIX |
| Rings | "Resonator" | Kept. It still names no category (decision 55), and its 3 derivatives stay empty |
| Beads, Elements | "Texture synthesizer" | Empty. No rule covers it. The Elements page reads the same as Beads, which looks like an error on that page |
| Blinds, Branches, Kinks, Streams | "Quad VC-Polarizer", "Dual Bernoulli Gate", "Mingling and Mangling", "Dual dynamics gate" | Empty |
| Peaks, Shades (2) | Several functions, "Attenuator/offset/mixer" | Empty |
| Warps | "Meta-modulator" | Empty. The rule gives LFO, but it processes audio, so filling it would be wrong |
| Anushri (2) | 404, no page in the docs | Unread, kept |

Michigan Synth Works Plancks II is "based on Opensource Frames", so it takes MIX from Frames' page. The other Mutable-derived rows stay empty for the reasons above. Of the rows linked to video only by brand (decision 54), the other 7 keep their stored category.

### Rows that were retired

Decisions 4, 13 and 14: a Module is a working unit that occupies HP.

| Row | The page says |
|---|---|
| Avalon Harmonics Alcove (Printed Blank) | "Blank for storing manuals" |
| Ethereal Electronics Starlight 8HP, 16HP | "Blanks don't have to be filled…" (lit panels) |
| Morph Modular Wormhole Portal | "blank panel" |
| Pittsburgh Modular Lifeforms HP-6 | "Blank Logo Panel" |
| WMD Black Panels | "replacement panels" |
| Plankton Nutone PCB only | a bare PCB |
| Behringer Eurorack Rack | "case kit" |
| Doepfer A-100 Systeme | a list of complete systems |
| Free Modular "Modular" | "A collection of free & open source DIY" designs |
| Humble Audio "Audio" | "Makers of the Quad Operator" (the home page) |

Six of the 11 aren't on the owner's list of 9: Lifeforms HP-6, WMD Black Panels, the Behringer case, the Doepfer page, Free Modular and Humble Audio. All 6 are the same mistake, and a retirement is a tombstone, so it can be undone.

Hive Mind USBee, WGD ramen and the Nozori expansion panel occupy HP and serve the rack, so they become SYSTEM (decision 14).

### A supply's output stored as its draw

The crawl read what 5 supplies deliver as what they draw, so a rack holding one showed thousands of mA of false load. Each value is archived and then cleared. The same values also come out of power overlays v9 and v11, because a later fill would otherwise bring them back, as with the rail fix in [#68](https://github.com/Zero-State-LLC/Patch-Hive/pull/68).

| Row | Stored as draw (+12V / -12V / +5V, mA) | The page says |
|---|---|---|
| Eowave SOURCE MK3 | 2500 / 2500 / 2000 | "-> 2500mA +12V" |
| vpme.de UPWR | 2000 / 1000 / 500 | "UPWR delivers" |
| Aircraft Designs DC High-Quality Power Supply | 2000 / 1500 / none | "Current Delivering" |
| ST Modular POW! | 300 / 150 / 500 | "provides up to" |
| WGD Modular STV | 700 / 150 / none | "rating of" |

ST Modular USB keeps its 8 mA, which is a real draw. The other SYSTEM rows store no draw.

### Widths

Decision 30's plain-GET retry settled 9 of the 17 unsourced widths. ADDAC's site, listed as blocked in the earlier record, answered every read.

| Row | Stored | Maker's page | Outcome |
|---|---:|---:|---|
| ADDAC200PI | 2 | 4 | Corrected |
| ADDAC200S Size Matter (black) | 2 | 4 | Corrected |
| ADDAC501B | 8 | 4 | Corrected |
| ADDAC001, 003, 005, 101, 203 | 12, 4, 4, 11, 4 | The same | Confirmed |
| Doepfer A-101-4 | 8 | 8 | Confirmed |

Decision 41: ALM's page gives Akemie's Castle as "38HP 32mm Deep". The manifest corrects a stored 18 to 38 and changes nothing if the value is already 38. The row wasn't in production's public catalog when this was read.

**8 stay `legacy_unsourced`** and go to the owner's drafted emails (decision 30):

| Maker | Rows | Why the read failed |
|---|---|---|
| Befaco | Mixer, Dual Atenuverter | robots.txt answers 403 |
| Instruo | dàil | robots.txt gave no usable answer |
| Cwejman | D-LFO | robots.txt answered 522 |
| Intellijel | μAtt, Quadra Expander | The legacy pages state no width |
| Make Noise | Mysteron, Strega | 404, and no HP on the page |

Doepfer A-155 also stays marked on a load from empty, as [T039](../../specs/003-catalog-dataset-pipeline/tasks.md) already records.

## Left empty: 280 rows

| Why | Rows |
|---|---:|
| Page read, and the words don't settle it (two functions, no rule, a platform, or not in English) | 212 |
| No page known | 49 |
| Refused by robots.txt | 18 |
| Page unreadable | 1 |

## For the owner

Nothing here changed these:

1. **Hexinverter Mutant Chicken** stores a 5,000 mA draw and SEQ. The maker's page describes an "analog rubber chicken" at $3,999, so it looks like a joke product. Retiring it needs a call.
2. **Rack infrastructure still outside SYSTEM,** with no power tag or wording that settles it: Intellijel Power Entry and USB Extender.
3. **After Later's "VCA+Mixer" rows** (Barback, Bartender, Inserts, Blend and others) stay empty, because the store files both functions together.
4. **Marbles clones file differently.** After Later's own store tags Dice, Cara and Pachinko as Modulation, so they're LFO, while Mutable Marbles stays SEQ.

## Staging

Loaded from branch `catalog/free-reads`, before merge. The owner confirmed this load in chat, on top of decision 20.

| Step | Run | Result |
|---|---|---|
| Dry run | [42117262485](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42117262485) | 0 conflicts, no destructive SQL |
| Apply | [42117702596](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42117702596) | The counts above. The archive went from 5,094 to 5,422 rows |
| Second dry run | [42118691507](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42118691507) | Plans nothing |
| Smoke | [42118706230](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42118706230) | 10/10 |

Reading staging's public API afterwards: the catalog total went from 3,171 to 3,160, public rows with no category from 555 to 278, and none of the rows mentions ModularGrid. UPWR, SOURCE MK3 and POW! show no draw, ST Modular USB keeps its 8 mA, and the retired rows are gone. Yarns, Frames, Edges, ADDAC200PI and Akemie's Castle are hidden from anonymous reads, so only the receipt shows those changes.

## Production, not yet loaded

Dry run [42119014963](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42119014963), from the same branch, wrote nothing. Its plan matches staging's.

- `plan_hash`: `95e8c235c4c47f5b3cf3c6a9572b8a23bd39f94621d5b3c40a75b2a7d801cdd8`
- `inputs_hash`: `2097e4cb323d894d81f8d3e16615d9ceeb48c35784eca27bb99222c587e5cab9`
- 0 conflicts, no destructive SQL.

## Not in this change

- The 30 maker rows the access-basis check left out.
- FR-034: moving a maker-confirmed lead out of `unknown`.

T031 stays open for the 280 rows. T039 waits on the 8 emails.
