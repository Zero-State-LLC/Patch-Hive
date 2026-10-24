# Spec 008 Operator Notes (Dual-Path F5 Cutover & Design Engine Staging Receipts)

Status: the code paths for T010-T060 are implemented and tested in-repo. The
walkthrough was run in-process (FastAPI TestClient, SQLite, synthetic golden
demo seed) only. No staging host walkthrough has been run, no receipt has been
captured on staging, and the readiness docs are NOT pinned: they carry the
placeholder `PENDING_OPERATOR_WALKTHROUGH`. No runtime config, routing, DNS, or
payment setting is changed by this repository.

T001 (feature tree and `specs/README.md` index line) was already satisfied on main
by the spec PR that added `tasks.md`; no further change was needed.

## Modules

| Task | Code | Artifact |
| --- | --- | --- |
| T010 | `backend/core/ops/f5_cutover.py` `collect_alias_evidence`; `backend/core/ops/design_walkthrough.py` `collect_live_alias_evidence` | `AliasParityEvidence` (`patchhive.f5-alias-evidence.v1`) |
| T020 | `frontend/src/pages/Racks.tsx`, `frontend/src/pages/Modules.tsx`, `frontend/src/lib/canonRigAdapter.ts`; `collect_fe_cutover_evidence` | `FeCutoverEvidence` (`patchhive.f5-fe-cutover.v1`) |
| T030 | `scripts/seed_golden_demo.py` (single source of demo credentials); `check_seed_auth` (read-only) | `SeedAuthCheck` (`patchhive.seed-auth-check.v1`) |
| T040 | `scripts/staging/design_engine_walkthrough.py`; `execute_walkthrough`; `start_walkthrough`; `capture_walkthrough_receipt` | `WalkthroughStart`, `WalkthroughReceipt` (`patchhive.design-walkthrough-receipt.v1`) |
| T050 | `pin_readiness_docs`; Spec 008 sections in `docs/evidence/PRODUCTION_READINESS_MATRIX.md` and `docs/evidence/DOMAIN_CUTOVER_CHECKLIST.md` | `ReadinessPin` (`patchhive.readiness-pin.v1`) |
| state machine | `backend/core/ops/f5_cutover.py` | INVENTORY_LEGACY -> F5_ALIAS_LIVE -> FE_CUTOVER -> WALKTHROUGH_PENDING -> RECEIPT_CAPTURED -> BETA_ELIGIBLE |
| T060 | `backend/tests/integration/test_008_f5_cutover_machine.py`, `backend/tests/integration/test_008_f5_live.py` | gate, path, and exhaustive tests |

Every artifact is a frozen record sealed by `record_sha256` and carries the SHA
of the artifact before it. The machine re-verifies integrity and SHA links on
every transition; a rejected event is recorded and the state does not change.
BETA_ELIGIBLE is terminal.

Records hold hashes, flags, step outcomes, and HTTP status codes only. They never
hold passwords, tokens, database URLs, or pack bytes (the pack zip is reduced to
its SHA-256).

## Operator procedure (staging)

1. Bring up the staging compose stack with the design-engine overlay
   (`docker-compose.staging.design-engine.yml`). It must keep
   `STRIPE_TEST_MODE=true` and `ALLOW_PRODUCTION_PAYMENTS=false`.
2. Check out the exact commit to be pinned. Set `DATABASE_URL`,
   `STAGING_API_URL`, and `PYTHONPATH=backend` in the shell (do not paste the DB
   URL into any doc or ticket). Optionally set `WALKTHROUGH_SOURCE_SHA`; otherwise
   `git rev-parse HEAD` is used.
3. Run `python scripts/staging/design_engine_walkthrough.py --receipt-out design-walkthrough-receipt.json`.
   The script seeds the golden demo, verifies the seeded credentials read-only
   (it never rewrites a password hash), collects alias and FE cutover evidence,
   calls `POST /api/patches/generate/{rig_id}` once on the seeded rig for the F3
   dual-write audit, runs preview -> credit grant -> export debit -> fulfillment ->
   download token -> download pack with the seeded accounts, and writes the
   evidence bundle. It exits non-zero (fail closed) on seed auth drift, health
   failure, non-test-mode flags, any failed step, or an unpinned source SHA.
   If seed auth is not aligned, re-run the seeder; do not patch credentials.
4. Pin (T050). Replace each `PENDING_OPERATOR_WALKTHROUGH` value in both docs
   with the receipt values (`receipt.source_commit_sha`, `receipt.record_sha256`,
   the Spec 007 enablement `receipt_sha256`, and the open P0 list, which must be
   empty). Then call `pin_readiness_docs(receipt=..., documents={path: text},
   unresolved_p0=(), enablement_receipt=<Spec 007 receipt>, pinned_by=<operator>)`.
   It fails closed if either doc lacks the exact SHA, any P0 is open, or the
   Spec 007 enablement receipt does not verify.
5. Replay the five events (`expose_canon_alias`, `switch_fe_list`,
   `run_walkthrough`, `capture_receipt`, `operator_pin`) with those artifacts;
   `beta_eligible(machine)` must be true. This is an evidence decision only: it
   does not enable payments or flip any flag.

## Conservative interpretations

- T010: the canonical list alias (`GET /api/canon/rigs`, `GET /api/canon/rigs/{rig_id}`)
  and the F4 evidence dual-mounts already exist on main. T010 adds parity evidence
  (full id sets hashed and compared) and a write-surface audit (every canon write
  route must have a `/api/racks` twin); no route was added or changed.
  The canon list orders by id descending while the legacy list is unordered, so
  full sets match but individual pages of a paginated list can differ.
- T020: only the active list pages (`Racks.tsx`, `Modules.tsx` rig picker) moved to
  `canonApi.listRigs`; the selected rig's placements load from `canonApi.getRig`.
  All writes (generate, compatibility, edit) stay on their existing endpoints.
  `frontend/src/legacy/pages/Publish.tsx` is not routed and was left unchanged.
  "No dual-write regression" is checked with the F3 audit on a real generate
  response (native `gen-run-*`/`rig-rev-*`/`inv-rev-*` ids, 64-hex manifest hash,
  no `legacy-*` ids).
- T030: "aligned" means the seeded accounts exist with the seeded password and
  role. The seeder is the single source of the demo credentials and the walkthrough
  script no longer re-hashes the admin password.
- T040: "flags enabled in test mode" means design engine and canon export
  fulfillment on, `stripe_test_mode` true, production payments off, and the
  environment not production. A missing attribute is treated as unsafe.
- T050 / operator_pin: "SHA-linked evidence" also requires a verified Spec 007
  enablement receipt (the declared upstream dependency).
