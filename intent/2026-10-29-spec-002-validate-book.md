# Intent

## Problem

Spec 002 gap closure (research R1, R2, R5). `compose_design_export_pack` has no book validation stage: the manifest has no per-page entries, `checksums.json` holds two hashes and no per-file hash, and nothing compares the pages drawn with the manifest. In plate mode the manifest says 2N+2 pages while `PatchBook.pdf` has N+2. Preflight warnings reach the manifest as codes (#138) but no stage receipt records them. Publishing moves `draft` to `published` without checking for a validated book (FR-048).

## Proposed outcome

- T030: a `validate_book` stage after render. It counts the pages drawn against the manifest and the patch pages against the patches, checks that every reference resolves, re-hashes each diagram SVG and replays `composition_hash` from the layout IR files on disk. It writes one manifest entry per page and a SHA-256 per bundle file in `checksums.json`. A failure raises `PATCH_BOOK_PAGE_COUNT_MISMATCH`, `PATCH_BOOK_REFERENCE_UNRESOLVED` or `PATCH_BOOK_ASSET_HASH_MISMATCH` with remediation, and the failed stage receipt stays in the pack.
- T031: a publication-profile plate pack fails `PATCH_BOOK_PAGE_COUNT_MISMATCH` because plates are not drawn, tested on the dual-artifact fixture.
- T036: the book validation receipt (`validation/book.json`) lists every preflight warning with its code, severity and message. The manifest keeps its `warnings` codes.
- T032: `draft` → `published` returns 409 `PUBLICATION_BOOK_NOT_VALIDATED`, because no publication export is bound to a validated book yet.

Out of scope: T033 (binding publication exports to canon exports, an owner decision under OQ-6), drawing plates, and deciding whether a warning may allow acceptance (OQ-7).

## Affected users / systems

Design Engine export packs (canon fulfillment), legacy publishing behind `ENABLE_LEGACY_PUBLISHING` (default off). Plate mode is behind `ENABLE_PATCHBOOK_PUBLICATION_PROFILE` (default off).

## Constraints / non-goals

Fail closed. No change to the canon contracts. The receipt is deterministic (no timestamps). No new product behaviour beyond the spec.

## Open questions

- OQ-6 (owner): must publication exports bind to a validated book at all? Until T033, publishing a draft is refused.
- OQ-7 (owner): may a warning allow acceptance? Today it does, and it is now recorded.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| `_render_execution_pdf` draws one page per patch plus cover and colophon | `OBSERVED` | backend/export/patchbook/design/engine.py |
| Plate mode adds a plate and an appendix IR per patch | `OBSERVED` | same file |
| Publication exports have no link to a Design Engine pack | `OBSERVED` | backend/publishing/models.py, routes.py |
| No other code reads `manifest/checksums.json` | `OBSERVED` | repo grep 2026-10-29 |

## Author / date

- Author: Claude (agent) for Daniel Meyer
- Date: 2026-10-29
