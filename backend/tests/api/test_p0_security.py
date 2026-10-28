"""
P0 security gaps from the 2026-10-27 gap analysis: rack evidence is private to its
owner, catalog imports need an admin, profiles hide private fields, exports are priced
by the server, runs stay append-only, and hosted environments refuse placeholder secrets.
"""

import hashlib
from types import SimpleNamespace

import pytest

pytest.importorskip("httpx", reason="httpx is required for FastAPI TestClient")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from admin.models import AdminAuditLog
from cases.models import Case
from community.models import User
from core import settings
from main import app
from racks.models import Rack
from tests.conftest import bearer_headers, make_user


@pytest.fixture
def client(db_session: Session):
    from core import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def people(db_session: Session) -> dict:
    return {
        "owner": make_user(db_session, "owner"),
        "other": make_user(db_session, "other"),
        "support": make_user(db_session, "support", "Support"),
        "ops": make_user(db_session, "ops", "Ops"),
    }


def _rack(db_session: Session, user: User, case: Case, *, public: bool = True) -> Rack:
    rack = Rack(user_id=user.id, case_id=case.id, name="Rig", tags=[], is_public=public)
    db_session.add(rack)
    db_session.commit()
    return rack


# --- Evidence -------------------------------------------------------------------


def test_rack_evidence_is_private_even_on_a_public_rack(
    client: TestClient, db_session: Session, people: dict, sample_case: Case
) -> None:
    rack = _rack(db_session, people["owner"], sample_case, public=True)
    reads = [
        f"/api/racks/{rack.id}/evidence/images",
        f"/api/canon/rigs/{rack.id}/evidence/candidates",
        f"/api/racks/{rack.id}/evidence/reconcile",
        f"/api/racks/{rack.id}/evidence/inventory",
    ]
    for url in reads:
        assert client.get(url).status_code == 401, url
        assert client.get(url, headers=bearer_headers(people["other"])).status_code == 404, url
        assert client.get(url, headers=bearer_headers(people["owner"])).status_code == 200, url
        assert client.get(url, headers=bearer_headers(people["support"])).status_code == 200, url


def test_only_the_owner_changes_rack_evidence(
    client: TestClient, db_session: Session, people: dict, sample_case: Case
) -> None:
    rack = _rack(db_session, people["owner"], sample_case)
    delete = f"/api/racks/{rack.id}/evidence/images/missing?purge_bytes=true"
    confirm = f"/api/racks/{rack.id}/evidence/confirmations"
    resolve = f"/api/racks/{rack.id}/evidence/decision-resolution"
    resolve_body = {"evidence_id": "e-1", "idempotency_key": "idem-1"}

    assert client.delete(delete).status_code == 401
    assert client.post(confirm, json={"decisions": []}).status_code == 401
    assert client.post(resolve, json=resolve_body).status_code == 401
    for who, code in (("other", 404), ("support", 403)):
        headers = bearer_headers(people[who])
        assert client.delete(delete, headers=headers).status_code == code
        assert client.post(confirm, json={"decisions": []}, headers=headers).status_code == code
        assert client.post(resolve, json=resolve_body, headers=headers).status_code == code
    # The owner gets past the guard to the route's own answer.
    assert client.delete(delete, headers=bearer_headers(people["owner"])).status_code == 404


# --- Catalog imports and bulk materialize --------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "/api/modulargrid/import/modules?clear_existing=true",
        "/api/modulargrid/import/all",
        "/api/synth-catalog/import/catalog?dry_run=true",
        "/api/synth-catalog/import/modules?clear_existing=true",
        "/api/synth-catalog/enrich/hp?dry_run=true",
        "/api/modules/catalog/materialize-batch",
        "/api/cases/catalog/materialize-batch",
    ],
)
def test_catalog_imports_need_an_admin(client: TestClient, people: dict, url: str) -> None:
    assert client.post(url).status_code == 401
    assert client.post(url, headers=bearer_headers(people["other"])).status_code == 403
    assert client.post(url, headers=bearer_headers(people["support"])).status_code == 403


def test_admin_catalog_imports_are_audited(
    client: TestClient, db_session: Session, people: dict
) -> None:
    resp = client.post(
        "/api/synth-catalog/enrich/hp?dry_run=true", headers=bearer_headers(people["ops"])
    )
    assert resp.status_code in (200, 500)  # the guard passed; the import may lack seed data
    resp = client.post(
        "/api/modules/catalog/materialize-batch?limit=1", headers=bearer_headers(people["ops"])
    )
    assert resp.status_code == 200
    actions = [row.action_type for row in db_session.query(AdminAuditLog).order_by(AdminAuditLog.id)]
    assert actions == ["synth_catalog.enrich.hp", "module_catalog.materialize_batch"]


# --- Profiles and referral codes ------------------------------------------------


def test_public_profiles_hide_email_referral_code_and_role(
    client: TestClient, db_session: Session, people: dict
) -> None:
    owner = people["owner"]
    owner.allow_public_avatar = False
    owner.avatar_url = "https://example.com/me.png"
    db_session.commit()
    for url in (f"/api/community/users/{owner.id}", f"/api/community/users/username/{owner.username}"):
        body = client.get(url).json()
        assert body["username"] == "owner"
        assert not {"email", "referral_code", "role", "referred_by"} & body.keys()
        assert body["avatar_url"] is None
    me = client.get("/api/community/users/me", headers=bearer_headers(owner)).json()
    assert me["email"] == "owner@example.com"


def test_referral_codes_are_not_derived_from_the_email(client: TestClient) -> None:
    resp = client.post(
        "/api/community/users",
        json={"username": "newbie", "email": "newbie@example.com", "password": "s3cret-pass"},
    )
    assert resp.status_code == 201, resp.text
    derived = hashlib.sha256(b"newbie:newbie@example.com").hexdigest()[:10]
    assert not resp.json()["referral_code"].startswith(derived)


# --- Exports, patches -----------------------------------------------------------


def test_exports_ignore_a_client_credit_cost(client: TestClient, db_session: Session) -> None:
    from tests.api.test_canon_export_api import _grant
    from tests.unit.test_canon_contracts import _persist_hierarchy

    user, _patch = _persist_hierarchy(db_session)
    _grant(db_session, user.id, 10)
    resp = client.post(
        "/api/canon/exports",
        headers=bearer_headers(user),
        json={
            "source_run_id": "run-1",
            "source_rig_revision_id": "rig-rev-1",
            "artifact_manifest_hash": "a" * 64,
            "idempotency_key": "idem-free-export",
            "credit_cost": 0,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["credit_cost"] == settings.patchbook_export_cost
    assert settings.patchbook_export_cost > 0


def test_a_hand_made_patch_cannot_join_a_run(
    client: TestClient, db_session: Session, people: dict, sample_case: Case
) -> None:
    rack = _rack(db_session, people["owner"], sample_case)
    body = {
        "rack_id": rack.id,
        "name": "Mine",
        "category": "Voice",
        "connections": [],
        "generation_seed": 1,
        "generation_version": "1.0.0",
    }
    owner = bearer_headers(people["owner"])
    assert client.post("/api/patches/", json={**body, "run_id": 1}, headers=owner).status_code == 400
    created = client.post("/api/patches/", json=body, headers=owner)
    assert created.status_code == 201
    assert created.json()["run_id"] is None


# --- Secrets --------------------------------------------------------------------


def _settings(environment: str, secret_key: str) -> SimpleNamespace:
    return SimpleNamespace(environment=environment, secret_key=secret_key)


def test_hosted_environments_refuse_placeholder_secret_keys() -> None:
    from core.security import validate_secret_policy

    validate_secret_policy(_settings("development", "dev-secret-key-change-in-production"))
    validate_secret_policy(_settings("test", "short"))
    validate_secret_policy(_settings("staging", "k" * 32))
    for env in ("staging", "production"):
        for key in ("dev-secret-key-change-in-production", "staging-secret-key-change-me-32chars-min", "short"):
            with pytest.raises(RuntimeError, match="SECRET_KEY"):
                validate_secret_policy(_settings(env, key))


def test_download_tokens_do_not_use_the_login_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from canon.routes import _download_secret

    monkeypatch.setattr(settings, "download_token_secret", "")
    assert _download_secret() != settings.secret_key
    assert len(_download_secret()) >= 32
    monkeypatch.setattr(settings, "download_token_secret", "d" * 40)
    assert _download_secret() == "d" * 40


def test_staging_webhooks_need_the_stripe_secret(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "")
    resp = client.post(
        "/api/canon/webhooks/stripe",
        content=b'{"id": "evt_1"}',
        headers={"Stripe-Signature": "t=1,v1=00"},
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "STRIPE_WEBHOOK_SECRET is not configured"


def test_the_demo_seed_runs_only_in_development(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from seed_data import load_seed_data

    monkeypatch.setattr(settings, "environment", "staging")
    with pytest.raises(RuntimeError, match="development"):
        load_seed_data(db_session)
    assert db_session.query(User).filter(User.username == "testuser").count() == 0
