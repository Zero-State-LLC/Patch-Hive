# Intent

## Problem

A patch's title and intent promise more than its cables deliver. On a book built with `scripts/seed_golden_demo.py` at `v0.3.0-alpha.14`, "First Sample-Loop" says "Self-evolving generative patch with modulation" and has one cable, a sequencer into a pitch input.

## Proposed outcome

A patch's title and intent are read from its cables. A patch too thin to do what its rule is for says plainly what it is. Tests cover the three examples from the report.

Out of scope: `backend/export/patchbook/design/` (spec 002 owns the page and its Operation section), changing any cable, and deciding how few cables still count as a patch.

## Affected users / systems

Patch generation (`backend/patches/engine.py`, `backend/core/naming.py`), so the title and Intent line on every patch page in newly generated runs. Existing runs keep their words (FR-020).

## Constraints / non-goals

The same seed wires the same cables. Every patch stays in the run. Each new sentence is a fact about the cables, not the hardware (FR-017): "No CV is patched into Quad VCA" says nothing about whether that VCA passes sound with its level turned up.

## Open questions

**For the owner: should a patch that can't do what its rule is for still get a page in a paid book?** This work makes those patches honest and keeps them. Of the 14 patches per run on the seeded rig:

| Patches | State | Rules |
|---|---|---|
| 5 | Nothing open | sequenced voice (3), sequenced hats, oscillator mix |
| 5 | Nothing fires the envelope | subtractive voice (3), noise voice, plucked voice |
| 2 | Nothing on the VCA's CV | drone, voice through effect |
| 2 | No sound path at all | generative (no audio cable), mixer into effect (nothing feeds the mixer) |

The options are to keep them as they now read, drop the last group, or change the rules to wire what's missing, such as the sequencer's gate on a rack that has one. The category is the same question: "Generative" and "Clock-Rhythm" still label patches with no modulator or no clock, because FR-011 defines those rules by what the rack holds.

FR-003 says names come from hashing the seed. The descriptor still does; the mechanism word now comes from the cables. The structural branches already departed from that wording, so the requirement may want rewording.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Titles ignored the cables: the fallback was a hash pick from 9 words, 8 of them structural. 1,774 of 2,800 patches carried a word their cables did not earn | `OBSERVED` | Baseline at `v0.3.0-alpha.14`, seeded rig, 200 seeds |
| On the seeded rig the three examples are not thinning: those rules overclaim at the same 21.4% on a rig with a second of everything | `OBSERVED` | Same measurement on a rich rig |
| Thinning is real but secondary: "Subtractive" with no filter and "noise and envelope" with no envelope, on sparse racks | `OBSERVED` | Same measurement on sparse racks |
| The fix moved no cable and no patch | `OBSERVED` | Digest of every cable, before and after, on all nine rigs |
| A book with the new words still fits and validates | `OBSERVED` | Production composer on the seeded rig: 16 pages, all pass, no warnings |
| A deployed run shows the same words | `NOT_COMPUTABLE` | Not deployed; this work does not deploy |

## Author / date

- Author: Claude (agent), under the owner's delegation
- Date: 2026-11-06
