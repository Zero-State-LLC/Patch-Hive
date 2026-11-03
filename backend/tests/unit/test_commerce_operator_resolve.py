"""Spec 004 T048b: operator resolve of an unresolved commerce event.

Machine B ``Unresolved --operator_resolves--> Credited`` (OQ-5 ``A_refetch_session``):
an Admin asks PatchHive to retrieve the Checkout Session by the ``object_id`` stored at
intake and run Machine B's fulfillment once. The provider here is a fake (or an
``httpx.MockTransport``); no network, no live keys.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import admin.routes as admin_routes
from canon.checkout import (
    PaymentProviderError,
    StripeCheckoutProvider,
    resolve_unresolved_event,
)
from canon.exports import credit_balance
from canon.models import (
    CanonicalAdminAuditEventRecord,
    CanonicalCreditLedgerEntryRecord,
    ProviderPaymentRecord,
    StripeEventRecordModel,
)
from core import get_db, settings
from main import app
from monetization.models import CreditsLedger, Referral
from monetization.referrals import REFERRAL_REWARD_CREDITS, create_referral
from tests.conftest import bearer_headers, make_user
from tests.unit.test_commerce_credit_checkout import (
    _deliver,
    _open_checkout,
    _session_object,
    _settings,
)


class FakeRetriever:
    def __init__(self, obj: dict[str, Any] | None = None, *, fail: bool = False) -> None:
        self.obj = obj
        self.fail = fail
        self.calls: list[str] = []

    def retrieve_checkout_session(self, session_id: str) -> dict[str, Any]:
        self.calls.append(session_id)
        if self.fail:
            raise PaymentProviderError("provider answered 404")
        assert self.obj is not None
        return self.obj


def _purchases(db: Session) -> int:
    return db.query(CanonicalCreditLedgerEntryRecord).filter_by(entry_type="purchase").count()


def _audits(db: Session) -> list[CanonicalAdminAuditEventRecord]:
    return db.query(CanonicalAdminAuditEventRecord).all()


def _unresolved_completion(db: Session, buyer) -> tuple[ProviderPaymentRecord, str]:
    """A paid completion whose event metadata did not match the record: unresolved."""
    payment = _open_checkout(db, buyer)
    event_id = f"evt_resolve_{payment.id}"
    intake = _deliver(
        db,
        event_id,
        "checkout.session.completed",
        _session_object(payment, metadata={"user_id": "999"}),
    )
    assert (intake.record.status, intake.record.reason_code) == (
        "unresolved",
        "METADATA_MALFORMED",
    )
    assert intake.record.object_id == payment.checkout_session_id
    return payment, event_id


def _resolve(db: Session, event_id: str, provider, admin, **settings_overrides: Any):
    return resolve_unresolved_event(
        db,
        event_id,
        provider=provider,
        app_settings=_settings(**settings_overrides),
        actor_user_id=admin.id,
        actor_role=admin.role,
        reason="provider shows the session paid",
    )


# --- resolve_unresolved_event ----------------------------------------------------------


def test_resolve_retrieves_the_session_and_credits_once_with_one_audit(db_session: Session):
    admin = make_user(db_session, "resolver", role="Admin")
    referrer = make_user(db_session, "resolve-referrer")
    buyer = make_user(db_session, "resolve-buyer")
    create_referral(db_session, referrer=referrer, referred=buyer)
    db_session.commit()
    payment, event_id = _unresolved_completion(db_session, buyer)
    provider = FakeRetriever(_session_object(payment))

    outcome = _resolve(db_session, event_id, provider, admin)
    db_session.commit()

    assert provider.calls == [payment.checkout_session_id]
    record = db_session.get(StripeEventRecordModel, event_id)
    assert (record.status, record.reason_code) == ("processed", None)
    db_session.refresh(payment)
    assert payment.status == "credited"
    assert _purchases(db_session) == 1
    assert credit_balance(db_session, buyer.id) == payment.credits
    # The same effect as a verified completion, Machine A included (FR-028).
    assert db_session.query(Referral).filter_by(status="Rewarded").count() == 1
    assert credit_balance(db_session, referrer.id) == REFERRAL_REWARD_CREDITS
    (audit,) = _audits(db_session)
    assert audit is outcome.audit
    assert (audit.actor_user_id, audit.actor_role, audit.action) == (
        admin.id,
        "Admin",
        "commerce.event.resolve",
    )
    assert (audit.target_type, audit.target_id) == ("stripe_event", event_id)
    assert audit.reason == "provider shows the session paid"
    assert audit.before_hash != audit.after_hash


def test_a_resolved_event_cannot_be_resolved_again(db_session: Session):
    admin = make_user(db_session, "resolver2", role="Admin")
    buyer = make_user(db_session, "resolve-buyer2")
    payment, event_id = _unresolved_completion(db_session, buyer)
    provider = FakeRetriever(_session_object(payment))
    _resolve(db_session, event_id, provider, admin)
    db_session.commit()

    from canon.webhook_events import InvalidEventTransitionError

    with pytest.raises(InvalidEventTransitionError, match="processed"):
        _resolve(db_session, event_id, provider, admin)
    db_session.rollback()
    assert provider.calls == [payment.checkout_session_id]
    assert _purchases(db_session) == 1
    assert len(_audits(db_session)) == 1


def test_resolve_after_a_later_delivery_credited_is_a_duplicate(db_session: Session):
    """A good delivery for the same session credited meanwhile: resolve adds nothing."""
    admin = make_user(db_session, "resolver3", role="Admin")
    buyer = make_user(db_session, "resolve-buyer3")
    payment, event_id = _unresolved_completion(db_session, buyer)
    _deliver(db_session, "evt_resolve_good", "checkout.session.completed", _session_object(payment))

    _resolve(db_session, event_id, FakeRetriever(_session_object(payment)), admin)
    db_session.commit()

    record = db_session.get(StripeEventRecordModel, event_id)
    assert (record.status, record.reason_code) == ("duplicate", "PAYMENT_ALREADY_RECORDED")
    assert _purchases(db_session) == 1
    assert db_session.query(CreditsLedger).filter_by(change_type="Purchase").count() == 1
    assert len(_audits(db_session)) == 1


@pytest.mark.parametrize(
    ("overrides", "reason_code"),
    [
        ({"payment_status": "unpaid"}, "SESSION_NOT_PAID"),
        ({"customer": "cus_someone_else"}, "CUSTOMER_MISMATCH"),
        ({"amount_total": 1}, "AMOUNT_MISMATCH"),
    ],
)
def test_resolve_that_still_cannot_map_the_session_stays_unresolved(
    db_session: Session, overrides: dict[str, Any], reason_code: str
):
    admin = make_user(db_session, "resolver4", role="Admin")
    buyer = make_user(db_session, "resolve-buyer4")
    payment, event_id = _unresolved_completion(db_session, buyer)

    outcome = _resolve(
        db_session, event_id, FakeRetriever(_session_object(payment, **overrides)), admin
    )
    db_session.commit()

    record = db_session.get(StripeEventRecordModel, event_id)
    assert (record.status, record.reason_code) == ("unresolved", reason_code)
    db_session.refresh(payment)
    assert payment.status == "open"
    assert _purchases(db_session) == 0
    assert db_session.query(CreditsLedger).count() == 0
    # The attempt is an operator action, so it is audited once.
    assert [a.id for a in _audits(db_session)] == [outcome.audit.id]


def _refused(db_session: Session, event_id: str) -> None:
    record = db_session.get(StripeEventRecordModel, event_id)
    assert record.status == "unresolved"
    assert _purchases(db_session) == 0
    assert db_session.query(CreditsLedger).count() == 0
    assert _audits(db_session) == []


def test_resolve_fails_closed_when_the_session_cannot_be_retrieved(db_session: Session):
    admin = make_user(db_session, "resolver5", role="Admin")
    buyer = make_user(db_session, "resolve-buyer5")
    payment, event_id = _unresolved_completion(db_session, buyer)

    with pytest.raises(PaymentProviderError):
        _resolve(db_session, event_id, FakeRetriever(fail=True), admin)
    db_session.rollback()

    _refused(db_session, event_id)


def test_resolve_fails_closed_when_the_provider_returns_another_object(db_session: Session):
    from canon.checkout import ResolveRefusedError

    admin = make_user(db_session, "resolver6", role="Admin")
    buyer = make_user(db_session, "resolve-buyer6")
    payment, event_id = _unresolved_completion(db_session, buyer)
    wrong = [
        _session_object(payment, id="cs_other"),
        _session_object(payment, livemode=True),
        _session_object(payment, object="payment_intent"),
    ]
    for obj in wrong:
        with pytest.raises(ResolveRefusedError) as excinfo:
            _resolve(db_session, event_id, FakeRetriever(obj), admin)
        db_session.rollback()
        assert (excinfo.value.code, excinfo.value.status_code) == (
            "PROVIDER_OBJECT_MISMATCH",
            502,
        )
    _refused(db_session, event_id)


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"enable_credit_checkout": False}, "PAYMENTS_DISABLED"),
        ({"environment": "production"}, "PRODUCTION_PAYMENTS_DISABLED"),
        ({"stripe_secret_key": ""}, "STRIPE_SECRET_KEY_MISSING"),
        ({"stripe_secret_key": "sk_live_fixture"}, "LIVE_KEY_REFUSED"),
    ],
)
def test_resolve_is_refused_by_the_same_gate_as_checkout(
    db_session: Session, overrides: dict[str, Any], code: str
):
    from canon.checkout import CheckoutUnavailableError

    admin = make_user(db_session, "resolver7", role="Admin")
    buyer = make_user(db_session, "resolve-buyer7")
    payment, event_id = _unresolved_completion(db_session, buyer)
    provider = FakeRetriever(_session_object(payment))

    with pytest.raises(CheckoutUnavailableError, match=code):
        _resolve(db_session, event_id, provider, admin, **overrides)
    db_session.rollback()

    assert provider.calls == []
    _refused(db_session, event_id)


def _stored_event(db: Session, event_id: str, *, event_type: str, object_id: str | None):
    db.add(
        StripeEventRecordModel(
            stripe_event_id=event_id,
            event_type=event_type,
            payload_hash="0" * 64,
            livemode=False,
            object_id=object_id,
            status="unresolved",
            reason_code="HANDLER_NOT_IMPLEMENTED",
            received_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            processed_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()


@pytest.mark.parametrize(
    ("event_type", "object_id", "code"),
    [
        # Received before T046 stored object ids: nothing to retrieve.
        ("checkout.session.completed", None, "OBJECT_ID_MISSING"),
        # Machine C (T049) has no operator resolve; an operator rejects instead.
        ("customer.subscription.created", "sub_1", "RESOLVE_NOT_SUPPORTED"),
        ("customer.subscription.updated", "sub_1", "RESOLVE_NOT_SUPPORTED"),
        ("customer.subscription.deleted", "sub_1", "RESOLVE_NOT_SUPPORTED"),
        ("invoice.paid", "in_1", "RESOLVE_NOT_SUPPORTED"),
    ],
)
def test_resolve_is_refused_without_a_machine_b_object_id(
    db_session: Session, event_type: str, object_id: str | None, code: str
):
    from canon.checkout import ResolveRefusedError

    admin = make_user(db_session, "resolver8", role="Admin")
    _stored_event(db_session, "evt_no_obj", event_type=event_type, object_id=object_id)
    provider = FakeRetriever({"id": "unused"})

    with pytest.raises(ResolveRefusedError) as excinfo:
        _resolve(db_session, "evt_no_obj", provider, admin)
    db_session.rollback()

    assert (excinfo.value.code, excinfo.value.status_code) == (code, 409)
    assert provider.calls == []
    _refused(db_session, "evt_no_obj")


def test_resolve_refuses_a_subscription_mode_session(db_session: Session):
    """A subscription-mode session left unresolved before T049 is Machine C: refused
    with nothing written, even though the provider reports it paid."""
    from canon.checkout import ResolveRefusedError

    admin = make_user(db_session, "resolver9", role="Admin")
    _stored_event(
        db_session, "evt_sub_session", event_type="checkout.session.completed", object_id="cs_sub"
    )
    provider = FakeRetriever(
        {
            "id": "cs_sub",
            "object": "checkout.session",
            "mode": "subscription",
            "payment_status": "paid",
            "livemode": False,
        }
    )

    with pytest.raises(ResolveRefusedError) as excinfo:
        _resolve(db_session, "evt_sub_session", provider, admin)
    db_session.rollback()

    assert (excinfo.value.code, excinfo.value.status_code) == ("RESOLVE_NOT_SUPPORTED", 409)
    _refused(db_session, "evt_sub_session")


# --- POST /api/admin/commerce/events/{id}/resolve -------------------------------------


@pytest.fixture
def provider() -> FakeRetriever:
    return FakeRetriever()


@pytest.fixture
def client(db_session: Session, provider: FakeRetriever, monkeypatch: pytest.MonkeyPatch):
    for name, value in vars(_settings()).items():
        monkeypatch.setattr(settings, name, value)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[admin_routes.get_commerce_provider] = lambda: provider
    yield TestClient(app)
    app.dependency_overrides.clear()


def _post(client: TestClient, user, event_id: str, reason: str = "provider shows it paid"):
    return client.post(
        f"/api/admin/commerce/events/{event_id}/resolve",
        json={"reason": reason},
        headers=bearer_headers(user),
    )


def test_the_route_resolves_an_unresolved_event(client, db_session, provider):
    admin = make_user(db_session, "api-resolver", role="Admin")
    buyer = make_user(db_session, "api-resolve-buyer")
    payment, event_id = _unresolved_completion(db_session, buyer)
    provider.obj = _session_object(payment)

    resp = _post(client, admin, event_id)

    assert resp.status_code == 200, resp.text
    (audit,) = _audits(db_session)
    assert resp.json() == {
        "stripe_event_id": event_id,
        "status": "processed",
        "reason_code": None,
        "audit_event_id": audit.id,
    }
    assert credit_balance(db_session, buyer.id) == payment.credits


def test_the_route_reports_a_provider_failure_as_502(client, db_session, provider):
    admin = make_user(db_session, "api-resolver2", role="Admin")
    buyer = make_user(db_session, "api-resolve-buyer2")
    _payment, event_id = _unresolved_completion(db_session, buyer)
    provider.fail = True

    resp = _post(client, admin, event_id)

    assert resp.status_code == 502
    assert resp.json()["detail"] == {"code": "PAYMENT_PROVIDER_ERROR"}
    _refused(db_session, event_id)


def test_the_route_refuses_with_the_checkout_gate(client, db_session, provider, monkeypatch):
    admin = make_user(db_session, "api-resolver3", role="Admin")
    buyer = make_user(db_session, "api-resolve-buyer3")
    payment, event_id = _unresolved_completion(db_session, buyer)
    provider.obj = _session_object(payment)
    monkeypatch.setattr(settings, "enable_credit_checkout", False)

    resp = _post(client, admin, event_id)

    assert resp.status_code == 403
    assert resp.json()["detail"] == {"code": "PAYMENTS_DISABLED"}
    assert provider.calls == []
    _refused(db_session, event_id)


@pytest.mark.parametrize("status", ["processed", "duplicate", "ignored", "rejected"])
def test_the_route_resolves_only_an_unresolved_event(client, db_session, provider, status):
    admin = make_user(db_session, "api-resolver4", role="Admin")
    _stored_event(
        db_session, "evt_final", event_type="checkout.session.completed", object_id="cs_x"
    )
    record = db_session.get(StripeEventRecordModel, "evt_final")
    record.status = status
    db_session.commit()

    resp = _post(client, admin, "evt_final")

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"code": "INVALID_TRANSITION", "status": status}
    assert provider.calls == []
    assert _audits(db_session) == []


def test_the_route_refuses_a_missing_object_id_with_409(client, db_session, provider):
    admin = make_user(db_session, "api-resolver5", role="Admin")
    _stored_event(db_session, "evt_old", event_type="checkout.session.completed", object_id=None)

    resp = _post(client, admin, "evt_old")

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"code": "OBJECT_ID_MISSING"}
    _refused(db_session, "evt_old")


@pytest.mark.parametrize("role", ["Ops", "Support", "ReadOnly", "User"])
def test_only_an_admin_may_resolve(client, db_session, provider, role):
    user = make_user(db_session, f"{role.lower()}-resolver", role=role)
    _stored_event(db_session, "evt_role", event_type="checkout.session.completed", object_id="cs_r")

    resp = _post(client, user, "evt_role")

    assert resp.status_code == 403
    assert provider.calls == []
    _refused(db_session, "evt_role")


def test_a_resolve_needs_a_reason_and_a_known_event(client, db_session, provider):
    admin = make_user(db_session, "api-resolver6", role="Admin")
    _stored_event(db_session, "evt_r", event_type="checkout.session.completed", object_id="cs_r")

    assert _post(client, admin, "evt_r", reason="  ").status_code == 422
    assert _post(client, admin, "evt_missing").status_code == 404
    assert provider.calls == []
    _refused(db_session, "evt_r")


# --- Stripe REST client ---------------------------------------------------------------


def test_the_stripe_client_retrieves_a_checkout_session_by_id() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "cs_test_9", "object": "checkout.session"})

    client = StripeCheckoutProvider(
        "sk_test_fixture", api_base="https://stripe.test", transport=httpx.MockTransport(handle)
    )
    assert client.retrieve_checkout_session("cs_test_9") == {
        "id": "cs_test_9",
        "object": "checkout.session",
    }
    (request,) = seen
    assert (request.method, request.url.path) == ("GET", "/v1/checkout/sessions/cs_test_9")
    assert request.headers["Authorization"] == "Bearer sk_test_fixture"
    assert request.content == b""


def test_a_retrieve_error_does_not_leak_the_key() -> None:
    client = StripeCheckoutProvider(
        "sk_test_secretvalue",
        api_base="https://stripe.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(404, json={"error": {}})),
    )
    with pytest.raises(PaymentProviderError) as excinfo:
        client.retrieve_checkout_session("cs_gone")
    assert "sk_test_secretvalue" not in str(excinfo.value)


def test_a_session_id_cannot_change_the_request_path() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "x"})

    client = StripeCheckoutProvider(
        "sk_test_fixture", api_base="https://stripe.test", transport=httpx.MockTransport(handle)
    )
    client.retrieve_checkout_session("../customers/cus_1")
    assert seen[0].url.raw_path == b"/v1/checkout/sessions/..%2Fcustomers%2Fcus_1"
