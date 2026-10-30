# Intent

## Problem

Spec 001 research R1: `canon.compiler.compile_patch` runs only in tests. Real runs get their plan, report and receipts from the dual-write adapter, which fills the five phases mechanically and seals one `design_engine` receipt. No `RigMetricsPacket` is emitted for a real rig (FR-004, FR-015, FR-016, FR-027; tasks T030, T031).

## Proposed outcome

- `run_generation` compiles each validated patch with `compile_patch`. The dual-write stores the compiler's graph, plan, report and variations on the `GeneratedPatchRecord` and its stage receipts in `stage_receipts`.
- Tests compare the compiler output with the adapter on the same patch.
- The `run_canon_pipeline` demo rig moves to `backend/tests/canon_demo_pipeline.py`.
- Each rig revision gets one `RigMetricsPacket` (`rig_id`, `module_count`, `category_counts`, `total_hp`). The six scores are `NOT_COMPUTABLE`.
- Out of scope: score formulas (OQ-11); switching the Path B compile-on-export fallback to the compiler; a compiler `ValidationReport` that fails the run.

## Affected users / systems

Patch generation, the canon tables (`generated_patches`, `stage_receipts`, new `rig_metrics_packets`), the Patch Book Path A load, `canon/contracts.py` and its TypeScript binding.

## Constraints / non-goals

`NOT_COMPUTABLE` over invented scores. No audio, no hardware control. A new Alembic revision, `20261029_rig_metrics_packets`, extends `20261029_ledger_append_only`; another slice may add a revision after the same head, so a merge-order head fix may be needed.

## Open questions

- OQ-11: formulas for the six scores. Owner decides.
- Should compiler findings of `error` severity (for example an undeclared feedback cycle under `allow_feedback`) fail the run? Today the report is stored and the run still succeeds.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The compiler was called only from tests | `OBSERVED` | research R1, repo grep 2026-10-29 |
| The six scores have no formula | `NOT_COMPUTABLE` | spec OQ-11 |
| Path B (compile on export) still uses the adapter, so its plan differs from Path A | `OBSERVED` | `content_spine._load_path_b` |

## Author / date

- Author: Claude (slice c4-rig)
- Date: 2026-10-29
