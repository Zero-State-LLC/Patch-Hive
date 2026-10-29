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
- [ ] T026 Render pass for script-rendered makers (4ms, Erica) and adapter fixes for Frap, Tiptop and Pittsburgh, under a small approved paid cap. Paid pass 2026-10-27 (context.dev, 10 credits): 4ms 44, Pittsburgh 56 and Erica 46 modules merged into `maker-crawl-v2.json`. Tiptop is excluded (CAPTCHA). Frap is still at 0 and needs a listing adapter over rendered HTML. Overlays built 2026-10-27 (`catalog-additions-v4`: 136 rows; `module-power-depth-v12`: 141 entries; jumper-dependent draws left unknown; staging replica: 0 conflicts). Loaded to staging (T025) and prod (T027). Open only for Frap.
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
- [ ] T030 Refuse a shared homepage when the crawler resolves a brand (`catalog_maker_crawl.py`), not only when overlays are built.
  - depends_on: [T029]
- [ ] T031 Rebuild the maker-crawl page cache (deleted 2026-10-28 with a worktree), only when a change needs the crawl re-parsed, under an approved paid cap; then classify the 644 untagged rows from their pages.
  - depends_on: [T028]

## Foundational

- [ ] T010 Encode the transitions table as tests (workflows: anti-slop-code, production-systems)
  - depends_on: [T002]

## Polish

- [ ] T090 Converge the code against the spec
  - depends_on: [T010]
