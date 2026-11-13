"""Closed-beta sign-up: a one-use code opens the door and carries test credits."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from canon.exports import credit_balance
from community import invites
from community.auth import require_auth
from community.models import BetaInvite, User
from core import settings
from core.database import get_db
from main import app

GOOD = "good-code"


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def invite_only(monkeypatch):
    monkeypatch.setattr(settings, "enable_invite_only_signup", True)


@pytest.fixture
def invite(db_session: Session) -> BetaInvite:
    row = BetaInvite(code_hash=invites.code_hash(GOOD), credits=9)
    db_session.add(row)
    db_session.commit()
    return row


def _sign_up(client: TestClient, n: int, code: str | None = GOOD, **fields):
    body = {"username": f"user{n}", "email": f"user{n}@example.com", "password": "correct-horse-1"}
    if code is not None:
        body["invite_code"] = code
    body.update(fields)
    return client.post("/api/community/users", json=body, headers={"x-forwarded-for": f"203.0.113.{n}"})


@pytest.mark.usefixtures("invite_only", "invite")
@pytest.mark.parametrize("code", [None, "", "wrong-code"])
def test_sign_up_needs_a_valid_code(client: TestClient, db_session: Session, code) -> None:
    response = _sign_up(client, 1, code)
    assert (response.status_code, response.json()["detail"]) == (403, "INVITE_REQUIRED")
    assert db_session.query(User).count() == 0


@pytest.mark.usefixtures("invite_only")
def test_a_code_creates_the_account_and_grants_its_credits_once(
    client: TestClient, db_session: Session, invite: BetaInvite
) -> None:
    response = _sign_up(client, 1)
    assert response.status_code == 201
    user_id = response.json()["id"]
    db_session.refresh(invite)
    assert invite.redeemed_by == user_id and invite.redeemed_at is not None
    assert credit_balance(db_session, user_id) == 9


@pytest.mark.usefixtures("invite_only", "invite")
def test_a_used_code_is_refused_and_grants_nothing_more(client: TestClient, db_session: Session) -> None:
    first = _sign_up(client, 1)
    second = _sign_up(client, 2)
    assert (second.status_code, second.json()["detail"]) == (403, "INVITE_REQUIRED")
    assert db_session.query(User).count() == 1
    assert credit_balance(db_session, first.json()["id"]) == 9


@pytest.mark.usefixtures("invite_only")
def test_without_a_code_a_caller_cannot_learn_who_has_an_account(
    client: TestClient, db_session: Session, invite: BetaInvite
) -> None:
    assert _sign_up(client, 1).status_code == 201
    probe = _sign_up(client, 2, None, username="user1")
    assert (probe.status_code, probe.json()["detail"]) == (403, "INVITE_REQUIRED")


@pytest.mark.usefixtures("invite_only")
def test_a_refused_sign_up_leaves_the_code_unused(
    client: TestClient, db_session: Session, invite: BetaInvite
) -> None:
    db_session.add(User(username="user1", email="taken@example.com", password_hash="x", role="User"))
    db_session.commit()
    assert _sign_up(client, 1).status_code == 400
    db_session.refresh(invite)
    assert invite.redeemed_by is None


def test_with_the_flag_off_sign_up_needs_no_code_and_grants_nothing(
    client: TestClient, db_session: Session, invite: BetaInvite
) -> None:
    response = _sign_up(client, 1)
    assert response.status_code == 201
    db_session.refresh(invite)
    assert invite.redeemed_by is None
    assert credit_balance(db_session, response.json()["id"]) == 0


@pytest.mark.parametrize("flag", [True, False])
def test_the_form_learns_whether_a_code_is_needed(client: TestClient, monkeypatch, flag: bool) -> None:
    monkeypatch.setattr(settings, "enable_invite_only_signup", flag)
    assert client.get("/api/community/auth/signup-options").json() == {"invite_required": flag}


def _as(db_session: Session, role: str) -> User:
    user = User(username=role.lower(), email=f"{role.lower()}@example.com", password_hash="x", role=role)
    db_session.add(user)
    db_session.commit()
    app.dependency_overrides[require_auth] = lambda: user
    return user


def test_a_minted_code_appears_once_and_only_its_hash_is_stored(
    client: TestClient, db_session: Session
) -> None:
    _as(db_session, "Admin")
    created = client.post("/api/admin/invites", json={"credits": 9, "note": "A tester"})
    assert created.status_code == 201
    code = created.json()["code"]
    row = db_session.query(BetaInvite).one()
    assert row.code_hash == invites.code_hash(code) and code not in row.code_hash
    listed = client.get("/api/admin/invites").json()["invites"]
    assert listed[0]["credits"] == 9 and "code" not in listed[0]


def test_only_an_admin_can_mint(client: TestClient, db_session: Session) -> None:
    _as(db_session, "User")
    assert client.post("/api/admin/invites", json={"credits": 9}).status_code == 403
    assert db_session.query(BetaInvite).count() == 0
