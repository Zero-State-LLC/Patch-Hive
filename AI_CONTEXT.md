# AI_CONTEXT — PatchHive (LLM retrieval optimized)

## One-liner

Deterministic Eurorack **rig intelligence + Patch Book publishing**. Not audio DSP. Not hardware control.

## Stack

- **BE:** FastAPI modular monolith (`backend/main.py`), SQLAlchemy, Alembic, JWT  
- **FE:** React + TypeScript + Vite (`frontend/`)  
- **DB:** PostgreSQL  
- **Tests:** pytest, Vitest, Playwright  
- **Tasks:** `just` + `Makefile`  

## Directory map

| Path | Meaning |
|------|---------|
| `backend/canon/` | Canonical contracts, compiler, inventory, exports ORM |
| `backend/evidence/` | Image security, vision providers, upload/confirm APIs, eval |
| `backend/patches/` | Patch engine + inventory gate (dual-path generate) |
| `backend/runs/` | Run list + native bridge IDs |
| `backend/racks|modules|cases/` | Catalog dual-path HTTP |
| `frontend/src/pages/` | MVP UI |
| `docs/` | Architecture, VSI, canon, ops |
| `docs/engineering/` | Agent/dev engineering guides |
| `.codebase-memory/` | Local indexes (gitignored) |

## Canonical flow

Photo/manual → untrusted evidence → user confirm → immutable inventory → generate patches → validate → export PDF/SVG/JSON/ZIP.

## Authority files

1. `CURRENT_STATE.md` — HEAD, alembic, CI, deploy truth  
2. `docs/CONTINUATION.md` — ordered work  
3. `docs/CANON.md` / ADR-0001 / ADR-005 — immutability + VSI  
4. `docs/VISUAL_SYSTEM_INTELLIGENCE.md` — vision contract  

## Commands

```bash
just setup | just lint | just test | just validate | just index | just memory
cd backend && env -u PYTHONPATH pytest tests --ignore=tests/acceptance -q
cd frontend && npm ci && npm test -- --run && npm run type-check && npm run lint
```

## API surface (MVP)

- Catalog: `/api/modules`, `/api/cases`, `/api/racks`, `/api/patches`, `/api/runs`  
- Canon: `/api/canon/credits|exports|runs|downloads`  
- Evidence: `/api/racks/{id}/evidence/images|candidates|confirmations`  
- Auth: `/api/community/auth/*`  

## Invariants

- Provider ≠ confirmed truth  
- Single Alembic head  
- Payments test-mode by default  
- Native IDs: `rig-rev-*`, `gen-run-*`  
- Signal `audio` ≠ audio engine  

## Philosophy

Fail closed. Prefer missing data over fabrication. Deterministic seeds and hashes. Modular monolith. Evidence-based readiness (no fake % complete).
