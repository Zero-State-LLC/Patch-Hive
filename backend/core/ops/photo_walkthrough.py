"""Spec 009 T060a: the staging walkthrough from a photo.

``run_photo_walkthrough`` drives the photo journey over HTTP against any client with httpx-style
``get``/``post`` (``httpx.Client`` for staging, ``TestClient`` in tests). It signs in as the seeded
owner, checks that photo reading is open, uploads the fixture photo with the owner's consent,
confirms its Reading as read (each Module at its closest match), generates, and exports a book
through the Design Engine walkthrough (spec 008). It stops at the first step that fails.

``photo_walkthrough_receipt`` seals what happened: the Reading, the revision, the run and the
export, as ids, counts and hashes only. Tokens and passwords stay in local variables.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from typing import Any, Callable

from core.ops.design_walkthrough import execute_walkthrough
from core.ops.f5_cutover import SeedAccount

SCHEMA = "patchhive.staging-photo-walkthrough.v1"
# Sightings a confirmation has to keep or leave out; the rest are shown only.
DECIDED_KINDS = ("module", "unknown")
# A Reading still being read is asked about again, this often, this many times.
READING_POLL_SECONDS = 2.0
READING_POLLS = 30


def _photo_file(photo: bytes) -> tuple[str, bytes, str]:
    """The photo as uploaded, declaring its own format so the server finds no mismatch."""
    if photo[:4] == b"RIFF" and photo[8:12] == b"WEBP":
        return "rig.webp", photo, "image/webp"
    if photo.startswith(b"\x89PNG\r\n\x1a\n"):
        return "rig.png", photo, "image/png"
    return "rig.jpg", photo, "image/jpeg"


def _json(resp: Any) -> dict[str, Any]:
    try:
        body = resp.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _code(body: dict[str, Any]) -> str | None:
    detail = body.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        code = detail.get("code")
        return str(code) if code else None
    return None


def _reading_summary(reading: dict[str, Any]) -> dict[str, Any]:
    sightings = reading.get("sightings") or []
    decided = [s for s in sightings if s.get("kind") in DECIDED_KINDS]
    return {
        "reading_id": reading.get("reading_id"),
        "photo_id": reading.get("photo_id"),
        "status": reading.get("status"),
        "reason_code": reading.get("reason_code"),
        "provider": reading.get("provider"),
        "provider_version": reading.get("provider_version"),
        "photo_sha256": reading.get("photo_sha256"),
        "policy_version": reading.get("policy_version"),
        "rows": [reading.get("first_row"), reading.get("last_row")],
        "sightings": {
            "count": len(sightings),
            "kinds": dict(Counter(str(s.get("kind")) for s in sightings)),
            "dispositions": dict(Counter(str(s.get("disposition")) for s in decided)),
        },
    }


def _confirmation(sightings: list[dict[str, Any]]) -> dict[str, Any]:
    """Each Module at its closest match and where it was read; one with no match is left out."""
    items: list[dict[str, Any]] = []
    excluded: list[str] = []
    for sighting in sightings:
        if sighting.get("kind") not in DECIDED_KINDS:
            continue
        candidates = sorted(sighting.get("candidates") or [], key=lambda c: -float(c["score"]))
        if not candidates:
            excluded.append(str(sighting["sighting_id"]))
            continue
        items.append(
            {
                "sighting_id": sighting["sighting_id"],
                "module_id": candidates[0]["module_id"],
                "row_index": sighting["row_index"],
                "start_hp": sighting["start_hp"],
            }
        )
    return {"items": items, "added": [], "excluded": excluded, "case_id": None}


def run_photo_walkthrough(
    http: Any,
    *,
    user: SeedAccount,
    admin: SeedAccount,
    photo: bytes,
    rows: str,
    wait: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """The journey from a photo to a book, step by step, stopping at the first that fails."""
    steps: list[dict[str, Any]] = []
    result: dict[str, Any] = {"steps": steps}

    def record(name: str, ok: bool, status: int | None, code: str | None = None) -> bool:
        steps.append({"step": name, "ok": bool(ok), "status": status, "code": code})
        return bool(ok)

    def finish() -> dict[str, Any]:
        result["outcome"] = "PASS" if steps and all(s["ok"] for s in steps) else "FAIL"
        return result

    login = http.post(
        "/api/community/auth/login",
        json={"username": user.username, "password": user.password},
    )
    signed_in = _json(login) if login.status_code == 200 else {}
    token = signed_in.get("access_token")
    if not record("login_user", bool(token), int(login.status_code)):
        return finish()
    headers = {"Authorization": f"Bearer {token}"}

    open_ = http.get("/api/evidence/photo-reading")
    capability = _json(open_)
    if not record(
        "capability",
        open_.status_code == 200 and capability.get("available") is True,
        int(open_.status_code),
        capability.get("reason"),
    ):
        return finish()

    upload = http.post(
        "/api/evidence/rig-photos",
        headers=headers,
        files={"file": _photo_file(photo)},
        data={"rows": rows, "consent_provider_processing": "true"},
    )
    started = _json(upload)
    if not record(
        "photo_start",
        upload.status_code == 201 and {"rig_id", "photo_id", "reading_id"} <= set(started),
        int(upload.status_code),
        _code(started),
    ):
        return finish()
    rig_id = int(started["rig_id"])
    result["rig_id"] = rig_id

    reading: dict[str, Any] | None = None
    for attempt in range(READING_POLLS):
        listed = http.get(f"/api/racks/{rig_id}/evidence/readings", headers=headers)
        reading = next(
            (
                r
                for r in _json(listed).get("readings", [])
                if r.get("reading_id") == started["reading_id"]
            ),
            None,
        )
        if reading is None or reading.get("status") != "reading" or attempt == READING_POLLS - 1:
            break
        wait(READING_POLL_SECONDS)
    if reading is not None:
        result["reading"] = _reading_summary(reading)
    if not record(
        "reading",
        listed.status_code == 200
        and reading is not None
        and reading.get("status") == "read"
        and reading.get("photo_sha256") == hashlib.sha256(photo).hexdigest(),
        int(listed.status_code),
        (reading or {}).get("reason_code"),
    ):
        return finish()

    confirm = http.post(
        f"/api/racks/{rig_id}/evidence/readings/confirm",
        headers=headers,
        json=_confirmation((reading or {}).get("sightings") or []),
    )
    confirmed = _json(confirm)
    result["revision"] = {
        "rig_revision_id": confirmed.get("rig_revision_id"),
        "inventory_revision_id": confirmed.get("inventory_revision_id"),
        "placements": len(confirmed.get("placements") or []),
        "ready_for_generation": confirmed.get("ready_for_generation"),
    }
    if not record(
        "confirm",
        confirm.status_code == 201
        and bool(confirmed.get("rig_revision_id"))
        and confirmed.get("ready_for_generation") is True,
        int(confirm.status_code),
        _code(confirmed),
    ):
        return finish()

    gen = http.post(f"/api/patches/generate/{rig_id}", headers=headers, json={})
    generated = _json(gen)
    result["run"] = {
        "run_id": generated.get("run_id"),
        "rig_revision_id": generated.get("rig_revision_id"),
        "generated_count": int(generated.get("generated_count") or 0),
    }
    # The run must be made from the revision the confirmation made.
    if not record(
        "generate",
        gen.status_code == 200
        and bool(generated.get("run_id"))
        and result["run"]["generated_count"] >= 1
        and generated.get("rig_revision_id") == confirmed.get("rig_revision_id"),
        int(gen.status_code),
        _code(generated),
    ):
        return finish()

    listed_runs = http.get("/api/canon/runs", params={"rig_id": rig_id}, headers=headers)
    run: dict[str, Any] = next(
        (r for r in _json(listed_runs).get("runs", []) if r.get("id") == generated.get("run_id")),
        {},
    )
    # The credit grant names the owner by id, which signing in answered with.
    owner = signed_in.get("user")
    owner_id = owner.get("id") if isinstance(owner, dict) else None
    if not record(
        "export_sources",
        listed_runs.status_code == 200
        and run.get("export_bridge_ready") is True
        and owner_id is not None,
        int(listed_runs.status_code),
    ):
        return finish()
    assert owner_id is not None  # the step above failed otherwise

    _, outcome = execute_walkthrough(
        http,
        user=user,
        admin=admin,
        user_id=int(owner_id),
        sources={
            "source_run_id": str(run["source_run_id"]),
            "source_rig_revision_id": str(run["rig_revision_id"]),
            "artifact_manifest_hash": str(run["artifact_manifest_hash"]),
        },
    )
    # The Design Engine walkthrough's own steps, from sign-in to the downloaded pack.
    for step in outcome.steps:
        record(f"book_{step.name}", step.passed, step.http_status)
    result["export"] = {
        "export_id": outcome.export_id,
        "status": outcome.export_status,
        "pack_manifest_hash": outcome.pack_manifest_hash,
        "composition_hash": outcome.composition_hash,
        "pack_zip_sha256": outcome.pack_zip_sha256,
    }
    return finish()


def _seal(receipt: dict[str, Any]) -> str:
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def photo_walkthrough_receipt(
    result: dict[str, Any], *, api: str, source_commit_sha: str, checked_at: str
) -> dict[str, Any]:
    """The walkthrough's receipt, sealed by ``receipt_sha256`` over every other field."""
    receipt = {
        "schema_version": SCHEMA,
        "api": api,
        "source_commit_sha": source_commit_sha,
        "checked_at": checked_at,
        **result,
    }
    receipt["receipt_sha256"] = _seal(receipt)
    return receipt


def receipt_intact(receipt: dict[str, Any]) -> bool:
    return bool(receipt.get("receipt_sha256")) and receipt["receipt_sha256"] == _seal(receipt)
