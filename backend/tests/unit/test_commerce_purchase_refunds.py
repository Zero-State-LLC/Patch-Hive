"""Spec 004 OQ-2 ``A_reverse_unspent`` (T053): refunds and disputes of a Machine B payment.

Every payment is credited through a fake-provider checkout and a signed
``checkout.session.completed``; refunds and disputes arrive as signed fixture events
(``receive_stripe_webhook``). No network, no live keys.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy.orm import Session

from canon.checkout import credits_for_refund, refund_key
from canon.exports import credit_balance, reconcile_ledger
from canon.models import CanonicalCreditLedgerEntryRecord, ProviderPaymentRecord
from monetization.models import CreditsLedger, Referral
from monetization.referrals import REFERRAL_REWARD_CREDITS, create_referral
from tests.unit.test_commerce_credit_checkout import (
    _deliver,
    _open_checkout,
    _session_object,
    _user,
)

# 30 credits cost max(500, 30 * 20) = 600 cents (OQ-1, provisional).


def _credited(session: Session, name: str = "refund-buyer", credits: int = 30):
    user = _user(session, name)
    payment = _open_checkout(session, user, credits=credits)
    intake = _deliver(
        session, f"evt_paid_{name}", "checkout.session.completed", _session_object(payment)
    )
    assert intake.record.status == "processed"
    session.refresh(payment)
    return user, payment


def _charge(payment: ProviderPaymentRecord, refunded: int, **overrides: Any) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "id": f"ch_{payment.checkout_session_id}",
        "object": "charge",
        "payment_intent": payment.provider_payment_id,
        "customer": f"cus_{payment.user_id}",
        "amount": payment.amount_cents,
        "amount_refunded": refunded,
        "currency": payment.currency,
        "refunded": refunded == payment.amount_cents,
    }
    obj.update(overrides)
    return obj


def _spend(session: Session, user_id: int, credits: int, key: str) -> None:
    session.add(
        CanonicalCreditLedgerEntryRecord(
            id=f"debit-{key}",
            user_id=user_id,
            delta=-credits,
            entry_type="debit",
            idempotency_key=f"test-spend:{key}",
            export_id=None,
            created_at=datetime.now(timezone.utc),
        )
    )
    session.commit()


def _refunds(session: Session) -> list[CanonicalCreditLedgerEntryRecord]:
    return (
        session.query(CanonicalCreditLedgerEntryRecord)
        .filter_by(entry_type="refund")
        .order_by(CanonicalCreditLedgerEntryRecord.created_at)
        .all()
    )


# --- the rounding rule ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("credits", "amount", "refunded", "expected"),
    [
        (30, 600, 600, 30),  # a full refund takes back every credit
        (30, 600, 300, 15),
        (30, 600, 100, 5),
        (30, 600, 110, 5),  # 5.5 rounds down
        (30, 600, 19, 0),  # less than one credit's share takes back nothing
        (30, 600, 599, 29),
        (1, 500, 499, 0),  # the minimum charge: one credit for 500 cents
        (1, 500, 500, 1),
        (30, 600, 9999, 30),  # never more than purchased
    ],
)
def test_a_refund_takes_back_credits_in_proportion_rounded_down(
    credits: int, amount: int, refunded: int, expected: int
) -> None:
    assert (
        credits_for_refund(credits=credits, amount_cents=amount, refunded_cents=refunded)
        == expected
    )


def test_cumulative_rounding_never_adds_up_across_partial_refunds() -> None:
    """Three refunds of 110 cents take back floor(30 * 330 / 600) = 16, not 3 * 5 = 15."""
    taken = 0
    for cumulative in (110, 220, 330):
        taken = credits_for_refund(credits=30, amount_cents=600, refunded_cents=cumulative)
    assert taken == 16


# --- charge.refunded ----------------------------------------------------------------------


def test_a_full_refund_of_unspent_credits_reverses_every_credit(db_session: Session) -> None:
    user, payment = _credited(db_session)

    intake = _deliver(db_session, "evt_refund_full", "charge.refunded", _charge(payment, 600))

    assert (intake.record.status, intake.record.reason_code) == ("processed", None)
    (entry,) = _refunds(db_session)
    assert (entry.user_id, entry.delta, entry.export_id) == (user.id, -30, None)
    assert entry.idempotency_key == refund_key(payment.provider_payment_id, 600)
    assert credit_balance(db_session, user.id) == 0
    db_session.refresh(payment)
    assert payment.status == "refunded"
    assert (
        payment.refunded_cents,
        payment.refund_reversed_credits,
        payment.refund_unrecovered_credits,
    ) == (600, 30, 0)
    # Canonical only: the legacy ledger keeps its one Purchase row.
    assert db_session.query(CreditsLedger).count() == 1


def test_partial_refunds_reverse_in_steps_by_the_cumulative_amount(db_session: Session) -> None:
    user, payment = _credited(db_session)

    first = _deliver(db_session, "evt_refund_p1", "charge.refunded", _charge(payment, 110))
    db_session.refresh(payment)
    assert (first.record.status, payment.status) == ("processed", "partially_refunded")
    assert credit_balance(db_session, user.id) == 25

    second = _deliver(db_session, "evt_refund_p2", "charge.refunded", _charge(payment, 330))

    assert second.record.status == "processed"
    assert [entry.delta for entry in _refunds(db_session)] == [-5, -11]
    assert credit_balance(db_session, user.id) == 30 - 16
    db_session.refresh(payment)
    assert (payment.status, payment.refunded_cents, payment.refund_reversed_credits) == (
        "partially_refunded",
        330,
        16,
    )

    rest = _deliver(db_session, "evt_refund_p3", "charge.refunded", _charge(payment, 600))
    assert rest.record.status == "processed"
    assert credit_balance(db_session, user.id) == 0
    db_session.refresh(payment)
    assert (payment.status, payment.refund_reversed_credits) == ("refunded", 30)


def test_a_refund_too_small_for_one_credit_moves_the_total_but_writes_no_entry(
    db_session: Session,
) -> None:
    user, payment = _credited(db_session)

    intake = _deliver(db_session, "evt_refund_tiny", "charge.refunded", _charge(payment, 10))

    assert intake.record.status == "processed"
    assert _refunds(db_session) == []
    assert credit_balance(db_session, user.id) == 30
    db_session.refresh(payment)
    assert (payment.status, payment.refunded_cents) == ("partially_refunded", 10)


@pytest.mark.parametrize(
    "event_id",
    [
        "evt_refund_dup",  # the same event redelivered
        "evt_refund_dup_other",  # a new event id with the same cumulative amount
    ],
)
def test_a_repeated_refund_reverses_nothing_more(db_session: Session, event_id: str) -> None:
    user, payment = _credited(db_session)
    _deliver(db_session, "evt_refund_dup", "charge.refunded", _charge(payment, 300))

    again = _deliver(db_session, event_id, "charge.refunded", _charge(payment, 300))

    if event_id == "evt_refund_dup":
        assert again.duplicate is True
    else:
        assert (again.record.status, again.record.reason_code) == (
            "duplicate",
            "REFUND_ALREADY_RECORDED",
        )
    assert len(_refunds(db_session)) == 1
    assert credit_balance(db_session, user.id) == 15


def test_an_older_cumulative_amount_delivered_late_reverses_nothing(db_session: Session) -> None:
    user, payment = _credited(db_session)
    _deliver(db_session, "evt_refund_new", "charge.refunded", _charge(payment, 300))

    late = _deliver(db_session, "evt_refund_old", "charge.refunded", _charge(payment, 100))

    assert (late.record.status, late.record.reason_code) == ("duplicate", "REFUND_ALREADY_RECORDED")
    assert credit_balance(db_session, user.id) == 15
    db_session.refresh(payment)
    assert payment.refunded_cents == 300


def test_a_refund_after_partial_spend_reverses_only_the_unspent_remainder(
    db_session: Session,
) -> None:
    """OQ-2: never negative; the spent part goes to the operator, the rest commits."""
    user, payment = _credited(db_session)
    _spend(db_session, user.id, 20, "partial")

    intake = _deliver(db_session, "evt_refund_spent", "charge.refunded", _charge(payment, 600))

    assert (intake.record.status, intake.record.reason_code) == (
        "unresolved",
        "REFUND_EXCEEDS_UNSPENT",
    )
    (entry,) = _refunds(db_session)
    assert entry.delta == -10
    assert credit_balance(db_session, user.id) == 0
    db_session.refresh(payment)
    assert payment.status == "refunded"
    assert (payment.refund_reversed_credits, payment.refund_unrecovered_credits) == (10, 20)

    # A repeat changes nothing, and never takes the balance below zero.
    again = _deliver(db_session, "evt_refund_spent_2", "charge.refunded", _charge(payment, 600))
    assert again.record.status == "duplicate"
    assert credit_balance(db_session, user.id) == 0


def test_a_refund_after_every_credit_was_spent_reverses_nothing(db_session: Session) -> None:
    user, payment = _credited(db_session)
    _spend(db_session, user.id, 30, "all")

    intake = _deliver(db_session, "evt_refund_none", "charge.refunded", _charge(payment, 300))

    assert (intake.record.status, intake.record.reason_code) == (
        "unresolved",
        "REFUND_EXCEEDS_UNSPENT",
    )
    assert _refunds(db_session) == []
    assert credit_balance(db_session, user.id) == 0
    db_session.refresh(payment)
    assert (payment.status, payment.refunded_cents) == ("partially_refunded", 300)
    assert (payment.refund_reversed_credits, payment.refund_unrecovered_credits) == (0, 15)


def test_the_cap_is_the_current_balance_including_other_credits(db_session: Session) -> None:
    """Credits are fungible: unspent credits from another purchase cover the reversal."""
    user, first = _credited(db_session)
    second = _open_checkout(db_session, user, credits=30)
    _deliver(db_session, "evt_paid_second", "checkout.session.completed", _session_object(second))
    _spend(db_session, user.id, 30, "first-batch")

    intake = _deliver(db_session, "evt_refund_first", "charge.refunded", _charge(first, 600))

    assert intake.record.status == "processed"
    assert credit_balance(db_session, user.id) == 0


def test_a_refund_never_revokes_the_referrers_reward(db_session: Session) -> None:
    """FR-030, spec 004 Machine A ``Rewarded --refund_processed--> Rewarded``."""
    referrer = _user(db_session, "refund-referrer")
    buyer = _user(db_session, "refund-referred")
    create_referral(db_session, referrer=referrer, referred=buyer)
    db_session.commit()
    payment = _open_checkout(db_session, buyer)
    _deliver(db_session, "evt_paid_ref", "checkout.session.completed", _session_object(payment))
    db_session.refresh(payment)

    _deliver(db_session, "evt_refund_ref", "charge.refunded", _charge(payment, 600))

    assert credit_balance(db_session, referrer.id) == REFERRAL_REWARD_CREDITS
    assert credit_balance(db_session, buyer.id) == 0
    assert db_session.query(Referral).filter_by(status="Rewarded").count() == 1


@pytest.mark.parametrize("refunded", [300, 600])
def test_a_late_completion_of_a_refunded_payment_credits_nothing(
    db_session: Session, refunded: int
) -> None:
    user, payment = _credited(db_session)
    _deliver(db_session, "evt_refund_first", "charge.refunded", _charge(payment, refunded))
    balance = credit_balance(db_session, user.id)

    late = _deliver(
        db_session,
        "evt_paid_late",
        "checkout.session.async_payment_succeeded",
        _session_object(payment),
    )

    assert (late.record.status, late.record.reason_code) == (
        "duplicate",
        "PAYMENT_ALREADY_RECORDED",
    )
    assert credit_balance(db_session, user.id) == balance


def test_a_purchase_refund_is_not_counted_as_an_export_reversal(db_session: Session) -> None:
    user, payment = _credited(db_session)
    _deliver(db_session, "evt_refund_recon", "charge.refunded", _charge(payment, 600))

    report = reconcile_ledger(db_session, user.id)

    assert (report.balance, report.reversals, report.anomalies) == (0, 0, ())


def _unresolved_cases() -> list[tuple[str, Any, str]]:
    return [
        ("unknown-payment", lambda p: {"payment_intent": "pi_unknown"}, "PAYMENT_RECORD_NOT_FOUND"),
        ("no-payment-id", lambda p: {"payment_intent": None}, "PAYMENT_ID_MISSING"),
        ("not-a-charge", lambda p: {"object": "refund"}, "EVENT_PAYLOAD_MALFORMED"),
        ("no-refunded-amount", lambda p: {"amount_refunded": None}, "EVENT_PAYLOAD_MALFORMED"),
        ("text-amount", lambda p: {"amount_refunded": "600"}, "EVENT_PAYLOAD_MALFORMED"),
        ("negative-amount", lambda p: {"amount_refunded": -1}, "EVENT_PAYLOAD_MALFORMED"),
        ("bool-amount", lambda p: {"amount": True}, "EVENT_PAYLOAD_MALFORMED"),
        ("other-amount", lambda p: {"amount": 601}, "AMOUNT_MISMATCH"),
        ("other-currency", lambda p: {"currency": "eur"}, "AMOUNT_MISMATCH"),
        ("more-than-paid", lambda p: {"amount": 600, "amount_refunded": 601}, "AMOUNT_MISMATCH"),
        ("other-customer", lambda p: {"customer": "cus_other"}, "CUSTOMER_MISMATCH"),
    ]


@pytest.mark.parametrize(
    ("change", "reason"),
    [(case[1], case[2]) for case in _unresolved_cases()],
    ids=[case[0] for case in _unresolved_cases()],
)
def test_an_unmappable_refund_is_unresolved_and_reverses_nothing(
    db_session: Session, change, reason: str
) -> None:
    user, payment = _credited(db_session)

    intake = _deliver(
        db_session, "evt_refund_bad", "charge.refunded", _charge(payment, 600, **change(payment))
    )

    assert (intake.record.status, intake.record.reason_code) == ("unresolved", reason)
    assert _refunds(db_session) == []
    assert credit_balance(db_session, user.id) == 30
    db_session.refresh(payment)
    assert (payment.status, payment.refunded_cents) == ("credited", 0)


@pytest.mark.parametrize(
    "event_type", ["checkout.session.expired", "checkout.session.async_payment_failed"]
)
def test_a_refund_of_a_payment_never_credited_goes_to_an_operator(
    db_session: Session, event_type: str
) -> None:
    user = _user(db_session, "never-credited")
    payment = _open_checkout(db_session, user)
    pending = _session_object(payment, payment_status="unpaid")
    _deliver(db_session, "evt_unpaid", "checkout.session.completed", pending)
    _deliver(db_session, "evt_closed", event_type, pending)
    db_session.refresh(payment)
    assert payment.provider_payment_id is not None

    intake = _deliver(db_session, "evt_refund_closed", "charge.refunded", _charge(payment, 600))

    assert (intake.record.status, intake.record.reason_code) == (
        "unresolved",
        "PAYMENT_STATE_CONFLICT",
    )
    assert _refunds(db_session) == []
    assert credit_balance(db_session, user.id) == 0


# --- refund.failed and disputes --------------------------------------------------------------


def _refund_object(payment: ProviderPaymentRecord, **overrides: Any) -> dict[str, Any]:
    obj = {
        "id": "re_failed",
        "object": "refund",
        "payment_intent": payment.provider_payment_id,
        "amount": 300,
        "currency": payment.currency,
        "status": "failed",
    }
    obj.update(overrides)
    return obj


def _dispute_object(payment: ProviderPaymentRecord, **overrides: Any) -> dict[str, Any]:
    obj = {
        "id": "dp_1",
        "object": "dispute",
        "payment_intent": payment.provider_payment_id,
        "charge": f"ch_{payment.checkout_session_id}",
        "amount": payment.amount_cents,
        "currency": payment.currency,
        "reason": "fraudulent",
        "status": "needs_response",
    }
    obj.update(overrides)
    return obj


def test_a_failed_refund_goes_to_an_operator_and_restores_nothing(db_session: Session) -> None:
    user, payment = _credited(db_session)
    _deliver(db_session, "evt_refund_then_fail", "charge.refunded", _charge(payment, 300))

    intake = _deliver(db_session, "evt_refund_failed", "refund.failed", _refund_object(payment))

    assert (intake.record.status, intake.record.reason_code) == ("unresolved", "REFUND_FAILED")
    assert credit_balance(db_session, user.id) == 15
    db_session.refresh(payment)
    assert payment.refunded_cents == 300


def test_a_dispute_goes_to_an_operator_with_no_reversal(db_session: Session) -> None:
    user, payment = _credited(db_session)

    intake = _deliver(db_session, "evt_dispute", "charge.dispute.created", _dispute_object(payment))

    assert (intake.record.status, intake.record.reason_code) == ("unresolved", "DISPUTE_OPENED")
    assert _refunds(db_session) == []
    assert credit_balance(db_session, user.id) == 30
    db_session.refresh(payment)
    assert payment.status == "credited"


@pytest.mark.parametrize(
    ("event_type", "obj", "reason"),
    [
        ("charge.dispute.created", {"payment_intent": "pi_unknown"}, "PAYMENT_RECORD_NOT_FOUND"),
        ("charge.dispute.created", {"payment_intent": None}, "PAYMENT_RECORD_NOT_FOUND"),
        ("charge.dispute.created", {"object": "charge"}, "EVENT_PAYLOAD_MALFORMED"),
        ("refund.failed", {"payment_intent": "pi_unknown"}, "PAYMENT_RECORD_NOT_FOUND"),
        ("refund.failed", {"object": "charge"}, "EVENT_PAYLOAD_MALFORMED"),
    ],
)
def test_an_unmappable_dispute_or_failed_refund_is_unresolved(
    db_session: Session, event_type: str, obj: dict[str, Any], reason: str
) -> None:
    user, payment = _credited(db_session)
    build = _dispute_object if event_type == "charge.dispute.created" else _refund_object

    intake = _deliver(db_session, "evt_bad_reversal", event_type, build(payment, **obj))

    assert (intake.record.status, intake.record.reason_code) == ("unresolved", reason)
    assert credit_balance(db_session, user.id) == 30
