"""API tests for the canonical export/download/webhook HTTP surface."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from canon.models import CanonicalCreditLedgerEntryRecord
from community.models import User
from core import create_access_token, settings
from main import app
from tests.unit.test_canon_contracts import _persist_hierarchy

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def client(db_session: Session):
    from core import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"user_id": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def _grant(db_session: Session, user_id: int, amount: int = 10) -> None:
    db_session.add(
        CanonicalCreditLedgerEntryRecord(
            id=f"grant-{user_id}-{amount}",
            user_id=user_id,
            delta=amount,
            entry_type="grant",
            idempotency_key=f"grant-{user_id}-{amount}",
            created_at=NOW,
        )
    )
    db_session.commit()


def test_canonical_export_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/api/canon/exports",
        json={
            "source_run_id": "run-1",
            "source_rig_revision_id": "rig-rev-1",
            "artifact_manifest_hash": "a" * 64,
            "idempotency_key": "idem-auth-1",
        },
    )
    assert resp.status_code == 401


def test_canonical_export_and_download_token_flow(export_fulfillment_pending, client: TestClient, db_session: Session) -> None:
    user, _patch = _persist_hierarchy(db_session)
    _grant(db_session, user.id, 10)

    create = client.post(
        "/api/canon/exports",
        headers=_auth_headers(user),
        json={
            "source_run_id": "run-1",
            "source_rig_revision_id": "rig-rev-1",
            "artifact_manifest_hash": "a" * 64,
            "formats": ["pdf", "json"],
            "license": "personal",
            "idempotency_key": "idem-export-1",
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["status"] == "queued"
    assert body["credit_cost"] == settings.patchbook_export_cost
    export_id = body["export_id"]

    # Idempotent retry returns the same export and does not re-debit.
    retry = client.post(
        "/api/canon/exports",
        headers=_auth_headers(user),
        json={
            "source_run_id": "run-1",
            "source_rig_revision_id": "rig-rev-1",
            "artifact_manifest_hash": "a" * 64,
            "formats": ["pdf", "json"],
            "license": "personal",
            "idempotency_key": "idem-export-1",
        },
    )
    assert retry.status_code == 201
    assert retry.json()["export_id"] == export_id

    balance = client.get("/api/canon/credits/balance", headers=_auth_headers(user))
    assert balance.status_code == 200
    assert balance.json()["balance"] == 10 - settings.patchbook_export_cost

    # Fulfillment finishes: the pack exists, so a download token may be issued.
    from canon.models import CanonicalExportRecord

    record = db_session.get(CanonicalExportRecord, export_id)
    record.status = "succeeded"
    record.pack_manifest_hash = "b" * 64
    db_session.commit()

    token_resp = client.post(
        f"/api/canon/exports/{export_id}/download-token",
        headers=_auth_headers(user),
        json={"ttl_seconds": 120},
    )
    assert token_resp.status_code == 200, token_resp.text
    token = token_resp.json()["token"]

    verify = client.post(
        f"/api/canon/exports/{export_id}/download",
        headers=_auth_headers(user),
        json={"token": token},
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["export_id"] == export_id
    assert verify.json()["user_id"] == str(user.id)

    listed = client.get("/api/canon/exports", headers=_auth_headers(user))
    assert listed.status_code == 200, listed.text
    assert any(item["export_id"] == export_id for item in listed.json())

    summary = client.get("/api/canon/credits/summary", headers=_auth_headers(user))
    assert summary.status_code == 200, summary.text
    body_summary = summary.json()
    assert body_summary["balance"] == 10 - settings.patchbook_export_cost
    assert any(entry["entry_type"] == "debit" for entry in body_summary["entries"])


def test_canonical_export_insufficient_credits(export_fulfillment_pending, client: TestClient, db_session: Session) -> None:
    user, _patch = _persist_hierarchy(db_session)
    resp = client.post(
        "/api/canon/exports",
        headers=_auth_headers(user),
        json={
            "source_run_id": "run-1",
            "source_rig_revision_id": "rig-rev-1",
            "artifact_manifest_hash": "a" * 64,
            "idempotency_key": "idem-no-credits",
        },
    )
    assert resp.status_code == 402
    assert resp.json()["detail"] == "INSUFFICIENT_CREDITS"


def test_legacy_patchbook_debit_disabled_by_default(
    client: TestClient, db_session: Session
) -> None:
    """Default ENABLE_LEGACY_PATCHBOOK_DEBIT=false rejects legacy debit POST with 410."""
    user, _patch = _persist_hierarchy(db_session)
    resp = client.post(
        "/api/export/runs/1/patchbook",
        headers=_auth_headers(user),
    )
    assert resp.status_code == 410
    assert "LEGACY_PATCHBOOK_DEBIT_DISABLED" in resp.json()["detail"]


def test_legacy_patchbook_debit_can_be_disabled(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ENABLE_LEGACY_PATCHBOOK_DEBIT=false returns 410 on the legacy debit route."""
    import export.routes as export_routes

    monkeypatch.setattr(settings, "enable_legacy_patchbook_debit", False)
    monkeypatch.setattr(export_routes, "settings", settings)

    user, _patch = _persist_hierarchy(db_session)
    resp = client.post(
        "/api/export/runs/1/patchbook",
        headers=_auth_headers(user),
    )
    assert resp.status_code == 410
    assert "LEGACY_PATCHBOOK_DEBIT_DISABLED" in resp.json()["detail"]


def _signature(payload: bytes, secret: str, timestamp: int) -> str:
    digest = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_stripe_webhook_rejects_livemode_in_test_mode(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "stripe_test_mode", True)
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test_secret_value_1234")
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "allow_production_payments", False)

    # Bind the module-level settings used by the route.
    import canon.routes as canon_routes

    monkeypatch.setattr(canon_routes, "settings", settings)

    import time

    timestamp = int(time.time())
    payload = json.dumps({"id": "evt_live", "type": "charge.succeeded", "livemode": True}).encode()
    resp = client.post(
        "/api/canon/webhooks/stripe",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": _signature(payload, "whsec_test_secret_value_1234", timestamp),
        },
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "LIVEMODE_EVENT_REJECTED"


def test_stripe_webhook_disabled_in_production_without_payments(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import canon.routes as canon_routes

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "allow_production_payments", False)
    monkeypatch.setattr(canon_routes, "settings", settings)

    resp = client.post(
        "/api/canon/webhooks/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=abc"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "PRODUCTION_PAYMENTS_DISABLED"


def test_payment_startup_policy_fail_closed() -> None:
    from canon.routes import validate_payment_startup_policy
    from types import SimpleNamespace

    # Safe production defaults.
    validate_payment_startup_policy(
        SimpleNamespace(
            environment="production",
            allow_production_payments=False,
            stripe_test_mode=True,
            stripe_webhook_secret="",
            download_token_secret="",
            secret_key="x" * 32,
        )
    )

    with pytest.raises(RuntimeError, match="STRIPE_TEST_MODE"):
        validate_payment_startup_policy(
            SimpleNamespace(
                environment="production",
                allow_production_payments=False,
                stripe_test_mode=False,
                stripe_webhook_secret="",
                download_token_secret="",
                secret_key="x" * 32,
            )
        )

    with pytest.raises(RuntimeError, match="STRIPE_WEBHOOK_SECRET"):
        validate_payment_startup_policy(
            SimpleNamespace(
                environment="production",
                allow_production_payments=True,
                stripe_test_mode=False,
                stripe_webhook_secret="short",
                download_token_secret="y" * 32,
                secret_key="x" * 32,
            )
        )


@pytest.mark.parametrize(
    "canon_on,inline_on",
    [(False, False), (True, False), (False, True)],
)
def test_an_export_nothing_will_fulfill_is_refused_before_any_debit(
    client: TestClient, db_session: Session, monkeypatch, canon_on: bool, inline_on: bool
) -> None:
    """Spec 004 FR-005: with no fulfiller, no credits are taken."""
    monkeypatch.setattr(settings, "enable_canon_export_fulfillment", canon_on)
    monkeypatch.setattr(settings, "enable_inline_export_fulfillment", inline_on)
    user, _patch = _persist_hierarchy(db_session)
    _grant(db_session, user.id, 10)
    resp = client.post(
        "/api/canon/exports",
        headers=_auth_headers(user),
        json={
            "source_run_id": "run-1",
            "source_rig_revision_id": "rig-rev-1",
            "artifact_manifest_hash": "a" * 64,
            "formats": ["pdf"],
            "license": "personal",
            "idempotency_key": f"idem-off-{canon_on}-{inline_on}",
        },
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "EXPORT_FULFILLMENT_UNAVAILABLE"
    balance = client.get("/api/canon/credits/balance", headers=_auth_headers(user)).json()["balance"]
    assert balance == 10
    assert client.get("/api/canon/exports", headers=_auth_headers(user)).json() == []


def _webhook_settings(monkeypatch: pytest.MonkeyPatch, *, environment: str, test_mode: bool) -> str:
    import canon.routes as canon_routes

    secret = "whsec_test_secret_value_1234"
    monkeypatch.setattr(settings, "stripe_test_mode", test_mode)
    monkeypatch.setattr(settings, "stripe_webhook_secret", secret)
    monkeypatch.setattr(settings, "environment", environment)
    monkeypatch.setattr(settings, "allow_production_payments", False)
    monkeypatch.setattr(canon_routes, "settings", settings)
    return secret


def test_stripe_webhook_rejects_livemode_in_staging_with_test_mode_off(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec 004 T041: live-mode events belong only to production."""
    import time

    secret = _webhook_settings(monkeypatch, environment="staging", test_mode=False)
    payload = json.dumps({"id": "evt_live", "type": "charge.succeeded", "livemode": True}).encode()
    resp = client.post(
        "/api/canon/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": _signature(payload, secret, int(time.time()))},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "LIVEMODE_EVENT_REJECTED"


def test_stripe_webhook_accepts_a_rotated_secret_on_the_second_v1(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec 004 T040: the provider sends one v1 per active secret during rotation."""
    import time

    secret = _webhook_settings(monkeypatch, environment="development", test_mode=True)
    timestamp = int(time.time())
    payload = json.dumps({"id": "evt_rot", "type": "charge.succeeded", "livemode": False}).encode()
    stale = _signature(payload, "whsec_retired_secret_value_99", timestamp).split(",")[1]
    current = _signature(payload, secret, timestamp)
    resp = client.post(
        "/api/canon/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": current.replace(",", f",{stale},", 1)},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["duplicate"] is False


def test_stripe_webhook_concurrent_duplicate_answers_200_duplicate(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec 004 T040: losing the insert race is a duplicate, not a 500."""
    import time

    from sqlalchemy import insert

    from canon.contracts import canonical_sha256
    from canon.models import StripeEventRecordModel

    secret = _webhook_settings(monkeypatch, environment="development", test_mode=True)
    event = {"id": "evt_race", "type": "charge.succeeded", "livemode": False}
    payload = json.dumps(event).encode()
    # The winning delivery commits after this one's lookup missed.
    db_session.execute(
        insert(StripeEventRecordModel.__table__).values(
            stripe_event_id="evt_race",
            event_type="charge.succeeded",
            payload_hash=canonical_sha256(event),
            livemode=False,
            status="received",
            received_at=NOW,
        )
    )
    db_session.commit()
    real_get = db_session.get
    lookups: list[str] = []

    def racing_get(model, ident, *args, **kwargs):
        lookups.append(ident)
        if model is StripeEventRecordModel and len(lookups) == 1:
            return None
        return real_get(model, ident, *args, **kwargs)

    monkeypatch.setattr(db_session, "get", racing_get)
    resp = client.post(
        "/api/canon/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": _signature(payload, secret, int(time.time()))},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["duplicate"] is True
    assert resp.json()["stripe_event_id"] == "evt_race"
    assert lookups == ["evt_race", "evt_race"]
