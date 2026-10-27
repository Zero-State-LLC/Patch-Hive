# Synth Catalog Research — PatchHive seed

Sealed research packet from Abraxas skill **`modular-synth-catalog-research`**
([PR #984](https://github.com/scrimshawlife-ctrl/Abraxas-v2.0/pull/984)).

## Files

| Path | Role |
|------|------|
| `seed-phase2-v1.json` | Deterministic seed (brands + catalog rows + full-spec subset) |
| `seed-phase2-v1.sources.json` | Access basis / evidence policy packet |
| `brand-index-modulargrid.txt` | Phase 1 brand index (~700) |
| `phase2-major-br.md` | Phase 2 major-brand tables (audit source) |
| `PATCHHIVE_INTEGRATION.md` | Integration analysis notes |
| `master-catalog.md` | Research master catalog summary |
| `alternative-sources.md` | 20-source rotation notes |
| `receipts/` | Dry-run / import receipts |

## Admit into PatchHive

```bash
# Dry-run (writes receipt only when --receipt set)
cd backend && python -m integrations.synth_catalog_importer --dry-run \
  --receipt ../data/synth-catalog/receipts/seed-phase2-v1.dry-run.json

# Catalog + curated full-spec
python -m integrations.synth_catalog_importer

# Fill null HP from manufacturer-curated specs (never invent)
python -m integrations.synth_catalog_importer --enrich-hp

# Or justfile
just synth-catalog-import --dry-run
just synth-catalog-import
just synth-catalog-import -- --enrich-hp
```

## Provenance rules

- `source = SynthCatalogResearch`
- HP / power / depth remain **null** when research did not record them (never invent)
- Catalog dedupe by **slug**; full modules skip existing `(brand, name)` from any source

## Rebuild

```bash
python3 scripts/build_synth_catalog_seed.py \
  --source-dir ~/Documents/Abraxas-v2.0/skills/modular-synth-catalog-research/references
```

## ModularGrid provenance (2026-10-17)

ModularGrid is never fetched. Earlier batches did scrape it, and those values are now handled like this
(Danny approval 2026-10-17):

- `provenance/modulargrid-reverify-v1.json` lists every ModularGrid-derived field (no values): 889 rows,
  2,281 spec values across 542 modules and 53 brands, plus the 179 batch-7b candidate labels and 168
  module HP values copied from ModularGrid catalog HP.
- On load, `population.py` copies the current DB value into `catalog_value_archive` with its source tag,
  then sets unconfirmed values to NULL and `needs_reverify = true`. The 60 values a maker page confirmed
  are kept. `modules.hp` is NOT NULL, so candidate HP is archived and flagged instead. The batch-7b
  `verified` label (a ModularGrid vendor-name match only) becomes `unverified`. Nothing is deleted and a
  re-run is a no-op.
- The extracted files (phase 2 source, brand index, overlays v1-v5, the candidates file, batch 4-8 results,
  related receipts, `modulargrid_data.py`, `patchhive-replit.zip`) were removed from HEAD and archived
  privately. Git history is unchanged.
- `scripts/check_no_modulargrid.py` runs in CI. `catalog_scrape.py` and the shared scrape-router deny
  the ModularGrid host.
- Manufacturer rows (703) stay in the database. The brand names remain in `seed-phase2-v1.json`, which is
  now labelled ModularGrid-derived and needs re-verification.
