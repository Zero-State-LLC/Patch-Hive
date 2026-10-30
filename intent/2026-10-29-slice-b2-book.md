# Intent

## Problem

Three gaps from the spec 002 research (R3, R4, R5):

- `PublicationCreate.visibility` is required, and the gallery `export_type` filter takes any string and returns an empty list for a bad one.
- The cover's patent disclaimer is drawn at 8 pt at a fixed spot. The metadata block starts at a fixed offset. A longer notice would overlap it, and 8 pt is under the body floor.
- Preflight warnings let a pack pass and are written nowhere.

## Proposed outcome

- `visibility` defaults to `unlisted`. The gallery `export_type` accepts only `patch` or `rack`; anything else is 422. (T034, FR-036, FR-042)
- The cover disclaimer is drawn with `_draw_wrapped` at `body_size_pt()`. The metadata block starts at the y it returns. (T035, FR-004)
- Every preflight warning code from the pre-render gate is listed in the book manifest as `warnings`. (part of T036, FR-019, OQ-7). T036 stays open: it depends on T030 and also asks for a stage receipt.
- Out of scope: `validate_book` (T030), plate mode (T031), publish gating (T032, T033), the colophon disclaimer size, the owner's call on whether a warning may allow acceptance.

## Affected users / systems

Publishing API clients (create default, gallery filter), the Design Engine cover page, the pack manifest and its hash.

## Constraints / non-goals

No audio DSP, no hardware control. Presentation only. No change to what a warning allows; it is only recorded.

## Open questions

- OQ-7: may a warning still allow acceptance? The owner decides. This slice records warnings either way.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The frontend publish form and gallery filter already send valid values | `OBSERVED` | `Publish.tsx` sends `unlisted` or `public`; `Gallery.tsx` offers `patch`, `rack` or none |
| Adding `warnings` changes `pack_manifest_hash` | `INFERRED` | The hash covers the manifest body; the full suite shows no golden depends on it |

## Author / date

- Author: Claude (slice B2)
- Date: 2026-10-29
