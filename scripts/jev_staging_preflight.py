#!/usr/bin/env python3
"""Fail-closed Jev staging preflight.

This tool does not enable Decision Intelligence. It verifies a pinned model,
executes one bounded provider-neutral choice request, and emits a receipt that
can be retained as T070 evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone

import httpx

MOVING_ALIASES = {"jev-latest", "jev-preview"}


def stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("JEV_BASE_URL", "https://api.typesafe.ai"))
    parser.add_argument("--model", default=os.getenv("JEV_MODEL", ""))
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    api_key = os.getenv("TYPESAFE_API_KEY", "")
    if not api_key:
        raise SystemExit("TYPESAFE_API_KEY is required")
    if not args.model:
        raise SystemExit("JEV_MODEL/--model is required and must be pinned")
    if args.model in MOVING_ALIASES:
        raise SystemExit("moving Jev aliases are forbidden for controlled evaluation")

    request_id = "patchhive-t070-preflight"
    payload = {
        "model": args.model,
        "state": {
            "purpose": "integration_preflight",
            "canonical_authority": False,
            "evidence": "synthetic",
        },
        "questions": {
            request_id: {
                "type": "choice",
                "instructions": "Select the explicit synthetic sentinel.",
                "criteria": {
                    "sentinel": "The explicit synthetic sentinel.",
                    "none_of_above": "Use only if the sentinel is not present.",
                },
            }
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Idempotency-Key": request_id,
    }

    started = time.perf_counter()
    status = "FAILED"
    error_code = None
    response_hash = None
    answer_shape_valid = False
    http_status = None
    try:
        with httpx.Client(timeout=args.timeout) as client:
            response = client.post(
                f"{args.base_url.rstrip('/')}/v1/systemone",
                headers=headers,
                json=payload,
            )
        http_status = response.status_code
        response.raise_for_status()
        body = response.json()
        response_hash = stable_hash(body)
        answers = body.get("result", body).get("answers", {})
        answer = answers.get(request_id)
        answer_shape_valid = isinstance(answer, dict)
        if not answer_shape_valid:
            error_code = "ANSWER_MISSING"
        else:
            status = "SUCCEEDED"
    except httpx.TimeoutException:
        error_code = "TIMEOUT"
    except httpx.HTTPStatusError as exc:
        error_code = f"HTTP_{exc.response.status_code}"
    except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError):
        error_code = "PROVIDER_OR_SCHEMA_ERROR"

    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    receipt = {
        "schema_version": "patchhive.jev-preflight.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider": "jev",
        "model": args.model,
        "base_url": args.base_url.rstrip("/"),
        "request_hash": stable_hash(payload),
        "response_hash": response_hash,
        "http_status": http_status,
        "latency_ms": latency_ms,
        "status": status,
        "error_code": error_code,
        "answer_shape_valid": answer_shape_valid,
        "canonical_authority": False,
        "feature_enabled": False,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if status == "SUCCEEDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
