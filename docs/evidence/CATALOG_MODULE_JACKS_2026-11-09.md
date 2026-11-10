# Module jack lists, 2026-11-09

`overlays/module-jacks-v1.json` proposes jack lists for 230 Modules: 1,638 jacks from 66 makers, read from 148 user manuals and 82 maker pages. Before this, 2 of the 3,379 public Modules declared jacks, so Patch Books printed role names such as "Audio Out".

## How the lists were chosen

`scripts/read_module_jacks.py` read each Module's maker page and user manual from the 2026-11-09 crawl, twice, with differently worded prompts, on Claude Haiku 5.5 through OpenRouter. That was 6,356 readings for $3.87. All came back usable.

A Module was proposed only when, for one document:

- both readings called the list complete
- both agreed on every jack's direction and signal
- each jack's quote was found in the document
- no two jacks shared a name
- the list had at least one output
- the list didn't look like one channel of a multi-channel Module

Of the 2,514 Modules read, 230 passed. Most of the rest fell short because the document doesn't name every jack.

## Hand check

25 accepted lists were compared with their documents, 10 from a 100-Module test and 15 chosen at random from the full run.

- 23 were right. For the 15 from the full run only the jack-related lines of each document were read, and two or three of those lists could be confirmed only in part.
- 2 were incomplete: Mutable Streams and Bard VTG are dual-channel, and both readings listed one channel. The last check above was added because of them, and took the count from 240 to 230. It also removes some good lists and can't catch every case.

## Limits

- "Complete" means the document appears to cover every jack. No list was checked against a physical panel.
- A document can describe a different revision from the row. A page for a later version (Rev2, II, Mk2) is no longer matched, but a manual can still cover a sibling revision, as with µVCA and the µVCA II manual.
- Two readings by one model catch slips, not a mistake both make.

## Files

| File | SHA-256 |
|---|---|
| `data/synth-catalog/overlays/module-jacks-v1.json` | `beff940d2af549c5b95792a214b2028f8094c977b80539994a19a4666f39961e` |
| Private proposal, with the quote behind every jack (not in this repository) | `7c0ec9a60dea70ea87a7a9a1ddce35cfc10e8b60a5e3dc3c4300e52ca49e232e` |

The loader fills `io_ports` only where it's empty, and a list that differs from a stored one is reported as a conflict and left alone (spec 003 FR-041). Each load needs the owner's yes on its plan and inputs hashes.
