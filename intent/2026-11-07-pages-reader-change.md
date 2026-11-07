# Intent

## Problem

Sign out and a refused token renewal clear the store and stay on the current page. Pages that fetched while signed in keep that data on screen unless they react to the change. Rigs, runs, patches, notes, style recipes, credits and the referral link belong to an account, so they stay readable on a shared screen after the person has signed out.

`Modules.tsx` and `Registry.tsx` already handle this, and #351 fixed the rack builder. `Account.tsx` was believed to redirect, but its effect depends on `isAuthenticated`, a function whose identity never changes, so it only runs on mount.

## Proposed outcome

- Rigs, a rig's workspace, the patch list, a patch page and the style studio start over when the reader changes, by keying each page on the signed-in account. The rack builder moves from its signed-in key to the same one.
- The account page goes to sign-in when the reader leaves, and shows nothing private on the way.
- A signed-in answer that arrives after sign-out changes nothing on screen, in the URL or in the store.
- A token renewal for the same account changes nothing. A renewal that brings back a different account starts the page over.

Out of scope: other tabs learning about a sign-out, and sign-out racing a renewal in flight, both in `lib/session.ts`.

## Affected users / systems

Frontend only: the pages above, `DeleteAccount`, and the auth store. No API change.

## Constraints / non-goals

- No key at the `Routes` level. It remounts the account page when deletion ends the session, which loses the "Account deleted" screen and the "session has ended" message.
- Unsaved work on a keyed page goes with the reader. That's the cost of not leaving data behind, and it also applies when a session expires mid-work.
- No new product behaviour beyond what the account page's existing redirect already intended.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The account page kept balance, ledger and profile on screen after sign-out | `OBSERVED` | `Account.reader.test.tsx` failed before the fix |
| A `Routes`-level key breaks two deletion tests in a browser | `OBSERVED` | Tried it; `delete-account.spec.ts` failed at lines 81 and 166, `Login.returnTo.test.tsx` still passed |
| A navigation from an unmounted page still happens | `OBSERVED` | The rigs list test fails with the guard removed |
| The case catalog answers the same for every reader | `OBSERVED` | `backend/cases/catalog_routes.py`: list, stats and detail take no reader. Only compatibility does, and the case pages don't call it |
| Admin screens lose their data on sign-out | `OBSERVED` | `AdminGuard.reader.test.tsx` for one screen; all seven wrap their content in the guard |
| This behaves the same on a deployed host | `NOT_COMPUTABLE` | Every test mocks the API by whether a request carries a token |

## Author / date

- Author: Claude Code, for Daniel Meyer
- Date: 2026-11-07
