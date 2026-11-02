# Intent

## Problem

Spec 003 OQ-9 was decided on 2026-11-01 (`enforce_inputs_hash`): close the two real gaps between the batch lifecycle and the scripts without building a full state machine.

- **Admit checks only the plan hash.** The Actions apply compares the reviewed dry run's `plan_hash`. `inputs_hash` (seeds, overlays, provenance, power-config receipts, case seed) is recorded in the receipt but never compared, so the guard "receipt binds the current overlay hash" (`RECEIPTED -> ADMITTED`) is only half enforced.
- **Retirement needs no evidence.** The row-lifecycle `retire` guard says "a reason and evidence", but `_schedule_retirement` checks only brand, name and reason.

## Proposed outcome

- `populate(..., expected_inputs_hash=, require_inputs_hash=)`: with `require_inputs_hash`, an apply whose inputs differ from the reviewed dry run's `inputs_hash` writes nothing.
- The Actions loader sets `require_inputs_hash` for apply and reads `PATCHHIVE_INPUTS_HASH`; `db-load.yml` gains an `inputs_hash` input; the job summary prints `inputs_hash` beside `plan_hash`. The `plan_hash` input is unchanged.
- A retirement entry without an `https://` `evidence_url` is a `retirement_needs_evidence` conflict and tombstones nothing.

Out of scope: the rest of the batch machine (BLOCKED, RETRY_QUEUED, REJECTED as code states), T010 and T090.

## Affected users / systems

- `data/synth-catalog/population.py`, `scripts/catalog_actions_load.py`, `.github/workflows/db-load.yml`.
- Operators: an Actions apply now needs both hashes from the dry run's summary.

## Constraints / non-goals

- No database load, migration or deploy in this change.
- Local `populate` callers keep working: both new parameters default off.
- Existing retirement manifests must keep validating.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| All 448 committed retirement rows (v1: 263, v2: 185) carry an `https://` `evidence_url`, so one rule for every entry keeps them valid | `OBSERVED` | `overlays/catalog-retirements-v1.json`, `-v2.json`; `test_every_committed_retirement_carries_https_evidence` |
| The dry-run receipt already carried `inputs_hash`; the job summary printed only `plan_hash` | `OBSERVED` | `populate` receipt (FR-030), `catalog_actions_load._summary` |

## Author / date

- Author: Claude (for Daniel Meyer)
- Date: 2026-11-01
