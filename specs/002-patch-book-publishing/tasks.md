# Tasks: 002-patch-book-publishing

## Setup

- [ ] T001 Confirm the spec with the operator (it is INFERRED today)
- [ ] T002 Write plan.md
  - depends_on: [T001]

## Foundational

- [ ] T010 Encode the transitions table as tests (workflows: anti-slop-code, production-systems)
  - depends_on: [T002]

## Implemented (reconciled 2026-10-29)

- [x] T020 Patch pages wrap instead of cutting, overflow fails with `PATCH_PAGE_TEXT_OVERFLOW` or `PATCH_PAGE_DIAGRAM_OVERFLOW`, and publications start as drafts with only lifecycle pairs allowed (409 `INVALID_TRANSITION`) (FR-003, FR-021, FR-038; #101).
  - depends_on: []
- [x] T021 Draw body text, steps, cables, cover and colophon at the profile's font floor (FR-004; #102).
  - depends_on: []
- [x] T022 A removed publication refuses any PATCH (FR-046; #130).
  - depends_on: []
- [x] T023 Legacy rig and patch PDFs wrap text and continue on a new page; legacy `POST /api/export/patchbook` is off by default (410) and refuses patches from another rig (FR-003, FR-013; #133).
  - depends_on: []

## Gap closure (2026-10-29)

- [ ] T030 Add a `validate_book` stage to `compose_design_export_pack`: count the pages drawn against the manifest, write one manifest entry per page (index, kind, patch artifact id, page hash, SVG hash, status), write a SHA-256 per bundle file in `checksums.json`, recompute `composition_hash`, and fail with `PATCH_BOOK_PAGE_COUNT_MISMATCH`, `PATCH_BOOK_REFERENCE_UNRESOLVED` or `PATCH_BOOK_ASSET_HASH_MISMATCH` (FR-016, FR-017, FR-006; research R1).
  - depends_on: []
- [ ] T031 Plate mode: with T030 in place, a publication-profile pack whose plates are not drawn fails `PATCH_BOOK_PAGE_COUNT_MISMATCH` (manifest 2N+2 against PDF N+2), with a test on the dual-artifact fixture (FR-016; research R1).
  - depends_on: [T030]
- [ ] T036 Record every preflight warning in the book manifest and stage receipt instead of dropping it (FR-019, OQ-7; research R5).
  - depends_on: [T030]
- [ ] T032 Refuse `draft` → `published` with 409 `PUBLICATION_BOOK_NOT_VALIDATED` when the export is not bound to a validated book, which today is every legacy export (FR-048; research R2 option 3).
  - depends_on: []
- [ ] T033 Only if the owner wants publishing back (OQ-6): bind each publication export to a canon export whose pack passed `validate_book`, and let T032's check pass for it (FR-048; research R2 option 1).
  - depends_on: [T001, T030, T032]
- [x] T034 Default `PublicationCreate.visibility` to `unlisted` and type the gallery `export_type` as `patch` or `rack` (422 otherwise), with tests (FR-036, FR-042; research R3). Done 2026-10-29.
  - depends_on: []
- [x] T035 Draw the cover's patent disclaimer at `body_size_pt()` with `_draw_wrapped`, and start the metadata block at the returned y, with a test that the two never overlap (FR-004; research R4). Done 2026-10-29.
  - depends_on: []

## Polish

- [ ] T090 Converge the code against the spec
  - depends_on: [T010, T030, T031, T032, T034, T035, T036]
