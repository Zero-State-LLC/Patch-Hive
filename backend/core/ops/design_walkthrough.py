"""Spec 008 T040: Design Engine walkthrough (debit -> fulfillment -> download pack).

``execute_walkthrough`` drives the HTTP flow against any client exposing
``get``/``post`` with httpx-style responses (``httpx.Client`` for a staging host,
``fastapi.testclient.TestClient`` in tests). It returns a health snapshot and a
hash-only outcome. Tokens and passwords stay in local variables and are never
returned, printed, or logged; pack bytes are reduced to a SHA-256.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Mapping

from core.ops.f5_cutover import HealthSnapshot, SeedAccount, WalkthroughOutcome, WalkthroughStep


def _json(resp: Any) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _unwrap_export(data: Mapping[str, Any]) -> dict[str, Any]:
    if "id" not in data and isinstance(data.get("export"), dict):
        return dict(data["export"])
    return dict(data)


def read_health(http: Any) -> HealthSnapshot:
    resp = http.get("/health/ready")
    body = _json(resp)
    return HealthSnapshot(
        http_status=int(resp.status_code),
        status=str(body.get("status", "")),
        database=str(body.get("database", "")),
    )


def execute_walkthrough(
    http: Any,
    *,
    user: SeedAccount,
    admin: SeedAccount,
    user_id: int,
    sources: Mapping[str, str],
    credits: int = 10,
    idempotency_key: str | None = None,
) -> tuple[HealthSnapshot, WalkthroughOutcome]:
    """Run the walkthrough with seeded credentials only (no credential patching).

    ``sources`` carries ``source_run_id``, ``source_rig_revision_id``, and
    ``artifact_manifest_hash`` from the export bridge. Stops at the first failed
    step; later steps are recorded as not passed.
    """
    steps: list[WalkthroughStep] = []
    result: dict[str, Any] = {}

    def record(name: str, passed: bool, status: int | None) -> bool:
        steps.append(WalkthroughStep(name=name, passed=passed, http_status=status))
        return passed

    def finish(health: HealthSnapshot) -> tuple[HealthSnapshot, WalkthroughOutcome]:
        return health, WalkthroughOutcome(steps=tuple(steps), **result)

    health = read_health(http)
    if not record("health_ready", health.ok, health.http_status):
        return finish(health)

    def login(account: SeedAccount, step: str) -> str | None:
        resp = http.post(
            "/api/community/auth/login",
            json={"username": account.username, "password": account.password},
        )
        token = _json(resp).get("access_token") if resp.status_code == 200 else None
        record(step, bool(token), int(resp.status_code))
        return str(token) if token else None

    user_token = login(user, "login_user")
    if not user_token:
        return finish(health)
    admin_token = login(admin, "login_admin")
    if not admin_token:
        return finish(health)
    user_headers = {"Authorization": f"Bearer {user_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    source_fields = {
        "source_run_id": sources["source_run_id"],
        "source_rig_revision_id": sources["source_rig_revision_id"],
        "artifact_manifest_hash": sources["artifact_manifest_hash"],
    }

    prev = http.post(
        "/api/canon/exports/preview", headers=user_headers, json={**source_fields, "max_pages": 3}
    )
    if not record(
        "preview",
        prev.status_code == 200 and bool(_json(prev).get("style_recipe_hash")),
        int(prev.status_code),
    ):
        return finish(health)

    grant = http.post(
        f"/api/admin/users/{int(user_id)}/credits/grant",
        headers=admin_headers,
        json={"credits": int(credits), "reason": "design-engine-staging-walkthrough"},
    )
    if not record("grant_credits", grant.status_code in (200, 201), int(grant.status_code)):
        return finish(health)

    export_body = {
        **source_fields,
        "formats": ["pdf", "json"],
        "license": "personal",
        "idempotency_key": idempotency_key or f"design-walk-{uuid.uuid4().hex}",
        "style_recipe": {},
    }
    ex = http.post("/api/canon/exports", headers=user_headers, json=export_body)
    export = _unwrap_export(_json(ex))
    export_id = export.get("id") or export.get("export_id")
    if not record("export_debit", ex.status_code in (200, 201) and bool(export_id), int(ex.status_code)):
        return finish(health)
    result["export_id"] = str(export_id)

    status = export.get("status")
    if status != "succeeded":
        polled = http.get(f"/api/canon/exports/{export_id}", headers=user_headers)
        if polled.status_code == 200:
            export = _unwrap_export(_json(polled))
            status = export.get("status")
    result["export_status"] = str(status) if status is not None else None
    result["pack_manifest_hash"] = export.get("pack_manifest_hash")
    result["composition_hash"] = export.get("composition_hash")
    if not record("fulfillment", status == "succeeded", None):
        return finish(health)

    tok = http.post(
        f"/api/canon/exports/{export_id}/download-token",
        headers=user_headers,
        json={"ttl_seconds": 120},
    )
    download_token = _json(tok).get("token") if tok.status_code == 200 else None
    if not record("download_token", bool(download_token), int(tok.status_code)):
        return finish(health)

    pack = http.get(
        f"/api/canon/exports/{export_id}/artifacts/zip",
        headers=user_headers,
        params={"token": download_token},
    )
    content = pack.content if pack.status_code == 200 else b""
    ok = pack.status_code == 200 and len(content) > 0
    if ok:
        result["pack_zip_sha256"] = hashlib.sha256(content).hexdigest()
    record("download_pack", ok, int(pack.status_code))
    return finish(health)


def fetch_all_ids(http: Any, path: str, *, items_key: str, id_field: str, page: int = 1000) -> list[int]:
    """Every id from a paginated ``skip``/``limit`` list endpoint (read-only)."""
    ids: list[int] = []
    skip = 0
    while True:
        resp = http.get(path, params={"skip": skip, "limit": page})
        if resp.status_code != 200:
            raise RuntimeError(f"LIST_FAILED:{path}:{resp.status_code}")
        rows = _json(resp).get(items_key) or []
        ids.extend(int(row[id_field]) for row in rows)
        if len(rows) < page:
            return ids
        skip += page


def collect_live_alias_evidence(http: Any) -> Any:
    """T010 evidence from a running API: OpenAPI route table plus full id sets."""
    from core.ops.f5_cutover import collect_alias_evidence, route_table

    spec = http.get("/openapi.json")
    if spec.status_code != 200:
        raise RuntimeError(f"OPENAPI_UNAVAILABLE:{spec.status_code}")
    return collect_alias_evidence(
        route_table(_json(spec)),
        legacy_ids=fetch_all_ids(http, "/api/racks/", items_key="racks", id_field="id"),
        canon_ids=fetch_all_ids(http, "/api/canon/rigs", items_key="rigs", id_field="rig_id"),
    )
