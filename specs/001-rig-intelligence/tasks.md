# Tasks: 001-rig-intelligence

## Setup

- [x] T001 Confirm the spec with the operator (it is INFERRED today). Done 2026-11-04 by an agent under the owner's delegation, not by the owner reading it: [T001_CONFIRMATION_2026-11-04.md](T001_CONFIRMATION_2026-11-04.md).
- [x] T002 Write plan.md. Done 2026-11-04 under the same delegation: [plan.md](plan.md), no longer a draft; three owner calls stay open in the T001 record.
  - depends_on: [T001]

## Foundational

- [x] T010 Encode the transitions table as tests (workflows: anti-slop-code, production-systems). Done 2026-11-06, through the mapping in [plan.md](plan.md). `backend/tests/unit/test_spec_001_transitions.py` holds the run lifecycle: every spec row is encoded or says why it isn't (`rig_selected` and `retry` have no handler, D1; `worker_started` moves the status but has no worker or start receipt, D4), the illegal moves are pinned by checking that `run_generation` is the only writer of a run's status, and stage receipts are asserted on the success path. `backend/tests/unit/test_spec_001_evidence_rules.py` names the test that holds each evidence row. T090 then added what these tests couldn't yet assert: recorded rejects (D8) and failed-run receipts (D5).
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

- [x] T033 Hash the generation IR's canonical JSON (modules, seed, all params, engine and ABX-Core versions; not run id, time, commit or host) into the 32-character `generation_ir_hash`, with a test that a module change changes the hash (FR-001; research R3). Done 2026-10-29.
  - depends_on: []
- [x] T032 Read `allow_feedback` (drop patches with a `FEEDBACK_LOOP` finding when false, counted in provenance) and `prefer_simple` (stable sort by cable count before the `max_patches` cut); bump `patch_engine_version` if a golden output changes (FR-013, P1.5; research R2). Done 2026-10-29.
  - depends_on: [T033]
- [x] T030 Run `canon.compiler.compile_patch` for each patch that passes validation in `run_generation`, compare it with the dual-write adapter in tests, then store the compiler's plan, report and stage receipts; move the `run_canon_pipeline` demo rig into a test fixture (FR-004, FR-015, FR-016, P5.2; research R1). Done 2026-10-29: `compile_orm_patch` runs `compile_patch` for each validated patch; the dual-write stores its graph, plan, report, variations and 3 stage receipts per patch (`stage_receipts`); tests compare it with the adapter; the demo rig is `tests/canon_demo_pipeline.py`. Path B still uses the adapter.
  - depends_on: [T032]
- [x] T031 Emit a `RigMetricsPacket` per rig revision with `rig_id`, `module_count` and `category_counts`; the six scores are `NOT_COMPUTABLE` until OQ-11 defines them (FR-027; research R1). Done 2026-10-29: `canon/rig_metrics.py` stores one packet per rig revision in `rig_metrics_packets` (migration `20261029_rig_metrics_packets`); `total_hp` is added when every width is known.
  - depends_on: [T030]
- [x] T035 Define `routing_flex_score` and `performance_density_index`; keep the other four scores `NOT_COMPUTABLE` (FR-027; OQ-11 decided 2026-10-30 by the owner: option 2; decision 11 in `docs/evidence/OPEN_DECISIONS_2026-10-30_RESEARCH.md`). Done 2026-10-30: `canon/rig_scores.py` holds the formulas (`routing_flex_score = round(1 - exp(-(total_ports / module_count) / 8), 4)`, `performance_density_index = round(total_ports / total_hp, 4)`), metrics version `canon-metrics.1.2.0`, and the formula plus covered fraction (modules with ports / modules) in `confidence_notes`. Either score is `NOT_COMPUTABLE` if any module has missing or empty `io_ports`; the density index also if any HP is null or 0; zero is never substituted. No blank-panel exemption: the module row has no reliable marker (`category_raw` is seed-only, and "Blank Panel / Multiple" also covers real modules). `canon.runes.map_metrics` uses the same function, so `suggest_layouts` raises on `NOT_COMPUTABLE` and scores when a number. Packets sealed before keep their hash. With today's catalog only about 3 modules carry `io_ports`, so most real rigs stay `NOT_COMPUTABLE` until a port-data pass exists.
  - depends_on: [T031]
- [x] T034 Rig page: show blocking findings for `VALIDATION_FAILED`, keep the inventory hint for `NOT_COMPUTABLE` only, and say "no patch rule fits this rack" for zero patches (frontend `RigDetail.tsx`; research R4). Done 2026-10-29.
  - depends_on: []

## Polish

- [x] T090 Converge the code against the spec. Done 2026-11-06: D2, D5, D6 and D8 (#321), D3 (#289, owner decision 35), D9 and one role per module (#322, owner decision 36), and the spec edits for D1, D4, D7, D10 and D11 (#322). The code is on `main` and not deployed: #321's migration has to run first.
  - depends_on: [T010, T030, T031, T032, T033, T034]
