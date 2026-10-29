# Research: 001-rig-intelligence

Decision research for the open 001 gaps (2026-10-29). Each item gives the evidence, the options, a recommendation and the effort (S, M or L). Labels follow the spec: `[OBSERVED: <source>]` or `[INFERRED]`. The fixes already merged (#88, #92, #93, #94, #96, #97, #118, #122, #131) are listed in the spec's implementation status, not here.

## R1. The canonical compiler is not on the generation path (FR-004, FR-015, FR-027; P5.2)

**Evidence**

- `canon.pipeline.run_canon_pipeline` is called only from tests (`tests/unit/test_pipeline_run.py`, `tests/unit/test_export_pack.py`). It builds a fixed two-module "MockAudio" demo rig, not a user's rack [OBSERVED: backend/canon/pipeline.py].
- `canon.compiler.compile_patch` builds the five-phase `PatchPlan` (prep, threshold, peak, release, seal), runs `validate_patch_graph` and seals `StageReceipt` records. Outside tests, only `canon/pipeline.py` calls it [OBSERVED: backend/canon/compiler.py, repo grep 2026-10-29].
- Real generation is `patches.routes.run_generation` → `patches.engine.generate_patches_with_ir` → `patches.validation.resolve_and_validate`. None of these calls the canonical compiler [OBSERVED: backend/patches/routes.py, backend/patches/engine.py].
- After a run succeeds, the Design Engine dual-write seals a `PatchGraph`, `PatchPlan`, `ValidationReport` and one `StageReceipt` (stage `design_engine`) per patch through `seal_orm_patch_to_compilation`. That adapter spreads the cables over the five phases mechanically; a phase with no cable reads "verify prior connection …" or "no cables (UNKNOWN topology)" [OBSERVED: backend/export/patchbook/design/dual_write.py, backend/export/patchbook/design/content_spine.py].
- The canon `RigMetricsPacket` holds `module_count`, `total_hp` and `routing_flex_score` [OBSERVED: backend/canon/contracts.py]. FR-027 lists nine fields. The historical `patchhive/ops/map_metrics.py` returns a constant `routing_flex_score=0.75` [OBSERVED]. Nothing on the generation path emits a packet.

**Options**

1. Call `compile_patch` from `run_generation` for each patch that passes `resolve_and_validate`, and have the dual-write store its output instead of the adapter's. The run then carries real per-stage receipts and the compiler's `ValidationReport`.
2. Keep the adapter and amend FR-004: the canonical compiler runs at export time only. This leaves P5.2 unmet for runs that are never exported.
3. Delete `run_canon_pipeline` and `compile_patch` as unused. This drops the only code that builds a five-phase plan from a graph.

**Recommendation:** option 1, in two steps. First run `compile_patch` beside the adapter and compare both outputs in tests. Then switch the dual-write to the compiler output and move the demo rig in `run_canon_pipeline` into a test fixture. For `RigMetricsPacket`, emit `rig_id`, `module_count` and `category_counts` on each rig revision now. The six scores have no formula (OQ-11). Mark them `NOT_COMPUTABLE` instead of writing a number. Effort: L.

## R2. `allow_feedback` and `prefer_simple` are never read (FR-013)

**Evidence**

- Both flags are stored in `PatchEngineConfig`, in the IR params and in each patch's `engine_config` [OBSERVED: backend/patches/engine.py, backend/patches/routes.py].
- `PatchGenerator.generate_patches` reads only `max_patches`, at the final cut [OBSERVED: backend/patches/engine.py].
- `resolve_and_validate` adds a `FEEDBACK_LOOP` finding of kind `flag` when a module is patched into itself. The finding does not drop the patch [OBSERVED: backend/patches/validation.py].
- P1 criterion 5 ("no feedback routes" by default) is therefore not enforced, only observed [INFERRED].

**Options**

1. Enforce both flags. When `allow_feedback` is false, drop a patch that has a `FEEDBACK_LOOP` finding, and record the count in provenance. When `prefer_simple` is true, sort candidates by cable count before the `max_patches` cut. Use a stable sort, so ties keep rule order.
2. Remove both flags from the request, config and FR-013.
3. Leave them stored and unread, and say so in FR-013.

**Recommendation:** option 1. Both flags are small, and the default output changes only if a current rule emits a self-patch. Bump `patch_engine_version` if any golden output changes. Effort: S.

## R3. The generation IR hash leaves out the inventory and engine version (FR-001)

**Evidence**

- `PatchGenerationIR.get_canonical_hash` hashes `rack_id:seed:max_patches:allow_feedback` and keeps 16 hex characters [OBSERVED: backend/core/ir.py].
- It leaves out `prefer_simple`, the rack's modules (`rack_state.modules`), `engine_version` and `abx_core_version`. Two runs on the same rack and seed get the same hash after the rack's modules change [INFERRED from the code].
- The value is written to `patches.generation_ir_hash` (`String(32)`, commented "Hash for deduplication"). No code reads it back [OBSERVED: backend/patches/models.py, repo grep 2026-10-29].

**Options**

1. Hash the IR's canonical JSON without `run_id`, `created_at`, `git_commit` and `host`. Keep 32 hex characters, so the column needs no migration.
2. Stop writing the field.

**Recommendation:** option 1. Rows already written keep their old values (append-only). Their `generation_version` tells the two forms apart. Effort: S.

## R4. The rig page hides validation findings (frontend)

**Evidence**

- `RigDetail.tsx` treats `NOT_COMPUTABLE` and any zero-patch result alike: "Generation {status}: no patches produced … Confirm inventory modules, then retry." [OBSERVED: frontend/src/pages/RigDetail.tsx].
- For `VALIDATION_FAILED` the response carries `validation`, the report with each blocking finding [OBSERVED: backend/patches/routes.py]. The page does not show it.
- A computable rack that no rule fits ends `succeeded` with zero patches (OQ-07). The page tells that user to confirm inventory, which won't help [INFERRED].

**Options**

1. Branch on `generation_status`. `NOT_COMPUTABLE` keeps the inventory message. `VALIDATION_FAILED` lists each blocking finding (code, message, cable number) and says nothing was saved. Success with zero patches says no patch rule fits this rack.
2. Show the raw report JSON.

**Recommendation:** option 1. Effort: S.

## R5. Readiness conditions (OQ-09)

**Evidence:** a rack is ready when its inventory has at least one `USER_CONFIRMED` module and at least one confirmed catalog module id [OBSERVED: backend/canon/inventory.py `inventory_ready_for_generation`, backend/patches/inventory_gate.py `evaluate_rack_inventory_gate`]. No case or HP condition is checked.

**Recommendation:** record the built rule as the answer to OQ-09. Adding "the rig has a case" is an owner choice; nothing in the engine needs one today [INFERRED]. Effort: none.

## R6. Rack versus rig revision (OQ-01)

**Evidence:** each run binds to a `RigRevisionRecord` with id `rig-rev-{content_hash[:32]}`, a hash of the rack's layout snapshot (`patchhive.rack-snapshot.v1`). The generation run id is `gen-run-{run_id}-{hash16}` and the library is `library-{source_run_id}` [OBSERVED: backend/runs/bridge.py].

**Recommendation:** record that answer. A `Rack` is the mutable rig. A rig revision is the immutable snapshot that a run generates from. Effort: none.

## R7. Abraxas feedback store (FR-028)

**Evidence:** no table, model or route stores Abraxas feedback [OBSERVED: repo grep 2026-10-29 for abraxas feedback]. The read-only query surface exists (`canon/query_surface.py`) [OBSERVED].

**Recommendation:** defer. Nothing sends feedback yet. Build the store with the bridge that sends it, and keep it apart from canon tables. No task until the bridge is planned. Effort: M when needed.

## R8. Questions only the owner can answer

OQ-10 (privacy and retention), OQ-11 (metric formulas) and OQ-13 (threat model) stay open. For OQ-10, image evidence already expires at `retention_expires_at` [OBSERVED: backend/evidence/retention.py]. The retention period itself and the overlay rules are still the owner's to set.
