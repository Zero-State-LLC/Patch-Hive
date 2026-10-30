# Intent

## Problem

The evidence decision-resolution path calls the provider before it looks for an earlier answer, so a repeat with the same idempotency key can write a second, different receipt. `evidence_hash` is the raw evidence id, not a hash of the evidence. No routing target is ever passed, so a policy ESCALATE or a failed provider can never reach ESCALATE (spec 005 research R5, R6).

## Proposed outcome

- **T083:** receipts store `idempotency_key`, with a unique `(request_id, idempotency_key)` index (new Alembic revision after `20261029_ledger_append_only`). The guarded resolution looks the key up before the provider call. Same key and same evidence returns the stored outcome with no provider call; same key with a different evidence hash is 409 `IDEMPOTENCY_KEY_CONFLICT`. `evidence_hash` is the SHA-256 of the retained evidence packet plus the image asset SHA.
- **T085:** `settings.decision_routing_target` names one target, `human_review`, and the route passes it as `routing_targets`. An empty value means no target.

## Affected users / systems

`backend/evidence/routes.py`, `backend/intelligence/` (resolution, persistence, models), `backend/core/config.py`, one migration, spec 005 `tasks.md`.

## Constraints / non-goals

No other routing targets. No change to policy thresholds or the response shape. Old receipts keep a NULL key and their old hash; the table is append-only so they are not rewritten.

## Open questions

- Default for `decision_routing_target`: `human_review` (R6 recommends it) versus empty. Chosen: `human_review`.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Provider was called before any receipt lookup | `OBSERVED` | `clef_resolution.py` before this change |
| Evidence and image rows are append-only, so a changed payload under one key arises only from a changed hash | `OBSERVED` | `canon/models.py` immutable listeners |
| Unique index ignores NULL keys on Postgres and SQLite | `INFERRED` | standard unique-index semantics; checked by migration run |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-29
