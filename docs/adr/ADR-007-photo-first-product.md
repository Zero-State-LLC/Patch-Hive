# ADR-007 — The product starts from a photo, and the Device Registry is a reference, not a public product

Status: Accepted

Date: 2026-11-07

Supersedes: [ADR-006](ADR-006-public-product-database.md)

## Context

PatchHive's central job is to turn a photo of someone's Rig into a Patch Book. ADR-006 made the Device Registry a public Product Database with its own explorer. Together with a Case-first builder and manual placement on HP rows, that made PatchHive read as a module database and rack planner, a product category other sites already own, with the photo as an afterthought. The owner chose a photo-first product on 2026-11-07 (decisions 57 to 60).

## Decision

- A Rig starts from a photo of the whole Rig. PatchHive reads each Module and its position, and the owner confirms the reading.
- The Device Registry stays, as the reference a reading matches against and as the search used to fix a misread Module. It is no longer a public product to browse. The Modules, Products and Cases pages leave the navigation and their routes redirect home. The admin catalog tools stay.
- The placement editor becomes "correct the layout" inside the photo journey, and manual entry where photo reading is unavailable.
- Positions confirmed from a photo count as placement, so generation doesn't wait for manual placement.

The journey is specified in [spec 009](../../specs/009-photo-to-patchbook/spec.md).

## Consequences

- The catalog's public browse surface, and the counsel questions that came with it, shrink. Anonymous reads of the catalog API are unchanged for now (decision 39).
- Recognition quality becomes the product's main risk. Spec 007 measures it on whole-rig photos before production turns it on.
- Manual entry stays as the fallback wherever photo reading is unavailable, which is everywhere until spec 007 and counsel clear it.
- Reversing this means restoring the browse pages and their routes. The data and the pipeline are untouched, so that would be a frontend change.
