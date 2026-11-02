# Intent

## Problem

Spec 004 OQ-12 / EC-8: there is no way to delete an account. The canonical credit ledger references users with `ON DELETE RESTRICT` and is append-only, and referral rows are append-only, so deleting the `users` row is not possible without breaking financial records. Jev decided `A_anonymize_keep` on 2026-11-01 (owner-delegated; a lawyer must confirm).

## Proposed outcome

A signed-in `DELETE /api/me` that re-confirms the current password, revokes every session and token, and in one transaction anonymizes the user (email, username, display name, avatar, bio, password hash, referral code), removes or detaches the user's personal content where foreign keys allow, keeps every ledger, export and referral row, and leaves one audit row with no personal data. Evidence image bytes are purged after the commit.

Out of scope: retention periods, scrubbing free text inside kept rows, provider-side customer data, backups and logs (listed as gaps in spec 004 OQ-12).

## Affected users / systems

Accounts (`users`, sessions), commerce ledgers and referrals (kept), racks, evidence images, publications, overlays, legacy social rows, `admin_audit_log`. One additive migration (`users.deleted_at`).

## Constraints / non-goals

No row in an append-only table is updated or deleted. Fail closed: a wrong password changes nothing except the lockout counter. No migration is run against staging or production. Payments stay test-mode.

## Open questions

- Retention periods for kept rows, and whether any kept row must later be erased: lawyer.
- Whether free text inside kept rows must be scrubbed: owner and lawyer.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The canonical ledger, canonical exports and generation runs RESTRICT user deletion | `OBSERVED` | `backend/canon/models.py` |
| The anonymized user can no longer sign in or use an old token | `OBSERVED` | `backend/tests/api/test_account_deletion.py` |
| Ledger and referral rows survive deletion | `OBSERVED` | `backend/tests/api/test_account_deletion.py` |
| The retention periods chosen are lawful | `NOT_COMPUTABLE` | Needs a lawyer |

## Author / date

- Author: Claude (for Daniel Meyer)
- Date: 2026-11-01
