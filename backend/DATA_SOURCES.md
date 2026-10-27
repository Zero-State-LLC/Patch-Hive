# PatchHive Data Sources Documentation

**Last Updated**: 2026-10-17
**ABX-Core Version**: 1.3
**Database Schema Version**: 1.0

> **Correction (2026-10-17).** Earlier versions of this file said the Phase 2 seed was
> "not a ModularGrid dump" and that ModularGrid was "reference only, not bulk scraped".
> That was wrong. The Phase 2 seed (`seed-phase2-v1.json`) was built from a browser scrape of
> ModularGrid manufacturer pages, its 703-name brand list came from the ModularGrid
> manufacturer index, and several HP and power/depth overlays (v1-v5, the batch-7b candidates,
> part of `module-catalog-hp-v1.json`) were scraped from ModularGrid module pages.
>
> What changed (Danny approval 2026-10-17):
> - About 2,281 ModularGrid-derived spec values (catalog HP; modules +12V/-12V/+5V/depth;
>   candidate HP) are preserved with source tags in the database table
>   `catalog_value_archive` (batch `modulargrid-provenance-v1`). The manifest without values is
>   `data/synth-catalog/provenance/modulargrid-reverify-v1.json`.
> - Values that a manufacturer page confirmed are kept. Every other ModularGrid-only value is
>   set to NULL and the row gets `needs_reverify = true`. `modules.hp` is NOT NULL, so candidate
>   HP is archived and flagged, not nulled.
> - The 179 batch-7b candidates were labelled `verified`. That only meant the ModularGrid vendor
>   name matched; they are now `unverified` with `needs_reverify = true`.
> - The extracted ModularGrid files were removed from the repo (history is unchanged) and
>   archived privately. Manufacturer rows (703) stay in the database.
> - ModularGrid is never fetched. `scripts/check_no_modulargrid.py` runs in CI and the fetch
>   layers deny `modulargrid.net`.

> **Owner decisions (2026-10-27, spec 003 D1/D2).**
> - The remaining ModularGrid-derived identities (703 brands, 376 modules) stay only as discovery leads (`access_basis = unknown`, `CATALOG_OBSERVED`). Their scraped descriptions are removed. They are never bulk-published, and a row becomes canonical only after manufacturer or manual confirmation.
> - Modules whose HP is flagged `needs_reverify` cannot be placed until re-verified.
> - Automated enrichment fetches official manufacturer pages and manuals only. Retailer values come from one-off manual lookups as `RETAILER_OBSERVED`.

## Overview

This document provides complete provenance tracking for all data in the PatchHive database, in accordance with ABX-Core v1.3 SEED principles (no mystery data, full traceability).

## Data Sources

### 1. Eurorack Modules (32 modules)

**Status (2026-10-17)**: removed. The 32 modules and 7 cases in `integrations/modulargrid_data.py` were partly curated from ModularGrid; the file was removed and archived privately. `integrations/seed_data.py` keeps manufacturer names only. Rows already imported with `source="ModularGrid"` stay in the database (never deleted).

**Source Type**: Manual curation from manufacturer specifications and ModularGrid community data
**Provenance**: `source="ModularGrid"`, `source_reference="https://www.modulargrid.net/"`
**Method**: Hand-curated from official manufacturer product pages and specifications
**Date Imported**: 2025-12-05
**Importer**: `integrations/modulargrid_importer.py`

#### Field-Level Provenance

| Field | Source | Trust Level | Notes |
|-------|--------|-------------|-------|
| `brand` | Manufacturer official | Direct | Standardized spelling |
| `name` | Manufacturer official | Direct | Exact product name |
| `hp` | Manufacturer specs | Direct | Width in HP units |
| `module_type` | Inferred from description | Inferred | VCO, VCF, VCA, ENV, LFO, SEQ, etc. |
| `power_12v_ma` | Manufacturer specs | Direct | +12V rail consumption |
| `power_neg12v_ma` | Manufacturer specs | Direct | -12V rail consumption |
| `power_5v_ma` | Manufacturer specs | Direct | +5V rail (when applicable) |
| `io_ports` | Manual mapping | Manual | Derived from manuals/specs |
| `tags` | Curated classification | Inferred | Based on functionality |
| `description` | Manufacturer copy | Direct | Product descriptions |
| `manufacturer_url` | Official website | Direct | Product page URLs |

#### Data Quality Notes

- **Power Specifications**: All values verified against official manufacturer datasheets
- **Missing Data**: Some older/discontinued modules may have incomplete power specs
- **I/O Ports**: Simplified representation; full patch diagrams would require additional schema
- **Module Types**: Primary categorization follows common Eurorack taxonomy (VCO, VCF, VCA, etc.)

### 2. Eurorack Cases (7 cases)

**Source Type**: Manual curation from manufacturer specifications
**Provenance**: `source="ModularGrid"`, `source_reference="https://www.modulargrid.net/"`
**Method**: Hand-curated from official manufacturer case specifications
**Date Imported**: 2025-12-05

#### Field-Level Provenance

| Field | Source | Trust Level | Notes |
|-------|--------|-------------|-------|
| `brand` | Manufacturer official | Direct | Case manufacturer |
| `name` | Manufacturer official | Direct | Product name |
| `total_hp` | Manufacturer specs | Direct | Total width in HP |
| `rows` | Manufacturer specs | Direct | Number of rows |
| `hp_per_row` | Manufacturer specs | Direct | HP distribution per row |
| `power_12v_ma` | Manufacturer specs | Direct | Total +12V capacity |
| `power_neg12v_ma` | Manufacturer specs | Direct | Total -12V capacity |
| `power_5v_ma` | Manufacturer specs | Direct | Total +5V capacity |
| `description` | Manufacturer copy | Direct | Product descriptions |
| `manufacturer_url` | Official website | Direct | Product page URLs |

### 3. Manufacturers (25 brands)

**Source Type**: Industry knowledge + manufacturer websites
**Method**: Curated list of major Eurorack manufacturers
**Storage**: Embedded in module records (normalized via brand field)

#### Manufacturer List

1. Mutable Instruments (France) - Now open-source
2. Make Noise (USA)
3. Intellijel (Canada)
4. Noise Engineering (USA)
5. Qu-Bit Electronix (USA)
6. 4ms Company (USA)
7. Doepfer (Germany) - Original Eurorack creator
8. ALM Busy Circuits (UK)
9. Mannequins (USA)
10. Hexinverter (Canada)
11. Befaco (Spain) - DIY focus
12. Erica Synths (Latvia)
13. Tiptop Audio (USA/China)
14. Malekko Heavy Industry (USA)
15. WMD (USA)
16. Joranalogue (Netherlands)
17. Xaoc Devices (Poland)
18. Industrial Music Electronics (USA)
19. Shakmat Modular (Belgium)
20. Instruo (UK)
21. Verbos Electronics (USA)
22. Synthesis Technology (USA)
23. Frequency Central (UK)
24. Random*Source (UK)
25. Buchla USA (USA)

### 4. Synth Catalog Research (Phase 2 seed)

**Source Type**: Sealed multi-source research packet (Abraxas skill `modular-synth-catalog-research`)  
**Provenance**: `source="SynthCatalogResearch"`, `source_reference="data/synth-catalog/seed-phase2-v1.json"`  
**Method**: Phase 1 brand index (~700+) + Phase 2 major-brand module tables, normalized into PatchHive catalog rows  
**Date Sealed**: 2026-07-21 (Abraxas PR #984)  
**Importer**: `integrations/synth_catalog_importer.py`  
**Seed**: `data/synth-catalog/seed-phase2-v1.json`  
**Policy packet**: `data/synth-catalog/seed-phase2-v1.sources.json`

#### What is admitted where

| Tier | Target table | Content |
|------|--------------|---------|
| Lightweight catalog | `module_catalog` | Phase 2 brand/name/category/availability; HP only when research recorded it (null otherwise) |
| Full specs | `modules` | Curated full-spec subset (power/I/O only when known; never invented) |

#### Field-Level Provenance

| Field | Source | Trust Level | Notes |
|-------|--------|-------------|-------|
| `brand` / `name` | Research Phase 2 tables | OBSERVED | Deduped by slug |
| `hp` | Research table when numeric | OBSERVED or null | Null when research used `—` / blank |
| `category` | Mapped from free-text research categories | Inferred | Taxonomy via `map_category()` |
| `is_available` | Research status column | OBSERVED | discontinued / available / upcoming |
| `power_*` / `io_ports` | Curated full-spec only | Direct when present | Null never filled with guesses |
| Brand index | ModularGrid manufacturer index (names only) | MODULARGRID_UNVERIFIED | 703 names; manufacturer rows stay in the DB |

#### Data Quality Notes

- **ModularGrid-derived**: identities, categories, descriptions and the brand list came from a browser scrape of ModularGrid manufacturer pages (corrected 2026-10-17; earlier text wrongly said "not a ModularGrid dump"). Spec values from ModularGrid were removed; re-verify on manufacturer pages
- **Sparse HP**: Most Phase 2 rows lack HP; catalog admits them for discovery; full rack placement still needs HP later
- **Idempotent**: Catalog skips existing slugs; full modules skip existing `(brand, name)` from any source
- **Rebuild**: retired. The seed is frozen; its ModularGrid inputs are no longer in the repo

#### API

- `GET /api/synth-catalog/stats`
- `GET /api/synth-catalog/manufacturers`
- `POST /api/synth-catalog/import/catalog?dry_run=`
- `POST /api/synth-catalog/import/modules?dry_run=&clear_existing=`
- `POST /api/synth-catalog/import/all?dry_run=&clear_existing=`
- `POST /api/synth-catalog/enrich/hp?dry_run=` — fill null catalog HP from the `modules` table (the curated ModularGrid list was removed 2026-10-17)

#### HP enrichment

```bash
python -m integrations.synth_catalog_importer --enrich-hp
```

Only copies HP (and UTIL→specific category) when a manufacturer-curated match exists. Never overwrites non-null HP.

## Data Collection Methodology

### Principles

1. **No ModularGrid**: ModularGrid is never fetched (CI guard + fetch-layer deny). Earlier ModularGrid-derived values are archived and flagged `needs_reverify`
2. **Manufacturer pages first**: new specs come from manufacturer pages and manuals, robots.txt respected
3. **Manufacturer Permission**: Product specs are publicly available marketing material
4. **Community Standards**: Follows established Eurorack taxonomy and conventions

### Process

1. **Module Selection**: Focus on popular, widely-available modules
2. **Specification Verification**: Cross-reference multiple sources
3. **Standardization**: Normalize units (mA, HP, mm)
4. **Categorization**: Apply consistent module_type taxonomy
5. **Provenance Tagging**: Every record includes source metadata

### Validation

- Power specs verified against official datasheets
- HP widths confirmed from manufacturer specs
- Module types validated against common usage
- URLs checked for accuracy

## Known Gaps & Limitations

### Current Limitations

1. **Coverage**: 32 curated full-spec modules + Synth Catalog Research catalog expansion (~300+ browse rows; HP often null)
2. **I/O Details**: Simplified port representation; full signal flow not captured
3. **Firmware Versions**: Digital modules may have firmware variations not tracked
4. **Discontinued Modules**: Historical data may be incomplete
5. **Regional Variations**: Some modules have region-specific power requirements

### Future Expansion Opportunities

1. **User Contributions**: Allow community to submit verified module data
2. **Manufacturer APIs**: Direct integration where APIs are available
3. **ModularGrid Exports**: Support user-provided ModularGrid rack exports
4. **Enhanced I/O Modeling**: Detailed signal routing and normalization
5. **Firmware Tracking**: Version-specific feature sets for digital modules

## Data Integrity

### Deduplication Strategy

Modules are identified by composite key: `(brand, name)`
- Prevents duplicate entries on re-import
- Hash-based ID generation ensures stability

### Update Policy

- **New Modules**: Import via API or CLI
- **Corrections**: Update via API with provenance note
- **Deprecation**: Mark `is_discontinued` rather than delete
- **Versioning**: Module revisions tracked via name suffix (e.g. "Plaits v2")

## Compliance

### ABX-Core v1.3 SEED Enforcement

✅ **No Mock Data**: All modules are real, commercially available products
✅ **Full Provenance**: Every record has `source` and `source_reference`
✅ **Traceability**: Import timestamps and run_id tracked
✅ **Deterministic**: Same import files → same database state

### Legal Compliance

- Product specifications are publicly available facts (not copyrightable)
- URLs and descriptions used for informational purposes (fair use)
- No bulk scraping or ToS violations
- Manufacturers retain all rights to product names and trademarks

## Import History

### Initial Bootstrap (2025-12-05)

```
Run ID: 4c8f067f-8e32-49e4-bfc9-05882001b43f
Imported: 32 modules, 7 cases
Duration: ~2.5 seconds
Status: Success
```

**Provenance Metrics**:
- `imported_count`: 32 modules, 7 cases
- `skipped_count`: 0 (clean database)
- `total_processed`: 39 items

## Maintenance

### Adding New Modules

1. Add a manufacturer-sourced overlay under `data/synth-catalog/overlays/` (never ModularGrid)
2. Include `source_url` and `verification_status` for every entry
3. Run the DB load workflow (dry run first)
4. Verify import via API: `GET /api/modules/`

### Data Quality Checks

- Monthly: Review for discontinued modules
- Quarterly: Update power specs for revised modules
- Annually: Full manufacturer catalog review

## Contact

For data corrections or additions:
- GitHub Issues: https://github.com/scrimshawlife-ctrl/Patch-Hive/issues
- Tag data submissions with: `data-quality` label

---

**Document Version**: 1.0
**Schema Version**: 1.0
**ABX-Core Compliance**: v1.3
