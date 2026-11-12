# Integrations

Read-only endpoints and helpers for maker names and the Synth Catalog Research seed, plus the case catalog importer that the loader calls.

Catalog rows have one writer: `data/synth-catalog/population.py` (spec 003 D5). The ModularGrid and Synth Catalog importers, their admin routes and the first-run bootstrap were removed on 2026-11-06. To fill a local database, run `scripts/import_catalog_population.py`. For a deployed database, use `.github/workflows/db-load.yml`. See `data/synth-catalog/README.md`.
