# Tasks: 002-patch-book-publishing

## Setup

- [x] T001 Confirm the spec with the operator (it is INFERRED today). Done 2026-11-04 by an agent under the owner's delegation, not by the owner reading the spec: [T001_CONFIRMATION_2026-11-04.md](T001_CONFIRMATION_2026-11-04.md).
- [x] T002 Write plan.md. Done 2026-11-04 by an agent: [plan.md](plan.md).
  - depends_on: [T001]

## Foundational

- [x] T010 Encode the transitions table as tests (workflows: anti-slop-code, production-systems). Done 2026-11-06 in `backend/tests/unit/test_spec_002_transitions.py`: the table is checked against spec.md, and every row is fired or held by a named test, including closing an account (D2), an admin acting second (D6) and the owner no-ops (D9). Illegal pairs, flag-off 404s, both `/me/exports` paths (D1), hidden and draft reads and the gallery (record row 3) are there too. The success row of `publish` can't run, because FR-048 refuses every publish until T033. Response codes the spec leaves open (422, 404, 403, 400 on a second create) are asserted as the code returns them. The page and book compile machines aren't encoded, because the owner chose not to build them (decision 37).
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

## Before publishing could return

The threat model's remaining gaps. They gate T033, and none has any effect while publishing is off. Its SVG escaping item is done (#280), and its rate limit on the report route is done (#197, T037).

- [ ] T038 Lengthen the random slug part to at least 96 bits, or add a separate random token for unlisted links (threat model P1).
  - depends_on: []
- [ ] T039 Send `X-Robots-Tag: noindex` on unlisted reads and `Cache-Control: no-store` on read and download, so removal takes effect (threat model P2).
  - depends_on: []
- [ ] T040 Add a rate limit to `/p/*` and the gallery. Add `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff` to downloads, and decide on signed or short-lived download URLs (threat model P1, P4).
  - depends_on: []
- [ ] T041 Validate `cover_image_url` as an `https` URL on an allowlist, or drop the field (threat model P5).
  - depends_on: []

## Gap closure (2026-10-29)

- [x] T030 Add a `validate_book` stage to `compose_design_export_pack`: count the pages drawn against the manifest, write one manifest entry per page (index, kind, patch artifact id, page hash, SVG hash, status), write a SHA-256 per bundle file in `checksums.json`, recompute `composition_hash`, and fail with `PATCH_BOOK_PAGE_COUNT_MISMATCH`, `PATCH_BOOK_REFERENCE_UNRESOLVED` or `PATCH_BOOK_ASSET_HASH_MISMATCH` (FR-016, FR-017, FR-006; research R1). Done 2026-10-29: `validate_book` in design/engine.py writes `pages`, per-file `checksums.json` and `validation/book.json`; tests in test_patchbook_validate_book.py.
  - depends_on: []
- [x] T031 Plate mode: with T030 in place, a publication-profile pack whose plates are not drawn fails `PATCH_BOOK_PAGE_COUNT_MISMATCH` (manifest 2N+2 against PDF N+2), with a test on the dual-artifact fixture (FR-016; research R1). Done 2026-10-29: the dual-artifact plate test now expects the failure and its receipt.
  - depends_on: [T030]
- [x] T036 Record every preflight warning in the book manifest and stage receipt instead of dropping it (FR-019, OQ-7; research R5). Done 2026-10-29: the manifest keeps the codes (#138) and `validation/book.json` lists each warning with its message.
  - depends_on: [T030]
- [x] T032 Refuse `draft` → `published` with 409 `PUBLICATION_BOOK_NOT_VALIDATED` when the export is not bound to a validated book, which today is every legacy export (FR-048; research R2 option 3). Done 2026-10-29: `update_publication` refuses it; the lifecycle API test changed with FR-048.
  - depends_on: []
- [ ] T033 Only if the owner wants publishing back (OQ-6): bind each publication export to a canon export whose pack passed `validate_book`, and let T032's check pass for it (FR-048; research R2 option 1).
  - depends_on: [T001, T030, T032, T038, T039, T040, T041]
- [x] T034 Default `PublicationCreate.visibility` to `unlisted` and type the gallery `export_type` as `patch` or `rack` (422 otherwise), with tests (FR-036, FR-042; research R3). Done 2026-10-29.
  - depends_on: []
- [x] T035 Draw the cover's patent disclaimer at `body_size_pt()` with `_draw_wrapped`, and start the metadata block at the returned y, with a test that the two never overlap (FR-004; research R4). Done 2026-10-29.
  - depends_on: []
- [x] T037 Lock the publication row (`SELECT ... FOR UPDATE`) in the owner PATCH and the admin hide and remove handlers (OQ-10 `row_lock`), and add the report rate limit and per-(publication, reporter) dedupe (OQ-13 `limit_and_require_dedupe`; FR-044). Done 2026-11-01: tests in test_spec_002_report_limits_and_locks.py. Report retention stays undecided.
  - depends_on: []

## Polish

- [x] T090 Converge the code against the spec. Done 2026-11-06. The owner chose not to build the page and book compile machines (decision 37), so spec.md replaces them with the stages as built, tested in `backend/tests/unit/test_spec_002_compose_stages.py`. Each book page now draws its diagram and names its modules; it didn't before. A missing fact is an error (D7), a loop is marked and warned about, the colophon notice meets the floor, the pack has a README, and a stopped compose keeps a receipt. Spec text corrected for D1, D2, D4, D5, D8, D9, D10, D12 and D13. Still partial, and why, in spec.md's table: FR-008 (T091), FR-012, FR-013, FR-015 (decision 38), FR-048 (T033).
  - depends_on: [T010, T030, T031, T032, T034, T035, T036, T037]
- [ ] T091 Write each page's operation steps for its own patch. At 0.3.0-alpha.14, a run generated through the API prints the same five lines on all 14 pages. The seeded demo's run has no sealed rows, so it takes `_plan_steps_from_connections`, which repeats the cables, adds 25 padding lines across 11 of its 14 pages, and prints a module id from the sixth cable on.
  - depends_on: [T090]
