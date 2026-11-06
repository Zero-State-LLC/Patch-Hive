# Second names in the public catalog, 2026-11-05

The [lead search](CATALOG_LEAD_SEARCH_2026-11-05.md) found public rows that list one module under two names. This review covers every public row that shares a maker page with another public row, not only the 18 that record named, because the same fault runs through the maker crawl too.

It retires 38 rows, which would take the public catalog from 3,426 to 3,388 rows. Retiring follows [spec 003 FR-036](../../specs/003-catalog-dataset-pipeline/spec.md): a tombstone with a reason, never a deletion. The list is `data/synth-catalog/overlays/catalog-retirements-v5.json`.

## Which row stays

1. The row holding more facts: category, power, depth.
2. If tied, the maker-sourced row over one that started as a lead.
3. If still tied, the plain product name over one with a tagline, as in [owner decision 7](OWNER_DECISIONS_2026-11-04.md).

Where the retired row alone held a fact, the row that stays now takes it:

| Row that stays | Fact | Source |
|---|---|---|
| Endorphin.es GRAND TERMINAL | Category VCF | "Dual 8 mode VCF / VCA" on its page |
| Endorphin.es AUTOPILOT | Category UTIL | The retired row's category. The page says "autotuner", and no catalog rule maps that word, so this is a judgment call |
| Expert Sleepers ES-40 | Depth 51 mm | "Module depth: 51mm" on its page |

## What retires

### Second names and tagline names: 21

| Retires | Stays |
|---|---|
| 4ms QCD: Quad Clock Distributor | 4ms QCD |
| Aircraft Designs EMBER | Ember Analog Mid/Side Saturator |
| Bastl Knit Rider Expander | Knit Rider EXP |
| DIE Systems 16 STEP SEQUENCER (Build to Order) | 16 STEP SEQUENCER |
| DPW Design AV3, Attenuverter, Mixer, Comparator | AV3 |
| Doepfer A-106-5 SEM | A-106-5 |
| Doepfer A-110 | A-110-1 |
| Expert Sleepers ESX-4CV CV Expander | ESX-4CV |
| Guru Gara Synth Dual Ringmodulator / Eurorack Platine und Frontplatte | Dual Ringmodulator |
| Make Noise Rene 2 | René |
| Make Noise Rene | René (Classic) |
| Modulaire Maritime VC Crossfader | R / K |
| Qu-Bit Chord | Chord v2 |
| Rides in the Storm DPM Dual Passive Multiple | DPM |
| ST Modular Chiasso | Chiasso V2 |
| SetonixSynth Noise Complaint | Noise Complaint 1U |
| Sitka Gravity Eurorack Clock and Trigger Sequencer | Gravity |
| York Modular Diode ladder VCF (6HP) | Diode ladder VCF |
| York Modular FRiSK: fixed Sallen-Key filter bank (4HP) | FRiSK: fixed Sallen-Key filter bank |
| York Modular SPLERGE: Stereo split/merge module | SPLERGE |
| York Modular TinyDVCOv2: AVR-based wavetable digital VCO | TinyDVCOv2 |

### Misread names: 6

| Retires | Stays |
|---|---|
| AT1 4 CV CHANNEL | 4 CV CHANNEL MIXER |
| AniModule MixMan Mixer/Man | MixMan Mixer/Manipulator |
| Expert Sleepers Sleepers | ES-40 SPDIF Interface |
| Noise Engineering : Basimilus Iteritas (Legacy Hardware) | Basimilus Iteritas |
| Plum Audio SCILLATOR | RO'VED |
| Steady State Fate State Gate | Steady State Gate |

### Finish variants: 11

The maker's page sells one module in several finishes, and the finish doesn't change anything a rack depends on.

| Retires | Stays |
|---|---|
| ADDAC ADDAC200S Size Matter black | ADDAC200S |
| Endorphin.es Autopilot (golden) | AUTOPILOT |
| Endorphin.es Blck_Noir (black) | BLCK_NOIR |
| Endorphin.es Cockpit (black), Cockpit (golden) | COCKPIT MK1 |
| Endorphin.es Furthrrrr Generator (black), (golden) | FURTHRRRR GENERATOR |
| Endorphin.es Grand Terminal (black), (golden) | GRAND TERMINAL |
| Endorphin.es Shuttle Control (black) | SHUTTLE CONTROL |
| Endorphin.es Shuttle System (golden) | Shuttle System (black) |

ADDAC's site answers with a holding page today, so that row rests on the pages read on 2026-11-05 before that began.

**Two corrections to the lead search.** It promoted QCD: Quad Clock Distributor and missed that 4ms QCD covers the same page, because the two addresses differ after `p=620`. It also promoted both Shuttle System colours, and this review keeps one. Both rows reached production on 2026-11-06.

## What a retirement does to a Rig

A placed module stays placed, and every read of that Rig warns that it's retired, with the reason. The reason names the row that stays. Nothing is removed from a Rig automatically, and old runs don't change.

The warning's list of alternatives only looks under other brands, so for these rows it shows none, and the reason text carries that information instead.

The loader's receipt now reports how many Rigs hold a module the plan retires (`retired_on_racks`): counts only, with no user data, so the owner can read the number before approving a load.

Patches generated for a Rig holding a retired row can change.

## What stays

| Rows | Why |
|---|---|
| Plum Audio ex2, ex2 CV Expander | The page states both "3u/12hp" and "3u / 2HP", so neither stored width can be called wrong. The maker needs to say which |
| Endorphin.es Milky Way 1U (silver) | It's a separate format. The page says the 1U version is 22 HP, and this row stores 6 HP, so the width looks wrong. Not changed here |
| Stochastic Instruments Strange-R, Strange-R Combo (Studio + Live) | The page sells a bundle of two sizes, so neither row is clearly the second name |
| Analogue Systems RS-650, RS-650 Echo Reverb | robots.txt didn't answer, so the page couldn't be read |
| Joranalogue Filter 8, Generate 3 (held under both "Joranalogue" and "Joranalogue Audio Design") | A brand split, which needs its own fix |
| Mutable Instruments Ripples, Tides (2014 version) | The same, because "Mutable Instruments" and "Mutable instruments" are separate brands |
| Expert Sleepers ES-3, ES-6, ESX-8GT and ESX-8MD revisions | The page names each revision |
| Atonal Circuits SEE, SEE (V1) | The page names a legacy V1, and the power differs |
| Bastl Knit Rider, Doepfer A-180-1 and A-180-2, the MetaModule expanders | Real separate modules that share a page or an address pattern |

## Found along the way, not changed here

- **Two brand splits:** "Mutable Instruments" (13 rows) and "Mutable instruments" (19), and "Joranalogue" (2) and "Joranalogue Audio Design" (27).
- **Guru Gara Dual Ringmodulator** is filed under LFO, and Strange-R under LFO though its page describes a sequencer.
- **77 pairs of public rows** have nearly the same name and the same width on different pages. Most look like real editions and kits, such as `Maths` and `MATHS (Classic)`. These weren't reviewed.
- **The 18 second names the lead search held back** stay hidden, so they don't need retiring.
