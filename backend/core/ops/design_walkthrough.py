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
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping

from core.ops.f5_cutover import (
    RUNTIME_FLAGS_ROUTE,
    STAGING_ENVIRONMENT,
    AliasParityEvidence,
    CutoverError,
    DesignEngineFlags,
    FeCutoverEvidence,
    HealthSnapshot,
    SeedAccount,
    SeedAuthCheck,
    WalkthroughOutcome,
    WalkthroughReceipt,
    WalkthroughStart,
    WalkthroughStep,
    alias_evidence_failures,
    capture_walkthrough_receipt,
    collect_fe_cutover_evidence,
    flags_from_server_payload,
    flags_test_mode_failures,
    route_table,
    start_walkthrough,
)


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


def fetch_all_ids(
    http: Any,
    path: str,
    *,
    items_key: str,
    id_field: str,
    page: int = 1000,
    headers: Mapping[str, str] | None = None,
) -> list[int]:
    """Every id from a paginated ``skip``/``limit`` list endpoint (read-only)."""
    ids: list[int] = []
    skip = 0
    while True:
        resp = http.get(path, params={"skip": skip, "limit": page}, headers=dict(headers or {}))
        if resp.status_code != 200:
            raise RuntimeError(f"LIST_FAILED:{path}:{resp.status_code}")
        rows = _json(resp).get(items_key) or []
        ids.extend(int(row[id_field]) for row in rows)
        if len(rows) < page:
            return ids
        skip += page


def login_headers(http: Any, account: SeedAccount, *, error_code: str) -> dict[str, str]:
    """Bearer header for a seeded account. The token never leaves the returned header."""
    resp = http.post(
        "/api/community/auth/login",
        json={"username": account.username, "password": account.password},
    )
    token = _json(resp).get("access_token") if resp.status_code == 200 else None
    if not token:
        raise CutoverError(error_code, f"login http {resp.status_code}")
    return {"Authorization": f"Bearer {token}"}


def collect_live_alias_evidence(
    http: Any, *, headers: Mapping[str, str] | None = None
) -> AliasParityEvidence:
    """T010 evidence from a running API: OpenAPI route table plus full id sets.

    Racks are owner-scoped, so the full id sets need an admin (read-all) header.
    """
    from core.ops.f5_cutover import collect_alias_evidence

    spec = http.get("/openapi.json")
    if spec.status_code != 200:
        raise RuntimeError(f"OPENAPI_UNAVAILABLE:{spec.status_code}")
    return collect_alias_evidence(
        route_table(_json(spec)),
        legacy_ids=fetch_all_ids(http, "/api/racks/", items_key="racks", id_field="id", headers=headers),
        canon_ids=fetch_all_ids(http, "/api/canon/rigs", items_key="rigs", id_field="rig_id", headers=headers),
    )


def fetch_server_flags(http: Any, *, admin: SeedAccount) -> DesignEngineFlags:
    """Effective flags reported by the TARGET server (not a local overlay).

    Logs in with the seeded admin and reads ``RUNTIME_FLAGS_ROUTE``. Any failure
    to obtain an unambiguous answer raises ``SERVER_FLAGS_UNVERIFIABLE``. The
    token stays in this function and is never returned or logged.
    """
    login = http.post(
        "/api/community/auth/login",
        json={"username": admin.username, "password": admin.password},
    )
    token = _json(login).get("access_token") if login.status_code == 200 else None
    if not token:
        raise CutoverError("SERVER_FLAGS_UNVERIFIABLE", f"admin login http {login.status_code}")
    resp = http.get(RUNTIME_FLAGS_ROUTE[1], headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        raise CutoverError("SERVER_FLAGS_UNVERIFIABLE", f"runtime flags http {resp.status_code}")
    try:
        payload = resp.json()
    except ValueError:
        payload = None
    return flags_from_server_payload(payload)


def verify_server_flags(
    http: Any, *, admin: SeedAccount, expected_environment: Literal["staging"]
) -> DesignEngineFlags:
    """Server flags that are verified test-mode with production payments disabled.

    The server must report exactly ``staging`` (spec 008 R2). ``expected_environment``
    is required; any other value, including a missing one, is refused before any
    request is made.
    """
    if expected_environment != STAGING_ENVIRONMENT:
        raise CutoverError("EXPECTED_ENVIRONMENT_NOT_STAGING", str(expected_environment))
    flags = fetch_server_flags(http, admin=admin)
    failed = flags_test_mode_failures(flags)
    blocking = [code for code in failed if code != "SERVER_ENVIRONMENT_NOT_STAGING"]
    if blocking:
        raise CutoverError("FLAGS_NOT_TEST_MODE", ",".join(failed))
    if failed:
        raise CutoverError("SERVER_ENVIRONMENT_NOT_STAGING", flags.environment)
    return flags


@dataclass(frozen=True)
class StagingWalkthroughRun:
    """Every record produced by one successful staging walkthrough (no secrets)."""

    alias: AliasParityEvidence
    fe_cutover: FeCutoverEvidence
    start: WalkthroughStart
    seed_auth: SeedAuthCheck
    receipt: WalkthroughReceipt

    def bundle(self) -> dict[str, Any]:
        return {
            "alias_evidence": self.alias.model_dump(mode="json"),
            "fe_cutover": self.fe_cutover.model_dump(mode="json"),
            "flags_source": f"{RUNTIME_FLAGS_ROUTE[0]} {RUNTIME_FLAGS_ROUTE[1]}",
            "walkthrough_start": self.start.model_dump(mode="json"),
            "seed_auth": self.seed_auth.model_dump(mode="json"),
            "receipt": self.receipt.model_dump(mode="json"),
        }


def run_staging_walkthrough(
    http: Any,
    *,
    seed_auth: SeedAuthCheck,
    user: SeedAccount,
    admin: SeedAccount,
    user_id: int,
    rig_id: int,
    sources: Mapping[str, str],
    fe_sources: Mapping[str, str],
    source_commit_sha: str,
    expected_environment: Literal["staging"],
    log: Callable[[str], None] = lambda _message: None,
) -> StagingWalkthroughRun:
    """Spec 008 live walkthrough with every gate enforced before side effects.

    Order: alias evidence must pass the same checks as the expose_canon_alias
    guard; the target server's effective flags must be verified (test mode,
    production payments disabled); only then are generate/export calls made.
    The flags are re-read after the walkthrough and must be unchanged before
    the receipt is sealed. Any failure raises ``CutoverError`` and no receipt
    is produced.
    """
    log("=== F5 alias evidence ===")
    admin_headers = login_headers(http, admin, error_code="ALIAS_EVIDENCE_UNVERIFIABLE")
    alias = collect_live_alias_evidence(http, headers=admin_headers)
    log(f"  same_set={alias.same_set} new_write_surface={list(alias.new_write_surface)}")
    alias_failed = alias_evidence_failures(alias)
    if alias_failed:
        raise CutoverError("ALIAS_EVIDENCE_REJECTED", ",".join(alias_failed))

    log("=== Target server effective flags ===")
    flags = verify_server_flags(http, admin=admin, expected_environment=expected_environment)
    log(
        f"  environment={flags.environment} stripe_test_mode={flags.stripe_test_mode} "
        f"allow_production_payments={flags.allow_production_payments}"
    )

    log("=== FE cutover evidence (generate dual-write audit) ===")
    # The seeded user owns the rig, so generation runs as that user.
    user_headers = login_headers(http, user, error_code="SEED_USER_LOGIN_FAILED")
    gen = http.post(f"/api/patches/generate/{rig_id}", json={}, headers=user_headers)
    spec = http.get("/openapi.json")
    if spec.status_code != 200:
        raise CutoverError("OPENAPI_UNAVAILABLE", str(spec.status_code))
    fe = collect_fe_cutover_evidence(
        alias,
        route_table(_json(spec)),
        fe_sources=fe_sources,
        generate_response=_json(gen) if gen.status_code == 200 else {},
    )
    log(f"  dual_write_passed={fe.dual_write.passed} legacy_list_callers={list(fe.legacy_list_callers)}")
    start = start_walkthrough(fe, flags)

    log("=== Walkthrough: preview -> debit -> fulfillment -> download pack ===")
    health, outcome = execute_walkthrough(
        http, user=user, admin=admin, user_id=user_id, sources=sources
    )
    for step in outcome.steps:
        log(f"  {step.name}: {'PASS' if step.passed else 'FAIL'} ({step.http_status})")

    after = verify_server_flags(http, admin=admin, expected_environment=expected_environment)
    if after != flags:
        raise CutoverError("SERVER_FLAGS_CHANGED")

    receipt = capture_walkthrough_receipt(
        start=start,
        seed_auth=seed_auth,
        health=health,
        outcome=outcome,
        source_commit_sha=source_commit_sha,
    )
    return StagingWalkthroughRun(
        alias=alias, fe_cutover=fe, start=start, seed_auth=seed_auth, receipt=receipt
    )
