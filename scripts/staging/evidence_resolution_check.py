#!/usr/bin/env python3
"""006 T060b check: upload one evidence image to staging and call decision-resolution.

Signs in as the seeded golden demo user, uploads one generated PNG (a flat test card
this repo makes, so nothing third-party is sent to a provider) to that user's private
rack with provider consent, reads the evidence id from the candidates listing, then
calls ``POST /api/racks/{rack_id}/evidence/decision-resolution`` twice with the same
idempotency key. It records the HTTP status and code of each step.

With no decision provider enabled on staging the expected answer is a fail-closed 409
(for example ``DECISION_INTELLIGENCE_DISABLED`` or ``ENABLEMENT_RECEIPT_REQUIRED``) and
no inventory change; with a provider enabled it is 200 with a disposition, and the
second call must return the same decision. Either is evidence for T060b; anything
else (404 on the evidence id, 5xx) is a failure.

Environment: STAGING_API_URL, PATCHHIVE_DEMO_USER_PASSWORD (the password the seeder
set). The receipt holds statuses, codes and hashes only: no password, token or
image bytes.

Usage (repo root):
  python scripts/staging/evidence_resolution_check.py --receipt-out t060b-receipt.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import struct
import sys
import time
import zlib
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "patchhive.staging-evidence-resolution-check.v1"
FAIL_CLOSED_CODES = {
    "DECISION_INTELLIGENCE_DISABLED",
    "ENABLEMENT_RECEIPT_REQUIRED",
    "CLEF_DISABLED",
    "NVIDIA_DISABLED",
}


def test_card_png(width: int = 96, height: int = 72, shade: int = 0x80) -> bytes:
    """A flat PNG built here, so the upload carries no third-party content.

    The default size clears the intake gate (`assess_local_image_quality`: 64 px each
    way); ``shade`` makes each run's bytes, and so its asset, distinct.
    """
    pixel = bytes((shade & 0xFF, 0x80, 0x80))
    raw = b"".join(b"\x00" + pixel * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _demo_username() -> str:
    path = REPO_ROOT / "scripts" / "seed_golden_demo.py"
    spec = importlib.util.spec_from_file_location("seed_golden_demo", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("seed_golden_demo.py not loadable")
    # The seeder imports backend models; only its constant is needed here.
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["seed_golden_demo"] = mod
    spec.loader.exec_module(mod)
    return str(mod.DEMO_USER_USERNAME)


def _json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return None


def _code(body: Any) -> str | None:
    if isinstance(body, dict):
        detail = body.get("detail", body)
        if isinstance(detail, dict):
            return detail.get("code") or detail.get("error_code")
        if isinstance(detail, str):
            return detail if detail.isupper() else None
        return body.get("code")
    return None


def run_check(http: httpx.Client, username: str, password: str) -> dict:
    steps: list[dict] = []

    def record(name: str, resp: httpx.Response, ok: bool) -> Any:
        body = _json(resp)
        steps.append(
            {"step": name, "status": resp.status_code, "code": _code(body), "ok": ok}
        )
        return body

    resp = http.post(
        "/api/community/auth/login", json={"username": username, "password": password}
    )
    token = (_json(resp) or {}).get("access_token") if resp.status_code == 200 else None
    record("login_user", resp, bool(token))
    if not token:
        return {"outcome": "FAIL", "steps": steps}
    headers = {"Authorization": f"Bearer {token}"}

    resp = http.get("/api/racks/", params={"is_public": "false"}, headers=headers)
    body = record("list_private_racks", resp, resp.status_code == 200)
    racks = (body or {}).get("racks") or []
    if not racks:
        steps[-1]["ok"] = False
        return {"outcome": "FAIL", "steps": steps}
    rack_id = int(racks[0]["id"])

    image = test_card_png(shade=int(time.time()) % 256)
    resp = http.post(
        f"/api/racks/{rack_id}/evidence/images",
        headers=headers,
        files={"files": ("t060b-test-card.png", image, "image/png")},
        data={"consent_provider_processing": "true"},
    )
    body = _json(resp)
    body = body if isinstance(body, dict) else {}
    uploaded = body.get("uploaded") or []
    # 201 also answers a batch whose every file was rejected; require this file's asset.
    record("upload_evidence", resp, resp.status_code == 201 and len(uploaded) == 1)
    if resp.status_code != 201 or len(uploaded) != 1:
        steps[-1]["rejected"] = [r.get("reason") for r in body.get("rejected") or []]
        return {"outcome": "FAIL", "rack_id": rack_id, "steps": steps}
    asset_id = str(uploaded[0]["id"])

    resp = http.get(f"/api/racks/{rack_id}/evidence/candidates", headers=headers)
    body = record("list_candidates", resp, resp.status_code == 200)
    # Candidates are sorted by confidence, not upload time: keep only this upload's.
    items = [
        i
        for i in (body or {}).get("candidates") or []
        if i.get("evidence_id") and str(i.get("image_asset_id")) == asset_id
    ]
    if not items:
        steps[-1]["ok"] = False
        return {
            "outcome": "FAIL",
            "rack_id": rack_id,
            "image_asset_id": asset_id,
            "steps": steps,
        }
    evidence_id = str(items[0]["evidence_id"])

    key = f"t060b-{int(time.time())}"
    answers = []
    for attempt in (1, 2):
        resp = http.post(
            f"/api/racks/{rack_id}/evidence/decision-resolution",
            headers=headers,
            json={"evidence_id": evidence_id, "idempotency_key": key},
        )
        body = _json(resp)
        code = _code(body)
        ok = resp.status_code == 200 or (
            resp.status_code == 409 and code in FAIL_CLOSED_CODES
        )
        record(f"decision_resolution_{attempt}", resp, ok)
        answers.append(
            {
                "status": resp.status_code,
                "code": code,
                "disposition": (body or {}).get("disposition")
                if isinstance(body, dict)
                else None,
                "selected_choice": (body or {}).get("selected_choice")
                if isinstance(body, dict)
                else None,
            }
        )
    same = answers[0] == answers[1]
    steps.append(
        {"step": "idempotent_replay", "status": None, "code": None, "ok": same}
    )
    outcome = "PASS" if all(s["ok"] for s in steps) else "FAIL"
    return {
        "outcome": outcome,
        "rack_id": rack_id,
        "evidence_id": evidence_id,
        "image_asset_id": asset_id,
        "image_sha256": hashlib.sha256(image).hexdigest(),
        "resolution": answers[0],
        "steps": steps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt-out", default="t060b-receipt.json")
    args = parser.parse_args(argv)
    api = os.environ.get("STAGING_API_URL", "").rstrip("/")
    password = os.environ.get("PATCHHIVE_DEMO_USER_PASSWORD", "")
    if not api.startswith("https://api-staging.") or not password:
        print(
            "refused: set STAGING_API_URL to the staging API and PATCHHIVE_DEMO_USER_PASSWORD",
            file=sys.stderr,
        )
        return 2
    with httpx.Client(base_url=api, timeout=90.0) as http:
        result = run_check(http, _demo_username(), password)
    receipt = {
        "schema_version": SCHEMA,
        "api": api,
        "source_commit_sha": os.environ.get("WALKTHROUGH_SOURCE_SHA")
        or os.environ.get("GITHUB_SHA"),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **result,
    }
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    receipt["receipt_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    Path(args.receipt_out).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for step in result["steps"]:
        print(
            f"  {step['step']}: ok={step['ok']} status={step['status']} code={step['code']}"
        )
    print(f"T060B {result['outcome']} receipt_sha256={receipt['receipt_sha256']}")
    return 0 if result["outcome"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
