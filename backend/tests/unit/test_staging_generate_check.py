"""Offline tests for scripts/staging/generate_check.py (fake API, no network)."""

from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
_spec = spec_from_file_location("generate_check", ROOT / "scripts" / "staging" / "generate_check.py")
assert _spec and _spec.loader
check = module_from_spec(_spec)
sys.modules["generate_check"] = check
_spec.loader.exec_module(check)


def _client(generated: dict, run: dict, *, generate_status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/community/auth/login":
            if json.loads(request.content)["password"] != "pw-for-tests-only":
                return httpx.Response(401, json={"detail": "Invalid credentials"})
            return httpx.Response(200, json={"access_token": "tok"})
        assert request.headers["authorization"] == "Bearer tok"
        if path == "/api/racks/":
            return httpx.Response(200, json={"racks": [{"id": 7}]})
        if path == "/api/patches/generate/7":
            return httpx.Response(generate_status, json=generated)
        if path == "/api/runs/19":
            return httpx.Response(200, json=run)
        raise AssertionError(path)

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api-staging.example")


GOOD_RUN = {"status": "succeeded", "failure_reason": None, "export_bridge_ready": True}
GOOD = {"generated_count": 2, "run_id": 19, "patches": [{"generation_version": "1.1.0"}, {"generation_version": "1.1.0"}]}


def _run(generated: dict, run: dict = GOOD_RUN, password: str = "pw-for-tests-only", **options) -> dict:
    with _client(generated, run, **options) as http:
        return check.run_check(http, "golden_demo", password, "1.1.0")


def test_a_real_generate_that_succeeds_passes() -> None:
    result = _run(GOOD)
    assert result["outcome"] == "PASS" and result["run_id"] == 19
    assert [step["step"] for step in result["steps"]] == ["login_user", "list_private_racks", "generate", "read_run", "engine_version"]


def test_a_wrong_password_fails_at_sign_in() -> None:
    result = _run(GOOD, password="wrong")
    assert result["outcome"] == "FAIL" and [s["step"] for s in result["steps"]] == ["login_user"]


def test_no_patches_fails_and_says_why() -> None:
    result = _run({"generated_count": 0, "run_id": None, "patches": [], "generation_status": "NOT_COMPUTABLE", "inventory_gate_messages": ["No modules"]})
    assert result["outcome"] == "FAIL"
    assert result["steps"][-1]["inventory_gate_messages"] == ["No modules"]


def test_an_old_engine_version_fails() -> None:
    result = _run({**GOOD, "patches": [{"generation_version": "1.0.0"}]})
    assert result["outcome"] == "FAIL" and result["steps"][-1]["found"] == ["1.0.0"]


def test_an_api_without_the_failure_reason_field_fails() -> None:
    result = _run(GOOD, {"status": "succeeded"})
    assert result["outcome"] == "FAIL"


def test_a_server_error_fails_and_no_token_reaches_the_receipt() -> None:
    result = _run({"detail": "boom"}, generate_status=500)
    assert result["outcome"] == "FAIL" and "tok" not in json.dumps(result)


def test_the_expected_engine_version_comes_from_the_code() -> None:
    assert check.expected_engine_version() == "1.3.0"
