#!/usr/bin/env python3
"""Check a real generate on the deployed staging API.

The Design Engine walkthrough exports a patch the seeder made in-process, so it never calls the
generate route. This signs in as the seeded golden demo user and generates on that user's rack
through the API, then reads the run back: the run succeeded, it keeps no failure reason, and its
patches carry the engine version this commit expects.

Environment: STAGING_API_URL, PATCHHIVE_DEMO_USER_PASSWORD (the password the seeder set). The
receipt holds statuses, counts and versions only: no password or token.

Usage (repo root):
  python scripts/staging/generate_check.py --receipt-out generate-receipt.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "staging"))

from evidence_resolution_check import _code, _demo_username, _json  # noqa: E402

SCHEMA = "patchhive.staging-generate-check.v1"


def expected_engine_version() -> str:
    source = (REPO_ROOT / "backend" / "core" / "config.py").read_text(encoding="utf-8")
    match = re.search(r'patch_engine_version: str = "([^"]+)"', source)
    if match is None:
        raise RuntimeError("patch_engine_version not found in core/config.py")
    return match.group(1)


def run_check(http: httpx.Client, username: str, password: str, engine_version: str) -> dict:
    steps: list[dict] = []

    def record(name: str, resp: httpx.Response, ok: bool, **extra: Any) -> Any:
        body = _json(resp)
        steps.append({"step": name, "status": resp.status_code, "code": _code(body), "ok": ok, **extra})
        return body

    resp = http.post("/api/community/auth/login", json={"username": username, "password": password})
    token = (_json(resp) or {}).get("access_token") if resp.status_code == 200 else None
    record("login_user", resp, bool(token))
    if not token:
        return {"outcome": "FAIL", "steps": steps}
    headers = {"Authorization": f"Bearer {token}"}

    resp = http.get("/api/racks/", params={"is_public": "false"}, headers=headers)
    racks = (_json(resp) or {}).get("racks") or []
    record("list_private_racks", resp, resp.status_code == 200 and bool(racks))
    if not racks:
        return {"outcome": "FAIL", "steps": steps}
    rack_id = int(racks[0]["id"])

    resp = http.post(f"/api/patches/generate/{rack_id}", json={}, headers=headers)
    generated = _json(resp) if resp.status_code == 200 else {}
    generated = generated if isinstance(generated, dict) else {}
    count = int(generated.get("generated_count") or 0)
    run_id = generated.get("run_id")
    record("generate", resp, resp.status_code == 200 and count >= 1 and bool(run_id), generated_count=count)
    if not (count >= 1 and run_id):
        steps[-1]["generation_status"] = generated.get("generation_status")
        steps[-1]["inventory_gate_messages"] = generated.get("inventory_gate_messages")
        return {"outcome": "FAIL", "rack_id": rack_id, "steps": steps}

    resp = http.get(f"/api/runs/{run_id}", headers=headers)
    run = _json(resp) if resp.status_code == 200 else {}
    run = run if isinstance(run, dict) else {}
    record(
        "read_run",
        resp,
        run.get("status") == "succeeded" and "failure_reason" in run and run["failure_reason"] is None,
        run_status=run.get("status"),
        export_bridge_ready=run.get("export_bridge_ready"),
    )

    patches = generated.get("patches") or []
    versions = sorted({str(patch.get("generation_version")) for patch in patches})
    steps.append(
        {
            "step": "engine_version",
            "status": None,
            "code": None,
            "ok": versions == [engine_version],
            "expected": engine_version,
            "found": versions,
        }
    )
    outcome = "PASS" if all(step["ok"] for step in steps) else "FAIL"
    return {"outcome": outcome, "rack_id": rack_id, "run_id": run_id, "steps": steps}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt-out", required=True)
    args = parser.parse_args()
    api = os.environ.get("STAGING_API_URL", "").rstrip("/")
    password = os.environ.get("PATCHHIVE_DEMO_USER_PASSWORD", "")
    if not api.startswith("https://api-staging.") or not password:
        print("refused: set STAGING_API_URL to the staging API and PATCHHIVE_DEMO_USER_PASSWORD", file=sys.stderr)
        return 2
    with httpx.Client(base_url=api, timeout=120.0) as http:
        result = run_check(http, _demo_username(), password, expected_engine_version())
    receipt = {
        "schema_version": SCHEMA,
        "api": api,
        "source_commit_sha": os.environ.get("WALKTHROUGH_SOURCE_SHA") or os.environ.get("GITHUB_SHA"),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **result,
    }
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    receipt["receipt_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    Path(args.receipt_out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for step in result["steps"]:
        print(f"  {step['step']}: ok={step['ok']} status={step['status']} code={step['code']}")
    print(f"GENERATE {result['outcome']} receipt_sha256={receipt['receipt_sha256']}")
    return 0 if result["outcome"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
