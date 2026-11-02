"""Spec 004 T047: a referral reward on a provider (Machine B) purchase.

Every purchase here arrives through the real webhook path: a checkout opened with a fake
provider, then a signed ``checkout.session.*`` event through ``receive_stripe_webhook``
(FR-026, FR-027, FR-032, SC-002). The concurrent case runs on Postgres in
``tests/acceptance/test_referral_purchase_postgres.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from canon.contracts import ExportRequest
from canon.exports import ExportBoundaryError, credit_balance, request_export
from canon.models import CanonicalCreditLedgerEntryRecord
from community.models import User
from monetization.models import CreditsLedger, Referral
from monetization.referrals import REFERRAL_REWARD_CREDITS, create_referral
from tests.unit.test_canon_contracts import _persist_hierarchy
from tests.unit.test_commerce_credit_checkout import (
    _deliver,
    _open_checkout,
    _session_object,
    _user,
)

NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)


def _referral_grants(session: Session) -> list[CanonicalCreditLedgerEntryRecord]:
    return (
        session.query(CanonicalCreditLedgerEntryRecord)
        .filter(
            CanonicalCreditLedgerEntryRecord.entry_type == "grant",
            CanonicalCreditLedgerEntryRecord.idempotency_key.like("referral-reward:%"),
        )
        .all()
    )


def _referred_pair(session: Session) -> tuple[User, User, Referral]:
    # The referrer owns a generation run, so it can spend the reward on an export.
    referrer, _patch = _persist_hierarchy(session)
    referred = _user(session, "referred-buyer")
    referral = create_referral(session, referrer=referrer, referred=referred)
    session.commit()
    return referrer, referred, referral


def _export(user_id: int, key: str) -> ExportRequest:
    return ExportRequest(
        request_id=f"request-{key}",
        user_id=user_id,
        source_run_id="run-1",
        source_rig_revision_id="rig-rev-1",
        formats=("pdf",),
        license="personal",
        credit_cost=REFERRAL_REWARD_CREDITS,
        idempotency_key=key,
        requested_at=NOW,
    )


def test_a_first_provider_purchase_writes_one_spendable_canonical_reward(
    db_session: Session,
) -> None:
    referrer, referred, referral = _referred_pair(db_session)
    payment = _open_checkout(db_session, referred)

    intake = _deliver(
        db_session, "evt_t047_first", "checkout.session.completed", _session_object(payment)
    )

    assert intake.record.status == "processed"
    (grant,) = _referral_grants(db_session)
    assert (grant.user_id, grant.delta, grant.idempotency_key) == (
        referrer.id,
        REFERRAL_REWARD_CREDITS,
        f"referral-reward:{referral.id}",
    )
    rewarded = db_session.query(Referral).filter_by(status="Rewarded").one()
    first_purchase = db_session.query(CreditsLedger).filter_by(change_type="Purchase").one()
    assert (rewarded.referrer_user_id, rewarded.referred_user_id) == (referrer.id, referred.id)
    assert rewarded.first_purchase_id == first_purchase.id
    assert credit_balance(db_session, referrer.id) == REFERRAL_REWARD_CREDITS
    assert credit_balance(db_session, referred.id) == payment.credits

    # Spendable: the referrer can spend the reward on an export, once (FR-009).
    request_export(
        db_session,
        _export(referrer.id, "t047-spend"),
        artifact_manifest_hash="a" * 64,
        export_version="1.0.0",
    )
    db_session.commit()
    assert credit_balance(db_session, referrer.id) == 0
    with pytest.raises(ExportBoundaryError, match="INSUFFICIENT_CREDITS"):
        request_export(
            db_session,
            _export(referrer.id, "t047-spend-again"),
            artifact_manifest_hash="a" * 64,
            export_version="1.0.0",
        )


@pytest.mark.parametrize(
    "event_id, event_type",
    [
        ("evt_t047_dup", "checkout.session.completed"),  # the same event redelivered
        ("evt_t047_dup_other", "checkout.session.completed"),  # a new id, same session
        ("evt_t047_dup_async", "checkout.session.async_payment_succeeded"),
    ],
)
def test_a_duplicate_delivery_writes_no_reward(
    db_session: Session, event_id: str, event_type: str
) -> None:
    referrer, referred, _referral = _referred_pair(db_session)
    payment = _open_checkout(db_session, referred)
    obj = _session_object(payment)
    _deliver(db_session, "evt_t047_dup", "checkout.session.completed", obj)

    again = _deliver(db_session, event_id, event_type, obj)

    if event_id == "evt_t047_dup":
        # Intake answers a repeated event id from its record and does not re-run it.
        assert again.duplicate is True
    else:
        assert (again.duplicate, again.record.status) == (False, "duplicate")
    assert len(_referral_grants(db_session)) == 1
    assert db_session.query(Referral).filter_by(status="Rewarded").count() == 1
    assert db_session.query(CreditsLedger).filter_by(change_type="Grant").count() == 1
    assert credit_balance(db_session, referrer.id) == REFERRAL_REWARD_CREDITS
    assert credit_balance(db_session, referred.id) == payment.credits


def test_a_later_provider_purchase_writes_no_reward(db_session: Session) -> None:
    referrer, referred, _referral = _referred_pair(db_session)
    first = _open_checkout(db_session, referred)
    second = _open_checkout(db_session, referred, credits=40)
    _deliver(db_session, "evt_t047_a", "checkout.session.completed", _session_object(first))

    later = _deliver(
        db_session, "evt_t047_b", "checkout.session.completed", _session_object(second)
    )

    assert later.record.status == "processed"
    assert len(_referral_grants(db_session)) == 1
    assert credit_balance(db_session, referrer.id) == REFERRAL_REWARD_CREDITS
    assert credit_balance(db_session, referred.id) == first.credits + second.credits


def test_an_unresolved_purchase_writes_no_reward(db_session: Session) -> None:
    """A completion the record cannot vouch for grants nothing, reward included (FR-014)."""
    referrer, referred, _referral = _referred_pair(db_session)
    payment = _open_checkout(db_session, referred)

    bad = _deliver(
        db_session,
        "evt_t047_bad",
        "checkout.session.completed",
        _session_object(payment, amount_total=payment.amount_cents - 1),
    )

    assert (bad.record.status, bad.record.reason_code) == ("unresolved", "AMOUNT_MISMATCH")
    assert _referral_grants(db_session) == []
    assert {r.status for r in db_session.query(Referral)} == {"Pending"}
    assert credit_balance(db_session, referrer.id) == 0
