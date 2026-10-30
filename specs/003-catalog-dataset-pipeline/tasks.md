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

## Catalog fill: manufacturer crawl v2 (2026-10-27)

- [x] T023 Deepen the manufacturer crawl: curated homepages for unresolved brands, adapters for the top 25 makers (Shopify, Squarespace and WooCommerce store feeds, or index pages), a configurable page cap, and a `--dry-run` that writes a yield and spend receipt (`receipts/maker-crawl-v2.dry-run.json`). All fetches go through the shared in-repo router (`catalog_scrape.py`): free HTTP, then context.dev, then Firecrawl (D2).
  - depends_on: [T022]
- [x] T024 Paid crawl run under an owner-approved cap, sized from the T023 dry-run receipt (`--max-paid-fetches`, `--cap`). Done 2026-10-27 via context.dev: 3,429 modules from 315 brands (`receipts/maker-crawl-v2.json`).
  - depends_on: [T023]
- [x] T026 Render pass for script-rendered makers (4ms, Erica) and adapter fixes for Frap, Tiptop and Pittsburgh, under a small approved paid cap. Paid pass 2026-10-27 (context.dev, 10 credits): 4ms 44, Pittsburgh 56 and Erica 46 modules merged into `maker-crawl-v2.json`. Tiptop is excluded (CAPTCHA). Frap is still at 0 and needs a listing adapter over rendered HTML. Overlays built 2026-10-27 (`catalog-additions-v4`: 136 rows; `module-power-depth-v12`: 141 entries; jumper-dependent draws left unknown; staging replica: 0 conflicts). Loaded to staging (T025) and prod (T027). Closed 2026-10-29: Frap is excluded (D7: its host refuses connections from the crawl network; no paid workaround), like Tiptop.
  - depends_on: [T024]
- [x] T025 Build loader overlays from `maker-crawl-v2.json` (insert-if-absent, fill-null, flag disagreements) and load them to staging. Done 2026-10-27: overlays through `catalog-additions-v4` and `module-power-depth-v12`, with the rail, jumper, review and signed-pair fixes; staging holds 4,172 catalog rows and 4,142 modules with 0 conflicts. The prod load is T027.
  - depends_on: [T024]
- [x] T027 Load the maker-crawl overlays to prod: `db-migrate.yml` (prod), then `db-load.yml` dry run, then apply after the receipt matches staging's (0 conflicts, no destructive SQL). Operator-run. Done 2026-10-28: prod migrated to `20261028_refresh_sessions`; dry run and apply with `plan_hash` `b5b62bb3…6ac`, 0 conflicts, no destructive SQL; prod holds 4,172 catalog rows and 4,142 modules, matching staging (Actions runs 40758360845, 40758948155).
  - depends_on: [T025]

## Catalog quality (2026-10-28)

- [x] T028 Fill missing categories from the crawl's own tags (`scripts/build_category_overlay.py`, `overlays/module-catalog-category-v1.json`); the loader fills nulls only. Done 2026-10-28 (#115): 183 rows on staging and prod; 24 ambiguous and 644 untagged rows stay empty. Prod rows without a category: 1,038 to 855.
  - depends_on: [T027]
- [x] T029 Tombstone rows filed under the wrong brand (the v1 crawl gave seven brands another maker's homepage) and re-add the modules only they held (`scripts/build_reattribution.py`, `overlays/catalog-retirements-v1.json`, `catalog-additions-v5`, `module-power-depth-v13`; migration `20261028_catalog_tombstones`). Done 2026-10-28 (#116): 263 rows tombstoned in each of `module_catalog` and `modules` (262 misattributed, plus TLM "ST MODULAR"), 7 re-added; staging and prod show 3,916 modules. Overlay builds now skip a brand whose homepage is another maker's site.
  - depends_on: [T027]
- [x] T030 Refuse a shared homepage when the crawler resolves a brand (`catalog_maker_crawl.py`), not only when overlays are built. Done 2026-10-28: every brand is resolved before any is crawled; a host another brand holds is recorded as `shared_homepage` (with owner and candidate) in the receipt and not crawled. The owner is the brand named in the host, else the one brand resolved by an adapter or the curated list. The committed v2 data shows 18 refused brands: the 8 retired in T029, 5 more with an owner (four copies of ALM Busy Circuits, and Instruō) and 5 on hosts with no owner. The 10 not yet retired are still live in prod.
  - depends_on: [T029]
- [ ] T031 Rebuild the maker-crawl page cache (deleted 2026-10-28 with a worktree), only when a change needs the crawl re-parsed, under an approved paid cap; then classify the 644 untagged rows from their pages.
  - depends_on: [T028]

## Corrections and one loader (2026-10-29)

- [x] T032 Delete both `seed_catalog_from_synth.py` copies and the skipped `test_seeder_catalog.py` (D5, research R2). Done 2026-10-29.
  - depends_on: []
- [x] T033 Add the `correct` provenance action (FR-038): archive, then write the new value while the stored value is `only_if_value`, with a maker-page citation; the FR-035 guard lifts on an `hp` correction. Ship `provenance/maker-corrections-v1.json` for Sovage CHICANE (hp 14 → 4, verification URL to the Eurorack page) and load it to staging and prod (D4, research R1). Done 2026-10-29 (#125): CHICANE holds 4 HP and the Eurorack page on staging and prod; 14 and the 1U URL are archived.
  - depends_on: [T029]
- [ ] T035 Scoped re-fetch of the jumper-dependent pages (about 45: the 42 live 4ms modules, the 2 Dave Jones Design modules and Velectronic A-Envelope), under an approved cap of about 50 context.dev credits; record each setting's draws verbatim (research R4).
  - depends_on: [T030]
- [ ] T034 Jumper-dependent power as `power_configs` (D8, research R5): migration, a loader action filling settings from T035's receipt, and a setting picker in rack budgets.
  - depends_on: [T033, T035]

## Lifecycle gaps and legacy HP (2026-10-29)

- [x] T036 Clear `needs_reverify` in the correction UPDATE once every field the row was flagged for has a `correct` archive row; keep it set while another flagged field is open. Test on a staging replica: CHICANE ends unflagged (research R8). Done 2026-10-29 (#135): on a staging replica (staging's load history replayed through #71, #125 and main), the dry run plans one `modules_reverify_cleared` update and 0 conflicts; the apply leaves CHICANE at 4 HP and unflagged, and a rerun changes nothing. TLM ST MODULAR stays flagged, as nothing corrects it. Staging and prod clear on their next db-load.
  - depends_on: [T033]
- [x] T037 Refuse archive, flag and correct entries on tombstoned rows (`tombstoned_at IS NULL` / `status <> 'tombstoned'` in every statement); count each as `refused: row_tombstoned` in the receipt (research R9). Done 2026-10-29 (#135): every statement carries the filter, and the scheduler counts each refusal as `refused_row_tombstoned`.
  - depends_on: [T029, T033]
- [x] T038 Owner decision on the 221 unsourced v1 HP values (research R7: keep, flag, or triage). Decided 2026-10-30 by the owner: triage (decision 9, `docs/evidence/OPEN_DECISIONS_2026-10-30.md`).
  - depends_on: []
- [ ] T039 If triage is chosen: a v3 HP manifest re-sourcing the 45 maker-confirmed values, a hand check of the 7 disagreements with `correct` entries for the wrong ones, an `hp_source = legacy_unsourced` marker on the rest, then a free maker-page lookup of the 169 and removal of `UNSOURCED_HP_OVERLAYS` once empty. Partly done 2026-10-30 for the 218 values left after #153: `overlays/module-catalog-hp-v3.json` re-sources 158 (156 official-page citations, 10 spot-checked by plain GET with none disagreeing, plus DPO and Morphagene hand-checked); `provenance/maker-corrections-v3.json` corrects DPO 30 to 28 and Morphagene 18 to 20 in `module_catalog` and `modules`; migration `20261030_catalog_hp_source` adds `module_catalog.hp_source`, which the loader sets to `legacy_unsourced` (36 rows on a staging replica) and clears once a value is sourced, and the catalog API returns it. Of the 12 disagreements the other 9 already hold the maker value, and ADDAC200PI (bot challenge) stays legacy. Still open: the free maker-page lookup of the 60 v1 values not in v3, then removal of `UNSOURCED_HP_OVERLAYS` once empty.
  - depends_on: [T038, T037]

## Foundational

- [ ] T010 Encode the transitions table as tests (workflows: anti-slop-code, production-systems)
  - depends_on: [T002]

## Polish

- [ ] T090 Converge the code against the spec
  - depends_on: [T010]
