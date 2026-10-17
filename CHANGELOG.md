# Changelog

All notable changes to PatchHive are documented here.

This project follows [Semantic Versioning](docs/VERSIONING.md) beginning with the adoption of the formal release policy. Historical entries are reconstructed from repository evidence and are labeled as retroactive classifications rather than invented release tags.

## Unreleased

## 0.3.0-alpha.2 — Proposed (untagged until the release PR merges)

### Changed

- Synced the personal repository main (964ce18) into the org repository: `.specify/memory/constitution.md`, `specs/005-decision-intelligence`, and the T050, T061, and T070 work.
- Aligned `backend/pyproject.toml` (`0.3.0a2`) and `frontend/package.json` (`0.3.0-alpha.2`) with the tag scheme. Both were `0.1.0`.

### Added

- `scripts/check_version_consistency.py` and `.github/workflows/release.yml`. The workflow checks versions on PRs, verifies tag/version match on tag push, and creates the GitHub release.


### Added

- Cases C1–C3: `format_family` / `capacity_unit` / `powered` columns + migration; list filters on columns; power validation (POWER_UNSPECIFIED advisory, hard fail when rails known or unpowered+draw); non-Eurorack placement blocked; staging bootstrap doc; rack `validation_warnings` on create/update.
- Cases C0 product loop: list filters (`format_family`, `powered`, `q`, `min_hp`); Cases page filters + “Use on new rig”; RackBuilder Step 0 Eurorack case picker + create empty rig; rack validation errors JSON-serializable.
- Case catalog research ingest: 50 cases from `fixtures/Cases4PatchHive.md` → `fixtures/cases_research_2026.json` (Case schema); `scripts/parse_cases_research.py` + `scripts/import_cases_research.py`; fail-closed null rails; non-Eurorack `meta.capacity_unit`.
- Production readiness assessment (2026-07-21): gate scorecard, blockers, continuity plan under `docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md`; refreshed SHA-pinned readiness matrix.
- README hero banner, product stills, Zero State lockup, and linked CI / readiness badges.
- Roadmap updated for late-alpha Design Engine + VSI delivery and beta/RC path.
- Zero State × PatchHive design system: brand hierarchy, guidelines, 340 SVG icons, CSS tokens, footer credit, design-system preview, lockups, app icon, Zero State monogram.
- Cyber Hive visual identity kit: brand assets under `brand/`, design system in `docs/brand/`, SVG icons + tokens.
- Local Docker staging receipt + domain cutover checklist; `just staging-up` / `staging-down`.
- F3 generate dual-write audit: native `rig-rev-*`/`gen-run-*` only, inventory row persistence, empty-rack NOT_COMPUTABLE still dual-writes; forbid legacy-* bridge ids on ready bridges.
- RigDetail inventory → generate → patches loop: step list, readiness-aware generate CTA, generation receipt, Playwright coverage.
- Staging host plan + `docker-compose.staging.yml`; dual-path retirement design F0 (`DUAL_PATH_RETIREMENT_DESIGN.md`).
- Release notes draft for `v0.3.0-alpha.1` (alpha hardening; not production).
- Canon-native replacements for residual legacy unit suites: `function_registry`, `query_surface`, `pipeline`, `export_pack` (no default-test imports of historical `patchhive`).
- `canon.gallery_revisions` append-only file store; `patchhive.gallery.revisions` is a compatibility shim; gallery revision tests no longer mark `legacy_pipeline`.
- Migrated schema roundtrip off historical `patchhive` onto `canon.contracts.RigMetricsPacket` (one fewer `legacy_pipeline` importer).
- Canon compiler edge-case tests: signal mismatch, direction, feedback declare/undeclared, attenuation, normals, empty graph.
- `patchhive` import telemetry quarantine: markers, package-test norecursedirs, CI import guard, `just telemetry-patchhive` / `test-historical`.
- Module gallery search, brand/type filters, sort, and place-on-rig entry links; Racks list loading/empty/retry parity.
- `GET /api/racks/{id}/evidence/inventory` latest sealed inventory receipt; RigDetail overview surfaces it.
- Fusion panel applied-status feedback; Playwright covers multi-photo fusion confirm + RigDetail receipt.
- Continuation plan post-#75 (`docs/evidence/CONTINUATION_PLAN_POST_75.md`).
- Fusion panel confirm/reject/defer actions and batch “confirm all non-conflict fused” (user-initiated only; conflicts blocked).
- Staging Compose drill receipt (`docs/evidence/STAGING_COMPOSE_RECEIPT.md`): local db+backend healthy at Alembic head `20240930_patch_user_overlays`.
- RackBuilder multi-photo upload and fusion review panel (reconcile API; never auto-confirms).
- Rig revision picker API/UI and mutable patch overlays (notes/favorite/tried) without mutating canonical patches.
- AI-native engineering foundation: `justfile`, `scripts/ai/rebuild_indexes.sh`, `docs/engineering/*`, `AI_CONTEXT.md`, `SYSTEM_CONTEXT.md`, engineering-quality CI, MCP template (see `ENGINEERING_SETUP_REPORT.md`).
- Cases and Patches list pages with loading / empty / error / retry parity.
- `evidenceApi` client; RackBuilder live upload → candidates → confirmation when a rack is selected.
- Vision evaluation harness + synthetic `fixtures/vision_eval` dataset (production accuracy remains `NOT_COMPUTABLE`).
- Consent-gated `CloudVisionProvider` and `select_vision_provider` (live calls fail-closed; CI uses mock).
- Canonical one-page Patch Book publishing invariant.
- Comprehensive Patch Book Generator specification.
- Versioning and release-candidate policy.
- Evidence-based production-readiness framework.
- Versioned product roadmap.
- Visual System Intelligence P0 contracts: provider-neutral `VisionEvidenceProvider`, `SystemInventoryRevision`, `SystemCapabilityGraph`, confirmed-inventory patch constraint gate.
- Local image quality assessment after secure re-encode.
- Audit receipts under `docs/evidence/` (baseline, audio-drift classification, capability matrix, readiness matrix, work packages).

### Changed

- Root README rebuilt as the canonical repository entrypoint.
- Canon and operations documentation aligned to page-fit, deterministic export, and manifest requirements.
- `docs/PATCH_ENGINE.md`: audio simulation and hardware CV/MIDI activation marked **OUT OF SCOPE** (symbolic waveform SVGs retained as non-audio visualization).
- Visual System Intelligence documents preserved and cross-linked to implementation paths.

### Tests

- Unit coverage for vision provider determinism, candidate self-confirm rejection, inventory immutability, and `NOT_COMPUTABLE` generation without confirmed modules.
- Inventory gate tests for rack-backed generation and generate-bridge API fields.
- Inventory persistence, multi-image evidence upload, retention expiry, native bridge IDs.
- Ranked candidate list + confirmation batch API; multi-candidate RackBuilder review UX.
- Acceptance (testcontainers): 11 passed on campaign branch.

### Database

- Alembic `20240929_visual_inventory_evidence`: `system_inventory_revisions`, `image_assets`, `classification_evidence_records`.

## 0.3.0 — Planned line

One-page Patch Book Generator implementation.

Planned scope includes versioned page contracts, deterministic semantic assembly, SVG-first technical diagrams, page-fit validation, accessible PDF/SVG/JSON/ZIP export, and manifest-bound release evidence.

No `v0.3.0` release tag exists at the time of this entry.

## 0.2.x — Retroactive canon-aligned MVP line

### Added

- Immutable user → rig → rig revision → run → patch library → patch hierarchy.
- Deterministic compiler contracts, canonical JSON, stable hashes, stage receipts, and artifact manifests.
- Canonical PatchGraph, five-phase PatchPlan, deterministic variations, and validation reporting.
- Canonical credits and exports API under `/api/canon/*`.
- Test-mode Stripe-style webhook and transactional ledger behavior.
- Instrument-bench workspace, graph/table accessibility pair, and light/dark themes.
- Security, operations, accessibility, canon-alignment, and continuation documentation.

### Changed

- Canonical UI export and credit clients migrated away from legacy frontend debit behavior.
- Historical social, publishing, leaderboard, and referral surfaces disabled by default.

### Known gaps

- Legacy acceptance and inventory paths remain partially present.
- Production deployment and live payments have not been authorized.
- Staging backup/restore, full operational, and production-readiness evidence remain incomplete.

This line includes work merged through PRs #47, #49, and subsequent documentation alignment. It is a descriptive lineage, not a claim that every `0.2.x` tag was issued.

## 0.1.x — Retroactive historical prototype line

Early PatchHive work explored rig ingestion, patch generation, exports, publishing, community, deployment packaging, and Abraxas bridge concepts. These surfaces vary in authority and maturity. Current ship authority comes from the canon-aligned documentation and active runtime classification, not historical root notes or disabled legacy modules.

No complete historical release sequence is asserted.
