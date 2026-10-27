# Tasks: 003-catalog-dataset-pipeline

## Setup

- [ ] T001 Confirm the spec with the operator (it is INFERRED today)
- [ ] T002 Write plan.md
  - depends_on: [T001]

## Owner decisions D1/D2 (2026-10-27)

- [x] T020 Strip ModularGrid-derived descriptions from the Phase 2 seed and catalog rows, and tag those rows `access_basis = unknown` / `CATALOG_OBSERVED`. Exclude them from bulk publication and export (FR-033).
  - depends_on: []
- [x] T021 Refuse rack placement of modules whose HP is flagged `needs_reverify`, with tests (FR-035).
  - depends_on: []
- [x] T022 Restrict `scripts/hermes_hp_enrich_firecrawl.py` to official manufacturer pages and manuals: remove the retailer fallback and record `access_basis = official_publication` (FR-004, D2).
  - depends_on: []

## Foundational

- [ ] T010 Encode the transitions table as tests (workflows: anti-slop-code, production-systems)
  - depends_on: [T002]

## Polish

- [ ] T090 Converge the code against the spec
  - depends_on: [T010]
