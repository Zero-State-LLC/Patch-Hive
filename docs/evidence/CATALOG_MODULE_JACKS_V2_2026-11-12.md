# Module jack lists, second overlay, 2026-11-12

`overlays/module-jacks-v2.json` proposes 38 more jack lists: 234 jacks from 29 makers, read from 13 user manuals and 25 maker pages. None of them is in `module-jacks-v1.json`, which loaded 224 lists on 2026-11-10 (see [CATALOG_MODULE_JACKS_2026-11-09.md](CATALOG_MODULE_JACKS_2026-11-09.md)).

## Where they came from

No new readings and no spend. `scripts/read_module_jacks.py decide --one-full` re-ran the gate over the 2026-11-09 readings, accepting a list when both readings gave the same jacks and at least one called the document complete. Every other gate stayed, and two were added:

- A name that stands for several jacks is refused, such as "Trigger inputs", "Outputs (OUT)" or "FM 1&2 input". A plural followed by a qualifier, as in "LP Outputs Left", is one jack.
- In a document about several channels, a list that marks channel 1 and nothing later is refused, as with one channel of a dual Module. "1 Volt" isn't a channel mark.

That accepted 335 lists, 115 of them not in v1. Leaving out the one list the first hand check found incomplete and the gates didn't catch left 114 candidates.

## Hand check

Each sample of 25 was drawn at random from the lists not yet checked, and each list was compared with its document. The verdicts are in `jack-list-reviews.json`.

| Round | Gates | Complete | Incomplete | Wrong | Unclear |
|---|---|---|---|---|---|
| 1 | before the two new gates | 20 | 5 | 0 | 0 |
| 2 | with them | 18 | 4 | 1 | 2 |

About one list in four is not complete. That's well short of v1, where 23 of 25 checked lists were right, so FR-041 now asks for a hand check whenever only one reading called the document complete. **v2 holds only the 38 lists the hand checks found complete.** The other 76 stay out until someone checks them.

The misses were mostly a missing second channel or extra CV jacks the document describes further down, which two readings by one model can both miss.

## Noticed, not changed here

- Four lists already loaded from v1 group several jacks under one name: Make Noise QPAS ("!!¡¡ Inputs"), AvonSynth AVS-S&R-1 ("Send Inputs" and the like), Pittsburgh Modular Sequencer ("Outputs (OUT)") and ACL Variable Sync VCO ("FM 1&2 input"). The loader never overwrites a declared list (FR-041), so fixing them needs a correction.
- Infrasonic Warp Core's catalog row says 4 HP, but its manual says 12 HP, and 4 HP is its expander's width.
- Hexdevices Osiris, Mosaic Clock and Mosaic Mono Reverb are 1U tiles.
- No reading used a trigger or clock type. Trigger and clock jacks came back as gates, which the engine accepts for every gate role.

## Files

| File | SHA-256 |
|---|---|
| `data/synth-catalog/overlays/module-jacks-v2.json` | `0947dc1ad2dfb0133bb63312f507b134757c0eaffff4d06e2e9ae5ba7fdfe7d2` |
| `data/synth-catalog/jack-list-reviews.json` | `625db3f2987647f54017b435587d52d83422fa540b77aa423318569de4417c82` |
| Private proposal, with the quote behind every jack (not in this repository) | `f5d3337eeeca849950ff8201f1e42444103a44e1ea5cdcd14832654b608202b5` |

The loader fills `io_ports` only where it's empty, and a list that differs from a stored one is reported as a conflict and left alone. A load needs the owner's yes on its plan and inputs hashes.
