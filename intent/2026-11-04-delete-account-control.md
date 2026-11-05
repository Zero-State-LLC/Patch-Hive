# Intent

## Problem

`DELETE /api/me` is live on production, but the Account page has no control for it. Sign-ups are open, and the only way to delete an account is a hand-made, signed-in API request.

## Proposed outcome

A delete-account control on the Account page, with a confirmation step that states what's removed and what's kept anonymised, and needs the username typed and the current password. Failures show in place. Success signs the person out and shows that the account is gone.

Out of scope: any backend change, a privacy contact, restoring a deleted account, and deleting single photos or rigs from the site.

## Affected users / systems

Signed-in users. `frontend/src/components/DeleteAccount.tsx`, `frontend/src/pages/Account.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/session.ts`, `frontend/src/styles/ops.css`, `frontend/tests/ui`.

## Constraints / non-goals

The confirmation states only what `backend/account/deletion.py` does. No backend change. Tests mock the API and never call a deployment.

## Open questions

- The privacy notice (#285) says the site has no delete button. That line, and the one in its contact gap, must change when both are on `main`, whichever lands second.

## Verified / assumed claims

- **Verified:** the code paths below.
- **Assumed:** nothing in the confirmation text.

| Claim | Label | Basis |
|---|---|---|
| What's removed and what's kept | `OBSERVED` | `backend/account/deletion.py`, spec 004 OQ-12 |
| The API needs the current password and answers 403 `PASSWORD_INCORRECT` or 429 | `OBSERVED` | `backend/account/routes.py`, `backend/account/schemas.py` |
| 5 wrong passwords lock the account for 15 minutes | `OBSERVED` | `backend/community/login_guard.py` |
| A locked account answers like a wrong password, even with the right one | `OBSERVED` | `backend/account/routes.py` (`is_locked` then `burn_password_check`) |

## Author / date

- Author: Claude Code, for the owner's decision 47
- Date: 2026-11-04
