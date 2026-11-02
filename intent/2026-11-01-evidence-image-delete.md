# Intent

## Problem

Spec 001 OQ-10 was decided 2026-11-01 (`minimal_images_only`, provisional). Evidence images could be requested with up to 365 days of retention, and the owner delete route only removed stored bytes when the caller added `purge_bytes=true`, so a plain delete left the photo on disk.

## Proposed outcome

- Keep the 30-day default. A requested retention above 90 days is refused (`RETENTION_DAYS_INVALID`); 1 to 90 is accepted.
- `DELETE /api/racks/{id}/evidence/images/{asset_id}` always soft-deletes the row (`deleted_at`) and removes the stored file, unless a live asset shares the same content hash (same rule as `evidence.retention.expire_image_assets`). `purge_bytes` is gone; a client that still sends it is unaffected. A failed storage delete keeps the soft-delete and answers 503; calling again retries.
- Owner only; a caller who cannot see the rack gets 404.
- A decision already linked to the image keeps working. Classification evidence, decision receipts and inventory revisions stay (append-only). Reads (candidates, inventory, reconcile, image list with `include_deleted`) answer 200. The deleted image's candidates drop out of the candidate list, and a new decision on that evidence is refused with 400 `EVIDENCE_NOT_BOUND_TO_RACK`, as `image_access_decision` already treats the asset as deleted.

Out of scope: scheduling `expire_image_assets` (waits for spec 006 T101b/T101c; no schedule added), overlays, the credit ledger, and account-level deletion (stay undefined; GDPR-style erasure is still open).

## Affected users / systems

Evidence upload and delete routes (`backend/evidence/routes.py`), `docs/OPERATIONS.md`, spec 001 OQ-10 text.

## Constraints / non-goals

Append-only tables are not written or removed. No migration. Fail closed on retention.

## Open questions

Owner to confirm the provisional OQ-10 decision; a lawyer must confirm retention and deletion terms.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Delete removes the file and keeps shared bytes | `OBSERVED` | `tests/api/test_evidence_upload.py` |
| Reads survive deleting an image with linked evidence and a receipt | `OBSERVED` | same file |
| Non-owner delete answers 404 | `OBSERVED` | same file; an admin read role answers 403, as on other rack writes |
| Existing images keep their stored retention (up to 365 days) until they expire or are deleted | `INFERRED` | the cap applies at upload only |

## Author / date

- Author: Claude (agent), for the owner
- Date: 2026-11-01
