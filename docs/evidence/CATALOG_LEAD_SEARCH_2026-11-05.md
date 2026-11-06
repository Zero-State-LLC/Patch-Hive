# Search for maker pages for hidden leads, 2026-11-05

The [lead promotion](CATALOG_LEAD_PROMOTION_2026-11-05.md) left 344 leads hidden, and 283 of them had no maker page on record. This search looked for those pages. It confirms 46 rows, which would leave 298 hidden.

The rules are the same as the promotion's. Every page was read by plain GET through `data/synth-catalog/catalog_scrape.py`: robots.txt honoured, the paid cap at 0, and the paid-service keys unset. ModularGrid wasn't fetched. A site that refused stays refused. This is an engineering policy under [ADR 0002](../adr/0002-maker-permission-basis.md), not legal advice, and the [owner decisions](OWNER_DECISIONS_2026-11-04.md) send the wider question to counsel (decision 39).

`data/synth-catalog/receipts/lead-search-2026-11-05.json` gives the outcome for each of the 283 rows, with no page text.

## How it looked

1. **Sites already on record.** For a maker with a known site, it read the home page, the sitemap and the product list pages, then matched those addresses and link texts to the row names.
2. **A maker's own name as the address.** For a maker with no known site, it tried that name as a domain. A site counts only if its pages show it's the maker's own. `7dials.com` belongs to a fund manager, and `abstractdata.com` is for sale, so neither counts.
3. **Web searches.** Eight searches looked for sites still missing. They found 3 addresses, and none gave a read, so no promotion rests on a search result.
4. **Row-by-row review.** Each candidate page was read by hand before a row was accepted.

## Result

| Outcome | Rows |
|---|---:|
| **Confirmed by the maker's page, and promoted** | **46** |
| A site was read, and it has no page for the row | 68 |
| robots.txt didn't answer (Dreadbox 35, Adventure Audio 5, Instruo 4, ACXSynth 3) | 47 |
| The site answers with a holding page (ADDAC 19, Antumbra 7, Abstract Data 6, 333modules 3, AI Synthesis 2) | 37 |
| Refused on an earlier read, and not read again (Befaco 29, AMSynths 2) | 31 |
| Second name for a row that's already public | 18 |
| No maker site found (Aion Modular 5, 5540lab 3, 7 Dials 2, AnalogRobotOrchestra 2) | 12 |
| Page read, but it doesn't confirm the row | 9 |
| robots.txt disallows the crawler (Analog Ordnance 8) | 8 |
| The page has no text by plain GET (Antimatter Audio 4) | 4 |
| The site answered 403 (Aemit 3) | 3 |
| **Total** | **283** |

Aion Modular's old address now answers as an unrelated gambling site, so it was left alone.

## What it promotes

The list is `data/synth-catalog/overlays/lead-promotions-v2.json`: each row's slug, maker page, content hash and a short quote.

| Maker | Rows |
|---|---:|
| Expert Sleepers | 16 |
| Erica Synths | 9 |
| Cwejman | 4 |
| 1010 Music, Altered State Machines, Doepfer | 3 each |
| Afterlife Laboratories, Endorphin.es | 2 each |
| 1V/Oct, 4ms Company, Allen Synthesis, Animal Factory Amplification | 1 each |

### Other changes in this load

| Change | Rows | File |
|---|---:|---|
| Category corrected, in both tables | 9 | `provenance/category-corrections-v7.json` |
| Category filled | 11 | `overlays/module-catalog-category-v8.json` |
| Width filled from the maker's page | 27 | `overlays/module-catalog-hp-v10.json` |

Laserbox stays with no category. Its page says it generates visual effects for lasers, and no category in the vocabulary fits that by the catalog's own rule.

The loader now reads every `lead-promotions-v*.json` file, adds up the counts, and archives each file under its own batch.

### Category corrections

| Row | Stored | Corrected | Maker's word |
|---|---|---|---|
| Expert Sleepers Disting mk3 | VCO | UTIL | "multifunction" |
| Expert Sleepers ES-3 MK3 | MIDI | UTIL | "Interface" |
| Expert Sleepers ES-40 | SEQ | UTIL | "Interface" |
| Expert Sleepers ES-5 mk2 | MIDI | UTIL | "Expander" |
| Expert Sleepers ESX-8MD mk2 | SEQ | MIDI | "MIDI" |
| Expert Sleepers FH-1 | SEQ | MIDI | "MIDI" |
| Expert Sleepers FH-2 | UTIL | MIDI | "MIDI" |
| Erica Synths Mutant Brain | UTIL | MIDI | "MIDI" |
| Erica Synths Synth Voice | UTIL | VCO | "Voice" |

These changes can alter the patches generated for a Rig holding one of these rows.

## Judgment calls for review

- **A named revision counts.** ES-3 mk2, mk3 and mk4 share one page, and it names each of them, so each is promoted.
- **A row with no version can rest on a page for one version.** Mixer/Splitter rests on a page for Black Mixer/Splitter V2, Erica Fusion VCF on Fusion VCF V2, Polivoks VCF on Black Polivoks VCF V1, and Orobas on Orobas II. These 4 rows take no width from those pages.
- **A DIY kit page can confirm a row.** Dtech VCF, Polivoks VCA and Synth Voice rest on Erica's kit pages. Dtech VCF and Synth Voice take their widths from those pages, and Polivoks VCA doesn't, because its page is for the II kit.
- **Colour names follow the earlier load.** Shuttle System (black) and (golden) are both promoted, because the page lists both colours and no public row covers it yet.
- **A blog post can confirm a row.** Pico VC EG's product address is gone, so it rests on the maker's own announcement.
- **Mutant Brain is an Erica row.** The page calls it Hexinverter Mutant Brain, and its manufacturer field says Erica Synths.

## Held back

**18 second names.** A lead stays hidden when a public row already covers the same product on the same page. Promoting it would list the module twice:

| Lead | Already public as |
|---|---|
| Aircraft Designs CASCADE, FL, LD | Cascade Discrete VCA Compressor, FL High-Quality Balanced Line Input, LD High-Quality Balanced Line Output |
| AJH Synth MiniMod Dual Contour Generators | MiniMod Contour |
| Alright Devices Chronoblob 2 Black & Gold Panel | Chronoblob2 |
| Animal Factory Vivisect | Eurorack: Vivisect 4 Channel CV Processor/Offset and Noise Source |
| Bastl CV Trinity Expander, Solenoid CV Velocity Expander | CV Trinity Exp, Solenoid Exp |
| Endorphin.es Shuttle Control (golden), Shuttle Mate (black), Shuttle Mate (golden), Two Of Cups (black) | SHUTTLE CONTROL, SHUTTLE MATE, TWO OF CUPS |
| Expert Sleepers ES-1 (DB25 version), ES-2-2, ESX-8MD (mk1) | ES-1, ES-2 CV/Audio Interface, ESX-8MD MIDI/DINsync Expander |
| Make Noise Rene (Limited Edition White), modDemod | René, modDemix |
| Mutable Instruments Braids (old version) | Braids |

**9 pages that don't confirm the row:**

| Row | Why |
|---|---|
| Cwejman VM-1 | The page is for VM-1S |
| Doepfer A-170-1 | The page names A-170 only |
| Erica Synths Matrix Mixer | The page is for a desktop unit |
| Make Noise Strega | The maker gives it the 0-COAST's form factor, so it isn't a rack module |
| AnalogFX SER-2020 | The page calls it a desktop synthesizer |
| 1010 Music Toolbox (Black) | The page doesn't name a black panel |
| AniModule SOB v1 | The page names SOB, not v1 |
| 4ms MetaAIO | It's named only on the MetaModule's page |
| Intellijel Dr. Octature | The address answers with the legacy list |

## Widths left out

- **Cwejman D-LFO:** the row is promoted, but its width stays marked `legacy_unsourced`. The page says "70.6 mm" and "12 TE", which don't agree, because 70.6 mm is about 14 HP. The owner's email to the maker still stands.
- **Doepfer A-155:** `maker-corrections-v5` already takes a stored 4 to the 50 HP the page states, so nothing was added.
- **Endorphin.es Shuttle System:** the page states 84 HP, which is past the overlay band of 1 to 42 HP, so the width stays empty.
- **Expert Sleepers ES-4:** the page states both 8 HP and 4 HP, so the width stays empty.

## Found along the way, not changed here

- **18 rows from the earlier promotion share a page with another public row.** Some are real pairs, such as Knit Rider and its expander. Others look like second names, such as Autopilot (golden) beside AUTOPILOT, and BLCK_NOIR beside Blck_Noir (black).
- **A public row named "Sleepers"** (`expert-sleepers-sleepers`, 6 HP) points at the ES-40 page. It looks like a crawl misreading of that module, so once ES-40 is public the module appears twice.
- **Dreadbox "Milky Way 1U (silver)" and "Two Of Cups (black)"** carry names of Endorphin.es products. Both stay hidden.

## Not in this change

T031 and T039 stay open. This list hasn't been loaded anywhere yet.
