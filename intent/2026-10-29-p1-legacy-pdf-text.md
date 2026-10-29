# Intent

## Problem

From the 2026-10-29 gap analysis (P1): the legacy PDF paths still broke spec 002.
- **Rig and patch PDFs.** `export/pdf.py` drew descriptions as one unwrapped line and cut the rig and patch descriptions at 100 characters (FR-003).
- **Legacy patch book.** `POST /api/export/patchbook` (`render_pdf.py`) gave each patch two pages with an 8–9 pt body, and it accepted patches from other rigs, silently dropping modules the requested rig lacks (FR-001/FR-004, FR-013/FR-014). The site doesn't call it; the Design Engine is the book path.

## Proposed outcome

- **Wrapping.** Rig and patch PDF text wraps to the page width (`_draw_wrapped`, reportlab `simpleSplit`) and is never cut.
- **Gate.** `POST /api/export/patchbook` answers 410 `LEGACY_PATCHBOOK_EXPORT_DISABLED` unless `ENABLE_LEGACY_PATCHBOOK_EXPORT` is set. With it set, a patch from another rig is refused with 400 `PATCH_BOOK_REFERENCE_UNRESOLVED`.
- `/runs/{id}/patchbook` was already 410 by default (`enable_legacy_patchbook_debit`).

Not here: the per-page book manifest and book validation stage (FR-016/FR-017), which belong to the Design Engine.

## Affected users / systems

Rig PDF download on the Racks page (still served, now wrapped); the legacy patch-book route (off).

## Constraints / non-goals

The rig PDF is a rig sheet, not a patch book, so it keeps its page structure.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The site calls only the rig PDF | `OBSERVED` | `frontend/src` grep |
| Wrapped text keeps every word within the page | `OBSERVED` | `tests/unit/test_legacy_pdf_wrap.py` |
| The gate and the foreign-patch refusal | `OBSERVED` | `tests/test_patchbook_api.py` |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-29
