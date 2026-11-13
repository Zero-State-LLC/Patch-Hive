# Intent

## Problem

Spec 002's threat model leaves four gaps on the publishing routes:
- P1: 32-bit slugs a crawler can guess.
- P2: no `noindex` on unlisted links, and no `Cache-Control`, so a removed publication can keep being served.
- P4: bare file responses and no rate limit on public reads.
- P5: an unchecked cover URL.

T038 to T041 cover them and gate T033.

## Proposed outcome

- Slugs carry 96 random bits.
- Every read, download and 404 is `no-store`, and unlisted ones are `noindex`.
- `/p/*` and the gallery allow 120 reads a minute per address, and downloads are `nosniff` attachments.
- A cover image must be `https` on an allowed host.

Out of scope: turning publishing on (decision 34 keeps it off through beta), and anonymous report spam beyond the existing limit (P3).

## Affected users / systems

The legacy publishing routes, which are off in every environment.

## Constraints / non-goals

- No signed download URLs: a published book is meant for anyone with its link, and an unlisted link's token is its secret.
- Existing slugs keep working. Only new publications get the longer token.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Each gap is closed as described | `OBSERVED` | `backend/tests/api/test_publishing_api.py` |
| 120 reads a minute is enough for a reader | `INFERRED` | A reader opens a page and a few downloads |

## Author / date

- Author: Claude Opus 5.5, for the owner
- Date: 2026-11-12
