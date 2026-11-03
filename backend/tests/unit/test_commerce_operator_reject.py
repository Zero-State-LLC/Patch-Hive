"""Spec 004 T048: operator review of unresolved commerce events.

Machine B ``Unresolved --operator_rejects--> Abandoned``: an Admin closes an unresolved
provider event with a reason; it grants nothing and writes one
``CanonicalAdminAuditEventRecord`` (OQ-5 recommendation). Any other status is 409
``INVALID_TRANSITION`` with no change. ``operator_resolves`` is T048b
(``tests/unit/test_commerce_operator_resolve.py``).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from canon.models import (
    CanonicalAdminAuditEventRecord,
    CanonicalCreditLedgerEntryRecord,
    StripeEventRecordModel,
)
from core import get_db
from main import app
from monetization.models import CreditsLedger
from tests.conftest import bearer_headers, make_user


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _event(db: Session, event_id: str, status: str, reason_code: str | None = None) -> None:
    db.add(
        StripeEventRecordModel(
            stripe_event_id=event_id,
            event_type="checkout.session.completed",
            payload_hash="0" * 64,
            livemode=False,
            status=status,
            reason_code=reason_code,
            received_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            processed_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()


def _reject(client: TestClient, user, event_id: str, reason: str = "test-mode duplicate"):
    return client.post(
        f"/api/admin/commerce/events/{event_id}/reject",
        json={"reason": reason},
        headers=bearer_headers(user),
    )


def _audits(db: Session) -> list[CanonicalAdminAuditEventRecord]:
    return db.query(CanonicalAdminAuditEventRecord).all()


def _no_grants(db: Session) -> bool:
    return db.query(CanonicalCreditLedgerEntryRecord).count() == 0 and db.query(CreditsLedger).count() == 0


def test_an_admin_rejects_an_unresolved_event_with_one_audit_and_no_grant(client, db_session):
    admin = make_user(db_session, "admin1", role="Admin")
    _event(db_session, "evt_1", "unresolved", "HANDLER_NOT_IMPLEMENTED")

    resp = _reject(client, admin, "evt_1")

    assert resp.status_code == 200, resp.text
    record = db_session.get(StripeEventRecordModel, "evt_1")
    assert (record.status, record.reason_code) == ("rejected", "HANDLER_NOT_IMPLEMENTED")
    (audit,) = _audits(db_session)
    assert resp.json() == {"stripe_event_id": "evt_1", "status": "rejected", "audit_event_id": audit.id}
    assert (audit.actor_user_id, audit.actor_role, audit.action) == (admin.id, "Admin", "commerce.event.reject")
    assert (audit.target_type, audit.target_id, audit.reason) == ("stripe_event", "evt_1", "test-mode duplicate")
    assert audit.before_hash and audit.after_hash and audit.before_hash != audit.after_hash
    assert _no_grants(db_session)


@pytest.mark.parametrize("status", ["processed", "duplicate", "ignored", "rejected"])
def test_only_an_unresolved_event_can_be_rejected(client, db_session, status):
    admin = make_user(db_session, "admin2", role="Admin")
    _event(db_session, "evt_2", status)

    resp = _reject(client, admin, "evt_2")

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"code": "INVALID_TRANSITION", "status": status}
    assert db_session.get(StripeEventRecordModel, "evt_2").status == status
    assert _audits(db_session) == []


@pytest.mark.parametrize("role", ["Ops", "Support", "ReadOnly", "User"])
def test_only_an_admin_may_reject(client, db_session, role):
    user = make_user(db_session, f"{role.lower()}1", role=role)
    _event(db_session, "evt_3", "unresolved", "EVENT_PAYLOAD_MALFORMED")

    resp = _reject(client, user, "evt_3")

    assert resp.status_code == 403
    assert db_session.get(StripeEventRecordModel, "evt_3").status == "unresolved"
    assert _audits(db_session) == []


def test_a_reject_needs_a_reason_and_a_known_event(client, db_session):
    admin = make_user(db_session, "admin4", role="Admin")
    _event(db_session, "evt_4", "unresolved", "RECEIVED_BEFORE_PROCESSOR")

    assert _reject(client, admin, "evt_4", reason="   ").status_code == 422
    assert _reject(client, admin, "evt_missing").status_code == 404
    assert db_session.get(StripeEventRecordModel, "evt_4").status == "unresolved"
    assert _audits(db_session) == []


def test_admin_readers_list_only_unresolved_events(client, db_session):
    reader = make_user(db_session, "support1", role="Support")
    _event(db_session, "evt_a", "unresolved", "HANDLER_NOT_IMPLEMENTED")
    _event(db_session, "evt_b", "processed")
    _event(db_session, "evt_c", "rejected", "HANDLER_NOT_IMPLEMENTED")

    resp = client.get("/api/admin/commerce/unresolved-events", headers=bearer_headers(reader))

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert [e["stripe_event_id"] for e in body["events"]] == ["evt_a"]
    assert body["events"][0]["reason_code"] == "HANDLER_NOT_IMPLEMENTED"
    user = make_user(db_session, "plain1")
    assert client.get("/api/admin/commerce/unresolved-events", headers=bearer_headers(user)).status_code == 403


def test_a_stale_read_cannot_reject_twice(db_session):
    """Two overlapping rejects: the second holds a stale ``unresolved`` copy but the
    conditional update finds no unresolved row, so it changes nothing and audits nothing."""
    from canon.webhook_events import InvalidEventTransitionError, reject_unresolved_event

    admin = make_user(db_session, "admin5", role="Admin")
    _event(db_session, "evt_5", "unresolved", "HANDLER_NOT_IMPLEMENTED")
    record = db_session.get(StripeEventRecordModel, "evt_5")
    # Another request rejects the event behind this session's back.
    db_session.query(StripeEventRecordModel).filter_by(stripe_event_id="evt_5").update(
        {"status": "rejected"}, synchronize_session=False
    )
    assert record.status == "unresolved"  # the stale in-memory copy

    with pytest.raises(InvalidEventTransitionError):
        reject_unresolved_event(
            db_session, record, actor_user_id=admin.id, actor_role="Admin", reason="second"
        )
    assert record.status == "rejected"
    assert _audits(db_session) == []
