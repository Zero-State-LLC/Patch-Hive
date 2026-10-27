"""Spec 008 T010-T040 against the real app (in-process, SQLite, synthetic seed).

The golden demo seed is synthetic fixture data. No staging host is contacted;
the operator re-runs scripts/staging/design_engine_walkthrough.py on staging
(see specs/008-dual-path-f5-design-receipts/OPERATOR_NOTES.md).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from community.models import User
from core.config import settings
from core.database import get_db
from canon.models import CanonicalExportRecord
from core.ops.design_walkthrough import (
    collect_live_alias_evidence,
    execute_walkthrough,
    run_staging_walkthrough,
)
from core.ops.f5_cutover import (
    RUNTIME_FLAGS_ROUTE,
    RUNTIME_FLAGS_SCHEMA,
    CutoverError,
    CutoverEvent,
    CutoverEventType,
    CutoverState,
    DesignEngineFlags,
    SeedAccount,
    beta_eligible,
    capture_walkthrough_receipt,
    check_seed_auth,
    collect_fe_cutover_evidence,
    flags_from_server_payload,
    pin_readiness_docs,
    replay,
    route_table,
    scan_fe_list_callers,
    start_walkthrough,
)
from core.security import get_password_hash
from main import app
from runs.bridge import ensure_legacy_run_export_bridge
from runs.models import Run
from tests.f5008_helpers import WALKTHROUGH_SHA, docs, enablement_receipt

REPO = Path(__file__).resolve().parents[3]
FE_PAGES = REPO / "frontend" / "src" / "pages"
FE_LIST_PAGES = ("frontend/src/pages/Racks.tsx", "frontend/src/pages/Modules.tsx")
E = CutoverEventType


def _seed_module():
    spec = importlib.util.spec_from_file_location("seed_golden_demo_008", REPO / "scripts" / "seed_golden_demo.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod  # dataclasses resolve their module at class creation
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def design_flags(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "enable_patchbook_design_engine", True)
    monkeypatch.setattr(settings, "enable_canon_export_fulfillment", True)
    monkeypatch.setattr(settings, "enable_inline_export_fulfillment", True)
    monkeypatch.setattr(settings, "export_store_root", str(tmp_path))
    monkeypatch.setattr(settings, "export_dir", str(tmp_path))
    monkeypatch.setattr(settings, "download_token_secret", "x" * 40)
    monkeypatch.setattr(settings, "stripe_test_mode", True)
    monkeypatch.setattr(settings, "allow_production_payments", False)
    monkeypatch.setattr(settings, "environment", "staging")
    return settings


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def seeded(db_session: Session):
    mod = _seed_module()
    result = mod.seed_golden_demo(db_session)
    user = SeedAccount(result.username, result.password, mod.DEMO_USER_ROLE)
    admin = SeedAccount(result.admin_username, result.admin_password, mod.DEMO_ADMIN_ROLE)
    return result, user, admin


def _fe_sources() -> dict[str, str]:
    return {page: (REPO / page).read_text(encoding="utf-8") for page in FE_LIST_PAGES}


# --- T010 -------------------------------------------------------------------


def test_live_alias_matches_legacy_and_adds_no_write_surface(client, seeded) -> None:
    alias = collect_live_alias_evidence(client)
    assert alias.intact()
    assert alias.missing_alias_routes == ()
    assert alias.same_set is True
    assert alias.rig_count >= 1
    assert alias.new_write_surface == ()
    assert alias.canon_write_routes  # the F4 dual-mounted evidence writers exist


# --- T020 -------------------------------------------------------------------


def test_active_fe_list_pages_use_canon_alias_only() -> None:
    sources = {
        str(path.relative_to(REPO)): path.read_text(encoding="utf-8")
        for path in sorted(FE_PAGES.rglob("*.tsx"))
    }
    legacy, canon = scan_fe_list_callers(sources)
    assert legacy == ()
    assert set(FE_LIST_PAGES) <= set(canon)


def test_generate_keeps_dual_write_and_gates(client, seeded) -> None:
    result, _, _ = seeded
    alias = collect_live_alias_evidence(client)
    gen = client.post(f"/api/patches/generate/{result.rig_id}", json={})
    assert gen.status_code == 200
    fe = collect_fe_cutover_evidence(
        alias,
        route_table(app.openapi()),
        fe_sources=_fe_sources(),
        generate_response=gen.json(),
    )
    assert fe.dual_write.passed, fe.dual_write.failures
    assert fe.missing_gate_routes == ()
    assert fe.legacy_list_callers == ()


# --- T030 -------------------------------------------------------------------


def test_seeded_credentials_are_aligned_without_patching(db_session, seeded) -> None:
    _, user, admin = seeded
    before = {u.username: u.password_hash for u in db_session.query(User).all()}
    check = check_seed_auth(db_session, (user, admin))
    after = {u.username: u.password_hash for u in db_session.query(User).all()}
    assert check.aligned and check.intact()
    assert before == after  # read-only


def test_seed_auth_detects_drift(db_session, seeded) -> None:
    _, user, admin = seeded
    row = db_session.query(User).filter(User.username == admin.username).one()
    row.password_hash = get_password_hash("something-else")
    db_session.commit()
    check = check_seed_auth(db_session, (user, admin))
    assert not check.aligned
    status = {s.username: s for s in check.accounts}
    assert status[admin.username].exists and not status[admin.username].password_matches
    missing = check_seed_auth(db_session, (SeedAccount("nobody", "x", "User"),))
    assert not missing.aligned and not missing.accounts[0].exists


def test_seed_is_idempotent_and_restores_seeded_credentials(db_session, seeded) -> None:
    _, user, admin = seeded
    row = db_session.query(User).filter(User.username == admin.username).one()
    row.password_hash = get_password_hash("drifted")
    db_session.commit()
    _seed_module().seed_golden_demo(db_session)
    assert check_seed_auth(db_session, (user, admin)).aligned


# --- T040 / T050 / machine ---------------------------------------------------


def _bridge_sources(db_session, run_id: int) -> dict[str, str]:
    run = db_session.get(Run, run_id)
    bridge = ensure_legacy_run_export_bridge(db_session, run)
    db_session.commit()
    return bridge.as_export_body_fields()


def test_in_process_walkthrough_receipt_reaches_beta_eligible(
    db_session, client, seeded, design_flags
) -> None:
    result, user, admin = seeded
    alias = collect_live_alias_evidence(client)
    gen = client.post(f"/api/patches/generate/{result.rig_id}", json={})
    fe = collect_fe_cutover_evidence(
        alias, route_table(app.openapi()), fe_sources=_fe_sources(), generate_response=gen.json()
    )
    start = start_walkthrough(fe, DesignEngineFlags.from_settings(design_flags))
    seed_auth = check_seed_auth(db_session, (user, admin))
    health, outcome = execute_walkthrough(
        client, user=user, admin=admin, user_id=result.user_id,
        sources=_bridge_sources(db_session, result.run_id),
    )
    assert [s.name for s in outcome.steps if not s.passed] == []
    assert outcome.passed and health.ok
    receipt = capture_walkthrough_receipt(
        start=start, seed_auth=seed_auth, health=health, outcome=outcome,
        source_commit_sha=WALKTHROUGH_SHA,
    )
    text = json.dumps(receipt.model_dump(mode="json"))
    for forbidden in (user.password, admin.password, "access_token", "Bearer ", "PK\\u0003"):
        assert forbidden not in text

    pin = pin_readiness_docs(
        receipt=receipt, documents=docs(), unresolved_p0=(),
        enablement_receipt=enablement_receipt(), pinned_by="operator-1",
    )
    machine = replay(
        [
            CutoverEvent(E.EXPOSE_CANON_ALIAS, alias=alias),
            CutoverEvent(E.SWITCH_FE_LIST, fe_cutover=fe),
            CutoverEvent(E.RUN_WALKTHROUGH, start=start),
            CutoverEvent(E.CAPTURE_RECEIPT, receipt=receipt),
            CutoverEvent(E.OPERATOR_PIN, pin=pin),
        ]
    )
    assert machine.state is CutoverState.BETA_ELIGIBLE, machine.history[-1].reasons
    assert beta_eligible(machine)
    assert settings.allow_production_payments is False


def test_design_engine_flag_off_blocks_walkthrough_start(client, seeded, design_flags, monkeypatch) -> None:
    result, _, _ = seeded
    monkeypatch.setattr(settings, "enable_patchbook_design_engine", False)
    alias = collect_live_alias_evidence(client)
    gen = client.post(f"/api/patches/generate/{result.rig_id}", json={})
    fe = collect_fe_cutover_evidence(
        alias, route_table(app.openapi()), fe_sources=_fe_sources(), generate_response=gen.json()
    )
    with pytest.raises(CutoverError) as exc:
        start_walkthrough(fe, DesignEngineFlags.from_settings(settings))
    assert exc.value.code == "FLAGS_NOT_TEST_MODE"
    assert "DESIGN_ENGINE_FLAG_OFF" in exc.value.detail


def test_walkthrough_with_wrong_password_fails_closed(db_session, client, seeded, design_flags) -> None:
    result, user, admin = seeded
    wrong_admin = SeedAccount(admin.username, "patched-by-hand", admin.role)
    health, outcome = execute_walkthrough(
        client, user=user, admin=wrong_admin, user_id=result.user_id,
        sources=_bridge_sources(db_session, result.run_id),
    )
    assert health.ok
    assert not outcome.passed
    assert [s.name for s in outcome.steps][-1] == "login_admin"
    assert outcome.steps[-1].passed is False


# --- repo artifacts ------------------------------------------------------------


def test_repo_readiness_docs_are_not_pinned_to_an_invented_sha() -> None:
    from core.ops.f5_cutover import REQUIRED_PIN_DOCUMENTS

    documents = {path: (REPO / path).read_text(encoding="utf-8") for path in REQUIRED_PIN_DOCUMENTS}
    for text in documents.values():
        assert "PENDING_OPERATOR_WALKTHROUGH" in text
        assert WALKTHROUGH_SHA not in text
    from tests.f5008_helpers import chain

    art = chain()
    with pytest.raises(CutoverError) as exc:
        pin_readiness_docs(
            receipt=art["receipt"], documents=documents, unresolved_p0=(),
            enablement_receipt=enablement_receipt(), pinned_by="operator-1",
        )
    assert exc.value.code == "DOCUMENT_NOT_PINNED_TO_SHA"


def _walkthrough_script():
    path = REPO / "scripts" / "staging" / "design_engine_walkthrough.py"
    spec = importlib.util.spec_from_file_location("design_engine_walkthrough_008", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod, path.read_text(encoding="utf-8")


def test_staging_script_trusts_server_flags_not_overlay_and_does_not_patch_credentials() -> None:
    mod, source = _walkthrough_script()
    assert not hasattr(mod, "_overlay_flags")
    assert "docker-compose.staging.design-engine.yml" not in source
    assert "run_staging_walkthrough" in source
    assert "get_password_hash" not in source
    assert "password_hash" not in source


# --- Codex review: effective server flags, alias guard ------------------------


class _Resp:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _ServerFlagsOverride:
    """Real app client, except the runtime-flags route answers with ``responses``."""

    def __init__(self, inner, responses) -> None:
        self._inner = inner
        self._responses = list(responses)
        self.flag_reads = 0

    def get(self, path, **kwargs):
        if path == RUNTIME_FLAGS_ROUTE[1]:
            self.flag_reads += 1
            resp = self._responses[min(self.flag_reads, len(self._responses)) - 1]
            return resp(kwargs) if callable(resp) else resp
        return self._inner.get(path, **kwargs)

    def post(self, path, **kwargs):
        return self._inner.post(path, **kwargs)


def _side_effect_counts(db_session) -> tuple[int, int]:
    db_session.expire_all()
    return (
        db_session.query(Run).count(),
        db_session.query(CanonicalExportRecord).count(),
    )


def _run(db_session, http, seeded, **kwargs):
    result, user, admin = seeded
    return run_staging_walkthrough(
        http,
        seed_auth=check_seed_auth(db_session, (user, admin)),
        user=user,
        admin=admin,
        user_id=result.user_id,
        rig_id=result.rig_id,
        sources=_bridge_sources(db_session, result.run_id),
        fe_sources=_fe_sources(),
        source_commit_sha=WALKTHROUGH_SHA,
        **kwargs,
    )


def test_runtime_flags_endpoint_is_admin_only_read_only_and_secret_free(
    client, seeded, design_flags
) -> None:
    _, user, admin = seeded
    assert client.get(RUNTIME_FLAGS_ROUTE[1]).status_code in (401, 403)

    def token(account):
        resp = client.post(
            "/api/community/auth/login",
            json={"username": account.username, "password": account.password},
        )
        return resp.json()["access_token"]

    as_user = client.get(RUNTIME_FLAGS_ROUTE[1], headers={"Authorization": f"Bearer {token(user)}"})
    assert as_user.status_code == 403
    resp = client.get(RUNTIME_FLAGS_ROUTE[1], headers={"Authorization": f"Bearer {token(admin)}"})
    assert resp.status_code == 200
    flags = flags_from_server_payload(resp.json())
    assert flags == DesignEngineFlags.from_settings(settings)
    assert flags.allow_production_payments is False and flags.stripe_test_mode is True
    assert set(resp.json()) == {"schema_version", *DesignEngineFlags.model_fields}
    assert settings.download_token_secret not in resp.text
    assert ("GET", RUNTIME_FLAGS_ROUTE[1]) in route_table(app.openapi())
    assert not any(
        path == RUNTIME_FLAGS_ROUTE[1] and method != "GET" for method, path in route_table(app.openapi())
    )


def test_verified_payments_disabled_server_proceeds_and_receipt_carries_server_flags(
    db_session, client, seeded, design_flags
) -> None:
    before = _side_effect_counts(db_session)
    run = _run(db_session, client, seeded, expected_environment="staging")
    after = _side_effect_counts(db_session)
    # The counters used by the refusal tests do move on a real run.
    assert after[0] > before[0] and after[1] > before[1]
    server = DesignEngineFlags.from_settings(settings)
    assert run.receipt.intact() and run.receipt.outcome_passed
    assert run.receipt.flags == server == run.start.flags
    assert run.receipt.flags.allow_production_payments is False
    bundle = json.dumps(run.bundle())
    assert "/api/admin/ops/runtime-flags" in bundle
    _, user, admin = seeded
    for forbidden in (user.password, admin.password, "access_token", "Bearer "):
        assert forbidden not in bundle


def test_server_reporting_live_production_payments_aborts_before_side_effects(
    db_session, client, seeded, design_flags, monkeypatch
) -> None:
    _run(db_session, client, seeded)  # warm the bridge so counts are stable
    before = _side_effect_counts(db_session)
    monkeypatch.setattr(settings, "allow_production_payments", True)
    monkeypatch.setattr(settings, "stripe_test_mode", False)
    with pytest.raises(CutoverError) as exc:
        _run(db_session, client, seeded)
    assert exc.value.code == "FLAGS_NOT_TEST_MODE"
    assert "PRODUCTION_PAYMENTS_ENABLED" in exc.value.detail
    assert "PAYMENTS_NOT_TEST_MODE" in exc.value.detail
    assert _side_effect_counts(db_session) == before  # no generate, no export


def test_production_environment_server_aborts(db_session, client, seeded, design_flags, monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    with pytest.raises(CutoverError) as exc:
        _run(db_session, client, seeded)
    assert exc.value.code == "FLAGS_NOT_TEST_MODE"
    assert "PRODUCTION_ENVIRONMENT" in exc.value.detail


def test_server_environment_must_match_expected(db_session, client, seeded, design_flags) -> None:
    with pytest.raises(CutoverError) as exc:
        _run(db_session, client, seeded, expected_environment="qa")
    assert exc.value.code == "SERVER_ENVIRONMENT_MISMATCH"


_GOOD_PAYLOAD = {
    "schema_version": RUNTIME_FLAGS_SCHEMA,
    "environment": "staging",
    "enable_patchbook_design_engine": True,
    "enable_canon_export_fulfillment": True,
    "enable_inline_export_fulfillment": True,
    "enable_patchbook_publication_profile": False,
    "stripe_test_mode": True,
    "allow_production_payments": False,
}


def _without(key: str) -> dict:
    return {k: v for k, v in _GOOD_PAYLOAD.items() if k != key}


@pytest.mark.parametrize(
    "response",
    [
        _Resp(404, {"detail": "Not Found"}),  # server predates the endpoint
        _Resp(500, {}),
        _Resp(200, ValueError("not json")),
        _Resp(200, []),
        _Resp(200, _without("allow_production_payments")),
        _Resp(200, _without("stripe_test_mode")),
        _Resp(200, {**_GOOD_PAYLOAD, "allow_production_payments": "false"}),
        _Resp(200, {**_GOOD_PAYLOAD, "allow_production_payments": None}),
        _Resp(200, {**_GOOD_PAYLOAD, "stripe_test_mode": 1}),
        _Resp(200, {**_GOOD_PAYLOAD, "environment": ""}),
        _Resp(200, {**_GOOD_PAYLOAD, "schema_version": "other"}),
        _Resp(200, {**_GOOD_PAYLOAD, "payments_live": False}),
    ],
)
def test_missing_or_ambiguous_server_flags_fail_closed(
    db_session, client, seeded, design_flags, response
) -> None:
    http = _ServerFlagsOverride(client, [response])
    _run(db_session, client, seeded)  # warm the bridge so counts are stable
    before = _side_effect_counts(db_session)
    with pytest.raises(CutoverError) as exc:
        _run(db_session, http, seeded)
    assert exc.value.code == "SERVER_FLAGS_UNVERIFIABLE"
    assert _side_effect_counts(db_session) == before


def test_server_flags_changed_during_walkthrough_refuses_to_seal(
    db_session, client, seeded, design_flags
) -> None:
    flipped = {**_GOOD_PAYLOAD, "enable_patchbook_publication_profile": True}
    http = _ServerFlagsOverride(client, [_Resp(200, _GOOD_PAYLOAD), _Resp(200, flipped)])
    with pytest.raises(CutoverError) as exc:
        _run(db_session, http, seeded)
    assert exc.value.code == "SERVER_FLAGS_CHANGED"
    assert http.flag_reads == 2


def test_server_flags_flipped_to_live_payments_mid_run_refuses_to_seal(
    db_session, client, seeded, design_flags
) -> None:
    live = {**_GOOD_PAYLOAD, "allow_production_payments": True}
    http = _ServerFlagsOverride(client, [_Resp(200, _GOOD_PAYLOAD), _Resp(200, live)])
    with pytest.raises(CutoverError) as exc:
        _run(db_session, http, seeded)
    assert exc.value.code == "FLAGS_NOT_TEST_MODE"


def _reject_alias(monkeypatch, **changes) -> None:
    from core.ops import design_walkthrough

    real = design_walkthrough.collect_live_alias_evidence

    def tampered(http):
        alias = real(http)
        return alias.model_copy(update={**changes, "record_sha256": ""}).sealed()

    monkeypatch.setattr(design_walkthrough, "collect_live_alias_evidence", tampered)


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"new_write_surface": ("POST /api/canon/rigs/{rig_id}/clone",)}, "NEW_WRITE_SURFACE"),
        ({"same_set": False}, "ALIAS_SET_DIFFERS_FROM_LEGACY"),
        ({"missing_alias_routes": ("GET /api/canon/rigs",)}, "F2_F4_ALIASES_MISSING"),
    ],
)
def test_failed_alias_evidence_aborts_before_side_effects(
    db_session, client, seeded, design_flags, monkeypatch, changes, reason
) -> None:
    _run(db_session, client, seeded)  # warm the bridge so counts are stable
    before = _side_effect_counts(db_session)
    _reject_alias(monkeypatch, **changes)
    with pytest.raises(CutoverError) as exc:
        _run(db_session, client, seeded)
    assert exc.value.code == "ALIAS_EVIDENCE_REJECTED"
    assert reason in exc.value.detail
    assert _side_effect_counts(db_session) == before


# --- the script end to end (no PASS / no receipt on any refusal) --------------


def _run_script(monkeypatch, tmp_path, db_engine, http):
    from types import SimpleNamespace

    mod, _ = _walkthrough_script()
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(mod, "create_engine", lambda _url: db_engine)
    monkeypatch.setattr(mod, "httpx", SimpleNamespace(Client=lambda **_kw: http))
    monkeypatch.setenv("WALKTHROUGH_SOURCE_SHA", WALKTHROUGH_SHA)
    monkeypatch.setattr(sys, "argv", ["design_engine_walkthrough.py", "--receipt-out", str(out)])
    return mod.main(), out


def test_script_passes_and_writes_receipt_on_verified_server(
    db_engine, db_session, client, design_flags, monkeypatch, tmp_path, capsys
) -> None:
    code, out = _run_script(monkeypatch, tmp_path, db_engine, client)
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "WALKTHROUGH PASS" in printed
    bundle = json.loads(out.read_text(encoding="utf-8"))
    assert bundle["receipt"]["flags"] == DesignEngineFlags.from_settings(settings).model_dump(mode="json")
    assert bundle["flags_source"] == "GET /api/admin/ops/runtime-flags"


@pytest.mark.parametrize("scenario", ["live_payments", "flags_unavailable", "alias_rejected"])
def test_script_refusal_prints_no_pass_and_writes_no_receipt(
    db_engine, db_session, client, design_flags, monkeypatch, tmp_path, capsys, scenario
) -> None:
    http = client
    if scenario == "live_payments":
        monkeypatch.setattr(settings, "allow_production_payments", True)
        expected = "FAIL FLAGS_NOT_TEST_MODE"
    elif scenario == "flags_unavailable":
        http = _ServerFlagsOverride(client, [_Resp(404, {"detail": "Not Found"})])
        expected = "FAIL SERVER_FLAGS_UNVERIFIABLE"
    else:
        _reject_alias(monkeypatch, new_write_surface=("POST /api/canon/rigs/{rig_id}/clone",))
        expected = "FAIL ALIAS_EVIDENCE_REJECTED"
    code, out = _run_script(monkeypatch, tmp_path, db_engine, http)
    printed = capsys.readouterr().out
    assert code == 1
    assert expected in printed
    assert "WALKTHROUGH PASS" not in printed
    assert not out.exists()
