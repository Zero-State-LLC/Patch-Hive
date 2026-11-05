# Intent

## Problem

Sign-ups are open and production answers 404 at `/privacy`. There is no page that tells people what the service holds about them.

## Proposed outcome

A factual privacy notice at `/privacy`, linked from the site footer and the sign-up form, served by the edge worker with 200, and covered by Vitest, the design guard and the live smoke suite. It is marked as not yet reviewed by counsel and dated 2026-11-04.

Out of scope: any backend change, a delete button on the account page, a contact address, deploying, terms of service, and any new script or analytics.

## Affected users / systems

Everyone who signs up or visits the site. `frontend/src` (page, route, footer, sign-up form), `frontend/worker/routes.ts`, `frontend/tests`.

## Constraints / non-goals

Facts only, each checked against the code. No legal conclusions, no invented rights or promises, no compliance claim, no invented retention period, no contact that can't be verified.

## Open questions

- The account page has no delete control today, so the only deletion route is a signed-in API request. Decision 47 approves a control in its own PR. The notice's deletion and gap lines change when both are on `main`, whichever lands second.
- `privacy@patch-hive.com` is the chosen contact (decision 48), but the owner hasn't created it and `patch-hive.com` has no MX record. The gap stays until it works.
- A JPEG comment field survives photo re-encoding as of 2026-11-04. #287 fixes it; the notice's line changes once that ships.
- Counsel's review of the notice (owner decision 24).

## Verified / assumed claims

- **Verified:** the code paths below, and a local run of `prepare_image_evidence` on marked files.
- **Assumed:** nothing on the page. The full claim list, with sources, is in the PR body.

| Claim | Label | Basis |
|---|---|---|
| The edge worker answers 404 for any path outside `APP_ROUTES` | `OBSERVED` | `frontend/worker/routes.ts`, `frontend/worker/index.ts` |
| The account page has no account-deletion control | `OBSERVED` | `frontend/src/pages/Account.tsx`, `frontend/src/lib/api.ts` |
| EXIF, XMP and ICC data are dropped by re-encoding; a JPEG comment is kept | `OBSERVED` | `backend/evidence/images.py`, run with Pillow 13.0.0 |
| Whether long-retention photos exist on production | `NOT_COMPUTABLE` | Production database not queried |
| Database region | `NOT_COMPUTABLE` | Not stated in the repo; owner to supply |

## Author / date

- Author: Claude Code, for the owner's decisions 24 to 26, 32 and 33
- Date: 2026-11-04
