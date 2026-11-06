# NOISE Module Category, 2026-11-05

This applies [owner decision](OWNER_DECISIONS_2026-11-04.md) 16: add a NOISE Module Category, in its own PR. Decision 6's naming rules for noise and random applied "for now", until this.

## Why it matters

The patch engine already has noise sources. It collects a module as one when `module_type` contains NOISE, and it uses them in Voice and Clock-Rhythm patches. The catalog had no such category, so a real noise generator filed under VCO or VCF was treated as an oscillator or a filter, and never used as noise.

## Which rows

83 live rows mention noise in their name or tags, and most only have noise as one feature. A row moves only when its maker's own words make noise its main function. Every page was read by plain GET with robots.txt honoured and nothing paid.

| Row | Stored | Maker's words |
|---|---|---|
| ARC Noise Rainbow v1.1 | VCO | "source of analogue noise" |
| Bastl Noise Square | VCO | "generator of noises and square wave signals" |
| Doepfer A-118-1 | UTIL | "Noise / Random" |
| Ear Modular Nightrain | LFO | "noise module" |
| Erica Synths Hexinverter VCNO | VCO | "pure white noise" |
| Feedback STATIC | VCO | "collection of noise sources" |
| Hexinverter VCNO | VCO | "voltage controlled noise oscillator" |
| Hexinverter vcNOIZ | VCO | "digital noise source" |
| Manikk NOISE | VCO | "three different noise types" |
| Nonlinearcircuits Mobius PiLL | VCF | "chaotic noise module" |
| Plum Audio Noise | VCF | "noise generator" |
| Ritual Electronics Krach | VCF | "analogue noise generator" |
| SetonixSynth Sands of Time | VCF | "compact 1U noise source" |
| Sovage BOUCAN | VCF | "odd analog noise generator" |
| Sovage PITI BOUCAN | VCO | "odd analog noise generator core" |
| Steady State Fate Quantum Rainbow 2 | VCO | "two new noise outputs", on a page listing its noise colors |
| Tokyo Tape Music Center White Noise Generator Model 160 | VCO | "White Noise Generator" |

Each is corrected in `module_catalog` and in `modules` (`provenance/category-corrections-v6.json`). The old value is archived first.

## Rows left as they are

| Why | Examples |
|---|---|
| Noise next to another function | Verbos Noise & Filter, AJH MiniMod Glide & Noise, AvonSynth AVS-S&H-1, System80 850, Hinton ModMix II |
| Noise inside a voice or a drum | ST Modular HH, Hexinverter Mutant Clap, Orpho metal noise designer |
| The page couldn't confirm it today | Wildsync NOISE (a holding page), AMSynths Noisillator (robots.txt refused) |
| Still a hidden lead | Befaco Noise Plethora and Noise & Lag, Cwejman NS-4 |

## What changes

- **Vocabulary:** `population.MODULE_CATEGORIES` gains NOISE. The frontend's category filter lists whatever the API returns, so the code needs no change. NOISE takes the default module color, as UTIL, MIX and MIDI do.
- **Patches:** a Rig holding one of these modules may get different patches on its next generation. It gains a noise source and loses an oscillator or filter. Old runs don't change. The same revision and seed can give a different result ([#295](https://github.com/Zero-State-LLC/Patch-Hive/issues/295)).
- **Other readers:** `derive_patch_semantics.py` and `core/naming.py` already read NOISE.

## Not in this change

`build_category_overlay.py` still sends a whole-tag `noise` to VCO under decision 6, and `build_maker_overlays.py` still files by function. A newly crawled noise module needs a reviewed correction until those rules change.
