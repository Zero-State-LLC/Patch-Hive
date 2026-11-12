# Intent

## Problem

Only 226 of the 3,379 public Modules declare jacks, so most Rigs are partly generic. Nothing tells a person how much of their Rig has real jack names until they read each Patch Book page.

## Proposed outcome

- The Rig page says "Jack names on file for 3 of 12 Modules."
- A Patch Book's colophon says the same for the Modules in that book. The cover has no room: at the largest body size its metadata already reaches the footer.

Out of scope: computing Rig scores over the Modules that have lists, which would change decision 11 and skew toward the makers with lists.

## Affected users / systems

The Rig page, the Rig detail response (each Module now includes its `io_ports`), and Patch Book colophons.

## Constraints / non-goals

- The count is of Modules with a list on file, and says nothing about whether a list is right on the panel.
- The book reads Modules at export time like the rest of its pages, so nothing sealed changes.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The count is right on both surfaces | `OBSERVED` | Tests in `RigDetail.reader.test.tsx` and `test_spec_002_compose_stages.py` |
| A person reads the count before relying on a page | `INFERRED` | No Patch Book reader has been asked |

## Author / date

- Author: Claude Opus 5.5, for the owner
- Date: 2026-11-10
