# Intent

## Problem

An uploaded rig photo could not reach `POST /api/racks/{rack_id}/evidence/decision-resolution`. The vision provider labelled candidates with its own `evidence-<hash>` id, while the upload stored the `ClassificationEvidenceRecord` under a separate `ev-<uuid>` id. `GET .../evidence/candidates` returned the provider id, so resolution answered 404; the stored id failed the candidate binding check in `load_identity_inputs`. This blocked 006 T060b (`docs/evidence/OWNER_ACTIONS_2026-11-02.md`, Enablement §3).

## Proposed outcome

The stored record id is the one authoritative evidence id. The upload allocates it first and rewrites each candidate's `evidence_id` in the packet to it before storing. Candidates, confirmations, advisory projection and decision resolution then all see the same id.

Out of scope: backfilling records stored before the fix (that would be a data migration); the T060b operator run itself.

## Affected users / systems

Evidence/vision upload (`backend/evidence/routes.py`), `backend/evidence/vision_provider.py`, Decision Intelligence resolution on uploaded evidence.

## Constraints / non-goals

Not storing the record under the provider's hash id: the mock id is derived from image bytes, so re-uploading the same photo (same or another rack) would collide on the primary key and share evidence across racks. The binding check in `load_identity_inputs` and the route's rack/deleted-image guard are unchanged. Idempotency and retention/consent checks are unchanged. No migration.

## Open questions

- Records uploaded before the fix keep the provider id in their packets and remain unresolvable; the owner uploads a fresh image for T060b.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Before the fix, the candidates endpoint's evidence id had no stored record | `OBSERVED` | new test in `tests/api/test_evidence_upload.py` failed with `assert (None is not None)` |
| After the fix, upload → candidates → resolution returns 200, replays idempotently, and another rack is refused | `OBSERVED` | same test passes |
| The upload route is the only writer of `ClassificationEvidenceRecord` outside tests | `OBSERVED` | grep of `backend/` and `scripts/` |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-02
