# `patchhive` package import telemetry

**Method:** `rg` over repo Python after live `main` checkout  
**Date:** 2026-07-21 · main baseline post-#79; Wave 4 + first legacy_pipeline migration  
**Goal:** Classify surfaces so agents do not confuse HISTORICAL `patchhive` trees with CANON_MVP `backend/canon` / `backend/evidence`.  
**Regenerate:** `just telemetry-patchhive` or `bash scripts/ai/patchhive_import_telemetry.sh`

## Classification

| Class | Meaning | Disposition |
|-------|---------|-------------|
| **CANON_MVP** | `backend/canon/*`, `backend/evidence/*` | Primary product authority |
| **CANON_SUPPORTING** | `backend/patchhive/*` pipeline still exercised by marked unit tests | Keep; **no new features** |
| **LEGACY_PIPELINE_TEST** | `backend/tests/**` files that `import patchhive` | Marked `legacy_pipeline`; still in default CI |
| **HISTORICAL_PACKAGE_TEST** | `backend/patchhive/tests/*` | **Quarantined** — not in default `testpaths` |
| **HISTORICAL_ORPHAN** | repo-root `patchhive/` (sibling of `backend/`) | Not on backend pytest path; do not extend |
| **NO_IMPORT_FROM_CANON** | `backend/canon` + `backend/evidence` must not import package `patchhive` | Enforced by CI script |

## Live evidence (OBSERVED)

### Forbidden direction: canon / evidence → package

```text
rg 'from patchhive|import patchhive' backend/canon backend/evidence  → NONE
rg 'from patchhive|import patchhive' backend/patches backend/racks backend/main.py backend/core  → NONE
```

**Exit criterion:** no accidental product-path imports of the historical package.  
**CI:** `bash scripts/ai/check_no_canon_patchhive_imports.sh` (engineering-quality workflow).

### Product package tree

| Tree | ~`.py` files | Role |
|------|--------------|------|
| `backend/canon` | product | CANON_MVP |
| `backend/evidence` | product | CANON_MVP |
| `backend/patchhive` | ~67 | CANON_SUPPORTING / historical pipeline |
| repo-root `patchhive/` | ~78 | HISTORICAL_ORPHAN (duplicate-era tree) |

### `backend/tests` files that import `patchhive` (LEGACY_PIPELINE_TEST)

**NONE** (as of full migration PR). All former residual unit suites now import `canon.*` only:

| Former file | Canon home |
|-------------|------------|
| `test_schema_roundtrip.py` | `test_canon_contracts` / `RigMetricsPacket` |
| `test_gallery_revisions.py` | `canon.gallery_revisions` |
| `test_function_store_commit.py` | `canon.function_registry` |
| `test_query_surface.py` | `canon.query_surface` |
| `test_pipeline_run.py` | `tests.canon_demo_pipeline` |
| `test_export_pack.py` | `canon.export_pack` + `tests.canon_demo_pipeline` |

Historical VL2 pipeline under `backend/patchhive/**` remains for package-internal / rune maps; default unit tests no longer import it.

```bash
cd backend
env -u PYTHONPATH python -m pytest tests -m legacy_pipeline --ignore=tests/acceptance -q
# expect: 0 collected / all deselected
```

### Heaviest importers inside `backend/patchhive` (internal)

| File | Import lines (approx) |
|------|----------------------|
| `pipeline/run.py` | 8 |
| `cli/export_pack.py` | 8 |
| `ops/build_patch_library.py` | 7 |
| `cli/confirm.py` | 6 |
| `pipeline/run_library.py` | 5 |
| `export/export_pack.py` | 5 |

### Quarantine map (pytest)

| Path | Default CI? | How |
|------|-------------|-----|
| `backend/tests/**` (non-legacy) | **yes** | `testpaths = ["tests", …]` |
| `backend/tests/**` with `legacy_pipeline` | **yes** (marked) | still collected; filterable |
| `backend/patchhive/runes/tests` | **yes** (narrow) | listed in `testpaths` |
| `backend/patchhive/tests/*` | **no** | not in `testpaths`; `norecursedirs` |
| repo-root `patchhive/**` | **no** | outside backend package |

Run quarantined package tests explicitly:

```bash
just test-historical
# or:
cd backend && env -u PYTHONPATH python -m pytest patchhive/tests patchhive/runes/tests -q
```

## Packaging (`backend/pyproject.toml`)

- setuptools still packages `patchhive*` submodules (runtime importability for marked tests).
- `testpaths`: `tests` + `patchhive/runes/tests` only.
- `norecursedirs` includes `patchhive/tests`.
- Marker: `legacy_pipeline`.

## Recommended slices (do not big-bang delete)

1. ~~Docs + markers + CI guard (this PR)~~  
2. Migrate LEGACY_PIPELINE_TEST consumers onto `canon` / `evidence` one suite at a time  
3. Drop `patchhive` from setuptools packages when no remaining importers  
4. Delete repo-root `patchhive/` after import graph is empty  

## Agent rules

```text
Prefer backend/canon and backend/evidence for new work.
Treat backend/patchhive as read-mostly historical pipeline unless fixing a red legacy_pipeline test.
Never import patchhive from canon or evidence.
Do not implement new product features under backend/patchhive or repo-root patchhive/.
Schema version strings containing "patchhive." are fine (not package imports).
```
