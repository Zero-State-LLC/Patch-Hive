# PatchHive developer and AI-agent task runner
# Install: https://github.com/casey/just
# Usage: just <recipe>

set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

root := justfile_directory()

default:
	@just --list

# Install backend+frontend deps and build local AI indexes
setup:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}/backend"
	if command -v uv >/dev/null 2>&1; then
		uv venv --allow-existing .venv 2>/dev/null || uv venv .venv
		# shellcheck disable=SC1091
		source .venv/bin/activate
		uv pip install -e '.[dev]'
	else
		python3 -m pip install -e '.[dev]'
	fi
	cd "{{root}}/frontend"
	npm ci
	cd "{{root}}"
	just index
	@echo "setup complete"

spec-dag:
	python3 "{{root}}/scripts/check_spec_dag.py" --strict

lint:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}/backend"
	python -m ruff check canon evidence core patches/inventory_gate.py runs/bridge.py || python3 -m ruff check canon evidence
	python -m black --check canon evidence || true
	cd "{{root}}/frontend"
	npm run lint
	npm run type-check

test:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	bash scripts/test/run.sh unit
	bash scripts/test/run.sh frontend

# Backend golden-path acceptance (Testcontainers or ACCEPTANCE_DATABASE_URL)
test-acceptance:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	bash scripts/test/run.sh acceptance

# CI parity: unit + frontend + acceptance
test-ci:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	bash scripts/test/run.sh ci

# Local compose staging stack checks (smoke + acceptance + design-engine)
test-staging:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	bash scripts/test/run.sh staging

# Full Docker staging suite (smoke + in-docker acceptance + design-engine)
test-docker:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	bash scripts/test/run.sh docker-suite

# Quarantined historical package corpus (not default CI unit path)
test-historical:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}/backend"
	env -u PYTHONPATH python -m pytest patchhive/tests patchhive/runes/tests -q

# Live import density + canon import guard
telemetry-patchhive:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	bash scripts/ai/patchhive_import_telemetry.sh

# Fail if canon/evidence import historical package
guard-patchhive-imports:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	bash scripts/ai/check_no_canon_patchhive_imports.sh

# Local Docker staging (requires .env.staging.local — see docs/evidence/STAGING_LOCAL_DOCKER_RECEIPT.md)
staging-up:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	if [[ ! -f .env.staging.local ]]; then
		echo "Create .env.staging.local first (see docs/evidence/STAGING_LOCAL_DOCKER_RECEIPT.md)" >&2
		exit 1
	fi
	docker compose -f docker-compose.staging.yml --env-file .env.staging.local up -d --build
	echo "Health: http://localhost:8000/health  App: http://localhost:5173"

staging-down:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	docker compose -f docker-compose.staging.yml --env-file .env.staging.local down

staging-ps:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	docker compose -f docker-compose.staging.yml --env-file .env.staging.local ps

# Parse Cases4PatchHive research markdown → fixtures/cases_research_2026.json
cases-parse:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	python3 scripts/parse_cases_research.py

# Validate research cases against CaseCreate (no DB)
cases-dry-run:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	backend/.venv/bin/python scripts/import_cases_research.py --dry-run

# Upsert research cases into DATABASE_URL (optional --replace-source)
cases-import *args:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	if [[ -z "${DATABASE_URL:-}" ]]; then
		echo "Set DATABASE_URL to the target Postgres instance" >&2
		exit 1
	fi
	backend/.venv/bin/python scripts/import_cases_research.py {{args}}

# Build normalized case-catalog seed + source/coverage manifests from research fixture
case-catalog-seed:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	python3 scripts/build_case_catalog_seed.py

# Build Phase 3 mid-tier condensed seed
synth-catalog-phase3-seed *args:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	python3 scripts/build_phase3_catalog_seed.py {{args}}

# Rebuild synth catalog seed from Abraxas research packet (optional --source-dir)
synth-catalog-seed *args:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	python3 scripts/build_synth_catalog_seed.py {{args}}

# Dry-run / import synth catalog research seed (pass --dry-run or empty)
synth-catalog-import *args:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}/backend"
	../backend/.venv/bin/python -m integrations.synth_catalog_importer {{args}}

# Import demo modules fixture into DATABASE_URL
modules-demo-import *args:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	if [[ -z "${DATABASE_URL:-}" ]]; then
		echo "Set DATABASE_URL to the target Postgres instance" >&2
		exit 1
	fi
	backend/.venv/bin/python scripts/import_modules_demo.py {{args}}

# Import seed-v1 into DATABASE_URL (durable; requires migrations at case catalog head)
case-catalog-seed-import:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	if [[ -z "${DATABASE_URL:-}" ]]; then
		echo "Set DATABASE_URL to the target Postgres instance" >&2
		exit 1
	fi
	cd backend
	../backend/.venv/bin/python -m integrations.case_catalog_populator \
	  --input ../data/cases/seed-v1.json \
	  --receipt ../data/cases/receipts/seed-v1.import.json

# Dry-run seed-v1 into an isolated SQLite catalog schema (no durable writes)
case-catalog-seed-dry-run:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}/backend"
	rm -f case_catalog_seed_test.db
	DATABASE_URL=sqlite:///./case_catalog_seed_test.db ../backend/.venv/bin/python - <<'PY'
	from cases.models import CaseCatalog  # noqa: F401
	from cases.source_policy import CaseSourcePolicyPacket  # noqa: F401
	from core.database import Base, engine

	Base.metadata.create_all(bind=engine)
	PY
	DATABASE_URL=sqlite:///./case_catalog_seed_test.db ../backend/.venv/bin/python -m integrations.case_catalog_populator \
	  --input ../data/cases/seed-v1.json \
	  --dry-run \
	  --receipt ../data/cases/receipts/seed-v1.dry-run.json

coverage:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}/backend"
	env -u PYTHONPATH python -m pytest tests --ignore=tests/acceptance --cov -q

# Rebuild symbol/graph indexes under .codebase-memory/
index:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	bash scripts/ai/rebuild_indexes.sh

memory: index
	@echo "codebase-memory indexes refreshed"

# Full DeusData codebase-memory-mcp knowledge graph (persistent artifact)
index-mcp:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	export PATH="${HOME}/.local/bin:${PATH}"
	if ! command -v codebase-memory-mcp >/dev/null 2>&1; then
		echo "install: pip install codebase-memory-mcp" >&2
		exit 1
	fi
	codebase-memory-mcp cli index_repository \
		--repo-path "{{root}}" \
		--mode full \
		--name patch-hive-full \
		--persistence true
	@echo "codebase-memory-mcp artifact → .codebase-memory/graph.db.zst"

clean:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	rm -rf .codebase-memory/indexes/* .codebase-memory/embeddings/* cache/* artifacts/* 2>/dev/null || true
	find . -type d -name __pycache__ -not -path './.git/*' -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/coverage backend/.coverage htmlcov frontend/test-results frontend/playwright-report 2>/dev/null || true
	@echo "clean complete (indexes may need just index)"

validate:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	just lint
	just test
	@echo "validate ok"

build:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}/frontend"
	npm run build

docs:
	@echo "Engineering docs: docs/engineering/"
	@ls -1 "{{root}}/docs/engineering"
	@echo "AI: AI_CONTEXT.md SYSTEM_CONTEXT.md"

# Optional security-ish local scans (best-effort)
scan:
	#!/usr/bin/env bash
	set -euo pipefail
	cd "{{root}}"
	if command -v gitleaks >/dev/null; then gitleaks detect --source . --no-git -v || true; fi
	if command -v codespell >/dev/null; then codespell backend frontend docs README.md --skip="*.json,*.lock,node_modules,.git" || true; fi
	if command -v ast-grep >/dev/null; then ast-grep scan || true; fi
