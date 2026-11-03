# Intent

## Problem

Spec 004 T010 asks that every commerce state machine be encoded as tests. Machines A, B (checkout, refunds, operator resolve) and C (subscriptions, tier, fair use) already have rows in `backend/tests/unit/test_spec_004_transitions.py`, but async settlement, `refund.failed`, subscription-invoice refunds and the append-only rules (FR-008, FR-029) are not covered, and `specs/004-commerce/tasks.md` still carries drift notes that are resolved.

## Proposed outcome

New tests in the existing file for: Machine B async success and failure, `refund.failed`, the subscription-invoice refund outcome, and append-only behavior (canonical ledger and period grants are only appended, key uniqueness, replayed event id with a new payload refused, trigger migration binds `canonical_credit_ledger`). The T010 note in tasks.md drops resolved drift and lists the enforcement gaps. T010 stays `[ ]` (T001 and T002 are the owner's). Out of scope: any production code change, migrations, new database guards.

## Affected users / systems

Tests and docs only: `backend/tests/unit/test_spec_004_transitions.py`, `specs/004-commerce/tasks.md`, `intent/`.

## Constraints / non-goals

No existing test weakened and no fixture patched. Tests assert what the code enforces; a missing guard is reported as a gap, not faked green and not marked xfail (AGENTS.md does not provide for it). Payments stay test-mode.

## Open questions

Should the owner add database guards for `referrals` (FR-029), `subscription_period_grants` and the legacy `credits_ledger`? That is a separate task.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Only `canonical_credit_ledger` has append-only triggers | `OBSERVED` | `grep -ri trigger backend/alembic/versions`: `20261029_ledger_append_only`, plus the unrelated `20260925_decision_receipts` |
| Trigger behavior on Postgres | `NOT_COMPUTABLE` here | no Postgres in this environment; covered by `tests/acceptance/test_ledger_append_only.py` |
| New tests pass on SQLite | `OBSERVED` | pytest run |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-02
