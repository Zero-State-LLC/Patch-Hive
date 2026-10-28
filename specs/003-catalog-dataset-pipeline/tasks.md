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
- [ ] T026 Render pass for script-rendered makers (4ms, Erica) and adapter fixes for Frap, Tiptop and Pittsburgh, under a small approved paid cap. Free part done 2026-10-27: 4ms and Pittsburgh need no render (dry run: 44 and 56 modules); Tiptop answers with a CAPTCHA and is excluded; Erica index pages need a paid render (`render_index`); Frap drops connections from the crawl host. Paid pass pending an approved cap (`receipts/maker-crawl-v2-t026.dry-run.json`).
  - depends_on: [T024]
- [ ] T025 Build loader overlays from `maker-crawl-v2.json` (insert-if-absent, fill-null, flag disagreements) and load them to staging. Overlays built 2026-10-27 (`catalog-additions-v3`, `module-power-depth-v11`; loader dry run: 3,878 catalog rows). Loaded to staging 2026-10-27 (4,019 catalog rows). Rail-parser fix 2026-10-27: overlays rebuilt in place, and `provenance/maker-crawl-v2-rail-fix-v1.json` corrects the misread draws already loaded on staging. Prod load pending.
  - depends_on: [T024]

## Foundational

- [ ] T010 Encode the transitions table as tests (workflows: anti-slop-code, production-systems)
  - depends_on: [T002]

## Polish

- [ ] T090 Converge the code against the spec
  - depends_on: [T010]
