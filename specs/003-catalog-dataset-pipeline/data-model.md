# Data model: 003-catalog-dataset-pipeline

Tables this spec added for a rollback (FR-031, migration `20261106_catalog_load_runs`). The catalog tables themselves are in `backend/modules/catalog.py` and `backend/modules/models.py`.

| Table | Holds |
|---|---|
| `catalog_load_runs` | One row per applied load or rollback: `run_id`, `kind`, `rollback_of`, `rolled_back_by`, `plan_hash`, `inputs_hash`, and the receipt. |
| `catalog_load_changes` | One row per inserted row and per changed field in a load: `run_id`, `table_name`, `row_id`, `row_key`, `change`, `field`, `old_value`, `new_value`. |
| `catalog_value_archive.rolled_back_run_id` | Set on archive rows a rollback undid, so the reverify guards stop reading them. |
