#!/usr/bin/env python3
"""Spec 009 T060: the staging walkthrough from a photo.

Signs in as the seeded golden demo owner, uploads the fixture photo, confirms its Reading,
generates, and exports a book on the deployed staging API, then writes a sealed receipt of the
Reading, the revision, the run and the export (backend/core/ops/photo_walkthrough.py). Staging
replays the photo's recorded answer from backend/data/photo-readings, so the script refuses to
start unless the repo ships that recording. The workflow seeds the golden demo first.

Environment: STAGING_API_URL (the staging API), PATCHHIVE_DEMO_USER_PASSWORD and
PATCHHIVE_DEMO_ADMIN_PASSWORD (the passwords the seeder set). The receipt holds ids, counts and
hashes only: no password, token or photo.

Usage (repo root, PYTHONPATH=backend):
  python scripts/staging/photo_walkthrough.py --photo fixtures/photo-walkthrough/rig.jpg \
      --rows 0 --receipt-out photo-walkthrough-receipt.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.ops.f5_cutover import SeedAccount  # noqa: E402
from core.ops.photo_walkthrough import (  # noqa: E402
    photo_walkthrough_receipt,
    run_photo_walkthrough,
)

RECORDINGS = BACKEND / "data" / "photo-readings"
# The only folder the walkthrough uploads a photo from, so a dispatch can't send any other file.
FIXTURES = REPO_ROOT / "fixtures" / "photo-walkthrough"


def recording_for(photo: Path, recordings: Path | None = None) -> Path | None:
    """The recorded answer staging will replay for this photo, when the repo ships one."""
    path = (recordings or RECORDINGS) / f"{hashlib.sha256(photo.read_bytes()).hexdigest()}.json"
    return path if path.is_file() else None


def _seed_accounts(user_password: str, admin_password: str) -> tuple[SeedAccount, SeedAccount]:
    """The golden demo's owner and admin, by the names the seeder gives them."""
    spec = importlib.util.spec_from_file_location(
        "seed_golden_demo", REPO_ROOT / "scripts" / "seed_golden_demo.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("seed_golden_demo.py not loadable")
    seed = importlib.util.module_from_spec(spec)
    sys.modules["seed_golden_demo"] = seed
    spec.loader.exec_module(seed)
    return (
        SeedAccount(seed.DEMO_USER_USERNAME, user_password, seed.DEMO_USER_ROLE),
        SeedAccount(seed.DEMO_ADMIN_USERNAME, admin_password, seed.DEMO_ADMIN_ROLE),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--photo", required=True, help="the fixture photo of the Rig")
    parser.add_argument("--rows", default="0", help='the rows it covers: "0", or "0-1"')
    parser.add_argument("--receipt-out", required=True)
    args = parser.parse_args(argv)

    api = os.environ.get("STAGING_API_URL", "").rstrip("/")
    user_password = os.environ.get("PATCHHIVE_DEMO_USER_PASSWORD", "")
    admin_password = os.environ.get("PATCHHIVE_DEMO_ADMIN_PASSWORD", "")
    if not api.startswith("https://api-staging.") or not user_password or not admin_password:
        print(
            "refused: set STAGING_API_URL to the staging API, and the demo passwords the seeder set",
            file=sys.stderr,
        )
        return 2
    photo = Path(args.photo)
    if not photo.resolve().is_relative_to(FIXTURES.resolve()):
        print(f"refused: the photo must be under {FIXTURES}", file=sys.stderr)
        return 2
    if not photo.is_file():
        print(
            f"refused: no fixture photo at {photo} (the owner supplies it, spec 009 T060b)",
            file=sys.stderr,
        )
        return 2
    if recording_for(photo) is None:
        print(
            "refused: backend/data/photo-readings holds no recorded answer for this photo, "
            "so staging can't read it",
            file=sys.stderr,
        )
        return 2

    user, admin = _seed_accounts(user_password, admin_password)
    with httpx.Client(base_url=api, timeout=120.0) as http:
        result = run_photo_walkthrough(
            http, user=user, admin=admin, photo=photo.read_bytes(), rows=args.rows
        )
    receipt = photo_walkthrough_receipt(
        result,
        api=api,
        source_commit_sha=os.environ.get("WALKTHROUGH_SOURCE_SHA")
        or os.environ.get("GITHUB_SHA")
        or "",
        checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    Path(args.receipt_out).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for step in result["steps"]:
        print(f"  {step['step']}: ok={step['ok']} status={step['status']} code={step['code']}")
    if result["steps"][-1]["code"] == "RECORDING_MISSING":
        print(
            "  the repo holds this photo's recording, so staging may be running an image from "
            "before it landed: redeploy staging, then run the walkthrough again"
        )
    print(f"PHOTO WALKTHROUGH {result['outcome']} receipt_sha256={receipt['receipt_sha256']}")
    return 0 if result["outcome"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
