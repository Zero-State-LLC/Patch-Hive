# Catalog rows whose tags point to two categories (2026-11-03)

Project card: "[catalog] Review 24 rows whose tags point to two categories". Done offline: committed data only, no maker-page, feed or listing fetch, no database load. The owner holds all catalog fetching until the maker-permission basis is signed off ([EXTERNAL_SOURCE_POLICY.md](../EXTERNAL_SOURCE_POLICY.md)). OBSERVED means read in this checkout; INFERRED means reasoned from it.

## How the rows were listed

`scripts/build_category_overlay.py --list-ambiguous` rebuilds the loader's catalog in memory (the seeds plus every committed overlay, no database), matches each uncategorized row to its maker-crawl page, and prints the rows whose whole tags point to more than one category. It writes nothing.

| | Rows | Live |
|---|---:|---:|
| Before this change | 24 | 20 |
| Settled here (`overlays/module-catalog-category-v2.json`) | 9 | 9 |
| Left after this change | 15 | 11 |

The 4 retired rows are In The Trees Tour and the Meng Qi DPLPG listed under Mad Rooster Lab, Olitronik_lab and Vintage Synth Lab (`catalog-retirements-v2`). They need nothing.

Of the 20 live rows: 9 are settled, 4 wait on the noise-versus-random convention below, and 7 need the maker page.

## Settled from committed data

One rule decides all nine: a tag that says how a module is built or played (`passive`, `touch`) yields to a tag that says what it does. Each entry in `module-catalog-category-v2.json` gives its evidence and cites the committed files it rests on. The loader fills nulls only, so a category already stored is never changed.

| Row | Tags → categories | Category | Evidence (OBSERVED) |
|---|---|---|---|
| beepboop-electronics-2hp-passive-touch-ctrl | passive, touch, control → SEQ, UTIL | SEQ | The name "Touch CTRL" names a hand controller, and controllers are SEQ (`NAME_CATEGORY`, `TAG_CATEGORY`). The brand's other passive rows take their function's category: Passive LPG V1 is VCA. |
| folktek-quiet | mute, touch, CV, audio → SEQ, UTIL | UTIL | mute is the function. The maker's image file is `Folktek-Quiet-Mute_Front-Face` (catalog-additions-v2). |
| jasmine-olive-trees-tour | random, expander, CV → LFO, UTIL | LFO | random is the only function tag. "expander" names the separate Tour Expander product, which has its own catalog row. |
| jolin-getrekt | waveshaper, touch, CV, analog → FX, SEQ | FX | The maker's shop title for the same product reads "touch waveshaper". |
| jolin-getrekt-touch-waveshaper | waveshaper, touch, CV, clipping → FX, SEQ | FX | Same product as jolin-getrekt. Retirement is proposed below. |
| plum-audio-ex2 | CV, Expander, Controller, Soft Parameters → SEQ, UTIL | UTIL | Its maker URL is the same as plum-audio-ex2-cv-expander's, which is already UTIL. The sibling CV expanders ex6 and ex12 are UTIL too. |
| signs-modular-peq | equalizer, passive, drive, Pultec → FX, UTIL | FX | equalizer, drive and Pultec are all EQ or drive. The brand's ampeq is FX. |
| tobinski-dynamics | compressor, expander, eq, exciter → FX, UTIL | FX | Next to compressor, "expander" means the dynamics processor. The name is "Dynamics". |
| york-modular-vaclpgv2 | low-pass gate, vactrol, passive → UTIL, VCA | VCA | The maker URL reads `passive-vactrol-low-pass-gate`, and low-pass gates are VCA (`TAG_CATEGORY`). |

## Waits on the noise-versus-random convention

| Row | Tags | Option A gives |
|---|---|---|
| wildsync-noise | noise, random | VCO (A1: the name says noise) |
| steady-state-fate-quantum-rainbow-2 | noise, random | VCO (A2) |
| nonlinearcircuits-pseudo | noise, random, pattern, generator | LFO (A3) |
| nonlinearcircuits-1u-reverse-sigmoid | chaos, CV, noise, 1u | LFO (A3) |

### Proposal

Today `TAG_CATEGORY` sends `noise` to VCO (a sound source) and `random`, `chaos` and `S&H` to LFO (a modulation source). A row tagged with both is left empty. The precedent is VCO: v1 filed 10 noise-tagged rows under VCO and one under LFO (ear-modular-nightrain, whose tags also say "modulation").

The catalog has no NOISE category, but the patch engine has one. OBSERVED:

- `backend/patches/engine.py:136` collects module type NOISE as noise sources for its percussion patches (`:341-354`, `:545`).
- `backend/core/ops/derive_patch_semantics.py:23` reads NOISE or RANDOM as a random output.
- A catalog row becomes a module with `module_type = category` (`backend/modules/catalog_routes.py:279`).

So a catalog noise module filed under VCO never counts as a noise source in patch generation.

| Option | What it does | Cost |
|---|---|---|
| A. Keep the vocabulary, add a rule | A1: if the name names one function, use it (noise → VCO; random, S&H or chaos → LFO). A2: noise and random only → VCO, as v1 did. A3: noise among modulation tags only (chaos, CV, pattern, generator) → LFO. A4: noise next to another function (ring mod, filter, percussion) → the existing rules, else the maker page. | A rule and a test. Settles the 4 rows above. |
| B. Add NOISE to the catalog vocabulary | Noise-first rows become NOISE, and the engine uses them as noise sources. | The frontend category filter, the CATEGORIES set in the tests, and `correct` entries for the noise rows already under VCO (10 from v1, plus any from A). The fill-null loader cannot move them. |
| C. Leave these rows empty | Status quo. | 4 rows stay without a category. |

**Recommendation:** A now, because it changes no vocabulary and matches v1. Put B to the owner as a separate product question, since it changes patch generation. Choosing B later costs the same either way: the existing VCO noise rows need `correct` entries regardless.

## Needs the maker page (after the permission decision)

| Row | Tags → categories | What the page must answer |
|---|---|---|
| erogenous-tones-blip | preset, random, gate, expander → LFO, UTIL | Is BLIP a random/gate source or an expander for another module? |
| laine-modular-vole | EQ, 1U, level, boost → FX, UTIL | An EQ (FX), or a level/boost utility? |
| nekyia-circuits-ouija | glide, noise, sub, ring mod → FX, VCO | A voice (sub, noise), or a ring modulator? |
| nonlinearcircuits-coupled-comparators | comparator, chaos → LFO, UTIL | A chaos source built from comparators, or a comparator utility? |
| nonlinearcircuits-spasm | chaos, vactrol, CV, LDR → LFO, VCA | A chaos source, or a vactrol VCA? |
| selestium-modular-osculatrix-for-the-times-intersect-in-ways-we-cannot-fathom | passive, touch → SEQ, UTIL | A touch controller (SEQ), or a passive utility? Neither tag names a function. |
| tsyklon-labs-chaos-divider-hv | chaos, divider, expander, set → LFO, UTIL | A chaos source or a clock divider (SEQ)? Is "expander" part of the set? |

## Proposal: retire the duplicate Jolin GETREKT

OBSERVED: the same product holds two live rows in both `module_catalog` and `modules`, from two maker pages in the v2 crawl (catalog-additions-v3). Both rows have 4 HP, +12 V 35 mA, −12 V 30 mA and 18 mm depth.

| Slug | Name | Maker URL |
|---|---|---|
| jolin-getrekt | GETREKT | https://jolin.tech/modules/getrekt |
| jolin-getrekt-touch-waveshaper | GETREKT ⇝ touch waveshaper | https://jolin.tech/shop/p/getrekt |

**Proposal:** keep `jolin-getrekt`, which has the plain product name, and retire `jolin-getrekt-touch-waveshaper`, whose shop title appends a tagline. A retirement tombstones the `module_catalog` row and the `modules` row. It never deletes them. A draft entry for a `catalog-retirements-v3.json` follows. It is not committed: retirements are owner decisions, as v1 and v2 record.

```json
{
 "slug": "jolin-getrekt-touch-waveshaper",
 "brand": "Jolin",
 "name": "GETREKT ⇝ touch waveshaper",
 "owner": "Jolin",
 "evidence_url": "https://jolin.tech/shop/p/getrekt",
 "reason": "duplicate: the maker's shop page for GETREKT, held as jolin-getrekt (same HP and power)",
 "kept_as": "jolin-getrekt"
}
```

NOT_COMPUTABLE offline: whether any rack in production places the `modules` row being retired.

Two more pairs of the same kind turned up during the review:

- **Jolin ROSA.** `jolin-rosa` (modules/rosa) and `jolin-rosa-infinite-morpher` (shop/p/rosa) are both UTIL, with the same HP (6) and the same power. The same proposal applies: keep `jolin-rosa`.
- **Plum Audio ex2.** `plum-audio-ex2` (v2 crawl, 12 HP) and `plum-audio-ex2-cv-expander` (v1 crawl, 2 HP) share one maker URL. The two HP values disagree, so which row to keep, and which HP is right, needs the maker page. The category is UTIL either way.

A local load from the committed seeds holds 22 maker URLs with two live rows each (44 rows). Some of these are brand spellings, such as Joranalogue Filter 8 and Generate 3; others are kit and assembled pairs. That is a separate review, not done here.

## Owner decisions needed

1. Retire `jolin-getrekt-touch-waveshaper` (and `jolin-rosa-infinite-morpher`)? Yes or no.
2. Noise versus random: A (recommended), B or C.
3. The maker-permission basis. The 7 rows above, plus the Plum ex2 HP, wait on it.
