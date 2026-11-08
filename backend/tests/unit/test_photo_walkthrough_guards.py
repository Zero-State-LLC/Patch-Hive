"""Spec 009 T060a: what the photo walkthrough refuses to call a pass, against a fake API.

The in-process walkthrough (``tests/integration/test_009_photo_walkthrough.py``) runs the real
app, which never reads the wrong photo or generates from another revision. These answers come from
a fake server that does, so the walkthrough's own checks are seen to fail."""

from __future__ import annotations

import hashlib
import json

import httpx

from core.ops.f5_cutover import SeedAccount
from core.ops.photo_walkthrough import run_photo_walkthrough

PHOTO = b"\xff\xd8 a fixture photo \xff\xd9"
USER = SeedAccount("golden_demo", "pw-user", "User")
ADMIN = SeedAccount("admin_demo", "pw-admin", "Admin")


def _server(*, photo_sha256: str, run_revision: str, reading_after: int = 0) -> httpx.Client:
    reading = {
        "reading_id": "read-1",
        "photo_id": "img-1",
        "status": "read",
        "reason_code": None,
        "provider": "recorded",
        "provider_version": "recorded-1",
        "photo_sha256": photo_sha256,
        "policy_version": "decision-policy-v1",
        "first_row": 0,
        "last_row": 0,
        "sightings": [
            {
                "sighting_id": "s-1",
                "kind": "module",
                "row_index": 0,
                "start_hp": 0,
                "hp": 12,
                "candidates": [{"module_id": 7, "score": 0.97}],
                "disposition": "auto_propose",
            }
        ],
    }

    asked = {"readings": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/community/auth/login":
            body = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "access_token": "tok",
                    "user": {"id": 1, "username": body["username"]},
                },
            )
        if path == "/api/evidence/photo-reading":
            return httpx.Response(200, json={"available": True, "reason": None})
        if path == "/api/evidence/rig-photos":
            return httpx.Response(
                201, json={"rig_id": 9, "photo_id": "img-1", "reading_id": "read-1"}
            )
        if path == "/api/racks/9/evidence/readings":
            asked["readings"] += 1
            status = "reading" if asked["readings"] <= reading_after else "read"
            return httpx.Response(200, json={"readings": [{**reading, "status": status}]})
        if path == "/api/racks/9/evidence/readings/confirm":
            return httpx.Response(
                201,
                json={
                    "rig_revision_id": "rig-rev-confirmed",
                    "inventory_revision_id": "inv-rev-1",
                    "ready_for_generation": True,
                    "placements": [{"module_id": 7, "row_index": 0, "start_hp": 0}],
                },
            )
        if path == "/api/patches/generate/9":
            return httpx.Response(
                200,
                json={
                    "run_id": 3,
                    "rig_revision_id": run_revision,
                    "generated_count": 2,
                },
            )
        raise AssertionError(f"the walkthrough should have stopped before {path}")

    return httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api-staging.example"
    )


def _run(waits: list | None = None, **server) -> dict:
    with _server(**server) as http:
        return run_photo_walkthrough(
            http,
            user=USER,
            admin=ADMIN,
            photo=PHOTO,
            rows="0",
            wait=waits.append if waits is not None else (lambda _: None),
        )


def test_a_reading_of_another_photo_is_not_a_pass() -> None:
    result = _run(photo_sha256="0" * 64, run_revision="rig-rev-confirmed")

    assert result["outcome"] == "FAIL"
    assert [s["step"] for s in result["steps"]][-1] == "reading"


def test_a_run_from_another_revision_is_not_a_pass() -> None:
    result = _run(photo_sha256=hashlib.sha256(PHOTO).hexdigest(), run_revision="rig-rev-other")

    assert result["outcome"] == "FAIL"
    assert result["steps"][-1]["step"] == "generate"
    assert result["run"]["rig_revision_id"] == "rig-rev-other"


def test_a_reading_still_being_read_is_waited_for() -> None:
    from core.ops.photo_walkthrough import READING_POLL_SECONDS

    waits: list = []
    result = _run(
        waits,
        photo_sha256=hashlib.sha256(PHOTO).hexdigest(),
        run_revision="rig-rev-other",
        reading_after=2,
    )

    # It read on the third look, and the walkthrough went on to confirm and generate.
    assert waits == [READING_POLL_SECONDS, READING_POLL_SECONDS]
    assert result["reading"]["status"] == "read"
    assert result["steps"][-1]["step"] == "generate"


def test_a_reading_that_never_finishes_fails_after_a_bounded_wait() -> None:
    from core.ops.photo_walkthrough import READING_POLLS

    waits: list = []
    result = _run(
        waits,
        photo_sha256=hashlib.sha256(PHOTO).hexdigest(),
        run_revision="rig-rev-confirmed",
        reading_after=10_000,
    )

    assert len(waits) == READING_POLLS - 1
    assert result["outcome"] == "FAIL" and result["steps"][-1]["step"] == "reading"
