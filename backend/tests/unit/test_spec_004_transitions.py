"""Spec 004 T010: the Machine A, B and C transitions tables and the append-only rules as tests.

Source: specs/004-commerce/spec.md, "## Stateful behavior", "### Machine A: Referral" and
"### Machine B: One-time credit purchase". Machine B (T046) lives in canon/checkout.py;
its ``Unresolved --operator_resolves--> Credited`` row is ``resolve_unresolved_event``
(T048b), and its refund and dispute rows (OQ-2 ``A_reverse_unspent``, T053) are
``handle_payment_reversal_event``, which also encodes Machine A's
``Rewarded --refund_processed--> Rewarded``. Machine C (subscription, T049) lives in
canon/subscriptions.py; see its section below for how its rows map to ``invoice.paid``
(research 2026-11-01 §3). The append-only section at the end asserts only what the code
enforces; the gaps it lists are reported in specs/004-commerce/tasks.md (T010).
Machine A purchases here are provider-verified
(``payment_verified=True``); an unverified one is refused before anything is written
(illegal row, FR-033).
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import Session

from account.deletion import anonymize_user
from admin.models import AdminAuditLog
from canon.checkout import (
    CheckoutUnavailableError,
    PaymentProviderError,
    resolve_unresolved_event,
    start_credit_checkout,
)
from canon.exports import ExportBoundaryError, credit_balance, receive_stripe_webhook
from canon.models import (
    CanonicalAdminAuditEventRecord,
    CanonicalCreditLedgerEntryRecord,
    ProviderPaymentRecord,
    StripeEventRecordModel,
    SubscriptionPeriodGrantRecord,
)
from canon.subscriptions import request_subscription_cancel, start_subscription_checkout
from canon.webhook_events import reject_unresolved_event
from community.models import User
from tests.unit.test_commerce_credit_checkout import (
    FakeProvider,
    _deliver,
    _open_checkout,
    _session_object,
    _settings,
)
import core.config as core_config
from tests.unit.test_commerce_subscriptions import (
    MONTH,
    P1,
    TS,
    FakeSubscriptionProvider,
    _c_settings,
)
from tests.unit.test_commerce_subscriptions import _customer as _c_customer
from tests.unit.test_commerce_subscriptions import _deliver as _c_deliver
from tests.unit.test_commerce_subscriptions import _invoice as _c_invoice
from tests.unit.test_commerce_subscriptions import _record as _c_record
from tests.unit.test_commerce_subscriptions import _subscription as _c_subscription
from monetization.models import CreditsLedger, Referral
from monetization.referrals import REFERRAL_REWARD_CREDITS, create_referral, record_purchase

NONE, PENDING, REWARDED = "NONE", "Pending", "Rewarded"


def _user(db: Session, name: str) -> User:
    user = User(
        username=name,
        email=f"{name}@example.com",
        password_hash="hashed",
        referral_code=f"code-{name}",
        role="User",
        display_name=name,
    )
    db.add(user)
    db.commit()
    return user


def _state(db: Session, referred: User) -> str:
    """Effective state per spec: Rewarded row wins, then Pending row, else NONE."""
    statuses = {
        r.status for r in db.query(Referral).filter(Referral.referred_user_id == referred.id)
    }
    if REWARDED in statuses:
        return REWARDED
    return PENDING if PENDING in statuses else NONE


def _grants(db: Session) -> int:
    return db.query(CreditsLedger).filter(CreditsLedger.change_type == "Grant").count()


def _canonical_grants(db: Session) -> list[CanonicalCreditLedgerEntryRecord]:
    return db.query(CanonicalCreditLedgerEntryRecord).filter_by(entry_type="grant").all()


def _snapshot(db: Session) -> tuple[int, int]:
    return db.query(Referral).count(), db.query(CreditsLedger).count()


@pytest.fixture
def pair(db_session: Session) -> tuple[User, User]:
    return _user(db_session, "referrer"), _user(db_session, "referred")


def _in_state(db: Session, state: str, referrer: User, referred: User) -> None:
    if state in (PENDING, REWARDED):
        create_referral(db, referrer=referrer, referred=referred)
        db.commit()
    if state == REWARDED:
        record_purchase(db, user=referred, credits_delta=5, payment_verified=True)
        db.commit()
    assert _state(db, referred) == state


# (from, event, error text, to): signup_with_code rejected, state unchanged.
SIGNUP_REJECTED = [
    (PENDING, "signup_with_code", "Referral already recorded", PENDING),
    (REWARDED, "signup_with_code", "Referral already rewarded", REWARDED),
]


def test_none_signup_with_code_becomes_pending(db_session: Session, pair):
    referrer, referred = pair
    assert _state(db_session, referred) == NONE
    create_referral(db_session, referrer=referrer, referred=referred)
    db_session.commit()
    assert _state(db_session, referred) == PENDING
    row = db_session.query(Referral).one()
    assert (row.referrer_user_id, row.status) == (referrer.id, PENDING)
    assert _grants(db_session) == 0


def test_none_self_referral_rejected_without_rows(db_session: Session, pair):
    _, referred = pair
    before = _snapshot(db_session)
    with pytest.raises(ValueError):
        create_referral(db_session, referrer=referred, referred=referred)
    assert _snapshot(db_session) == before
    assert _state(db_session, referred) == NONE


@pytest.mark.parametrize(("start", "event", "message", "end"), SIGNUP_REJECTED)
def test_signup_rejected_when_already_pending_or_rewarded(
    db_session: Session, pair, start, event, message, end
):
    referrer, referred = pair
    _in_state(db_session, start, referrer, referred)
    before = _snapshot(db_session)
    with pytest.raises(ValueError, match=message):
        create_referral(db_session, referrer=referrer, referred=referred)
    assert _snapshot(db_session) == before
    assert _state(db_session, referred) == end


def test_pending_first_purchase_rewards_once_atomically(db_session: Session, pair):
    referrer, referred = pair
    _in_state(db_session, PENDING, referrer, referred)
    pending = db_session.query(Referral).one()

    purchase = record_purchase(db_session, user=referred, credits_delta=5, payment_verified=True)
    db_session.commit()

    assert _state(db_session, referred) == REWARDED
    grant = db_session.query(CreditsLedger).filter_by(change_type="Grant").one()
    assert grant.user_id == referrer.id
    assert grant.credits_delta == REFERRAL_REWARD_CREDITS == 3
    assert grant.notes == f"Referral reward: {referred.id}"
    assert grant.referral_id == pending.id
    rewarded = db_session.query(Referral).filter_by(status=REWARDED).one()
    assert rewarded.first_purchase_id == purchase.id
    assert rewarded.rewarded_at is not None
    # The spendable reward lands on the canonical ledger once (FR-009).
    (canonical,) = _canonical_grants(db_session)
    assert (canonical.user_id, canonical.delta) == (referrer.id, REFERRAL_REWARD_CREDITS)


def test_pending_non_first_purchase_stays_pending_without_reward(db_session: Session, pair):
    referrer, referred = pair
    _in_state(db_session, PENDING, referrer, referred)
    db_session.add(CreditsLedger(user_id=referred.id, change_type="Purchase", credits_delta=5))
    db_session.commit()

    # The purchase count is now 2.
    record_purchase(db_session, user=referred, credits_delta=5, payment_verified=True)
    db_session.commit()

    assert _state(db_session, referred) == PENDING
    assert _grants(db_session) == 0
    assert db_session.query(Referral).filter_by(status=REWARDED).count() == 0


def test_rewarded_further_purchases_are_no_ops(db_session: Session, pair):
    referrer, referred = pair
    _in_state(db_session, REWARDED, referrer, referred)
    before = (_grants(db_session), db_session.query(Referral).count())

    record_purchase(db_session, user=referred, credits_delta=5, payment_verified=True)
    record_purchase(db_session, user=referred, credits_delta=5, payment_verified=True)
    db_session.commit()

    assert _state(db_session, referred) == REWARDED
    assert (_grants(db_session), db_session.query(Referral).count()) == before
    assert _grants(db_session) == 1  # illegal: Rewarded -> Rewarded with a second Grant
    assert len(_canonical_grants(db_session)) == 1


def test_none_purchase_creates_no_referral_or_grant(db_session: Session, pair):
    _, referred = pair
    record_purchase(db_session, user=referred, credits_delta=5, payment_verified=True)
    db_session.commit()
    assert _state(db_session, referred) == NONE
    assert _grants(db_session) == 0
    assert db_session.query(Referral).count() == 0


def test_pending_unverified_purchase_is_refused_without_reward(db_session: Session, pair):
    """Illegal: a reward triggered by a client-submitted purchase (FR-033)."""
    referrer, referred = pair
    _in_state(db_session, PENDING, referrer, referred)
    before = _snapshot(db_session)

    with pytest.raises(ValueError, match="FR-033"):
        record_purchase(db_session, user=referred, credits_delta=5)
    db_session.rollback()

    assert _state(db_session, referred) == PENDING
    assert _snapshot(db_session) == before
    assert _canonical_grants(db_session) == []


# --- Machine B: one-time credit purchase (T046) ----------------------------------------

CHECKOUT_OPEN, CREDITED, ABANDONED = "CheckoutOpen", "Credited", "Abandoned"
_B_STATES = {
    "open": CHECKOUT_OPEN,
    "pending": CHECKOUT_OPEN,
    "credited": CREDITED,
    "failed": ABANDONED,
    "abandoned": ABANDONED,
    "partially_refunded": "PartiallyRefunded",
    "refunded": "Refunded",
}


def _b_state(db: Session, payment: ProviderPaymentRecord) -> str:
    db.refresh(payment)
    return _B_STATES[payment.status]


def _purchase_entries(db: Session) -> int:
    return db.query(CanonicalCreditLedgerEntryRecord).filter_by(entry_type="purchase").count()


def test_b_none_request_credits_enabled_opens_checkout(db_session: Session, pair):
    _, buyer = pair
    payment = _open_checkout(db_session, buyer)
    assert _b_state(db_session, payment) == CHECKOUT_OPEN
    assert _purchase_entries(db_session) == 0


def test_b_none_request_credits_disabled_is_refused(db_session: Session, pair):
    _, buyer = pair
    provider = FakeProvider()
    with pytest.raises(CheckoutUnavailableError, match="PAYMENTS_DISABLED"):
        start_credit_checkout(
            db_session,
            user=buyer,
            credits=30,
            provider=provider,
            app_settings=_settings(enable_credit_checkout=False),
        )
    assert provider.sessions == []
    assert db_session.query(ProviderPaymentRecord).count() == 0


def test_b_checkout_completed_verified_credits_through_machine_a(db_session: Session, pair):
    referrer, buyer = pair
    create_referral(db_session, referrer=referrer, referred=buyer)
    db_session.commit()
    payment = _open_checkout(db_session, buyer)

    _deliver(db_session, "evt_b_paid", "checkout.session.completed", _session_object(payment))

    assert _b_state(db_session, payment) == CREDITED
    assert _purchase_entries(db_session) == 1
    assert db_session.query(CreditsLedger).filter_by(change_type="Purchase").count() == 1
    assert _state(db_session, buyer) == REWARDED


def test_b_checkout_completed_malformed_is_unresolved(db_session: Session, pair):
    _, buyer = pair
    payment = _open_checkout(db_session, buyer)

    intake = _deliver(
        db_session,
        "evt_b_bad",
        "checkout.session.completed",
        _session_object(payment, metadata={"user_id": "999"}),
    )

    assert intake.record.status == "unresolved" and intake.record.reason_code
    assert _b_state(db_session, payment) == CHECKOUT_OPEN
    assert _purchase_entries(db_session) == 0


@pytest.mark.parametrize(
    "event_type", ["checkout.session.expired", "checkout.session.async_payment_failed"]
)
def test_b_checkout_canceled_or_expired_is_abandoned(db_session: Session, pair, event_type):
    _, buyer = pair
    payment = _open_checkout(db_session, buyer)

    _deliver(db_session, "evt_b_end", event_type, _session_object(payment, payment_status="unpaid"))

    assert _b_state(db_session, payment) == ABANDONED
    assert _purchase_entries(db_session) == 0
    assert db_session.query(CreditsLedger).count() == 0


def test_b_credited_duplicate_completion_is_a_no_op(db_session: Session, pair):
    """Also the illegal row: no second ``Purchase`` for the same payment identifier."""
    _, buyer = pair
    payment = _open_checkout(db_session, buyer)
    _deliver(db_session, "evt_b_1", "checkout.session.completed", _session_object(payment))

    again = _deliver(db_session, "evt_b_2", "checkout.session.completed", _session_object(payment))

    assert again.record.status == "duplicate"
    assert _b_state(db_session, payment) == CREDITED
    assert _purchase_entries(db_session) == 1
    assert db_session.query(CreditsLedger).filter_by(change_type="Purchase").count() == 1


def test_b_unresolved_operator_rejects_grants_nothing(db_session: Session, pair):
    admin, buyer = pair
    payment = _open_checkout(db_session, buyer)
    _deliver(
        db_session,
        "evt_b_rej",
        "checkout.session.completed",
        _session_object(payment, customer="cus_other"),
    )
    record = db_session.get(StripeEventRecordModel, "evt_b_rej")
    assert record.status == "unresolved"

    reject_unresolved_event(
        db_session, record, actor_user_id=admin.id, actor_role="Admin", reason="not ours"
    )
    db_session.commit()

    assert record.status == "rejected"
    assert _b_state(db_session, payment) == CHECKOUT_OPEN
    assert _purchase_entries(db_session) == 0


class _Retriever:
    def __init__(self, obj=None) -> None:
        self.obj = obj

    def retrieve_checkout_session(self, session_id: str):
        if self.obj is None:
            raise PaymentProviderError("provider answered 404")
        return self.obj


def _unresolved_b_event(db: Session, payment: ProviderPaymentRecord, event_id: str):
    _deliver(
        db,
        event_id,
        "checkout.session.completed",
        _session_object(payment, metadata={"user_id": "999"}),
    )
    record = db.get(StripeEventRecordModel, event_id)
    assert record.status == "unresolved"
    return record


def test_b_unresolved_operator_resolves_credits_through_machine_a(db_session: Session, pair):
    """Same effect as the verified completion, from the session the provider reports."""
    referrer, buyer = pair
    create_referral(db_session, referrer=referrer, referred=buyer)
    db_session.commit()
    payment = _open_checkout(db_session, buyer)
    record = _unresolved_b_event(db_session, payment, "evt_b_res")

    resolve_unresolved_event(
        db_session,
        record.stripe_event_id,
        provider=_Retriever(_session_object(payment)),
        app_settings=_settings(),
        actor_user_id=referrer.id,
        actor_role="Admin",
        reason="provider shows it paid",
    )
    db_session.commit()

    assert record.status == "processed"
    assert _b_state(db_session, payment) == CREDITED
    assert _purchase_entries(db_session) == 1
    assert _state(db_session, buyer) == REWARDED
    assert db_session.query(CanonicalAdminAuditEventRecord).count() == 1


def test_b_unresolved_operator_resolves_needs_the_provider_session(db_session: Session, pair):
    """Guard: the operator verifies identity and payment. Unretrievable stays Unresolved."""
    admin, buyer = pair
    payment = _open_checkout(db_session, buyer)
    record = _unresolved_b_event(db_session, payment, "evt_b_res_gone")

    with pytest.raises(PaymentProviderError):
        resolve_unresolved_event(
            db_session,
            record.stripe_event_id,
            provider=_Retriever(),
            app_settings=_settings(),
            actor_user_id=admin.id,
            actor_role="Admin",
            reason="try again",
        )
    db_session.rollback()

    assert db_session.get(StripeEventRecordModel, "evt_b_res_gone").status == "unresolved"
    assert _b_state(db_session, payment) == CHECKOUT_OPEN
    assert _purchase_entries(db_session) == 0
    assert db_session.query(CanonicalAdminAuditEventRecord).count() == 0


def test_b_abandoned_to_credited_is_illegal(db_session: Session, pair):
    _, buyer = pair
    payment = _open_checkout(db_session, buyer)
    _deliver(db_session, "evt_b_exp", "checkout.session.expired", _session_object(payment))

    late = _deliver(db_session, "evt_b_late", "checkout.session.completed", _session_object(payment))

    assert (late.record.status, late.record.reason_code) == ("unresolved", "PAYMENT_STATE_CONFLICT")
    assert _b_state(db_session, payment) == ABANDONED
    assert _purchase_entries(db_session) == 0


def test_b_open_to_credited_needs_a_verified_provider_event(db_session: Session, pair):
    """Illegal: crediting without a verified confirmation. A forged event is refused."""
    _, buyer = pair
    payment = _open_checkout(db_session, buyer)
    payload = json.dumps(
        {
            "id": "evt_b_forged",
            "type": "checkout.session.completed",
            "livemode": False,
            "data": {"object": _session_object(payment)},
        }
    ).encode()
    with pytest.raises(ExportBoundaryError, match="WEBHOOK_SIGNATURE_INVALID"):
        receive_stripe_webhook(
            db_session,
            payload=payload,
            signature_header="t=1700000000,v1=forged",
            secret="whsec_machine_b",
            now=1_700_000_000,
        )
    db_session.rollback()
    assert _b_state(db_session, payment) == CHECKOUT_OPEN
    assert _purchase_entries(db_session) == 0


# --- Machine B refunds and disputes (OQ-2 ``A_reverse_unspent``, T053) -------------------

PARTIALLY_REFUNDED, REFUNDED = "PartiallyRefunded", "Refunded"


def _refund_entries(db: Session) -> list[CanonicalCreditLedgerEntryRecord]:
    return db.query(CanonicalCreditLedgerEntryRecord).filter_by(entry_type="refund").all()


def _credited_b(db: Session, buyer: User, event_id: str) -> ProviderPaymentRecord:
    payment = _open_checkout(db, buyer)
    _deliver(db, event_id, "checkout.session.completed", _session_object(payment))
    assert _b_state(db, payment) == CREDITED
    return payment


def _charge_refunded(payment: ProviderPaymentRecord, refunded: int) -> dict:
    return {
        "id": f"ch_{payment.checkout_session_id}",
        "object": "charge",
        "payment_intent": payment.provider_payment_id,
        "customer": f"cus_{payment.user_id}",
        "amount": payment.amount_cents,
        "amount_refunded": refunded,
        "currency": payment.currency,
    }


def test_b_credited_full_refund_reverses_unspent_credits(db_session: Session, pair):
    _, buyer = pair
    payment = _credited_b(db_session, buyer, "evt_b_rf_paid")

    intake = _deliver(db_session, "evt_b_rf", "charge.refunded", _charge_refunded(payment, 600))

    assert intake.record.status == "processed"
    assert _b_state(db_session, payment) == REFUNDED
    assert [entry.delta for entry in _refund_entries(db_session)] == [-payment.credits]
    assert credit_balance(db_session, buyer.id) == 0


def test_b_credited_partial_refund_reverses_its_share(db_session: Session, pair):
    _, buyer = pair
    payment = _credited_b(db_session, buyer, "evt_b_prf_paid")

    _deliver(db_session, "evt_b_prf", "charge.refunded", _charge_refunded(payment, 300))

    assert _b_state(db_session, payment) == PARTIALLY_REFUNDED
    assert credit_balance(db_session, buyer.id) == payment.credits // 2


def test_b_credited_refund_after_spend_reverses_the_rest_and_holds_the_remainder(
    db_session: Session, pair
):
    _, buyer = pair
    payment = _credited_b(db_session, buyer, "evt_b_srf_paid")
    db_session.add(
        CanonicalCreditLedgerEntryRecord(
            id="debit-b-srf",
            user_id=buyer.id,
            delta=-25,
            entry_type="debit",
            idempotency_key="test-spend:b-srf",
            export_id=None,
        )
    )
    db_session.commit()

    intake = _deliver(db_session, "evt_b_srf", "charge.refunded", _charge_refunded(payment, 600))

    assert (intake.record.status, intake.record.reason_code) == (
        "unresolved",
        "REFUND_EXCEEDS_UNSPENT",
    )
    assert _b_state(db_session, payment) == REFUNDED
    assert credit_balance(db_session, buyer.id) == 0  # never negative
    assert payment.refund_unrecovered_credits == 25


def test_b_refunded_duplicate_refund_is_a_no_op(db_session: Session, pair):
    _, buyer = pair
    payment = _credited_b(db_session, buyer, "evt_b_drf_paid")
    _deliver(db_session, "evt_b_drf_1", "charge.refunded", _charge_refunded(payment, 600))

    again = _deliver(db_session, "evt_b_drf_2", "charge.refunded", _charge_refunded(payment, 600))

    assert again.record.status == "duplicate"
    assert _b_state(db_session, payment) == REFUNDED
    assert len(_refund_entries(db_session)) == 1


def test_b_credited_dispute_opened_goes_to_an_operator_without_reversal(db_session: Session, pair):
    _, buyer = pair
    payment = _credited_b(db_session, buyer, "evt_b_dp_paid")
    dispute = {
        "id": "dp_b",
        "object": "dispute",
        "payment_intent": payment.provider_payment_id,
        "amount": payment.amount_cents,
        "currency": payment.currency,
    }

    intake = _deliver(db_session, "evt_b_dp", "charge.dispute.created", dispute)

    assert (intake.record.status, intake.record.reason_code) == ("unresolved", "DISPUTE_OPENED")
    assert _b_state(db_session, payment) == CREDITED
    assert _refund_entries(db_session) == []


def test_b_abandoned_refund_reverses_nothing(db_session: Session, pair):
    """Illegal: a refund reversal for a payment that was never credited."""
    _, buyer = pair
    payment = _open_checkout(db_session, buyer)
    unpaid = _session_object(payment, payment_status="unpaid")
    _deliver(db_session, "evt_b_arf_unpaid", "checkout.session.completed", unpaid)
    _deliver(db_session, "evt_b_arf_fail", "checkout.session.async_payment_failed", unpaid)

    intake = _deliver(db_session, "evt_b_arf", "charge.refunded", _charge_refunded(payment, 600))

    assert (intake.record.status, intake.record.reason_code) == (
        "unresolved",
        "PAYMENT_STATE_CONFLICT",
    )
    assert _b_state(db_session, payment) == ABANDONED
    assert _refund_entries(db_session) == []


def test_a_pending_purchase_recorded_with_a_deleted_referrer_stays_pending(
    db_session: Session, pair
):
    """Machine A, owner decision 44: no reward of either kind, and a trace of why."""
    referrer, referred = pair
    _in_state(db_session, PENDING, referrer, referred)
    anonymize_user(db_session, referrer)
    db_session.commit()

    purchase = record_purchase(
        db_session, user=referred, credits_delta=30, payment_verified=True
    )
    db_session.commit()

    assert _state(db_session, referred) == PENDING
    assert _grants(db_session) == 0
    assert _canonical_grants(db_session) == []
    assert credit_balance(db_session, referrer.id) == 0
    assert purchase.user_id == referred.id
    (trace,) = db_session.query(AdminAuditLog).filter_by(action_type="referral_reward_withheld")
    assert trace.reason == "REFERRER_ACCOUNT_DELETED"


def test_a_rewarded_refund_processed_is_a_no_op(db_session: Session, pair):
    """Machine A ``Rewarded --refund_processed--> Rewarded``: no revocation (FR-030)."""
    referrer, buyer = pair
    create_referral(db_session, referrer=referrer, referred=buyer)
    db_session.commit()
    payment = _credited_b(db_session, buyer, "evt_a_rf_paid")
    assert _state(db_session, buyer) == REWARDED
    before = (_grants(db_session), db_session.query(Referral).count())

    _deliver(db_session, "evt_a_rf", "charge.refunded", _charge_refunded(payment, 600))

    assert _state(db_session, buyer) == REWARDED
    assert (_grants(db_session), db_session.query(Referral).count()) == before
    assert credit_balance(db_session, referrer.id) == REFERRAL_REWARD_CREDITS


# --- Machine C: subscription (T049) ------------------------------------------------------
#
# Decided deviation from the table (not drift to fix): the period grant is triggered by ``invoice.paid``
# (research 2026-11-01 §3, OQ-4 ``A_stripe_mapping``), not by ``subscription_created`` or
# ``subscription_updated``, which only sync the record. So each "grant once" row is
# encoded as: the subscription event grants nothing, and the paid invoice for the period
# grants exactly once. ``operator_resolves`` is not supported for Machine C.

C_NONE, C_ACTIVE, C_NOT_ACTIVE = "NONE", "Active", "NotActive"
C_CANCEL_SCHEDULED, C_CANCELED = "CancelScheduled", "Canceled"


@pytest.fixture
def c_prices(monkeypatch: pytest.MonkeyPatch):
    """The webhook side reads ``core.config.settings``; point it at the test prices."""
    app_settings = _c_settings()
    monkeypatch.setattr(core_config, "settings", app_settings)
    return app_settings


def _c_state(db: Session, sub_id: str = "sub_c") -> str:
    record = _c_record(db, sub_id)
    if record is None:
        return C_NONE
    if record.status == "canceled":
        return C_CANCELED
    # Owner decision 43: any of the three live statuses can carry a scheduled cancel.
    if record.status in ("active", "trialing", "past_due") and record.cancel_at_period_end:
        return C_CANCEL_SCHEDULED
    return C_ACTIVE if record.status == "active" else C_NOT_ACTIVE


def _c_period_grants(db: Session) -> int:
    return db.query(SubscriptionPeriodGrantRecord).count()


def _c_snapshot(db: Session) -> tuple:
    record = _c_record(db, "sub_c")
    fields = None if record is None else (record.status, record.tier, record.cancel_at_period_end)
    return fields, _c_period_grants(db), db.query(CanonicalCreditLedgerEntryRecord).count()


def _c_in_state(db: Session, user: User, state: str) -> None:
    _c_customer(db, user)
    status = "past_due" if state == C_NOT_ACTIVE else "active"
    _c_deliver(
        db,
        "evt_c_setup",
        "customer.subscription.created",
        _c_subscription("sub_c", user.id, status=status),
    )
    if state == C_CANCEL_SCHEDULED:
        request_subscription_cancel(
            db, user=user, provider=FakeSubscriptionProvider(), app_settings=_c_settings()
        )
        db.commit()
    assert _c_state(db) == state


def test_c_none_choose_tier_enabled_opens_checkout(db_session: Session, pair, c_prices):
    _, buyer = pair
    provider = FakeSubscriptionProvider()
    started = start_subscription_checkout(
        db_session, user=buyer, tier="core", provider=provider, app_settings=_c_settings()
    )
    db_session.commit()
    assert started.checkout_url
    assert [name for name, _ in provider.calls] == ["customer", "session"]
    # CheckoutOpen writes no subscription record.
    assert _c_state(db_session) == C_NONE


@pytest.mark.parametrize(
    ("tier", "overrides", "error"),
    [
        ("platinum", {}, ValueError),
        ("core", {"enable_subscription_checkout": False}, CheckoutUnavailableError),
    ],
)
def test_c_none_choose_tier_invalid_or_disabled_is_refused(
    db_session: Session, pair, c_prices, tier, overrides, error
):
    _, buyer = pair
    provider = FakeSubscriptionProvider()
    with pytest.raises(error):
        start_subscription_checkout(
            db_session,
            user=buyer,
            tier=tier,
            provider=provider,
            app_settings=_c_settings(**overrides),
        )
    assert provider.calls == []
    assert _c_state(db_session) == C_NONE


def test_c_checkout_canceled_or_expired_writes_no_record(db_session: Session, pair, c_prices):
    _, buyer = pair
    _c_customer(db_session, buyer)
    intake = _c_deliver(
        db_session,
        "evt_c_expired",
        "checkout.session.expired",
        {"id": "cs_c", "object": "checkout.session", "mode": "subscription"},
    )
    assert (intake.record.status, intake.record.reason_code) == (
        "ignored",
        "SUBSCRIPTION_SESSION_NO_EFFECT",
    )
    assert _c_state(db_session) == C_NONE


def test_c_subscription_created_known_active_then_paid_invoice_grants_once(
    db_session: Session, pair, c_prices
):
    referrer, buyer = pair
    create_referral(db_session, referrer=referrer, referred=buyer)
    db_session.commit()
    _c_customer(db_session, buyer)

    _c_deliver(
        db_session,
        "evt_c_created",
        "customer.subscription.created",
        _c_subscription("sub_c", buyer.id),
    )
    assert _c_state(db_session) == C_ACTIVE
    assert _c_period_grants(db_session) == 0

    _c_deliver(db_session, "evt_c_paid", "invoice.paid", _c_invoice("in_c", "sub_c", buyer.id))
    assert _c_period_grants(db_session) == 1
    assert credit_balance(db_session, buyer.id) == 25
    # OQ-3 ``A_both``: the first paid invoice also goes through Machine A.
    assert _state(db_session, buyer) == REWARDED


def test_c_subscription_created_known_not_active_grants_nothing(
    db_session: Session, pair, c_prices
):
    _, buyer = pair
    _c_customer(db_session, buyer)
    _c_deliver(
        db_session,
        "evt_c_incomplete",
        "customer.subscription.created",
        _c_subscription("sub_c", buyer.id, status="incomplete"),
    )
    assert _c_state(db_session) == C_NOT_ACTIVE
    assert _c_period_grants(db_session) == 0
    assert credit_balance(db_session, buyer.id) == 0


@pytest.mark.parametrize("start", [C_NONE, C_ACTIVE, C_NOT_ACTIVE, C_CANCEL_SCHEDULED])
@pytest.mark.parametrize(
    "event_type", ["customer.subscription.created", "customer.subscription.updated"]
)
@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"customer": "cus_unknown"}, "CUSTOMER_NOT_FOUND"),
        ({"items": {"data": [{"price": {"id": "price_unmapped"}}]}}, "PRICE_UNKNOWN"),
    ],
)
def test_c_unknown_customer_or_price_is_unresolved(
    db_session: Session, pair, c_prices, start, event_type, change, reason
):
    _, buyer = pair
    if start == C_NONE:
        _c_customer(db_session, buyer)
    else:
        _c_in_state(db_session, buyer, start)
    before = _c_snapshot(db_session)
    obj = _c_subscription("sub_c", buyer.id, status="unpaid")
    obj.update(change)

    intake = _c_deliver(db_session, "evt_c_unknown", event_type, obj, created=TS + 50)

    assert (intake.record.status, intake.record.reason_code) == ("unresolved", reason)
    assert _c_state(db_session) == start
    assert _c_snapshot(db_session) == before


def test_c_active_updated_same_period_syncs_only(db_session: Session, pair, c_prices):
    _, buyer = pair
    _c_in_state(db_session, buyer, C_ACTIVE)
    _c_deliver(db_session, "evt_c_paid", "invoice.paid", _c_invoice("in_c", "sub_c", buyer.id))

    intake = _c_deliver(
        db_session,
        "evt_c_sync",
        "customer.subscription.updated",
        _c_subscription("sub_c", buyer.id, cancel=False),
        created=TS + 1,
    )

    assert (intake.record.status, intake.record.reason_code) == (
        "duplicate",
        "SUBSCRIPTION_UNCHANGED",
    )
    assert _c_state(db_session) == C_ACTIVE
    assert _c_period_grants(db_session) == 1


@pytest.mark.parametrize("start", [C_ACTIVE, C_NOT_ACTIVE])
def test_c_period_renewed_grants_the_new_period_once(
    db_session: Session, pair, c_prices, start
):
    _, buyer = pair
    _c_in_state(db_session, buyer, start)
    renewal = _c_invoice(
        "in_c2",
        "sub_c",
        buyer.id,
        start=P1 + MONTH,
        end=P1 + 2 * MONTH,
        billing_reason="subscription_cycle",
    )

    first = _c_deliver(db_session, "evt_c_renew", "invoice.paid", renewal)
    again = _c_deliver(db_session, "evt_c_renew_again", "invoice.paid", renewal)
    _c_deliver(
        db_session,
        "evt_c_now_active",
        "customer.subscription.updated",
        _c_subscription("sub_c", buyer.id, start=P1 + MONTH, end=P1 + 2 * MONTH),
        created=TS + 10,
    )

    assert first.record.status == "processed"
    assert (again.record.status, again.record.reason_code) == (
        "duplicate",
        "PERIOD_ALREADY_GRANTED",
    )
    assert _c_period_grants(db_session) == 1
    assert _c_state(db_session) == C_ACTIVE


def test_c_active_updated_not_active_becomes_not_active(db_session: Session, pair, c_prices):
    _, buyer = pair
    _c_in_state(db_session, buyer, C_ACTIVE)
    _c_deliver(
        db_session,
        "evt_c_past_due",
        "customer.subscription.updated",
        _c_subscription("sub_c", buyer.id, status="past_due"),
        created=TS + 1,
    )
    assert _c_state(db_session) == C_NOT_ACTIVE
    assert _c_period_grants(db_session) == 0


def test_c_not_active_updated_active_then_paid_period_grants_once(
    db_session: Session, pair, c_prices
):
    _, buyer = pair
    _c_in_state(db_session, buyer, C_NOT_ACTIVE)
    _c_deliver(
        db_session,
        "evt_c_back",
        "customer.subscription.updated",
        _c_subscription("sub_c", buyer.id),
        created=TS + 1,
    )
    assert _c_state(db_session) == C_ACTIVE
    assert _c_period_grants(db_session) == 0
    _c_deliver(db_session, "evt_c_paid", "invoice.paid", _c_invoice("in_c", "sub_c", buyer.id))
    assert _c_period_grants(db_session) == 1


def test_c_active_cancel_requested_becomes_cancel_scheduled(
    db_session: Session, pair, c_prices
):
    _, buyer = pair
    _c_in_state(db_session, buyer, C_ACTIVE)
    provider = FakeSubscriptionProvider()
    request_subscription_cancel(
        db_session, user=buyer, provider=provider, app_settings=_c_settings()
    )
    db_session.commit()
    assert _c_state(db_session) == C_CANCEL_SCHEDULED
    assert [name for name, _ in provider.calls] == ["cancel"]


@pytest.mark.parametrize("status", ["trialing", "past_due"])
def test_c_not_active_live_cancel_requested_becomes_cancel_scheduled(
    db_session: Session, pair, c_prices, status: str
):
    _, buyer = pair
    _c_customer(db_session, buyer)
    _c_deliver(
        db_session,
        "evt_c_live",
        "customer.subscription.created",
        _c_subscription("sub_c", buyer.id, status=status),
    )
    assert _c_state(db_session) == C_NOT_ACTIVE
    provider = FakeSubscriptionProvider()
    request_subscription_cancel(
        db_session, user=buyer, provider=provider, app_settings=_c_settings()
    )
    db_session.commit()
    assert _c_state(db_session) == C_CANCEL_SCHEDULED
    assert [name for name, _ in provider.calls] == ["cancel"]
    assert _c_period_grants(db_session) == 0


@pytest.mark.parametrize("start", [C_ACTIVE, C_NOT_ACTIVE, C_CANCEL_SCHEDULED])
def test_c_subscription_deleted_becomes_canceled_and_keeps_credits(
    db_session: Session, pair, c_prices, start
):
    _, buyer = pair
    _c_in_state(db_session, buyer, start)
    _c_deliver(db_session, "evt_c_paid", "invoice.paid", _c_invoice("in_c", "sub_c", buyer.id))
    balance = credit_balance(db_session, buyer.id)

    _c_deliver(
        db_session,
        "evt_c_deleted",
        "customer.subscription.deleted",
        _c_subscription("sub_c", buyer.id, status="canceled"),
        created=TS + 20,
    )

    assert _c_state(db_session) == C_CANCELED
    assert credit_balance(db_session, buyer.id) == balance == 25


def test_c_unresolved_operator_resolves_is_not_supported(db_session: Session, pair, c_prices):
    from canon.checkout import ResolveRefusedError

    _, buyer = pair
    admin = _user(db_session, "c-admin")
    intake = _c_deliver(
        db_session, "evt_c_orphan", "invoice.paid", _c_invoice("in_c", "sub_c", buyer.id)
    )
    assert (intake.record.status, intake.record.reason_code) == (
        "unresolved",
        "CUSTOMER_NOT_FOUND",
    )

    with pytest.raises(ResolveRefusedError, match="RESOLVE_NOT_SUPPORTED"):
        resolve_unresolved_event(
            db_session,
            "evt_c_orphan",
            provider=None,
            app_settings=_settings(),
            actor_user_id=admin.id,
            actor_role="Admin",
            reason="mapped the customer",
        )
    db_session.rollback()
    assert db_session.get(StripeEventRecordModel, "evt_c_orphan").status == "unresolved"
    assert _c_period_grants(db_session) == 0


def test_c_second_grant_for_the_same_period_is_illegal(db_session: Session, pair, c_prices):
    _, buyer = pair
    _c_in_state(db_session, buyer, C_ACTIVE)
    _c_deliver(db_session, "evt_c_paid", "invoice.paid", _c_invoice("in_c", "sub_c", buyer.id))
    second = _c_deliver(
        db_session, "evt_c_paid_b", "invoice.paid", _c_invoice("in_c_b", "sub_c", buyer.id)
    )
    assert second.record.status == "duplicate"
    assert _c_period_grants(db_session) == 1
    assert credit_balance(db_session, buyer.id) == 25


def test_c_canceled_invoice_paid_grants_once_and_stays_canceled(
    db_session: Session, pair, c_prices
):
    """Owner decision 42. ``Canceled`` to ``Canceled``: the period is granted, not refused."""
    _, buyer = pair
    _c_in_state(db_session, buyer, C_ACTIVE)
    _c_deliver(
        db_session,
        "evt_c_gone",
        "customer.subscription.deleted",
        _c_subscription("sub_c", buyer.id, status="canceled"),
    )
    assert _c_state(db_session) == C_CANCELED

    paid = _c_deliver(db_session, "evt_c_late", "invoice.paid", _c_invoice("in_c", "sub_c", buyer.id))

    assert paid.record.status == "processed"
    assert _c_state(db_session) == C_CANCELED
    assert _c_period_grants(db_session) == 1
    assert credit_balance(db_session, buyer.id) == 25


def test_c_canceled_to_active_is_illegal(db_session: Session, pair, c_prices):
    _, buyer = pair
    _c_in_state(db_session, buyer, C_ACTIVE)
    _c_deliver(
        db_session,
        "evt_c_deleted",
        "customer.subscription.deleted",
        _c_subscription("sub_c", buyer.id, status="canceled"),
        created=TS + 1,
    )
    _c_deliver(
        db_session,
        "evt_c_revive",
        "customer.subscription.updated",
        _c_subscription("sub_c", buyer.id),
        created=TS + 2,
    )
    assert _c_state(db_session) == C_CANCELED


def test_c_grant_for_an_unknown_tier_or_customer_is_illegal(
    db_session: Session, pair, c_prices
):
    _, buyer = pair
    unknown_customer = _c_deliver(
        db_session, "evt_c_x1", "invoice.paid", _c_invoice("in_x1", "sub_c", buyer.id)
    )
    _c_customer(db_session, buyer)
    obj = _c_invoice("in_x2", "sub_c", buyer.id)
    obj["lines"]["data"][0]["price"] = {"id": "price_unmapped"}
    unknown_tier = _c_deliver(db_session, "evt_c_x2", "invoice.paid", obj)

    assert unknown_customer.record.reason_code == "CUSTOMER_NOT_FOUND"
    assert unknown_tier.record.reason_code == "PRICE_UNKNOWN"
    assert _c_period_grants(db_session) == 0
    assert credit_balance(db_session, buyer.id) == 0


def test_c_tier_from_client_input_is_illegal(db_session: Session, pair, c_prices):
    """The tier chosen at checkout never becomes the stored tier; the price decides."""
    _, buyer = pair
    start_subscription_checkout(
        db_session,
        user=buyer,
        tier="studio",
        provider=FakeSubscriptionProvider(),
        app_settings=_c_settings(),
    )
    db_session.commit()
    obj = _c_subscription(
        "sub_c", buyer.id, metadata={"user_id": str(buyer.id), "tier": "studio"}
    )

    _c_deliver(db_session, "evt_c_created", "customer.subscription.created", obj)

    assert _c_record(db_session, "sub_c").tier == "core"


# --- Machine C entitlement: tier and STUDIO spending (T050) -------------------------------
#
# Not rows of the table: what each Machine C state entitles (OQ-4 ``A_stripe_mapping``).
# Active, CancelScheduled and a ``past_due`` NotActive keep the subscription's tier; any
# other NotActive status and Canceled resolve to FREE. A STUDIO
# period grant covers exports without a debit up to its fair-use cap (OQ-8).


@pytest.fixture
def c_default_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    import canon.entitlements as entitlements

    # Not ``free``, so a lapsed subscription resolving to FREE is told apart from the
    # default a user who never subscribed gets.
    monkeypatch.setattr(entitlements.settings, "design_engine_default_tier", "pro")


def _c_studio_user(db: Session, status: str = "active") -> User:
    from tests.unit.test_canon_contracts import _persist_hierarchy

    user, _ = _persist_hierarchy(db)
    _c_customer(db, user)
    _c_deliver(
        db,
        "evt_c_studio",
        "customer.subscription.created",
        _c_subscription("sub_c", user.id, tier="studio", status=status),
    )
    return user


@pytest.mark.parametrize(
    ("status", "tier"),
    [
        ("active", "studio"),
        ("trialing", "studio"),
        ("past_due", "studio"),
        ("incomplete", "free"),
        ("unpaid", "free"),
        ("paused", "free"),
    ],
)
def test_c_state_entitles_the_oq4_tier(
    db_session: Session, c_prices, c_default_tier, status, tier
):
    from canon.entitlements import resolve_user_tier

    user = _c_studio_user(db_session, status=status)
    assert resolve_user_tier(db_session, user.id) == tier


def test_c_cancel_scheduled_keeps_the_tier_and_canceled_falls_back(
    db_session: Session, c_prices, c_default_tier
):
    from canon.entitlements import resolve_user_tier

    user = _c_studio_user(db_session)
    request_subscription_cancel(
        db_session, user=user, provider=FakeSubscriptionProvider(), app_settings=_c_settings()
    )
    db_session.commit()
    assert _c_state(db_session) == C_CANCEL_SCHEDULED
    assert resolve_user_tier(db_session, user.id) == "studio"

    _c_deliver(
        db_session,
        "evt_c_deleted",
        "customer.subscription.deleted",
        _c_subscription("sub_c", user.id, tier="studio", status="canceled"),
        created=TS + 20,
    )
    assert _c_state(db_session) == C_CANCELED
    assert resolve_user_tier(db_session, user.id) == "free"


def test_c_studio_paid_period_spends_against_the_fair_use_cap(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    from datetime import datetime, timezone

    from canon.contracts import ExportRequest
    from canon.exports import request_export

    monkeypatch.setattr(
        core_config, "settings", _c_settings(subscription_studio_fair_use_exports_per_period=1)
    )
    user = _c_studio_user(db_session)
    _c_deliver(
        db_session,
        "evt_c_paid",
        "invoice.paid",
        _c_invoice("in_c", "sub_c", user.id, tier="studio"),
    )
    at = datetime.fromtimestamp(P1 + 86_400, tz=timezone.utc)

    def export(key: str):
        return request_export(
            db_session,
            ExportRequest(
                request_id=key,
                user_id=user.id,
                source_run_id="run-1",
                source_rig_revision_id="rig-rev-1",
                formats=("pdf",),
                license="personal",
                credit_cost=3,
                idempotency_key=key,
                requested_at=at,
            ),
            artifact_manifest_hash="a" * 64,
            export_version="1.0.0",
        )

    first = export("studio-1")
    db_session.commit()
    assert (first.credit_cost, first.ledger_entry_id) == (0, None)
    assert first.subscription_grant_id == db_session.query(SubscriptionPeriodGrantRecord).one().id
    with pytest.raises(ExportBoundaryError, match="FAIR_USE_CAP_REACHED"):
        export("studio-2")
    db_session.rollback()
    assert credit_balance(db_session, user.id) == 0


# --- Machine B gaps filled by T010: async settlement, failed refunds, invoice refunds ------


def test_b_completed_unpaid_waits_and_async_success_credits_once(db_session: Session, pair):
    referrer, buyer = pair
    create_referral(db_session, referrer=referrer, referred=buyer)
    db_session.commit()
    payment = _open_checkout(db_session, buyer)

    waiting = _deliver(
        db_session,
        "evt_b_wait",
        "checkout.session.completed",
        _session_object(payment, payment_status="unpaid"),
    )
    assert waiting.record.status == "processed"
    assert _b_state(db_session, payment) == CHECKOUT_OPEN
    assert payment.status == "pending"
    assert _purchase_entries(db_session) == 0
    assert _state(db_session, buyer) == PENDING

    _deliver(
        db_session,
        "evt_b_settled",
        "checkout.session.async_payment_succeeded",
        _session_object(payment),
    )
    assert _b_state(db_session, payment) == CREDITED
    assert _purchase_entries(db_session) == 1
    assert _state(db_session, buyer) == REWARDED

    again = _deliver(
        db_session,
        "evt_b_settled_again",
        "checkout.session.async_payment_succeeded",
        _session_object(payment),
    )
    assert again.record.status == "duplicate"
    assert _purchase_entries(db_session) == 1


def test_b_pending_async_failure_is_abandoned_with_status_failed(db_session: Session, pair):
    _, buyer = pair
    payment = _open_checkout(db_session, buyer)
    unpaid = _session_object(payment, payment_status="unpaid")
    _deliver(db_session, "evt_b_pf_wait", "checkout.session.completed", unpaid)
    assert payment.status == "pending"

    _deliver(db_session, "evt_b_pf_fail", "checkout.session.async_payment_failed", unpaid)

    assert _b_state(db_session, payment) == ABANDONED
    assert payment.status == "failed"
    assert _purchase_entries(db_session) == 0


def test_b_credited_refund_failed_goes_to_an_operator_without_reversal(db_session: Session, pair):
    _, buyer = pair
    payment = _credited_b(db_session, buyer, "evt_b_rf_paid")
    failed = {
        "id": "re_b",
        "object": "refund",
        "payment_intent": payment.provider_payment_id,
        "amount": 300,
        "currency": payment.currency,
        "status": "failed",
    }

    intake = _deliver(db_session, "evt_b_rf", "refund.failed", failed)

    assert (intake.record.status, intake.record.reason_code) == ("unresolved", "REFUND_FAILED")
    assert _b_state(db_session, payment) == CREDITED
    assert _refund_entries(db_session) == []


def test_b_refund_for_a_subscription_invoice_payment_is_unresolved(
    db_session: Session, pair, c_prices
):
    """Gap, not a machine row: no machine handles a subscription invoice refund.

    A ``charge.refunded`` for an invoice payment finds no ``provider_payments`` record, so
    it waits for an operator (``PAYMENT_RECORD_NOT_FOUND``) and changes nothing.
    """
    _, buyer = pair
    _c_in_state(db_session, buyer, C_ACTIVE)
    _c_deliver(db_session, "evt_c_inv", "invoice.paid", _c_invoice("in_c", "sub_c", buyer.id))
    before = _c_snapshot(db_session)
    charge = {
        "id": "ch_invoice",
        "object": "charge",
        "payment_intent": "pi_invoice",
        "customer": f"cus_{buyer.id}",
        "amount": 499,
        "amount_refunded": 499,
        "currency": "usd",
        "invoice": "in_c",
    }

    intake = _deliver(db_session, "evt_c_inv_refund", "charge.refunded", charge)

    assert (intake.record.status, intake.record.reason_code) == (
        "unresolved",
        "PAYMENT_RECORD_NOT_FOUND",
    )
    assert _c_snapshot(db_session) == before
    assert credit_balance(db_session, buyer.id) == 25


# --- Append-only: what the code enforces (FR-008, FR-029, research R2) --------------------
#
# Enforced: the canonical ledger rejects UPDATE and DELETE with Postgres triggers
# (migration ``20261029_ledger_append_only``, proved on Postgres by
# ``tests/acceptance/test_ledger_append_only.py``); ledger idempotency keys, grant keys,
# grant invoice ids and (subscription, period) pairs are unique; a stripe event id replayed
# with a different payload is refused. SQLite, which this file runs on, has no triggers.
# Not enforced anywhere (reported as gaps, not asserted): UPDATE and DELETE on the
# ``Referral`` rows, the legacy ``credits_ledger``, ``subscription_period_grants`` and
# ``stripe_event_records`` (whose status and reason code are written after intake by
# design). The tests below show that the commerce code paths append and never rewrite.


def _ledger_rows(db: Session) -> dict[str, tuple]:
    db.expire_all()
    return {
        row.id: (row.user_id, row.delta, row.entry_type, row.idempotency_key, row.created_at)
        for row in db.query(CanonicalCreditLedgerEntryRecord).all()
    }


def _assert_only_appended(before: dict[str, tuple], after: dict[str, tuple]) -> None:
    assert len(after) > len(before)
    assert {key: after[key] for key in before} == before


def test_append_only_purchase_refund_and_reversal_only_append_ledger_rows(
    db_session: Session, pair
):
    _, buyer = pair
    payment = _credited_b(db_session, buyer, "evt_ao_paid")
    after_purchase = _ledger_rows(db_session)
    assert len(after_purchase) == 1

    _deliver(db_session, "evt_ao_r1", "charge.refunded", _charge_refunded(payment, 300))
    after_partial = _ledger_rows(db_session)
    _assert_only_appended(after_purchase, after_partial)

    _deliver(db_session, "evt_ao_r2", "charge.refunded", _charge_refunded(payment, 600))
    after_full = _ledger_rows(db_session)
    _assert_only_appended(after_partial, after_full)

    # A repeated refund changes nothing at all.
    _deliver(db_session, "evt_ao_r3", "charge.refunded", _charge_refunded(payment, 600))
    assert _ledger_rows(db_session) == after_full
    assert sorted(row[1] for row in after_full.values()) == [-15, -15, payment.credits]


def _grant_rows(db: Session) -> dict[str, tuple]:
    db.expire_all()
    return {
        row.id: (
            row.grant_key,
            row.provider_invoice_id,
            row.tier,
            row.period_start,
            row.period_end,
            row.credits,
            row.unlimited,
        )
        for row in db.query(SubscriptionPeriodGrantRecord).all()
    }


def test_append_only_subscription_grants_are_never_rewritten(db_session: Session, pair, c_prices):
    _, buyer = pair
    _c_in_state(db_session, buyer, C_ACTIVE)
    _c_deliver(db_session, "evt_ao_c1", "invoice.paid", _c_invoice("in_c1", "sub_c", buyer.id))
    first = _grant_rows(db_session)
    ledger_first = _ledger_rows(db_session)
    assert len(first) == 1

    # A second invoice for the same period, a status sync and a cancellation add nothing.
    _c_deliver(db_session, "evt_ao_c2", "invoice.paid", _c_invoice("in_c2", "sub_c", buyer.id))
    _c_deliver(
        db_session,
        "evt_ao_c3",
        "customer.subscription.updated",
        _c_subscription("sub_c", buyer.id, status="past_due"),
        created=TS + 5,
    )
    _c_deliver(
        db_session,
        "evt_ao_c4",
        "customer.subscription.deleted",
        _c_subscription("sub_c", buyer.id, status="canceled"),
        created=TS + 6,
    )
    assert _grant_rows(db_session) == first
    assert _ledger_rows(db_session) == ledger_first


def test_append_only_next_period_appends_a_second_grant(db_session: Session, pair, c_prices):
    _, buyer = pair
    _c_in_state(db_session, buyer, C_ACTIVE)
    _c_deliver(db_session, "evt_ao_p1", "invoice.paid", _c_invoice("in_p1", "sub_c", buyer.id))
    first = _grant_rows(db_session)

    renewal = _c_invoice("in_p2", "sub_c", buyer.id, start=P1 + MONTH, end=P1 + 2 * MONTH)
    _c_deliver(db_session, "evt_ao_p2", "invoice.paid", renewal)

    after = _grant_rows(db_session)
    assert len(after) == 2
    assert {key: after[key] for key in first} == first


def test_append_only_ledger_and_grant_keys_are_unique(db_session: Session, pair, c_prices):
    from sqlalchemy.exc import IntegrityError

    _, buyer = pair
    payment = _credited_b(db_session, buyer, "evt_ao_u_paid")
    existing = db_session.query(CanonicalCreditLedgerEntryRecord).one()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                CanonicalCreditLedgerEntryRecord(
                    id="dup-entry",
                    user_id=buyer.id,
                    delta=payment.credits,
                    entry_type="purchase",
                    idempotency_key=existing.idempotency_key,
                    created_at=existing.created_at,
                )
            )
    db_session.rollback()
    assert db_session.query(CanonicalCreditLedgerEntryRecord).count() == 1

    other = _user(db_session, "grant-dupe")
    _c_in_state(db_session, other, C_ACTIVE)
    _c_deliver(db_session, "evt_ao_u_g", "invoice.paid", _c_invoice("in_u", "sub_c", other.id))
    grant = db_session.query(SubscriptionPeriodGrantRecord).one()
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(
                SubscriptionPeriodGrantRecord(
                    id="dup-grant",
                    subscription_record_id=grant.subscription_record_id,
                    user_id=grant.user_id,
                    grant_key=grant.grant_key,
                    provider_invoice_id="in_other",
                    tier=grant.tier,
                    period_start=grant.period_start,
                    period_end=grant.period_end,
                    credits=grant.credits,
                    unlimited=grant.unlimited,
                    fair_use_export_cap=grant.fair_use_export_cap,
                )
            )
    db_session.rollback()
    assert db_session.query(SubscriptionPeriodGrantRecord).count() == 1


def test_append_only_stripe_event_replay_with_a_new_payload_is_refused(
    db_session: Session, pair
):
    _, buyer = pair
    payment = _open_checkout(db_session, buyer)
    _deliver(db_session, "evt_ao_e", "checkout.session.completed", _session_object(payment))
    stored = db_session.get(StripeEventRecordModel, "evt_ao_e")
    identity = (stored.event_type, stored.payload_hash, stored.livemode, stored.received_at)

    with pytest.raises(ExportBoundaryError, match="WEBHOOK_REPLAY_CONFLICT"):
        _deliver(
            db_session,
            "evt_ao_e",
            "checkout.session.completed",
            _session_object(payment, amount_total=1),
        )
    db_session.rollback()

    db_session.expire_all()
    stored = db_session.get(StripeEventRecordModel, "evt_ao_e")
    assert (stored.event_type, stored.payload_hash, stored.livemode, stored.received_at) == identity
    assert stored.status == "processed"
    assert _purchase_entries(db_session) == 1


def test_append_only_migration_installs_ledger_triggers_on_postgres():
    """The enforced rule: a Postgres trigger denies UPDATE and DELETE on the ledger."""
    import re
    from pathlib import Path

    versions = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    source = (versions / "20261029_ledger_append_only.py").read_text()
    bound = re.findall(r"CREATE TRIGGER \w+\s+BEFORE (UPDATE|DELETE) ON (\w+)", source)
    assert sorted(bound) == [
        ("DELETE", "canonical_credit_ledger"),
        ("UPDATE", "canonical_credit_ledger"),
    ]
