"""Spec 004 T050: the tier comes from the user's subscription, and STUDIO spends against
its fair-use cap instead of credits (FR-001, FR-004, FR-035, OQ-4, OQ-7, OQ-8).

Concurrent spends against the last fair-use slot: tests/acceptance/
test_studio_fair_use_postgres.py (SQLite cannot block on the per-user lock).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import canon.entitlements as entitlements
from canon.contracts import ExportRequest
from canon.entitlements import (
    ENTITLED_STATUSES,
    current_unlimited_grant,
    get_design_entitlements,
    resolve_user_tier,
)
from canon.exports import (
    ExportBoundaryError,
    compensate_failed_export,
    credit_balance,
    reconcile_ledger,
    request_export,
)
from canon.models import (
    SUBSCRIPTION_STATUSES,
    CanonicalCreditLedgerEntryRecord,
    CanonicalExportRecord,
    ProviderSubscriptionRecord,
    SubscriptionPeriodGrantRecord,
)
from community.models import User
from export.patchbook.design.recipe import TemplateFamilyId
from tests.unit.test_canon_contracts import _persist_hierarchy

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
PERIOD_START = NOW - timedelta(days=10)
PERIOD_END = NOW + timedelta(days=20)


@pytest.fixture(autouse=True)
def _default_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entitlements.settings, "design_engine_default_tier", "core")


def _subscription(
    db: Session,
    user: User,
    *,
    tier: str = "studio",
    status: str = "active",
    sub_id: str = "sub_t050",
    created_at: datetime = NOW - timedelta(days=10),
) -> ProviderSubscriptionRecord:
    record = ProviderSubscriptionRecord(
        id=f"subrec-{sub_id}",
        user_id=user.id,
        provider_subscription_id=sub_id,
        provider_customer_id=f"cus_{user.id}",
        price_id=f"price_{tier}",
        tier=tier,
        status=status,
        current_period_start=PERIOD_START,
        current_period_end=PERIOD_END,
        cancel_at_period_end=False,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(record)
    db.commit()
    return record


def _studio_grant(
    db: Session,
    record: ProviderSubscriptionRecord,
    *,
    cap: int = 2,
    start: datetime = PERIOD_START,
    end: datetime = PERIOD_END,
) -> SubscriptionPeriodGrantRecord:
    grant = SubscriptionPeriodGrantRecord(
        id=f"subgrant-{record.id}-{int(start.timestamp())}",
        subscription_record_id=record.id,
        user_id=record.user_id,
        grant_key=f"subscription-period:{record.provider_subscription_id}:{int(start.timestamp())}",
        provider_invoice_id=f"in-{record.id}-{int(start.timestamp())}",
        tier="studio",
        period_start=start,
        period_end=end,
        credits=0,
        unlimited=True,
        fair_use_export_cap=cap,
        ledger_entry_id=None,
        created_at=start,
    )
    db.add(grant)
    db.commit()
    return grant


def _credits(db: Session, user: User, amount: int, key: str = "grant-t050") -> None:
    db.add(
        CanonicalCreditLedgerEntryRecord(
            id=key,
            user_id=user.id,
            delta=amount,
            entry_type="grant",
            idempotency_key=key,
            created_at=NOW,
        )
    )
    db.commit()


def _export(db: Session, user: User, key: str, *, at: datetime = NOW) -> CanonicalExportRecord:
    export = request_export(
        db,
        ExportRequest(
            request_id=f"request-{key}",
            user_id=user.id,
            source_run_id="run-1",
            source_rig_revision_id="rig-rev-1",
            formats=("pdf", "json"),
            license="personal",
            credit_cost=3,
            idempotency_key=key,
            requested_at=at,
        ),
        artifact_manifest_hash="a" * 64,
        export_version="1.0.0",
    )
    db.commit()
    return export


# --- Tier resolution (OQ-4 ``A_stripe_mapping``) -----------------------------------------


def test_the_entitled_statuses_are_the_oq4_paid_tier_statuses() -> None:
    assert ENTITLED_STATUSES == {"active", "trialing", "past_due"}
    assert ENTITLED_STATUSES <= set(SUBSCRIPTION_STATUSES)


def test_a_user_without_a_subscription_gets_the_default_tier(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, _ = _persist_hierarchy(db_session)
    assert resolve_user_tier(db_session, user.id) == "core"
    monkeypatch.setattr(entitlements.settings, "design_engine_default_tier", "free")
    assert resolve_user_tier(db_session, user.id) == "free"
    monkeypatch.setattr(entitlements.settings, "design_engine_default_tier", "platinum")
    assert resolve_user_tier(db_session, user.id) == "core"


@pytest.mark.parametrize("status", sorted(ENTITLED_STATUSES))
@pytest.mark.parametrize("tier", ["core", "pro", "studio"])
def test_an_entitled_subscription_sets_the_tier(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, status: str, tier: str
) -> None:
    monkeypatch.setattr(entitlements.settings, "design_engine_default_tier", "free")
    user, _ = _persist_hierarchy(db_session)
    _subscription(db_session, user, tier=tier, status=status)
    assert resolve_user_tier(db_session, user.id) == tier


@pytest.mark.parametrize("status", sorted(set(SUBSCRIPTION_STATUSES) - ENTITLED_STATUSES))
def test_a_subscription_that_is_not_entitled_falls_back_to_the_default_tier(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    monkeypatch.setattr(entitlements.settings, "design_engine_default_tier", "free")
    user, _ = _persist_hierarchy(db_session)
    _subscription(db_session, user, tier="studio", status=status)
    assert resolve_user_tier(db_session, user.id) == "free"


def test_another_users_subscription_never_sets_the_tier(db_session: Session) -> None:
    user, _ = _persist_hierarchy(db_session)
    other = User(username="other", email="other@example.com", password_hash="hash")
    db_session.add(other)
    db_session.commit()
    _subscription(db_session, other, tier="studio")
    assert resolve_user_tier(db_session, user.id) == "core"


def test_the_newest_entitled_subscription_decides(db_session: Session) -> None:
    user, _ = _persist_hierarchy(db_session)
    _subscription(db_session, user, tier="studio", status="canceled", sub_id="sub_old")
    _subscription(
        db_session, user, tier="pro", sub_id="sub_mid", created_at=NOW - timedelta(days=5)
    )
    _subscription(
        db_session,
        user,
        tier="core",
        status="incomplete",
        sub_id="sub_new",
        created_at=NOW - timedelta(days=1),
    )
    assert resolve_user_tier(db_session, user.id) == "pro"


def test_design_entitlements_use_the_subscription_tier(db_session: Session) -> None:
    user, _ = _persist_hierarchy(db_session)
    assert TemplateFamilyId.RITUAL_MACHINE not in get_design_entitlements(
        db_session, user.id
    ).allowed_families
    _subscription(db_session, user, tier="studio")
    resolved = get_design_entitlements(db_session, user.id)
    assert resolved.tier == "studio"
    assert TemplateFamilyId.RITUAL_MACHINE in resolved.allowed_families


# --- STUDIO spending (FR-004, OQ-8 ``A_flag_with_fair_use``) -----------------------------


def test_a_studio_export_takes_no_credits_and_points_at_the_period_grant(
    db_session: Session,
) -> None:
    user, _ = _persist_hierarchy(db_session)
    grant = _studio_grant(db_session, _subscription(db_session, user))

    export = _export(db_session, user, "studio-1")

    assert export.credit_cost == 0
    assert export.ledger_entry_id is None
    assert export.subscription_grant_id == grant.id
    assert db_session.query(CanonicalCreditLedgerEntryRecord).count() == 0
    assert credit_balance(db_session, user.id) == 0
    assert reconcile_ledger(db_session, user.id).anomalies == ()


def test_the_fair_use_cap_refuses_the_next_export_with_a_clear_code(
    db_session: Session,
) -> None:
    user, _ = _persist_hierarchy(db_session)
    _studio_grant(db_session, _subscription(db_session, user), cap=2)
    _credits(db_session, user, 10)

    _export(db_session, user, "studio-1")
    _export(db_session, user, "studio-2")
    with pytest.raises(ExportBoundaryError, match="FAIR_USE_CAP_REACHED"):
        _export(db_session, user, "studio-3")
    db_session.rollback()

    # The cap does not fall through to the ledger: credits the user holds stay put.
    assert db_session.query(CanonicalExportRecord).count() == 2
    assert credit_balance(db_session, user.id) == 10


def test_a_retry_of_a_covered_export_returns_it_even_at_the_cap(db_session: Session) -> None:
    user, _ = _persist_hierarchy(db_session)
    _studio_grant(db_session, _subscription(db_session, user), cap=1)
    first = _export(db_session, user, "studio-1")
    assert _export(db_session, user, "studio-1").id == first.id


def test_a_failed_covered_export_gives_its_slot_back(db_session: Session) -> None:
    user, _ = _persist_hierarchy(db_session)
    _studio_grant(db_session, _subscription(db_session, user), cap=1)
    first = _export(db_session, user, "studio-1")

    assert compensate_failed_export(db_session, first, occurred_at=NOW) is None
    db_session.commit()
    assert first.status == "failed"
    assert db_session.query(CanonicalCreditLedgerEntryRecord).count() == 0

    second = _export(db_session, user, "studio-2")
    assert second.subscription_grant_id == first.subscription_grant_id


def test_a_new_period_grant_has_its_own_cap(db_session: Session) -> None:
    user, _ = _persist_hierarchy(db_session)
    record = _subscription(db_session, user)
    _studio_grant(db_session, record, cap=1)
    nxt = _studio_grant(db_session, record, cap=1, start=PERIOD_END, end=PERIOD_END + timedelta(days=30))
    _export(db_session, user, "studio-1")
    with pytest.raises(ExportBoundaryError, match="FAIR_USE_CAP_REACHED"):
        _export(db_session, user, "studio-2")
    db_session.rollback()

    later = _export(db_session, user, "studio-3", at=PERIOD_END + timedelta(days=1))
    assert later.subscription_grant_id == nxt.id


@pytest.mark.parametrize(
    "case", ["no_grant_for_this_period", "not_entitled", "core_grant", "other_users_grant"]
)
def test_without_a_current_studio_grant_the_export_pays_from_the_ledger(
    db_session: Session, case: str
) -> None:
    user, _ = _persist_hierarchy(db_session)
    if case == "no_grant_for_this_period":
        # ``past_due`` keeps the tier, but the period's invoice is not paid: no grant.
        record = _subscription(db_session, user, status="past_due")
        _studio_grant(db_session, record, start=PERIOD_START - timedelta(days=30), end=PERIOD_START)
    elif case == "not_entitled":
        _studio_grant(db_session, _subscription(db_session, user, status="unpaid"))
    elif case == "core_grant":
        _subscription(db_session, user, tier="core")
    else:
        other = User(username="other", email="other@example.com", password_hash="hash")
        db_session.add(other)
        db_session.commit()
        _studio_grant(db_session, _subscription(db_session, other))
    assert current_unlimited_grant(db_session, user.id, NOW) is None

    with pytest.raises(ExportBoundaryError, match="INSUFFICIENT_CREDITS"):
        _export(db_session, user, "ledger-0")
    db_session.rollback()

    _credits(db_session, user, 10)
    export = _export(db_session, user, "ledger-1")
    assert export.credit_cost == 3
    assert export.subscription_grant_id is None
    assert credit_balance(db_session, user.id) == 7


def test_core_and_pro_keep_the_credit_ledger(db_session: Session) -> None:
    user, _ = _persist_hierarchy(db_session)
    _subscription(db_session, user, tier="pro")
    _credits(db_session, user, 3)
    export = _export(db_session, user, "pro-1")
    assert (export.credit_cost, export.subscription_grant_id) == (3, None)
    assert credit_balance(db_session, user.id) == 0


def test_a_covered_export_with_a_debit_is_refused_by_the_schema(db_session: Session) -> None:
    user, _ = _persist_hierarchy(db_session)
    grant = _studio_grant(db_session, _subscription(db_session, user))
    db_session.add(
        CanonicalExportRecord(
            id="export-bad",
            user_id=user.id,
            source_run_id="run-1",
            source_rig_revision_id="rig-rev-1",
            artifact_manifest_hash="a" * 64,
            export_version="1.0.0",
            license="personal",
            credit_cost=3,
            ledger_entry_id=None,
            subscription_grant_id=grant.id,
            idempotency_key="bad-shape",
            status="queued",
            created_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
