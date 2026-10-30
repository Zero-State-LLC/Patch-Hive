#!/usr/bin/env python3
"""API walkthrough: Design Engine preview + debit + fulfillment + download pack.

Spec 008 T030/T040. Seeds the golden demo, verifies the seeded credentials
(read-only, no password patching), collects F5 alias/FE cutover evidence, runs
the walkthrough with the seeded accounts, and writes a SHA-sealed receipt.

Prerequisites:
  - Compose stack with design-engine overlay (flags on, test payments). The
    script verifies the running server's effective flags via the admin-only
    GET /api/admin/ops/runtime-flags and fails closed if they cannot be read
    or are not test mode with production payments disabled.
  - Host Python with backend deps (backend/.venv-acceptance is fine)

Usage (repo root):
  set DATABASE_URL=postgresql://patchhive:...@localhost:5433/patchhive
  set STAGING_API_URL=http://localhost:18000
  set PYTHONPATH=backend
  python scripts/staging/design_engine_walkthrough.py --receipt-out walkthrough-receipt.json

The receipt holds hashes, flags, and step outcomes only. It never contains
passwords, tokens, database URLs, or pack bytes.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Register SQLAlchemy relationships used by User / ledger / exports (same as main.py).
from account.models import CreditLedgerEntry, ExportRecord  # noqa: E402, F401
from canon.models import CanonicalCreditLedgerEntryRecord, CanonicalExportRecord  # noqa: E402, F401
from core.ops.design_walkthrough import run_staging_walkthrough  # noqa: E402
from core.ops.f5_cutover import CutoverError, SeedAccount, check_seed_auth  # noqa: E402
from monetization.models import CreditsLedger  # noqa: E402, F401
from runs.bridge import ensure_legacy_run_export_bridge  # noqa: E402
from runs.models import Run  # noqa: E402

FE_PAGES_DIR = REPO_ROOT / "frontend" / "src" / "pages"


def _load_seed_module():
    path = REPO_ROOT / "scripts" / "seed_golden_demo.py"
    spec = importlib.util.spec_from_file_location("seed_golden_demo", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("seed_golden_demo.py not loadable")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["seed_golden_demo"] = mod
    spec.loader.exec_module(mod)
    return mod


def _source_sha() -> str:
    pinned = os.environ.get("WALKTHROUGH_SOURCE_SHA", "").strip()
    if pinned:
        return pinned
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    return out.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt-out", default="design-walkthrough-receipt.json")
    args = parser.parse_args()

    api = os.environ.get("STAGING_API_URL", "http://localhost:18000").rstrip("/")
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://patchhive:staging-smoke-db-pass-xx@localhost:5433/patchhive",
    )
    print(f"API={api}")
    print(f"DATABASE_URL host={db_url.split('@')[-1]}")

    engine = create_engine(db_url)
    db = sessionmaker(bind=engine)()
    seed_mod = _load_seed_module()

    print("=== Seed golden demo ===")
    seed = seed_mod.seed_golden_demo(db)
    user = SeedAccount(seed.username, seed.password, seed_mod.DEMO_USER_ROLE)
    admin = SeedAccount(seed.admin_username, seed.admin_password, seed_mod.DEMO_ADMIN_ROLE)
    print(f"  user={seed.username} admin={seed.admin_username} run_id={seed.run_id}")

    print("=== Seed auth alignment (read-only) ===")
    seed_auth = check_seed_auth(db, (user, admin))
    print(f"  aligned={seed_auth.aligned}")
    if not seed_auth.aligned:
        print("FAIL seed auth not aligned; re-run scripts/staging/seed-demo.* (no manual patching)")
        return 1

    run = db.get(Run, seed.run_id)
    if run is None:
        print("FAIL seeded run missing")
        return 1
    bridge = ensure_legacy_run_export_bridge(db, run)
    db.commit()
    sources = bridge.as_export_body_fields()
    db.close()

    client = httpx.Client(base_url=api, timeout=90.0)
    # Scan every active page (frontend/src/legacy is not routed); the guard also
    # requires the known list pages to be on the canon alias.
    fe_sources = {
        path.relative_to(REPO_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(FE_PAGES_DIR.rglob("*.ts*"))
    }
    # Alias evidence and the TARGET server's effective flags are verified inside
    # run_staging_walkthrough before any generate/export call; a local overlay
    # file is never trusted. Any failure aborts with no receipt written.
    try:
        result = run_staging_walkthrough(
            client,
            seed_auth=seed_auth,
            user=user,
            admin=admin,
            user_id=seed.user_id,
            rig_id=seed.rig_id,
            sources=sources,
            fe_sources=fe_sources,
            source_commit_sha=_source_sha(),
            expected_environment="staging",
            log=print,
        )
    except CutoverError as exc:
        # Codes and non-secret detail only (failed checks, HTTP status, env name).
        print(f"FAIL {exc}")
        return 1
    receipt = result.receipt
    bundle = result.bundle()

    Path(args.receipt_out).write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WALKTHROUGH PASS receipt_sha256={receipt.record_sha256}")
    print(f"  source_commit_sha={receipt.source_commit_sha}")
    print(f"  written to {args.receipt_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
