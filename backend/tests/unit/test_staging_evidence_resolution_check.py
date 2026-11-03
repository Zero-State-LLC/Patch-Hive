"""Offline tests for scripts/staging/evidence_resolution_check.py (fake API, no network)."""

from __future__ import annotations

import json
import sys
import zlib
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]
_spec = spec_from_file_location(
    "evidence_resolution_check", ROOT / "scripts" / "staging" / "evidence_resolution_check.py"
)
assert _spec and _spec.loader
check = module_from_spec(_spec)
sys.modules["evidence_resolution_check"] = check
_spec.loader.exec_module(check)


def _api(
    resolution: tuple[int, object],
    *,
    candidates: list[dict] | None = None,
    upload_rejected: bool = False,
):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path == "/api/community/auth/login":
            body = json.loads(request.content)
            if body["password"] != "pw-for-tests-only":
                return httpx.Response(401, json={"detail": "Invalid credentials"})
            return httpx.Response(200, json={"access_token": "tok"})
        assert request.headers["authorization"] == "Bearer tok"
        if path == "/api/racks/":
            assert request.url.params["is_public"] == "false"
            return httpx.Response(200, json={"total": 1, "racks": [{"id": 7}]})
        if path == "/api/racks/7/evidence/images":
            assert b'name="consent_provider_processing"' in request.content
            assert b"\x89PNG" in request.content
            if upload_rejected:
                return httpx.Response(
                    201,
                    json={"uploaded": [], "rejected": [{"reason": "IMAGE_DIMENSIONS_TOO_SMALL"}]},
                )
            return httpx.Response(201, json={"uploaded": [{"id": "asset-new"}], "rejected": []})
        if path == "/api/racks/7/evidence/candidates":
            items = (
                candidates
                if candidates is not None
                else [
                    {"evidence_id": "ev-old", "image_asset_id": "asset-old"},
                    {"evidence_id": "ev-abc", "image_asset_id": "asset-new"},
                ]
            )
            return httpx.Response(200, json={"total": len(items), "candidates": items})
        if path == "/api/racks/7/evidence/decision-resolution":
            body = json.loads(request.content)
            assert body["evidence_id"] == "ev-abc" and body["idempotency_key"].startswith("t060b-")
            status, payload = resolution
            return httpx.Response(status, json=payload)
        return httpx.Response(404)

    return httpx.Client(
        base_url="https://api-staging.example", transport=httpx.MockTransport(handler)
    ), seen


def test_the_default_card_clears_the_intake_size_gate() -> None:
    png = check.test_card_png()
    width, height = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
    assert width >= 64 and height >= 64
    assert check.test_card_png(shade=1) != check.test_card_png(shade=2)


def test_the_test_card_is_a_valid_png() -> None:
    png = check.test_card_png(4, 3)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    idat = png.index(b"IDAT")
    length = int.from_bytes(png[idat - 4 : idat], "big")
    assert len(zlib.decompress(png[idat + 4 : idat + 4 + length])) == 3 * (1 + 4 * 3)


@pytest.mark.parametrize(
    "resolution",
    [
        (409, {"detail": "DECISION_INTELLIGENCE_DISABLED"}),
        (409, {"detail": {"code": "ENABLEMENT_RECEIPT_REQUIRED", "failures": ["x"]}}),
        (200, {"disposition": "ESCALATE", "selected_choice": None}),
    ],
)
def test_a_fail_closed_or_answered_resolution_passes(resolution) -> None:
    http, seen = _api(resolution)
    result = check.run_check(http, "golden_demo", "pw-for-tests-only")
    assert result["outcome"] == "PASS", result["steps"]
    assert result["evidence_id"] == "ev-abc" and result["rack_id"] == 7
    assert [s["step"] for s in result["steps"]][-1] == "idempotent_replay"
    assert sum(1 for r in seen if r.url.path.endswith("decision-resolution")) == 2


@pytest.mark.parametrize(
    "resolution",
    [(404, {"detail": "Evidence record not found"}), (502, {"detail": "CLEF_UNAVAILABLE"})],
)
def test_a_missing_evidence_or_provider_error_fails(resolution) -> None:
    http, _ = _api(resolution)
    assert check.run_check(http, "golden_demo", "pw-for-tests-only")["outcome"] == "FAIL"


def test_a_wrong_password_stops_before_any_upload() -> None:
    http, seen = _api((409, {"detail": "DECISION_INTELLIGENCE_DISABLED"}))
    result = check.run_check(http, "golden_demo", "wrong")
    assert result["outcome"] == "FAIL" and len(seen) == 1


def test_a_rejected_upload_fails_before_resolution() -> None:
    http, seen = _api((409, {"detail": "DECISION_INTELLIGENCE_DISABLED"}), upload_rejected=True)
    result = check.run_check(http, "golden_demo", "pw-for-tests-only")
    assert result["outcome"] == "FAIL"
    assert result["steps"][-1]["rejected"] == ["IMAGE_DIMENSIONS_TOO_SMALL"]
    assert not any(r.url.path.endswith("decision-resolution") for r in seen)


def test_older_evidence_on_the_rack_is_never_resolved() -> None:
    http, _ = _api(
        (409, {"detail": "DECISION_INTELLIGENCE_DISABLED"}),
        candidates=[{"evidence_id": "ev-old", "image_asset_id": "asset-old"}],
    )
    assert check.run_check(http, "golden_demo", "pw-for-tests-only")["outcome"] == "FAIL"


def test_no_candidates_fails() -> None:
    http, _ = _api((200, {}), candidates=[])
    assert check.run_check(http, "golden_demo", "pw-for-tests-only")["outcome"] == "FAIL"


def test_main_refuses_a_non_staging_api(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STAGING_API_URL", "https://api.patch-hive.com")
    monkeypatch.setenv("PATCHHIVE_DEMO_USER_PASSWORD", "pw-for-tests-only")
    assert check.main(["--receipt-out", str(tmp_path / "r.json")]) == 2
    assert not (tmp_path / "r.json").exists()
