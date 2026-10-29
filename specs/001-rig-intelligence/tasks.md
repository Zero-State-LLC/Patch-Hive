# Tasks: 001-rig-intelligence

## Setup

- [ ] T001 Confirm the spec with the operator (it is INFERRED today)
- [ ] T002 Write plan.md
  - depends_on: [T001]

## Foundational

- [ ] T010 Encode the transitions table as tests (workflows: anti-slop-code, production-systems)
  - depends_on: [T002]

## Implemented (reconciled 2026-10-29)

- [x] T020 Readiness gate before a run exists, a `NOT_COMPUTABLE` answer with no run, and real provenance on each patch (FR-018, FR-022, FR-024; #88).
  - depends_on: []
- [x] T021 Keep runs and generated patches append-only: reads write nothing; a generated patch cannot be renamed or deleted (409 `GENERATED_PATCH_IS_APPEND_ONLY`) (FR-020; #92).
  - depends_on: []
- [x] T022 Soft-delete racks so their runs and patches stay; `runs.rack_id` and `patches.rack_id` are RESTRICT (OQ-02; #93).
  - depends_on: []
- [x] T023 Five canonical categories only, and no invented `Study` padding (FR-012, FR-017, OQ-03; #94).
  - depends_on: []
- [x] T024 Six more patch rules, each needing every module it wires (FR-011; #96).
  - depends_on: []
- [x] T025 Resolve generic jacks to declared ones, mark the rest `unresolved`, and fail a run on a contradiction with a validation report (FR-016, FR-017, OQ-04, OQ-08; #97).
  - depends_on: []
- [x] T026 Count unknown module power per rail instead of as 0 mA (FR-017; #118).
  - depends_on: []
- [x] T027 Warn when a rack holds a retired module (`MODULE_TOMBSTONED`) (FR-005; #122).
  - depends_on: []
- [x] T028 Every run ends terminal, and the admin rerun goes through `run_generation` and its readiness gate (FR-018, FR-019, OQ-07; #131).
  - depends_on: []

## Gap closure (2026-10-29)

- [ ] T033 Hash the generation IR's canonical JSON (modules, seed, all params, engine and ABX-Core versions; not run id, time, commit or host) into the 32-character `generation_ir_hash`, with a test that a module change changes the hash (FR-001; research R3).
  - depends_on: []
- [ ] T032 Read `allow_feedback` (drop patches with a `FEEDBACK_LOOP` finding when false, counted in provenance) and `prefer_simple` (stable sort by cable count before the `max_patches` cut); bump `patch_engine_version` if a golden output changes (FR-013, P1.5; research R2).
  - depends_on: [T033]
- [ ] T030 Run `canon.compiler.compile_patch` for each patch that passes validation in `run_generation`, compare it with the dual-write adapter in tests, then store the compiler's plan, report and stage receipts; move the `run_canon_pipeline` demo rig into a test fixture (FR-004, FR-015, FR-016, P5.2; research R1).
  - depends_on: [T032]
- [ ] T031 Emit a `RigMetricsPacket` per rig revision with `rig_id`, `module_count` and `category_counts`; the six scores are `NOT_COMPUTABLE` until OQ-11 defines them (FR-027; research R1).
  - depends_on: [T030]
- [ ] T034 Rig page: show blocking findings for `VALIDATION_FAILED`, keep the inventory hint for `NOT_COMPUTABLE` only, and say "no patch rule fits this rack" for zero patches (frontend `RigDetail.tsx`; research R4).
  - depends_on: []

## Polish

- [ ] T090 Converge the code against the spec
  - depends_on: [T010, T030, T031, T032, T033, T034]
