# PatchHive Acceptance Tests

This suite validates the MVP golden path end-to-end:

1. Create rig
2. Generate patch library
3. View patches
4. Export patch book (credit gated)
5. Admin controls

## Prerequisites

- Python 3.11+
- Docker (for Testcontainers) **or** `ACCEPTANCE_DATABASE_URL` pointing at Postgres
- Optional: Node 18+ for Playwright UI smoke

## One command (preferred)

```bash
# Host runner (auto Testcontainers, or use ACCEPTANCE_DATABASE_URL)
bash scripts/test/run.sh acceptance          # Linux/macOS/CI
powershell -File scripts/test/run.ps1 acceptance  # Windows

# Full CI parity locally
bash scripts/test/run.sh ci

# Against local staging Compose Postgres
bash scripts/test/run.sh staging
# or: make test-acceptance / just test-acceptance
```

## Backend acceptance tests

```bash
cd backend
# Default: spins Postgres via Testcontainers
python -m pytest tests/acceptance -q

# Or external DB (CI / compose):
export ACCEPTANCE_DATABASE_URL=postgresql://patchhive:pass@localhost:5433/patchhive_acceptance
python -m pytest tests/acceptance -q
```

Compose helper (creates `patchhive_acceptance` DB, does not truncate live staging):

```bash
bash scripts/staging/acceptance.sh
# powershell -File scripts/staging/acceptance.ps1
```

## UI smoke tests (Playwright)

```bash
bash scripts/test/run.sh e2e
# or:
cd frontend && npm run test:e2e
```

## Golden Demo fixture

The acceptance tests use the Golden Demo fixture at `fixtures/golden_demo_seed.json`.

```bash
python scripts/seed_golden_demo.py --update-fixture
```

## CI

Workflow: the `acceptance` job in `.github/workflows/ci.yml`.  
Sets `ACCEPTANCE_DATABASE_URL` against a Postgres 15 service container and runs `pytest tests/acceptance`.

Payments remain fail-closed (`STRIPE_TEST_MODE=true`, `ALLOW_PRODUCTION_PAYMENTS=false`).
