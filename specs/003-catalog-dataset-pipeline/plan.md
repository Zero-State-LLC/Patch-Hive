# Plan: 003-catalog-dataset-pipeline

TODO: Tech stack and architecture, drawn from the sources listed in spec.md. Carry the spec's Workflows list and transitions table forward unchanged. (T002, after the operator confirms the spec in T001.)

## Addendum: catalog corrections and one loader (2026-10-29)

Scoped plan for T032–T033. Decisions: D4, D5 in spec.md; evidence in research.md R1–R2.

Stack (unchanged):
- **Loader:** Python, `data/synth-catalog/population.py`, plain SQL through SQLAlchemy `text()`.
- **Database:** Postgres 15 (Neon); loads through `db-load.yml` (dry run, then apply bound to `plan_hash`).
- **Placement guard:** `backend/racks/validation.py`.

**T032 (D5)**
- Delete `scripts/seed_catalog_from_synth.py`, `backend/scripts/seed_catalog_from_synth.py` and `backend/tests/unit/test_seeder_catalog.py`.
- Nothing calls them; the registry reads `module_catalog` (#114).

**T033 (D4, FR-038)**
- `ARCHIVE_ACTIONS` gains `correct`. An entry needs `field`, `only_if_value`, `value` and `evidence_url`. HP values must lie in 1–42 (FR-007).
- `_schedule_provenance` archives the current value as for every action. A follow-up `UPDATE` sets the field to `value` only where the archived copy (action `correct`) equals the current value, so a re-run, or a value changed since review, writes nothing. The archive row keeps the evidence URL in `source_tag`.
- `hp_needs_reverify` blocks only while an `hp` flag row exists and no `hp` correct row does.
- New manifest `provenance/maker-corrections-v1.json`, appended to `PROVENANCE_MANIFESTS`.
- Row lifecycle transition `FLAGGED -correct-> LIVE` (spec.md, Row lifecycle).

Verification:
- unit tests for the action (match, mismatch, re-run, validation) and the guard;
- the Postgres population test;
- a staging dry run showing exactly the CHICANE updates, then apply, a rerun with no changes, and a prod dry run for review.
