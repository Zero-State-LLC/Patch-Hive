"""API endpoint tests for account dashboard endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from account.models import AccountReferral
from canon.models import CanonicalCreditLedgerEntryRecord
from community.models import User
from core import create_access_token
from main import app
from monetization.models import Referral
from monetization.referrals import REFERRAL_REWARD_CREDITS, create_referral, record_purchase


@pytest.fixture
def client(db_session: Session):
    """Create a test client with database override."""
    from core import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"user_id": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def test_the_old_balance_route_is_gone(client: TestClient, sample_user: User):
    """One balance endpoint (spec 004 FR-009): the old route read a table nothing writes, so
    it answered 0 beside a real canonical balance."""
    response = client.get("/api/me/credits", headers=auth_headers(sample_user))
    assert response.status_code in (404, 405)


def _account(db: Session, name: str) -> User:
    user = User(username=name, email=f"{name}@example.com", password_hash="$2b$12$dummyhash")
    db.add(user)
    db.commit()
    return user


def test_referral_summary_reads_what_machine_a_wrote(
    client: TestClient, db_session: Session, sample_user: User
):
    """FR-031 and P4 AC2, T001 D8a: a reward shows as rewarded, and its credits as earned."""
    sample_user.referral_code = "REFCODE"
    db_session.commit()
    waiting = _account(db_session, "pendinguser")
    buyer = _account(db_session, "earneduser")
    create_referral(db_session, referrer=sample_user, referred=waiting)
    create_referral(db_session, referrer=sample_user, referred=buyer)
    db_session.commit()
    record_purchase(db_session, user=buyer, credits_delta=5, payment_verified=True)
    db_session.commit()

    response = client.get("/api/me/referrals", headers=auth_headers(sample_user))

    assert response.status_code == 200
    data = response.json()
    assert data["referral_code"] == "REFCODE"
    assert data["referral_link"].endswith("/signup?ref=REFCODE")
    assert data["pending_count"] == 1
    assert data["rewarded_count"] == 1
    assert data["earned_credits"] == REFERRAL_REWARD_CREDITS
    assert sorted(row["status"] for row in data["recent_referrals"]) == ["Pending", "Rewarded"]
    for row in data["recent_referrals"]:
        assert row["referred_user_id"].startswith("user-****")
    credits = db_session.query(CanonicalCreditLedgerEntryRecord).filter_by(user_id=sample_user.id)
    assert sum(entry.delta for entry in credits) == data["earned_credits"]


def test_a_rewarded_referral_is_not_also_counted_as_pending(
    client: TestClient, db_session: Session, sample_user: User
):
    buyer = _account(db_session, "earneduser")
    create_referral(db_session, referrer=sample_user, referred=buyer)
    db_session.commit()
    record_purchase(db_session, user=buyer, credits_delta=5, payment_verified=True)
    db_session.commit()
    assert db_session.query(Referral).filter_by(referred_user_id=buyer.id).count() == 2

    data = client.get("/api/me/referrals", headers=auth_headers(sample_user)).json()

    assert (data["pending_count"], data["rewarded_count"]) == (0, 1)
    assert [row["status"] for row in data["recent_referrals"]] == ["Rewarded"]


def test_a_summary_lists_at_most_ten_recent_referrals_and_counts_them_all(
    client: TestClient, db_session: Session, sample_user: User
):
    for index in range(12):
        create_referral(
            db_session, referrer=sample_user, referred=_account(db_session, f"friend{index}")
        )
    db_session.commit()

    data = client.get("/api/me/referrals", headers=auth_headers(sample_user)).json()

    assert data["pending_count"] == 12
    assert len(data["recent_referrals"]) == 10


def test_signup_writes_one_referral_row_and_no_legacy_projection(
    client: TestClient, db_session: Session, sample_user: User
):
    sample_user.referral_code = "REFCODE"
    db_session.commit()

    response = client.post(
        "/api/community/users",
        json={
            "username": "newfriend",
            "email": "newfriend@example.com",
            "password": "correct horse battery",
            "referral_code": "REFCODE",
        },
    )

    assert response.status_code == 201
    assert db_session.query(Referral).filter_by(status="Pending").count() == 1
    assert db_session.query(AccountReferral).count() == 0


def test_referral_link_stable(client: TestClient, db_session: Session, sample_user: User):
    """Referral link should be stable for a user."""
    sample_user.referral_code = "STABLECODE"
    db_session.commit()

    response = client.get("/api/me/referrals", headers=auth_headers(sample_user))
    assert response.status_code == 200
    data = response.json()
    assert data["referral_code"] == "STABLECODE"
    assert "STABLECODE" in data["referral_link"]
