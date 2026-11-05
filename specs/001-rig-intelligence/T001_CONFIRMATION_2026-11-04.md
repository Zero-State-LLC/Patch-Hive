# T001 confirmation: 001-rig-intelligence

Date: 2026-11-04. Code checked: `main` at 007b437 (0.3.0-alpha.8).

**Who confirmed this.** An agent ran this sitting under the owner's delegation. On 2026-11-04 the owner said "you can do all of this" about their open cards. The owner has not read the spec, and this record does not stand in for them reading it. They approve by merging the PR that adds this file. Delegation does not settle the legal call in O3: it stays with the owner and a lawyer.

**How claims were checked.** Each claim was read against the code, tests and prior owner decisions. The cited backend test files pass on SQLite with Python 3.11 (229 tests). The cited frontend test was read, not run. Where no repo test covers a behavior, a throwaway probe ran the real route or engine; these are marked "Probe" and are not committed. Nothing ran against Postgres, staging or production, and no production data was queried. Paths are relative to `backend/` unless they start with another top-level folder.

**Statuses.**

- CONFIRMED: code and spec agree.
- DRIFT: spec says X, code does Y. The [DRIFT list](#drift) says which is right, and T010 or T090 covers it.
- OPEN: a real product, legal or money call. Not decided here. The [OPEN list](#open) gives a recommended default.

**spec.md is unchanged.** The 001 checklist calls for no corrections, so the stale wording in D10 stays until T090.

## Claims

"Lines" are `spec.md` lines. A line can appear twice when its parts have different statuses.

### Owner checklist (`docs/evidence/OWNER_ACTIONS_2026-11-02.md`, "001 rig-intelligence")

| # | Lines | Claim | Status | Evidence |
|---|---|---|---|---|
| 1 | 81, 113, 119, 221, 417 | A readiness failure answers `NOT_COMPUTABLE` and creates no run (FR-022, SC-006). | CONFIRMED | `patches/routes.py:201-212`. Tests: `tests/unit/test_spec_001_transitions.py:102`, `tests/api/test_generate_bridge.py:102`. |
| 2 | 80 | Generation loads confirmed inventory only. | CONFIRMED | "Confirmed" means placed on the rack by its owner: `patches/inventory_gate.py:58-123,142-165`, `patches/validation.py:136-139`. Tests: `tests/unit/test_inventory_gate.py:14,31`, `tests/api/test_generate_bridge.py:210`. |
| 3 | 80, 218, 315, 316, 327, 342 | A run selects a rig revision, through `IDLE`, `RIG_LOADED` and `rig_selected`. | DRIFT (D1) | The request has no revision field (`patches/schemas.py:84-90`). The revision comes from the rack's current layout (`runs/bridge.py:213-218`). No handler has those states. Test: `tests/unit/test_run_bridge.py:92`. |
| 4 | 119, 329 | The `NOT_COMPUTABLE` receipt names the failed condition. | DRIFT (D2) | The gate writes the message (`patches/inventory_gate.py:187-190`), and the route drops it (`patches/routes.py:205-212`). The test asserts the code only (`tests/api/test_generate_bridge.py:102`). |
| 5 | 96 | Patch pages and the Patch Book are out of scope here. | CONFIRMED | No 001 FR renders a page. `export/patchbook/design/dual_write.py:26-119` writes records and renders nothing. Test: `tests/test_patchbook_api.py:84`. |
| 6 | 161 | A new revision never edits the old one. | CONFIRMED | `runs/bridge.py:223-235`, `canon/inventory_persist.py:19-21`. Tests: `tests/unit/test_run_bridge.py:92`, `tests/api/test_generate_bridge.py:163`, `tests/unit/test_inventory_persist.py:15`. |
| 7 | 161, 374, 385 | Confirming a module creates a new rig revision that includes it. | DRIFT (D3) | Confirming writes an `inv-rev-*` row only (`evidence/routes.py:716-735`). The gate and the bridge read `RackModule` (`patches/inventory_gate.py:54,73`, `runs/bridge.py:213`), and only `racks/routes.py:89,194` write it. Probe: on an empty rack, a confirm returned `ready_for_generation: true`, then 0 rack modules and 0 rig revisions, and generate answered `NOT_COMPUTABLE`. |
| 8 | 161 | How a photo-confirmed module, which has no position, joins the rig. | OPEN (O1) | See D3. The spec names the outcome, not the mechanism. |
| 9 | 266 | Rollback selects an earlier revision or run and never deletes. | CONFIRMED | Selection is read-only: `canon/routes.py:486-525`. Generated patches refuse edit and delete (`patches/routes.py:135-137,161-162`), and racks are soft-deleted (`racks/routes.py:228`). Tests: `tests/api/test_overlays_and_revisions.py:34`, `tests/unit/test_spec_001_transitions.py:188`, `tests/api/test_racks_api.py:292`. No route regenerates from an earlier revision, and no user story asks for one. |
| 10 | 319, 321 | The lifecycle holds `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED` and `NOT_COMPUTABLE`. | CONFIRMED | `patches/routes.py:216,241,252,300,320`. `FAILED` is stored as `failed` or `validation_failed`. `NOT_COMPUTABLE` is an answer with no run row. Test: `tests/unit/test_spec_001_transitions.py:89-138`. |
| 11 | 338, 339, 342, 343 | Illegal moves do not happen: `FAILED` never becomes `SUCCEEDED`, and `NOT_COMPUTABLE` leads nowhere. | CONFIRMED | By construction: the five assignments in row 10 are the only writers of a run's status, and `patches/routes.py:319` limits failure to `queued` or `running`. No guard rejects an illegal move, because nothing attempts one. Tests: `tests/unit/test_spec_001_transitions.py:143,163,176,188`. |
| 12 | 361, 391 | Evidence never skips the proposal step, and nothing self-confirms. | CONFIRMED | `canon/visual_contracts.py:109-116`, `evidence/vision_provider.py:108-110`, `evidence/routes.py:660-665`, `intelligence/resolution_machine.py:293-299`. Tests: `tests/unit/test_visual_system_intelligence.py:81,99,142`, `tests/unit/test_resolution_machine.py:147,263`. |
| 13 | 372, 374, 375 | The evidence lifecycle runs as the five named states. | DRIFT (D7) | No code has those five states. The rules run through `intelligence/resolution_machine.py:20-32` and the decisions at `evidence/routes.py:667-690`. Low confidence and "none of the above" end `UNRESOLVED`, never rejected (`intelligence/policy.py:68-70,89`; test `tests/unit/test_decision_intelligence.py:96`). |
| 14 | 375, 386 | `REJECTED` is recorded and final. | DRIFT (D8) | A reject drops the candidate (`canon/inventory.py:74-77`), and no decision is stored (`canon/inventory_persist.py:23-34`). Probe: the rejected id is absent from the revision row, the candidate stays listed, and a later confirm answers 201. |
| 15 | 425 | A module matching two classes may serve in more than one role. | CONFIRMED | Independent checks at `patches/engine.py:117-135`. No repo test uses a two-class type. Probe: a `VCO LFO` module was wired both as an oscillator and as an LFO. |
| 16 | 425 | Whether one module may fill two roles in one patch. | OPEN (O2) | The spec leaves it undefined, and the code allows it. Probe over seeds 0 to 59: 73 kept patches used one module as both VCO and LFO. |
| 17 | 264 | Photos and overlays "may be personal", the assumption behind the retention decision. | OPEN (O3) | Code already treats them as private (`racks/access.py:63-68`, `canon/routes.py:537-542`, `evidence/images.py:88-92`). The retention rule on top of that is provisional and a lawyer must confirm it. |

### Other `[INFERRED]` lines

| # | Lines | Claim | Status | Evidence |
|---|---|---|---|---|
| 18 | 74 | FR-031 row: no 001 surface renders a page, and the legacy book is off by default. | CONFIRMED | `core/config.py:119`. Test: `tests/test_patchbook_api.py:84`. |
| 19 | 228 | Each run binds to its source rig revision (FR-026). | CONFIRMED | Bound before `running`, so failed runs bind too: `patches/routes.py:226-232`, `runs/bridge.py:237-251`. Tests: `tests/api/test_generate_bridge.py:44,126`. |
| 20 | 318, 330 | `RUNNING` means a worker runs compiler stages, and `worker_started` records a start receipt. | DRIFT (D4) | No worker exists. The request handler runs generation inline (`patches/routes.py:181,241-246`). No start receipt is written. |
| 21 | 320, 332 | A `validation_failed` run keeps its report and saves no patches. | CONFIRMED | `patches/routes.py:252-253`. Test: `tests/unit/test_spec_001_transitions.py:120`. |
| 22 | 265, 320, 332, 333 | Each run stage emits a `StageReceipt`, and failed runs keep theirs. | DRIFT (D5) | Receipts are written per patch at compile time (`export/patchbook/design/dual_write.py:37-38,91-104`). The test covers success only (`tests/api/test_generate_compiler_path.py:42`). Probe: success 3 per patch; `validation_failed`, `failed` and zero-patch runs 0. A `failed` run also keeps no reason (`patches/routes.py:316-322`). |
| 23 | 319 | `SUCCEEDED` means the manifest is sealed. | DRIFT (D6) | `canon/compiler.py:340-351` builds a manifest, and the dual-write does not store it. `artifact_manifests` (`canon/models.py:173`) has no writer. The library hash comes from ids (`runs/bridge.py:107-109`). Probe: 0 manifest rows after a successful run. |
| 24 | 327 | Guard: the rig has a case. | CONFIRMED | `racks.case_id` is NOT NULL: `racks/models.py:24-26`, `alembic/versions/20240919_legacy_foundation.py:99`. Test: `tests/unit/test_models.py:365`. |
| 25 | 328 | Readiness passes: a `queued` run bound to the revision and seed. | CONFIRMED | `patches/routes.py:216,226-232`. Test: `tests/api/test_generate_bridge.py:126`. |
| 26 | 334 | Retry creates a new run and leaves the failed one unchanged. | CONFIRMED | Retry is another generate call. Test: `tests/unit/test_spec_001_transitions.py:143`. There is no separate `retry` event (D1). |
| 27 | 415 | SC-004: no test path performs an illegal transition. | CONFIRMED | Run lifecycle: rows 10 and 11. Evidence: `tests/unit/test_resolution_machine.py:126`. This is a universal claim, so it rests on reading the status writers, not on an exhaustive check. |
| 28 | 423 | Zero patches: the resulting state is undefined. | DRIFT (D10) | Stale. OQ-07 settled it as `succeeded`: `patches/validation.py:123-124`. Tests: `tests/unit/test_patch_validation.py:76`, `frontend/src/lib/generateOutcome.test.ts:47`. Probe: status `succeeded`. |
| 29 | 292, 294, 295, 296 | Workflows: the three skills, FORGE decomposes, a cloud agent implements, reuse `ci.yml`. | CONFIRMED | `AGENTS.md`, "Skills". `.github/workflows/ci.yml` is still the CI path. Org pack: `agent-context/DECISIONS.md:45`, `agent-context/templates/sdlc/README.md:45`. |
| 30 | 295, 296 | Workflows: SCRIBE files the artifact, and CI has jobs `backend` and `frontend`. | DRIFT (D11) | SCRIBE appears only in spec and plan text here. I found it in none of `DECISIONS.md`, `TEAM.md`, `HANDOFF.md` or `templates/sdlc/README.md` in `agent-context`. `ci.yml` has six jobs (lines 17, 52, 83, 115, 139, 165). |
| 31 | 434, 435 | OQ-01: a `Rack` is the mutable rig, and a rig revision is its immutable snapshot. | CONFIRMED | `runs/bridge.py:42-47,213-235`. Tests: `tests/unit/test_run_bridge.py:30,92`. |
| 32 | 451, 452 | OQ-09: readiness is at least one `USER_CONFIRMED` module and one confirmed catalog module. | CONFIRMED | `canon/inventory.py:207-214`, `patches/inventory_gate.py:179`. Test: `tests/unit/test_inventory_gate.py:24`. The "require a case?" choice is moot: see row 24. |

### Found while checking (not `[INFERRED]`)

| # | Lines | Claim | Status | Evidence |
|---|---|---|---|---|
| 33 | 111, 209 | Default config produces no feedback routes (P1.5, FR-013). | DRIFT (D9) | Only a direct self-cable is flagged (`patches/validation.py:184-187`). Probe: a `VCO VCA` module with a VCF produced `1 -> 2 -> 1`, the run ended `succeeded`, and the sealed report said `valid: false` with `UNDECLARED_FEEDBACK_CYCLE` (`canon/compiler.py:159-167`). 150 sealed patches from ordinary racks were all valid. |

**Counts:** 33 rows: 19 CONFIRMED, 11 DRIFT, 3 OPEN.

## DRIFT

| ID | Spec says, code does | Which is right | Covered by |
|---|---|---|---|
| D1 | Spec: explicit revision selection through `IDLE`, `RIG_LOADED`, `rig_selected`. Code: the rack's current layout selects the revision, and the run records it. | Code. A revision id is a function of the layout, so the selection is exact. Generating from an older revision would be new behavior no story names. ADR 0001 names explicit selection as a cost of its design, so T090 should say how the code meets it. | T010 de-scopes those rows. T090 edits the table. |
| D2 | Spec: the receipt names the failed condition. Code: the answer carries only the code. | Spec. The message already exists and is dropped. | T090. |
| D3 | Spec: a confirmed module enters a new rig revision. Code: it enters an `inv-rev-*` row that generation never reads, and the answer says `ready_for_generation: true`. | Spec on the outcome: this is the AGENTS.md path "image, evidence, user confirm, inventory". The mechanism waits on O1. | T090, after O1. |
| D4 | Spec: a worker and a start receipt. Code: synchronous handler, no start receipt. | Code on the worker: nothing needs a queue. The receipt question goes with D5. | T090 edits the table. |
| D5 | Spec: every stage emits a receipt, and failed runs keep them. Code: per-patch receipts on success only, and a `failed` run keeps no reason. | Spec. A failed run must say why. | T010 asserts today's success path. T090 adds the rest, with its tests. |
| D6 | Spec: the run seals an `ArtifactManifest` (also SC-003). Code: built, not stored. | Spec. | T090. |
| D7 | Spec: five named evidence states. Code: the spec 005 machine plus confirm decisions. | The spec's rules and the code's names. The rules hold in code; a second state machine would duplicate spec 005. | T010 encodes the rules through a mapping (`plan.md`). T090 replaces the table. |
| D8 | Spec: a rejection is recorded and final. Code: no record, and it can be reversed by a later batch. | Spec on the record (FR-025). A person changing their mind is fine if that is recorded too. | T090. |
| D9 | Spec: no feedback routes by default. Code: a loop through a second module passes. | Spec. Reachable only with a two-class type, so it follows O2. | T090. |
| D10 | Stale text. Line 423: zero patches undefined. Line 452: "No case is required". Line 454: account deletion undefined, though `account/deletion.py:9-14` exists (test: `tests/api/test_account_deletion.py:180`). | Code. | T090 edits the text. |
| D11 | Spec: SCRIBE, and two CI jobs. Code and org pack: no SCRIBE, six jobs. | Code and org pack. `AGENTS.md`: "Do not invent skills or bots." I searched only the files listed in row 30. | T090 edits the text. |

T010's own drift list (`tasks.md`) is covered by D1, D5, D7 and row 11.

## OPEN

| ID | Question | Kind | Recommended default | Evidence |
|---|---|---|---|---|
| O1 | How does a photo-confirmed module join the rig? A photo gives no reliable row or HP position. | Product | No auto-placement. Confirming lists the module as still to place. Placing it uses the existing rack route, which checks fit, and the next run mints the revision. `ready_for_generation` reports the rack's real state. Other options: place it in the first free slot, or generate from the inventory revision with no position. | Row 7. Waits on this: only the D3 step of T090. |
| O2 | May one module fill two roles in one patch? | Product, hardware truth | No, unless the catalog declares independent sections. A type string does not prove a module's sections work at the same time, and assuming so invents a hardware fact. Bump `patch_engine_version` if golden output changes. | Rows 16 and 33. The committed catalog has no two-class value: 4,563 category values in 23 files under `data/synth-catalog`, 11 distinct, and `modules/catalog_routes.py:282` sets the type from one category. So it is reachable today only through a type entered by hand (`admin/routes.py:386,428`). Production was not queried. |
| O3 | How long are photos, OCR output and overlays kept, and who sees them? | Legal | Keep `minimal_images_only` as built, treat all three as personal data, and have a lawyer confirm. Two owner follow-ups: whether images already stored for up to 365 days get shortened, and scheduling expiry (spec 006 T101b, T101c). | `evidence/routes.py:40-42,133-134`, `evidence/retention.py:14`, `evidence/expire.py:8` ("Nothing schedules this"), `account/deletion.py:9-14`. Tests: `tests/api/test_evidence_upload.py:138,203`. `docs/evidence/JEV_DECISIONS_2026-11-01.md`: provisional, confidence 0.29, and the top two options were 0.47 and 0.45 (`docs/evidence/jev-decisions-2026-11-01.json:199-208`). |

Not `[INFERRED]` claims, carried in `plan.md`: the production image scanner (spec line 284 says it needs an owner decision), and the Path B fallback.

## Why T001 is ticked

No claim needs a human product decision before planning. D3 came closest, because a photo-confirmed module cannot reach generation today. But the spec already states the outcome, so that is a code gap. Only the mechanism is a product call, and it blocks one step of T090, not the plan. The owner should read O1 before merging.

Not done, for the owner or the next agent: `AGENTS.md` "Escalation" asks for a bounded `bug` issue when a suite looks green but inert. `tests/api/test_evidence_confirmations.py:47` asserts `ready_for_generation` on a rack that already holds modules and never generates, so it cannot see D3. This PR is docs only, so no issue was opened.
