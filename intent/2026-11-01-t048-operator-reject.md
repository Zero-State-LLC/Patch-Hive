# Intent

## Problem

Spec 004 FR-014 holds provider events PatchHive cannot apply as `unresolved`, and Machine B says only an operator action can leave that state (OQ-5). No such action existed, so unresolved events (including the `RECEIVED_BEFORE_PROCESSOR` backfill) could never be closed.

## Proposed outcome

An Admin can reject an unresolved event with a reason: it becomes `rejected`, grants nothing, and writes one `CanonicalAdminAuditEventRecord`. Admin readers can list unresolved events. Resolve (crediting after operator verification) is split to T048b because it needs Machine B (T046) and a way to recover the event, which PatchHive does not store.

Out of scope: resolve, Machines B and C, any price or tier decision.

## Affected users / systems

Admin API (`/api/admin/commerce/...`), `stripe_event_records.status`, `canonical_admin_audit_events`.

## Constraints / non-goals

Fail closed: no credit is ever written by this path. Admin role only (Ops excluded, as OQ-5 recommends). No migration: the status column has no constraint and the audit table is insert-only. Payments stay in test mode.

## Open questions

- OQ-5 itself stays open for the owner to confirm the recommendation this implements.
- T048b design (store `data.object.id`, retrieve from the provider at resolve time) is a recommendation in docs/evidence/COMMERCE_BLOCKERS_RESEARCH_2026-11-01.md.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Stripe serves an event from the API only for 30 days | `OBSERVED` | docs.stripe.com/api/events/retrieve, read 2026-11-01 |
| PatchHive stores only the payload hash of an event | `OBSERVED` | `StripeEventRecordModel` |
| Reject grants nothing and writes one audit record | `OBSERVED` | `tests/unit/test_commerce_operator_reject.py` |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-01
