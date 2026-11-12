# Intent

## Problem

When a Module's jacks are on file, a generic role takes the first free jack of the right type unless a keyword matches, and nine of sixteen roles have no keyword. So an FM cable can land on a jack called "Damp CV", and a VCA's envelope cable on "Time CV". A Patch Book then prints a real jack name that is wrong, and nothing marks it as a guess.

## Proposed outcome

- A cable takes a declared jack only when its name settles it: the exact name, a keyword, a channel mark (1, A, Left), or being the only jack of its kind.
- Otherwise it keeps its generic role, and the run reports `SEVERAL_JACKS_FIT`.
- `patch_engine_version` goes to 1.4.0, because the same input now wires different jacks (spec 001 FR-001).

Out of scope: what a Patch Book says about a generic jack (slice N3), and changing which roles a Module fills when its list rules one out.

## Affected users / systems

Patch generation and Patch Books for Modules with jack lists. Saved runs keep the version they were made with.

## Constraints / non-goals

- A wrong jack with no warning is worse than a role name (owner's call, 2026-11-10).
- Channels are interchangeable, so a plain channel mark is enough to name one. Pitch, FM and cutoff inputs each have a specific job, so a channel mark doesn't settle them.
- Lists come from documents, so a missing jack stays `unresolved` and doesn't block.

## Open questions

None for this slice.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The rule's effect on the 224 lists | `OBSERVED` | The resolver run over `overlays/module-jacks-v1.json`, in the PR |
| The name forms in those lists resolve as intended | `OBSERVED` | `backend/tests/unit/test_patch_validation.py` |
| A side jack is rarely the one a generated patch wants | `INFERRED` | Usual patching; no Patch Book reader has been asked |
| A chosen jack is right on the physical panel | `NOT_COMPUTABLE` | No cable has been patched on a real Rig |

## Author / date

- Author: Claude Opus 5.5, for the owner
- Date: 2026-11-10
