# Categories for Modules with jack lists, 2026-11-10

Slice N5 of the 2026-11-10 plan (#393). A Module with no category can't be used by any patch rule, so some well-known Modules with jacks on file never appear in patches. `overlays/module-catalog-category-v11.json` proposes a category for 9 of them. **Nothing has been loaded to staging or production.**

OBSERVED means read from a maker's document in the 2026-11-09 crawl, this checkout, or the public production API on 2026-11-10. INFERRED means reasoned from those.

| Rows | Count | Outcome |
|---|---:|---|
| Jack list on file, no category | 19 | 9 filled, 10 left for the owner |
| Drums filed as VCO | 4 | Not changed, [see below](#the-four-drums) |

The plan said about 20. OBSERVED: joining all 224 rows of `overlays/module-jacks-v1.json` with `/api/modules/` and `/api/modules/catalog` finds 19, each with `module_type` UNKNOWN and an empty `category`.

## How a row was decided

The test is the one [the A-138m record](CATALOG_A138M_ANALOGUE_SYSTEMS_2026-11-08.md) and the free reads used:

1. The maker's document says what the Module does.
2. Those words name one function. A row that names two stays empty, as Make Noise DXG did in [the free reads](CATALOG_FREE_READS_2026-11-05.md).
3. That function maps to one existing category, by `CATEGORY` or `NAME_CATEGORY` in `scripts/build_maker_overlays.py`, `TAG_CATEGORY` in `scripts/build_category_overlay.py`, or a named owner decision.

Every row was read by hand. A keyword match alone gets several of these wrong: the first match would file Bruxa as VCF for its filters, and VC Bend as LFO for the word modulation.

## The nine filled rows

| Row | Category | Rule | Source document |
|---|---|---|---|
| 2hp Tape Stop | FX | `effect` | [manual](https://www.twohp.com/s/2hp_Tape_Stop.pdf) |
| Alyseum PUSH | SEQ | `manual gate` | [manual](https://www.alyseum.com/wa_files/ALYSEUM_User_27s_20Manual_PUSH_V1_2_EN.pdf) |
| Ge0sync Synth GS1-O | VCO | `vco` | [page](https://geosyncsynth.com/2023/02/25/gs1-o/) |
| Make Noise Bruxa | FX | `delay` | [manual](https://www.makenoise-manuals.com/bruxa/bruxa-manual.pdf) |
| Mutable Instruments Warps | FX | `ring modulator` | [quickstart](https://pichenettes.github.io/mutable-instruments-documentation/modules/warps/downloads/warps_quickstart.pdf) |
| Pittsburgh Modular Collapse | FX | `bitcrusher` | [page](https://pittsburghmodular.com/collapse) |
| Pittsburgh Modular Crush | FX | `bitcrusher` | [page](https://pittsburghmodular.com/crush) |
| Pittsburgh Modular VC Bend | UTIL | Owner decision 17, `rectifier` | [page](https://pittsburghmodular.com/vc-bend) |
| Qu-Bit Electronix Prism | FX | `delay` | [manual](https://www.qubitelectronix.com/s/QB_Prism_Manual-6j8x.pdf) |

The overlay gives each row's reasoning in the reviewer's words. Three rows took more judgement than the others, so the owner may want to read them:

- **Warps.** The 2026-11-05 review left it empty because the keyword rule said LFO, which is wrong for an audio processor. The quickstart lists seven ways of combining two audio signals. Three of them are ring modulation and wavefolding, which are the catalog's FX words, and the other four also process audio.
- **Prism.** The maker says it sits among an effect, a filter and a looper. The delay line is its core, and the filter is one optional stage, so this one reads as an effect. Read strictly, it could join the rows that name two functions.
- **PUSH.** It has gate outputs only. Filed under SEQ, a patch rule can pick it to sequence a voice, and that voice's pitch cable finds no CV output. The cable stays `unresolved`, as it would for the existing manual-gate rows such as Sfeo PUSHR. ST Modular's Push is stored as UTIL and wasn't reviewed here.

## Left for the owner

| Row | What the document says | Why it isn't settled | Suggestion |
|---|---|---|---|
| Analogue Systems RS-260 | Voltage quantiser | Listed for the owner on 2026-11-08 and not yet decided. The `quantiz` rule gives UTIL, but only for the z spelling, and the catalog's two named quantisers split SEQ and UTIL | UTIL |
| Intellijel Scales | Dual quantiser and step sequencer, with quantising as the basic job | Names two functions, UTIL and SEQ. Same question as RS-260 | UTIL |
| Make Noise MMG | Both a filter and a low pass gate, built on vactrols | Names two functions, VCF and VCA. Make Noise DXG stayed empty for the same reason | VCF |
| Verbos Electronics Amp & Tone (2020 Version) | A VCA after a lowpass filter | Names two functions, VCF and VCA. The catalog's three combined rows hold VCF | VCF |
| Infrasonic Audio DISENTANGLER | Converts stereo to mid-side and back, and changes stereo width | No rule names this. One mid-side row is UTIL and one is FX | UTIL |
| Pittsburgh Modular Toolbox | Slew, noise, sample and hold, and inverter | Names four functions, in four different categories | UTIL |
| Rossum Electro-Music PANHARMONIUM Mutating Spectral Resynthesizer | Analyses incoming audio and drives a bank of oscillators with the result | The oscillator bank points to VCO, while the manual also calls it a processor. With no audio patched in and no saved spectrum selected it is silent, and a patch rule using it as a VCO patches no audio in | FX |
| Tall Dog µRings SE | Resonator derived from Rings | Decision 55 holds Rings-derived rows until a maker page settles the category, and this one again says only resonator | Match Mutable Rings, now VCO, or use the FX name rule |
| Tall Dog µo_C SE | Generic inputs and outputs, remapped by apps | What it does depends on the app loaded, the reason decision 17 keeps firmware platforms empty. It isn't one of the 10 rows that decision named | Leave empty |
| Tenderfoot Electronics Morse | Morse code sender and receiver: sound source, gate generator, practice tool | Names several functions | None |

One owner decision on quantisers would settle both RS-260 and Scales. INFERRED: the one SEQ quantiser, Blue Lantern's, got that category from its `trigger` tag, which comes first in the keyword order.

## The four drums

The brief asked for a correction manifest. None is included, because no existing category passes the test above.

| Row | Stored | Pitch jack in the document | Source document |
|---|---|---|---|
| 2hp Hat | VCO | None. Two trigger inputs, one output | [manual](https://www.twohp.com/s/2hp_Hat.pdf) |
| Mosaic Bass Drum | VCO | **Yes.** The manual and page say the pitch follows 1V/octave | [manual](https://www.mosaic1u.com/s/Bass_Drum-ean3.pdf) |
| ST Modular DRUM | VCO | None. One trigger input, one output | [page](https://www.st-modular.de/modules/drum) |
| Manikk DRM7 | VCO | None. Seven trigger inputs, one mix output | [page](https://manikk.com/product/drm7/) |

- **VCO is the catalog's category for a drum voice.** `CATEGORY` sends `drum` to VCO, `NAME_CATEGORY` sends hi-hats, snares and kicks there, and `TAG_CATEGORY` sends `percussion` and `kick` there. Reviewed changes follow it: the fill for Endorphin.es BLCK_NOIR, and the correction of Erica Synths Pico DRUMS from UTIL. Of the public rows whose name, tags or description mention drums or percussion, 47 are VCO, these four among them.
- **There is no drum category.** The vocabulary has 14 names, and none is for drums. Moving these four anywhere else would file them as something the maker doesn't say they are.
- **ST Modular's own site groups DRUM with its oscillators.** Most of its module pages in the crawl carry a group name, such as effects or sequencers, and DRUM's is the oscillator group.
- **Mosaic's pitch cable is correct,** so that row shouldn't move even if the others do.

The pitch cable comes from the sequenced-voice rule in `patches/engine.py`, which sends V/Oct to every module in the VCO list. On these rows the cable stays `unresolved`, because no CV jack is on file.

The owner has three options:

| Option | What changes | Cost |
|---|---|---|
| A. Engine rule (recommended) | No pitch cable to a Module whose complete jack list has no CV input. The plan lists this rule under Left out | A code change and an engine version. Also covers every other drum with a complete list |
| B. New category | A drum category, plus a patch rule that gates it | A vocabulary change and an engine change, and about 47 rows to re-file |
| C. Leave as they are | Nothing | Those patches keep an `unresolved` pitch cable |

### Other things found

- **Mosaic Bass Drum's jack list looks incomplete.** The document describes CV control of colour, decay and pitch, while `module-jacks-v1` lists only the trigger and the output. The loader won't overwrite a stored list, so a fix needs its own route.
- **Manikk's page gives DRM7 a status of planned.** It may not have shipped.
- **Discontinued products.** MMG, Collapse, VC Bend and DISENTANGLER are marked retired or no longer made on their makers' sites. Their rows are still live, and this doesn't affect a category.
- **TLM Audio METAX, a Warps clone, is VCO.** It wasn't reviewed here, and the same applies to the 8 ring modulators still filed as LFO.

## How the documents were read

All 23 documents came from the private 2026-11-09 crawl in the R2 bucket `patchhive-maker-assets`, as the jack lists did. Nothing was fetched from a maker, and nothing was spent. No value comes from ModularGrid. Each shard was checked against its recorded SHA-256, and each PDF against the hash that names it. Decision 65 covers descriptions and manuals on a maker's own site.

Quotes from these documents aren't committed. A manual's hash is the file's SHA-256, and a page's hash is the SHA-256 of the text stored for it in the crawl's `meta/pages.jsonl.gz`.

| Row | Kind | SHA-256 |
|---|---|---|
| 2hp Hat | manual | `bfc17f476ef09c91e905602d0c353ee7346ad61bf166fa45dc0b696fc2f4d1d0` |
| 2hp Tape Stop | manual | `42a5c5302227a340f9f327ae8ba90acd730b1a27d21ea9ac062306be9021a3cf` |
| Alyseum PUSH | manual | `8f424ea257249c16b5496f951b065501c60b37dafceca0a653c77cdb6435d8cf` |
| Analogue Systems RS-260 | manual | `e304272be320657de33d3b00e10756c28e993cc97a0cc7846e4e6daba499a55e` |
| Ge0sync Synth GS1-O | page | `b67c612af7ad2e4458c5b3b480b0965be839652784d125ce1216fc5920edabc3` |
| Infrasonic Audio DISENTANGLER | manual | `a2d43b5cb07e7571e815ffac0f8354d453582ae8834dec112c6b8ec20556c773` |
| Intellijel Scales | manual | `a4727b55c0ba85c91d4be3d01e4bcd7c09d6ee373449410c6eb1eb66e70647cf` |
| Make Noise Bruxa | manual | `bda01d009f0915837ac7fbb36db9478dc2456c59d2d209e1225a421c623b3e9c` |
| Make Noise MMG | manual | `a07b5586b5368acf9d01f8cd1b17854e6271dbecefdec917e1f65c3c8ae89c6d` |
| Manikk DRM7 | page | `f2ffc23b03c8af1aba99dc680dca7cbb310e2779bd79700030bb577af9362037` |
| Mosaic Bass Drum | manual | `4ae2583aec58be758263f2d23269f5a512efb0acde6c1d873048909865796da8` |
| Mutable Instruments Warps | manual | `6b5ed9f20cf3c76197765495aa325f37b535c88d54c33c38081ee6a21470d915` |
| Pittsburgh Modular Collapse | page | `2d70f93eb81f0090fe070b365066db8a57d7cb94a4f55da027d2b474d1191fe9` |
| Pittsburgh Modular Crush | page | `c33a8b6a991a768a4678596539d86c126985675c9bb0259fc92e5e8da37e9b17` |
| Pittsburgh Modular Toolbox | page | `28916afd634e2f94ef45a4a8d79665708e16d9a52a733a6507f2ddd5267098c0` |
| Pittsburgh Modular VC Bend | page | `de33d851b928d96129f129303b85e8ac69d54bb785c114722e6310a78e6e19d0` |
| Qu-Bit Electronix Prism | manual | `87e0091ca1fcec83a467a5e80e272d37f38a10c22c0ba4a6eaf0ba319e35637c` |
| Rossum Electro-Music PANHARMONIUM | manual | `53f1e18c44d7f1c7b36ad87da33ab4c3959511935537f451a2f41a6ec296eca0` |
| ST Modular DRUM | page | `eeb3a4d5d6af274535d216d6809a2917e47503bc45802ea5e66970032b70a629` |
| Tall Dog µo_C SE | manual | `a98aac655fa6a5775f86079adb4e93d52d23baa2a091843205ea88877763dc08` |
| Tall Dog µRings SE | manual | `1d28d0cbfbb54b5e9d4d77d0397613e2527fbad72054e9deda2ae2aeb95a33a9` |
| Tenderfoot Electronics Morse | manual | `cf4613949ec5a5657a7a1767d08cf24ac7335346652a5308c02507e26d27eca0` |
| Verbos Electronics Amp & Tone | manual | `12676805e6cbcf3e753231f0822c4830e7fb717fa399fe2129636cc31bdd1857` |

## What a Rig sees

Once loaded, these 9 Modules can join patches. The revision hash omits `module_type`, as decision 56 records, so a Rig holding one of them can get different patches from the same revision and seed. Old runs don't change.

## Local check

On a throwaway Postgres, loaded with everything except this overlay:

| Step | Result |
|---|---|
| Dry run | 9 categories filled, 9 `module_type` values set from the placeholder, 9 values archived, 0 conflicts |
| Apply | All written |
| Second dry run | Plans nothing |
| Load from empty | The same 9 categories in `module_catalog` and `modules` |

It gave the same `plan_hash` as both deployed dry runs below.

## Dry run

The owner gave the go-ahead on 2026-11-10. Both runs went through `db-load.yml` from branch `claude/n5-catalog-category-fills` at `ff312a9`. **Neither run wrote anything.**

| Environment | Run | Result |
|---|---|---|
| Staging | [42926869828](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42926869828) | 9 categories to fill, 9 `module_type` values to set from the placeholder, 9 old values to archive. 0 conflicts, no destructive SQL, table counts unchanged |
| Production | [42926874415](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42926874415) | The same as staging, with the same hashes |

The owner's yes on each load needs these two hashes:

- `plan_hash`: `0dd5d92289d863d27e22d214bdc0bb877dc04204bd39a9e016d1cf71af9ab1c0`
- `inputs_hash`: `9985cf9ad95de5e8786b95cf7ce9d66093bc17850ca2c85757b627a2be1ed97c`

The plan hash covers every statement and its parameters, so both databases would receive the same writes. An apply refuses if the plan or the committed inputs have changed since, and this record isn't an input.

The one difference between the databases is outside this plan: `catalog_value_archive` holds 6,235 rows on production and 6,351 on staging.
