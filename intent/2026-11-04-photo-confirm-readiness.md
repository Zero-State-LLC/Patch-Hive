# Intent

## Problem

Confirming a module from a photo answered `ready_for_generation: true`, but generation's gate reads `RackModule`, not the inventory revision the confirmation writes. A Rig built only from photos was told it was ready and then refused with `NOT_COMPUTABLE` (#283).

## Proposed outcome

Owner decision 35 ([OWNER_DECISIONS_2026-11-04.md](../docs/evidence/OWNER_DECISIONS_2026-11-04.md), #278):

- No auto-placement, because a photo gives no reliable row or HP.
- `ready_for_generation` on the confirmation and inventory routes is generation's own gate answer, from `evaluate_rack_inventory_gate`.
- Both routes add `modules_to_place`: confirmed photo modules that no placement on the Rig accounts for. Placing one uses the existing `PATCH /api/racks/{id}`, which checks fit.
- The builder and Rig page show the list, with a link to place each one.

Out of scope: any change to the gate, to generation, or to how a Rig revision is sealed.

## Affected users / systems

Evidence confirmation and inventory API responses, Rack Builder's evidence step, and the Rig page. Generation itself doesn't change.

## Constraints / non-goals

Vision can't self-confirm: image, evidence, user confirm, inventory. The list only reads confirmed revisions. A catalog match is a `catalog-module-{id}` label or one exact brand and name; anything else has `module_id: null` rather than a guess.

## Open questions

Decision 35 says the API doesn't say ready "until it's placed". On a Rig with other Modules already placed, generation accepts the Rig, so the API says ready and lists the unplaced Module. The owner can read this on the PR.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| A photo-only Rig gets `false` and generation answers `NOT_COMPUTABLE` | `OBSERVED` | `tests/api/test_evidence_confirmations.py` |
| After a placement through the rack route, both say yes | `OBSERVED` | same test file |
| Vision providers don't set `gallery_revision_id`, so a live confirmation's label is `catalog-{candidate_id}` or `gallery-{id}` and most matches are by brand and name | `OBSERVED` | `backend/evidence/`, `frontend/src/pages/RackBuilder.tsx` |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-11-04
