# Intent

## Problem

The engine wires a generic "Audio Out", and with no keyword for that role it takes the first audio output a Module lists. Pittsburgh Modular's Fltr lists highpass first, so a Patch Book built from the new jack lists tells people to patch every filter voice from "Highpass Output". The warning that used to send them to the panel no longer appears once the jacks are on file.

## Proposed outcome

- A generic audio output resolves to a declared lowpass jack when the Module has one, wherever it is listed.
- `patch_engine_version` goes to 1.3.0, because the same input now wires a different jack (spec 001 FR-001).

Out of scope: choosing a better jack for other kinds of Module, such as an Inverter or FX Send output listed first, and the catalog load, whose inputs don't change.

## Affected users / systems

Patch generation and Patch Books for Modules with several audio outputs and a declared lowpass jack. Of the 224 lists in `overlays/module-jacks-v1.json`, 5 change, and all 5 are filters.

## Constraints / non-goals

- The match uses the existing role keywords. A word that only contains "low", such as "below", is not a lowpass jack.
- A Module with no lowpass jack keeps the first audio output listed.

## Open questions

Whether other first-listed outputs need their own rule. They are valid cables, and only a few of the 224 lists have one.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| 5 of the 224 lists resolve to a different jack: Bastl Cinnamon, Mosaic State Variable Filter, Nonlinearcircuits Serious Filter, Pittsburgh Modular Fltr, b:art b:16 | `OBSERVED` | The resolver run over `overlays/module-jacks-v1.json` |
| The name forms in those lists resolve to lowpass | `OBSERVED` | `backend/tests/unit/test_patch_validation.py` |
| Lowpass is the output a person wants on a filter voice | `INFERRED` | Usual subtractive patching; no Patch Book reader has been asked |

## Author / date

- Author: Claude Opus 5.5, for the owner
- Date: 2026-11-09
