# Intent

## Problem

A Patch Book says a Module's "real names aren't on file" whenever a cable shows a generic role. That is false for a Module whose jack list is on file, where the list either doesn't settle which jack takes the cable or has no such jack.

## Proposed outcome

The page gives the true reason, per Module:

- No list on file: the existing note.
- A list on file and a jack of the right kind, but no name settles which: check the panel.
- A list on file and no jack of that kind: check the panel.

Out of scope: how many Modules have lists (slice N4), and which jack a cable takes (slice N2).

## Affected users / systems

Patch Book pages for Rigs with jack lists on file.

## Constraints / non-goals

- The note reads the Module's declared jacks at export time, like the rest of the page, so nothing sealed changes.
- Lists come from documents, so the note says "on file" and never that a jack doesn't exist.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Each case prints its own note | `OBSERVED` | `backend/tests/unit/test_spec_002_compose_stages.py` |
| A reader acts on the note | `INFERRED` | No Patch Book reader has been asked |

## Author / date

- Author: Claude Opus 5.5, for the owner
- Date: 2026-11-10
