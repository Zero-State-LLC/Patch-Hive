# Corpus photo search, 2026-11-02 (spec 007 T010b)

Run of `scripts/vision/find_corpus_photos.py search` under approval `corpus-photos-2026-11` (owner: 300 context.dev searches). Counts and rights only; no image bytes are in the repo. Files stay outside any checkout, in `~/patchhive-corpus/` on the operator's machine.

## Inputs

- 300 identities from `starter`: every Mutable Instruments, Mannequins, Instruo, Qu-Bit, Xaoc, Squarp, Monome, Music Thing, Mordax, Frap, Verbos and Vermona row, then Make Noise, Intellijel, Doepfer, 4ms, ALM, Erica, Befaco, Noise Engineering, Joranalogue, Expert Sleepers, Bastl, WMD, Endorphin.es, Pittsburgh, 2hp, Steady State Fate, LZX, Cwejman, Dreadbox and ADDAC taken in turn.
- Query per identity: `"<brand> <name>" eurorack (site:commons.wikimedia.org OR site:flickr.com)`.

## Spend

| | Value | Source |
|---|---|---|
| Searches | 300 | `summary.json` |
| Paid (context.dev) searches | 300 | DuckDuckGo's free endpoint gave no results for any query, so each fell through to context.dev |
| Ledger paid fetches | 2569 → 2869 (+300) | `receipts/scrape-ledger.json` |
| Ledger context.dev credits | 1116 → 1411 (+295) | same |
| Firecrawl calls | 0 (78 fallbacks skipped: no key in the process) | `receipts.jsonl` |

The approval's cap (300 fetches, 300 credits) is used up: 0 searches remain.

## Results

| Stage | Count |
|---|---|
| Result URLs | 2371 |
| Commons File / Flickr photo pages | 1372 (75 distinct Commons pages) |
| Flickr photo pages refused by robots.txt | 108 (no Flickr row) |
| Pages with an accepted license | 664 rows (CC BY-SA 2.0 302, BY-SA 4.0 277, BY 2.0 45, PD 20, BY-SA 3.0 13, CC0 6, BY 3.0 3, BY 4.0 2) |
| Excluded for license | 4 (`attribution_missing`) |
| Rows whose page names the searched maker and module | **6 rows, 2 images** |

The search engine answered most module queries with the same few generic photos ("Eurorack Modular Synthesizer.jpg" came back for 158 different modules). The first version of the tool kept those rows and proposed the searched module as their identity. This PR adds a stricter check: a row stays a candidate only if its page names the maker and the module as a phrase. Applying that check to the stored rows (`refilter`, no network) leaves:

| Proposed identity | Photo | License, author |
|---|---|---|
| `doepfer-a-101-2`, `-a-102`, `-a-103`, `-a-104`, `-a-106-1` | Commons: Doepfer Eurorack, 2016 NAMM Show (one rack, about 20 modules) | CC BY-SA 2.0, Daniel Larsen |
| `verbos-electronics-complex-oscillator` | Commons: Verbos Electronics Complex Oscillator, frequency knob, 2014 NAMM Show | CC BY-SA 2.0, Brandon Daniel |

All rows stay `UNVERIFIED` / `DISCOVERED`. The review queue (`review-queue.json`, 6 items, 0 admitted, thresholds `NOT_COMPUTABLE`) is on the operator's machine.

## What this means for T010b

Open web search does not reach the 50 to 100 identities T010b needs: Commons has few photos of single modules, and Flickr refuses crawlers. The owner's own photos, or photos makers license to PatchHive, stay the realistic source. Any further paid search needs a new approval entry.
