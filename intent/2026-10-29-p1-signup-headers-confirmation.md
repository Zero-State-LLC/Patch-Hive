# Intent

## Problem

From the 2026-10-29 gap analysis (P1):
- **Sign-up abuse.** Sign-up had no rate limit, and separate replies for a taken username and a taken email let anyone check whether an email has an account.
- **Missing headers.** No host sent HSTS; the API also lacked `nosniff` and framing protection.
- **Forgeable confirmation.** Evidence confirmation wrote a client-supplied `confirmed_by` into the canonical inventory revision (spec 005 FR-006).
- **Editable removed publications.** A PATCH without `status` still edited a removed publication (spec 002 lifecycle).

## Proposed outcome

- **Sign-up:** limited to 5 per address per 10 minutes (429 `TOO_MANY_SIGNUPS`, separate from the login limit); one reply, `USERNAME_OR_EMAIL_TAKEN`, for either duplicate. The sign-in page shows both as words.
- **HSTS** (one year, subdomains included) on the frontend Worker. The API Worker adds HSTS, `nosniff`, `X-Frame-Options: DENY` and a referrer policy to every response.
- **Confirmation:** `confirmed_by` is `user:<id>` of the signed-in user; the request field is gone.
- **Removed publications:** any PATCH answers 409 `PUBLICATION_UNDER_MODERATION`.

Not here:
- Turnstile and email verification, which need a site key and a mail sender (operator).
- A shared rate-limit store; the limits stay per container.

## Affected users / systems

Sign-up and sign-in, both Workers, the evidence confirmation API, publication edits.

## Constraints / non-goals

No change to login lockout or tokens.

## Open questions

Turnstile site key and an email sender, for verification.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The limit and single reply work | `OBSERVED` | `tests/api/test_signup_limits.py` |
| Headers present in both Workers | `OBSERVED` | `tests/unit/test_edge_security_headers.py`, `headers.test.ts` |
| `confirmed_by` ignores the client | `OBSERVED` | `test_list_and_confirm_candidates` |
| Removed publication edits are refused | `OBSERVED` | `test_a_removed_publication_cannot_be_edited` |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-29
