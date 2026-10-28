# Intent

## Problem

Spec 002 requires that every published patch fit on one page with all of its required content (FR-001, FR-003, FR-010, FR-021). The Design Engine execution PDF broke this in two ways:
- It stopped drawing steps and cables when the page filled (`if y < inch + 40: break`).
- It cut titles to 80 characters, intents to 120, cable lines to 110 and diagram labels to 18, with no error.

A buyer could pay for a patch book that silently left out cables. Separately, publications skipped the `draft` state, and admin hide and remove accepted moves from any state.

## Proposed outcome

- Each patch page is laid out before it is drawn. Text wraps by measured width, and a word wider than the line is split, not cut.
- If the page is full, the optional title block is dropped. If required content still does not fit, the export fails with `PATCH_PAGE_TEXT_OVERFLOW` and remediation. The existing fulfillment path compensates the debit.
- Diagram labels over 18 characters wrap inside the node, up to three lines; beyond that, `PATCH_PAGE_DIAGRAM_OVERFLOW`.
- The cover's patent disclaimer wraps instead of being cut.
- Publications are created as `draft`. Owner, admin and report actions follow the spec 002 lifecycle table; any other move answers 409 `INVALID_TRANSITION`.

Out of scope:
- Font-size floors (FR-004). The renderer still draws 9 pt body and 8 pt cables; changing that alters page fit, so it is a separate change.
- Rejecting only one patch from a book while the rest compile.
- Alternative layouts (FR-009).
- The legacy two-page renderer (`render_pdf.py`).

## Affected users / systems

- `export/patchbook/design/engine.py` and `diagram_svg.py`.
- Canonical paid exports, through the existing fulfillment compensation.
- Legacy publishing (`ENABLE_LEGACY_PUBLISHING`, off by default).

## Constraints / non-goals

- Never truncate, clip or drop required content: fail with a code instead.
- SVG output for labels of 18 characters or fewer is byte-identical, so the goldens still pass.
- Payments stay in test mode.

## Open questions

- Should an overflowing patch be dropped from the book with a manifest entry, rather than failing the export? FR-021 allows rejecting the patch from the profile. Owner decides.
- Do we need a `draft → published` guard that the export is bound to a validated book (OQ-1)?

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Every step and cable of a 12-step, 10-cable patch is on its page | `OBSERVED` | `tests/unit/test_patchbook_page_fit.py` |
| Long titles, intents and port ids wrap without losing a word | `OBSERVED` | same file |
| An over-full patch raises `PATCH_PAGE_TEXT_OVERFLOW` with remediation | `OBSERVED` | same file |
| `PreflightFailed` from the renderer compensates the export debit | `OBSERVED` | `canon/fulfillment.py:135` catches it on the existing failure path |
| SVG goldens are unchanged | `OBSERVED` | `tests/unit/test_patchbook_svg_goldens.py` passes |
| Publication lifecycle pairs outside the table are refused | `OBSERVED` | `test_publication_lifecycle_follows_the_spec` |
| Real patches rarely overflow one page | `INFERRED` | engine patches have at most 5 cables and a few steps; not measured across the catalog |

## Author / date

- Author: Claude (for Zero-State-LLC)
- Date: 2026-10-28
