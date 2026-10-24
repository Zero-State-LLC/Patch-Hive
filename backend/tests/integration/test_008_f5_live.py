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
from core.ops.design_walkthrough import collect_live_alias_evidence, execute_walkthrough
from core.ops.f5_cutover import (
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


def test_staging_overlay_flags_are_test_mode_and_script_does_not_patch_credentials() -> None:
    from core.ops.f5_cutover import flags_test_mode_failures

    mod, source = _walkthrough_script()
    overlay = mod._overlay_flags("staging")
    assert flags_test_mode_failures(overlay) == ()
    assert overlay.allow_production_payments is False
    assert flags_test_mode_failures(mod._overlay_flags("production")) == ("PRODUCTION_ENVIRONMENT",)
    assert "get_password_hash" not in source
    assert "password_hash" not in source
