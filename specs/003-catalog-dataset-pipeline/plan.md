# Plan: 003-catalog-dataset-pipeline

An agent wrote this plan on 2026-11-03 and finished it on 2026-11-04 (T002) from spec.md, the [T001 record](T001_CONFIRMATION_2026-11-04.md) and the code on `main` at 007b437 (0.3.0-alpha.8). The agent confirmed the spec under the owner's delegation. The owner has not read it and approves by merging. "Row" below means a row of that record.

## Stack (as built)

- Backend: Python 3.11 (`backend/Dockerfile`, and the CI jobs `backend`, `migrations` and `acceptance`), FastAPI, SQLAlchemy 2, Alembic migrations, Pydantic 2 (`backend/pyproject.toml`). `db-load.yml`, `db-migrate.yml` and `backend-lint` run 3.12.
- Database: Postgres 15 (Neon in staging and production, a `postgres:15.13` service in CI); unit tests use SQLite fixtures (`backend/tests/conftest.py`).
- Frontend: React 18, TypeScript, Vite, React Router (`frontend/package.json`).
- Edge: the Cloudflare Worker in `edge/api` fronts the API (spec 006).
- CI: `.github/workflows/ci.yml`, jobs `backend`, `migrations`, `acceptance`, `backend-lint`, `frontend` and `frontend-e2e`. `just spec-dag` runs the task DAG check; no workflow runs it.

## Architecture

- **Fetch.** `data/synth-catalog/catalog_scrape.py` is the shared router: free HTTP first, then a paid backend only with a key and an unexpired approval in `data/synth-catalog/receipts/fetch-approvals.json` (T040). It applies the transport limits (content type, 10 MiB, public redirects only) and the ModularGrid deny list. `scripts/hermes_hp_enrich_firecrawl.py` targets official product pages. `scripts/catalog_maker_crawl.py` crawls maker sites and refuses a shared homepage (D6). Firecrawl's proxy tier defaults to `auto` until the owner decides (row 30).
- **Evidence.** Fetch output stays `EVIDENCE_ONLY` under `data/synth-catalog/hermes-research/`. The loader does not read scrape results. Builders (`scripts/build_maker_overlays.py`, `build_category_overlay.py`, `build_reattribution.py`) turn crawl data into overlays that are reviewed and committed.
- **Overlays and manifests.** Versioned files in `data/synth-catalog/overlays/` (HP, category, power, retirements) and `data/synth-catalog/provenance/` (maker corrections). `applied-inputs.sha256` freezes each file by hash, and a test fails if one changes.
- **Loader.** `data/synth-catalog/population.py` `build_plan` and `populate`: insert-if-absent, fill-null, reviewed corrections (D4), retirements (D3), `hp_source` markers, cases through `plan_cases`, and a plan bound to `plan_hash` and `inputs_hash`. `scripts/import_catalog_population.py` runs it locally. `.github/workflows/db-load.yml` (through `scripts/catalog_actions_load.py`) runs a dry run, then an apply that must match the reviewed hashes.
- **Read side.** `backend/modules/catalog_routes.py` serves `module_catalog` (live rows only). `backend/racks/validation.py` blocks placement of an HP that needs reverification and warns on a retired module.
- **Batch lifecycle.** A description of the process, not code (OQ-9). Scripts and `db-load.yml` run the steps. Only the row lifecycle is enforced in code and encoded in tests.

`contracts/README.md` stays a stub: this plan adds no API route. `data-model.md` records the two load tables.

## Work list

T010 and T090 are done. What each plan item became:

| Item | Result |
|---|---|
| T010: `not_nullable` and `identity_mismatch` tests | #334 |
| Spec text: batch table, FR-002, FR-003, SC-005, FR-029, `SEEDED`, owners, stale text | This PR |
| A refusal is recorded and retried (row 3) | #335 |
| Frap refused (row 27) | #335 |
| Remove the writers that bypass the loader (rows 8, 26) | #338 |
| Filter step and residual targets (rows 4, 11) | #335 |
| Applied overlays don't change (row 5) | #340 |
| Lasting load receipts (row 12) | #340 |
| Rollback by run (row 13, decision 40) | #340 |
| Threat model and injection test (row 19) | This PR and #335 |
| FR-016, FR-023, FR-025, FR-026 | T092, not done |
| FR-034 | Built in #308; 298 leads still have no maker page |

### Other open work

- **T031.** Categories for the rows still empty on a load from committed inputs, under the free reads (decision 18).
- **T039.** The 17 rows still marked `legacy_unsourced`, then removal of `UNSOURCED_HP_OVERLAYS` (decision 30).
- **T092.** The schema gaps above.
- **006 T101b.** An owner-only GitHub setting: `production` and `staging` have no protection rules today (row 12).

### Answered since T001

The record's OPEN rows, by the owner's decisions of 2026-11-04: maker permission basis and proxy tier (1, 2), video and power rows (5, 49, 4, 14), a paid cap only for T035 (18), the unsourced HP values (30), Akemie's Castle (41), and the paged catalog API (39, with the full question to counsel). Row 36, keeping the scraped names, is still with counsel.

## Verification

- `cd backend && PYTHONPATH=. pytest tests/unit/test_spec_003_transitions.py tests/test_catalog_corrections.py tests/test_catalog_scrape_router.py tests/test_catalog_transport_limits.py tests/test_crawl_shared_homepages.py tests/test_maker_crawl.py tests/unit/test_003_source_scope.py -q`.
- `tests/test_catalog_population.py`: needs the throwaway Postgres at `127.0.0.1:5432` (it skips otherwise) and takes minutes. CI runs it.
- A `db-load.yml` dry run on staging before any apply, with a go-ahead for each apply.
- `just spec-dag`.

## What T001 settled

- Every remaining `[INFERRED]` line is classified in the [T001 record](T001_CONFIRMATION_2026-11-04.md).
- Workflows skeleton: skills and CI confirmed, owners amended (rows 23, 24).
- D5 stands: T090 removes the other writers (row 26).
- FR-002: amend the text (row 2).
- FR-031 stands: the pre-apply checksum cannot restore anything and `catalog_value_archive` holds no inserts, so a rollback path is still owed (row 13).
- OQ-1 is still open (row 34).

## Spec text

Workflows and the stateful sections used to be copied here. They now live only in [spec.md](spec.md).
