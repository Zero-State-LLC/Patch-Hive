# Intent

## Problem

Access tokens lasted 7 days and the SPA kept them in `localStorage`. Any script that ran on the page, such as an injected one or a compromised dependency, could read the token and use it for a week. There was no way to revoke a token: signing out only forgot it locally, and a role change did not take effect until expiry. The frontend sent no Content-Security-Policy. (2026-10-27 gap analysis, P1 hardening.)

## Proposed outcome

- **Access tokens:** 15 minutes, held only in memory, and carrying `tv` (the user's `token_version`).
- **Refresh tokens:**
  - random, stored as SHA-256 only, lasting 30 days;
  - kept in an `HttpOnly`, `SameSite=Strict` cookie on the API host, which is `Secure` with the `__Host-` prefix outside local development;
  - rotated on every use, and replaying a replaced token revokes the whole family.
- **Cookie-authenticated calls** are only refresh and sign-out. They require an `X-PatchHive-Session` header and an allowed `Origin`.
- **Sign-out:**
  - "Sign out" revokes this browser's session.
  - "Sign out everywhere" bumps `token_version` and revokes every refresh token.
  - A role change does the same for the affected user.
- **SPA:**
  - restores the session on load from the cookie;
  - renews once, then retries, on a 401;
  - removes any leftover `auth_token` from `localStorage`.
- **Frontend Worker:**
  - sends `Content-Security-Policy-Report-Only`, with `connect-src` limited to the host's own API;
  - adds `X-Content-Type-Options: nosniff` and a `Referrer-Policy`.

Out of scope:

- Enforcing the CSP. That comes once the console is clean on both hosts.
- A CSP report endpoint.
- A UI for "sign out everywhere". The API route exists.
- Rate limiting on refresh.

## Affected users / systems

- `community/sessions.py`, `community/auth.py` and `community/auth_routes.py` (`/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/logout-all`).
- Admin role changes.
- `users.token_version` and the new `refresh_tokens` table (migration `20261028_refresh_sessions`).
- Frontend: `lib/store.ts`, `lib/session.ts`, `lib/api.ts`, `App.tsx`, `Account.tsx` and the style studio download.
- `frontend/worker`.
- Every signed-in user signs in again once the 7-day tokens they hold expire.

## Constraints / non-goals

- Fail closed: a refresh that cannot be verified clears the session.
- No token is ever written to web storage.
- The cookie is never sent cross-site.
- Tokens minted before this change have no `tv`. They read as version 0, so they keep working until their own 7-day expiry unless the user's version is bumped.

## Open questions

- **CSP enforcement:** promote the report-only policy to enforcing once both hosts show no violations. Owner decides.
- **Lifetimes:** are 15-minute access and 30-day refresh right? Owner decides. Settings: `access_token_expire_minutes`, `refresh_token_days`.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Sign-in sets an HttpOnly, SameSite=Strict refresh cookie, and `__Host-` plus `Secure` on hosted environments | `OBSERVED` | `tests/api/test_sessions.py` |
| Refresh rotates the token, and a replayed token revokes its family | `OBSERVED` | `test_refresh_rotates_and_a_replayed_token_revokes_the_family` |
| Refresh and sign-out refuse requests without the session header or from another origin | `OBSERVED` | `test_cookie_routes_need_the_session_header_and_an_allowed_origin` |
| Sign-out everywhere and role changes kill outstanding access tokens | `OBSERVED` | `test_sign_out_everywhere…`, `test_a_role_change…` |
| The SPA shares one refresh between concurrent calls and keeps the token out of localStorage | `OBSERVED` | `frontend/src/lib/session.test.ts` |
| The migration upgrades, downgrades and upgrades on Postgres 15 | `OBSERVED` | local postgres:15.13 container |
| patch-hive.com ↔ api.patch-hive.com and staging.patch-hive.com ↔ api-staging.patch-hive.com are same-site, so a Strict cookie reaches the API | `INFERRED` | registrable domain `patch-hive.com`; not yet exercised in a browser on staging (accounts closed) |
| The report-only CSP flags nothing the app needs | `INFERRED` | built from the origins found in `index.html` and `src`; check the console after deploy |

## Author / date

- Author: Claude (for Zero-State-LLC)
- Date: 2026-10-28
