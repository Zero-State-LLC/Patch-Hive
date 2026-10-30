# Intent

## Problem

The catalog loader plans a `needs_reverify` clear for every flagged row that has a `correct` entry, but the clear's SQL only applies once every flagged field is fixed and no nulled field is still empty. When a row still has an open field, the plan promises a write the database refuses on every run, so a dry run is never empty. Seen on staging on 2026-10-30 after #153: the Doepfer A-101-3 `modules` row had its HP corrected, but its power and depth fields, nulled by `modulargrid-reverify-v1`, are still empty, so it stays flagged and every rerun plans `modules_reverify_cleared` 1.

## Proposed outcome

The planner reads each row's archived flags, relabels, nulls and corrections once per load and schedules a clear only when the clear's own condition holds: a correction exists, every flagged or relabelled field has a later correction (or one written in this run), and every nulled field holds a value again. A rerun after a load plans nothing. Out of scope: filling the A-101-3 power and depth values, and any change to the clear's SQL, which stays the authority.

## Affected users / systems

`data/synth-catalog/population.py` (the provenance scheduler) and the `db-load.yml` dry-run receipts for staging and prod.

## Constraints / non-goals

No change to what is written: the SQL clear is unchanged, so the database still decides. When no archive history is passed (a unit test calling the scheduler directly), behaviour is as before.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Staging run 41005403304 planned 5 clears and module flags fell by 1 instead of 2 | `OBSERVED` | db-load receipts 41005403304 and 41005862481 |
| A-101-3's `modules` row was flagged for hp and had four power and depth fields nulled | `OBSERVED` | `provenance/modulargrid-reverify-v1.json` |
| Those fields are still empty on staging | `INFERRED` | the clear refused in the apply and is planned again in the next dry run |
| The planner now mirrors the clear's condition | `OBSERVED` | `backend/tests/test_catalog_corrections.py`, 84 catalog tests and 1311 backend tests green |

## Author / date

- Author: Claude Opus 5.5 for the operator
- Date: 2026-10-30
