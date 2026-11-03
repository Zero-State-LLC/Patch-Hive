# Repository map

**Generated for:** AI-native engineering foundation  
**Baseline SHA:** `8e22fd2` (refresh after merges)  
**Machine indexes:** `.codebase-memory/` (local, gitignored)

## Product identity

PatchHive is a **deterministic Eurorack rig-intelligence and Patch Book publishing** system.

Canonical loop:

```text
Photo/Manual input → untrusted evidence → user confirmation → immutable inventory
→ hardware-constrained patch generation → validation → Patch Book export
```

**Out of scope:** audio DSP, recording, hardware MIDI/CV activation, production payments by default.

## Entry points

| Surface | Path |
|---------|------|
| Backend app | `backend/main.py` |
| Frontend app | `frontend/src/App.tsx` |
| Docker compose | `docker-compose.yml` |
| Task runner | `Makefile`, `justfile` |
| Migrations | `backend/alembic/` |
| Canon domain | `backend/canon/` |
| Visual evidence | `backend/evidence/` |

## Backend module graph (packages)

| Package | Role |
|---------|------|
| `canon` | Immutable contracts, compiler, runes, inventory, exports, ORM |
| `evidence` | Image prep, vision providers, upload routes, eval harness |
| `patches` | Legacy/dual-path generation engine + inventory gate |
| `runs` | Run listing + native export bridge IDs |
| `racks` / `modules` / `cases` | Inventory catalog dual-path |
| `export` | PDF/SVG/waveform approximation (symbolic, not audio DSP) |
| `community` | Auth (always on) + social (flagged off) |
| `monetization` / `account` | Credits (FE prefers `/api/canon/*`) |
| `admin` | Diagnostics / gallery confirm |
| `patchhive` | Historical package; many tests still import |

Coarse import edges are persisted at `.codebase-memory/graph/module_graph.json`.

## Frontend areas

| Area | Path |
|------|------|
| Routes | `frontend/src/App.tsx` |
| Pages | `frontend/src/pages/` |
| API client | `frontend/src/lib/api.ts` |
| Types | `frontend/src/types/` |
| Admin | `frontend/src/pages/admin/` |

## Public HTTP APIs (active)

- `/api/modules`, `/api/cases`, `/api/racks`, `/api/patches`, `/api/runs`
- `/api/canon/*` — credits, exports, downloads, runs alias
- `/api/racks/{id}/evidence/*` — images, candidates, confirmations
- `/api/export/*` — artifact GETs
- `/api/community/auth/*` — login/register
- Flagged off: social, publishing, leaderboards, referrals

## Ownership graph (logical)

| Concern | Owner package |
|---------|----------------|
| Immutable truth | `canon` |
| Vision evidence | `evidence` (never self-confirms) |
| Patch generation (dual-path) | `patches` + inventory gate |
| Export bridge IDs | `runs.bridge` → native `rig-rev-*` / `gen-run-*` |
| UI MVP shell | `frontend/src/pages` + `App.tsx` |
| Ship authority docs | `CURRENT_STATE.md`, `docs/CONTINUATION.md` |

## Extension points

1. `VisionEvidenceProvider` protocol — mock / fixture / consent-gated cloud  
2. `ImageScanner` protocol — malware adapter  
3. Canon runes — pure operations without ORM  
4. Feature flags in `core/config.py` for legacy surfaces  
5. Alembic chain — single head only  

## Dead code / dual-path candidates

| Surface | Classification |
|---------|----------------|
| Top-level / nested `patchhive` package | HISTORICAL; tests still import |
| Legacy patchbook debit POST | Gated off by default |
| Root `DEPLOY_STATUS.md`, `CANON_DIFF.md` | Superseded notes |

## TODO hotspots (rg)

| Location | Note |
|----------|------|
| `backend/core/ers.py` | async queue integration |
| `backend/core/abrexport.py` | usage tracking |
| `backend/tests/api/test_racks_api.py` | validation status codes |

## Dependency graph (runtime)

```text
React/Vite FE ──HTTP──▶ FastAPI modular monolith
                              │
                              ├─ SQLAlchemy/Alembic ──▶ PostgreSQL
                              ├─ Pillow (image re-encode)
                              ├─ ReportLab/SVG export
                              └─ JWT auth
```

Pinned Python deps: `backend/pyproject.toml`  
Pinned Node deps: `frontend/package-lock.json`

## Indexes for agents

| Index | Path |
|-------|------|
| ctags symbols | `.codebase-memory/symbols/tags` |
| Module graph JSON | `.codebase-memory/graph/module_graph.json` |
| Content hashes | `.codebase-memory/embeddings/content_hashes.json` |
| Arch summary | `.codebase-memory/summaries/architecture_summary.json` |

Regenerate: `just index` or `make index`.
