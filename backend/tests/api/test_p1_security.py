"""
P1 security hardening from the 2026-10-27 gap analysis: per-user export idempotency,
Admin-only Admin grants, sign-in lockout and rate limit, password hashing, one referral
reward, and the legacy purchases endpoint staying off.
"""

from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("httpx", reason="httpx is required for FastAPI TestClient")

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from canon.contracts import ExportRequest
from canon.exports import request_export
from canon.models import CanonicalCreditLedgerEntryRecord
from community import login_guard
from community.models import User
from core.security import get_password_hash, verify_and_update_password
from main import app
from monetization.models import CreditsLedger, Referral
from tests.conftest import bearer_headers, make_user
from tests.unit.test_canon_contracts import _persist_hierarchy

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)
# Real hashes of "correct horse": passlib's pbkdf2 fallback, and bcrypt.
PASSLIB_PBKDF2 = "$pbkdf2-sha256$29000$vjeG0DpnzJlzLgVACCGk9A$YXCfMAnmklNY99QJi//HpDLIzisezUgI6y2hlfLOilQ"
BCRYPT = "$2b$04$E3tERmAj0El5J/wJ2vmpVefd1svxjsa8C4Pz9d5yfam5jfVbRpvAu"


@pytest.fixture
def client(db_session: Session):
    from core import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- Export idempotency is per user -------------------------------------------------


def _grant(db: Session, user_id: int) -> None:
    db.add(
        CanonicalCreditLedgerEntryRecord(
            id=f"grant-{user_id}", user_id=user_id, delta=10, entry_type="grant",
            idempotency_key=f"grant-{user_id}", created_at=NOW,
        )
    )
    db.commit()


def _request(user_id: int) -> ExportRequest:
    return ExportRequest(
        request_id=f"request-{user_id}", user_id=user_id, source_run_id="run-1",
        source_rig_revision_id="rig-rev-1", formats=("pdf",), license="personal",
        credit_cost=3, idempotency_key="shared-key", requested_at=NOW,
    )


def test_one_users_key_never_returns_another_users_export(db_session: Session) -> None:
    owner, _patch = _persist_hierarchy(db_session)
    other = make_user(db_session, "other-exporter")
    _grant(db_session, owner.id)
    _grant(db_session, other.id)

    first = request_export(db_session, _request(owner.id), artifact_manifest_hash="a" * 64, export_version="1")
    second = request_export(db_session, _request(other.id), artifact_manifest_hash="a" * 64, export_version="1")
    db_session.commit()
    assert first.id != second.id
    assert (first.user_id, second.user_id) == (owner.id, other.id)
    # The same user retrying still gets its own export back.
    again = request_export(db_session, _request(owner.id), artifact_manifest_hash="a" * 64, export_version="1")
    assert again.id == first.id


# --- Only an Admin grants or removes Admin -----------------------------------------


def test_ops_cannot_grant_or_remove_admin(client: TestClient, db_session: Session) -> None:
    ops = bearer_headers(make_user(db_session, "ops-user", "Ops"))
    admin = bearer_headers(make_user(db_session, "admin-user", "Admin"))
    target = make_user(db_session, "target")
    other_admin = make_user(db_session, "other-admin", "Admin")
    body = {"reason": "test"}

    assert client.patch(f"/api/admin/users/{target.id}/role", json={**body, "role": "Admin"}, headers=ops).status_code == 403
    assert client.patch(f"/api/admin/users/{other_admin.id}/role", json={**body, "role": "User"}, headers=ops).status_code == 403
    assert client.patch(f"/api/admin/users/{target.id}/role", json={**body, "role": "Support"}, headers=ops).status_code == 200
    assert client.patch(f"/api/admin/users/{target.id}/role", json={**body, "role": "Admin"}, headers=admin).status_code == 200
    assert client.patch(f"/api/admin/users/{target.id}/role", json={**body, "role": "Overlord"}, headers=admin).status_code == 422


# --- Sign-in --------------------------------------------------------------------------


def _user_with_password(db: Session, username: str, password_hash: str) -> User:
    user = make_user(db, username)
    user.password_hash = password_hash
    db.commit()
    return user


def _login(client: TestClient, username: str, password: str):
    return client.post("/api/community/auth/login", json={"username": username, "password": password})


def test_unknown_names_and_wrong_passwords_answer_alike(client: TestClient, db_session: Session) -> None:
    _user_with_password(db_session, "real", get_password_hash("correct horse"))
    unknown = _login(client, "nobody", "whatever1")
    wrong = _login(client, "real", "whatever1")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": "Invalid credentials"}


def test_repeated_failures_lock_the_account(client: TestClient, db_session: Session) -> None:
    user = _user_with_password(db_session, "locky", get_password_hash("correct horse"))
    for _ in range(login_guard.MAX_FAILURES):
        assert _login(client, "locky", "wrong-pass").status_code == 401
    db_session.refresh(user)
    assert user.locked_until is not None
    # Locked: even the right password gets the same 401.
    locked = _login(client, "locky", "correct horse")
    assert locked.status_code == 401 and locked.json() == {"detail": "Invalid credentials"}
    # After the lock expires, the right password works and clears the counter.
    user.locked_until = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()
    assert _login(client, "locky", "correct horse").status_code == 200
    db_session.refresh(user)
    assert user.failed_login_count == 0 and user.locked_until is None


def test_one_address_is_rate_limited(client: TestClient, db_session: Session) -> None:
    for _ in range(login_guard.IP_ATTEMPTS_PER_MINUTE):
        assert _login(client, "nobody", "whatever1").status_code == 401
    assert _login(client, "nobody", "whatever1").status_code == 429


# --- Password hashing -------------------------------------------------------------------


def test_new_hashes_are_argon2id() -> None:
    hashed = get_password_hash("correct horse")
    assert hashed.startswith("$argon2id$")
    assert verify_and_update_password("correct horse", hashed) == (True, None)
    assert verify_and_update_password("wrong", hashed)[0] is False


@pytest.mark.parametrize("legacy", [PASSLIB_PBKDF2, BCRYPT])
def test_legacy_hashes_verify_and_upgrade_on_sign_in(
    client: TestClient, db_session: Session, legacy: str
) -> None:
    assert verify_and_update_password("wrong", legacy)[0] is False
    user = _user_with_password(db_session, "legacy", legacy)
    assert _login(client, "legacy", "correct horse").status_code == 200
    db_session.refresh(user)
    assert user.password_hash.startswith("$argon2id$")
    assert _login(client, "legacy", "correct horse").status_code == 200


def test_malformed_hashes_and_long_passwords_never_verify() -> None:
    assert verify_and_update_password("x", "not-a-hash") == (False, None)
    assert verify_and_update_password("a" * 200, get_password_hash("a" * 100)) == (False, None)


# --- Referrals and legacy purchases ---------------------------------------------------


def test_a_referred_user_is_rewarded_at_most_once(db_session: Session) -> None:
    referrer = make_user(db_session, "referrer")
    referred = make_user(db_session, "referred")
    db_session.add(Referral(referrer_user_id=referrer.id, referred_user_id=referred.id, status="Rewarded"))
    db_session.commit()
    db_session.add(Referral(referrer_user_id=referrer.id, referred_user_id=referred.id, status="Rewarded"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("flag", [False, True])
def test_legacy_purchase_route_is_gone(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch, flag: bool
) -> None:
    """POST /api/monetization/purchases was deleted (spec 004 T043); no flag brings it back."""
    from core import settings
    from core.config import Settings

    assert Settings.model_fields["enable_referrals"].default is False
    assert "enable_legacy_referrals" not in Settings.model_fields
    monkeypatch.setattr(settings, "enable_referrals", flag)
    buyer = bearer_headers(make_user(db_session, "buyer"))
    resp = client.post("/api/monetization/purchases", json={"credits_delta": 1000}, headers=buyer)
    assert resp.status_code in (404, 405)
    assert db_session.query(CreditsLedger).filter(CreditsLedger.change_type == "Purchase").count() == 0


def test_racing_failures_each_count(db_session: Session) -> None:
    """Requests that loaded the same counter must each count (atomic update)."""
    user = _user_with_password(db_session, "racer", get_password_hash("correct horse"))
    sessions = [Session(bind=db_session.get_bind()) for _ in range(login_guard.MAX_FAILURES)]
    loaded = [s.get(User, user.id) for s in sessions]  # every one reads 0 failures
    for session, row in zip(sessions, loaded):
        login_guard.record_failure(session, row)
        session.commit()
    for session in sessions:
        session.close()
    db_session.expire_all()
    locked = db_session.get(User, user.id)
    assert locked.locked_until is not None and locked.failed_login_count == 0
