"""Sign-up is rate limited per address and does not reveal which emails have accounts."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from community import login_guard
from core.database import get_db
from main import app


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _register(client: TestClient, n: int, *, ip: str = "203.0.113.7", **fields):
    body = {"username": f"user{n}", "email": f"user{n}@example.com", "password": "correct-horse-1"}
    body.update(fields)
    return client.post("/api/community/users", json=body, headers={"x-forwarded-for": ip})


def test_a_taken_username_or_email_gets_one_reply(client: TestClient) -> None:
    assert _register(client, 1).status_code == 201
    by_name = _register(client, 2, username="user1")
    by_email = _register(client, 3, email="user1@example.com")
    assert by_name.status_code == by_email.status_code == 400
    assert by_name.json()["detail"] == by_email.json()["detail"] == "USERNAME_OR_EMAIL_TAKEN"


def test_sign_up_is_limited_per_address(client: TestClient) -> None:
    for n in range(login_guard.REGISTER_ATTEMPTS):
        assert _register(client, 10 + n).status_code == 201
    blocked = _register(client, 99)
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "TOO_MANY_SIGNUPS"
    # Another address is not affected, and failed attempts count too (a script can't probe freely).
    assert _register(client, 100, ip="198.51.100.9").status_code == 201


def test_the_window_expires() -> None:
    address = "192.0.2.1"
    for _ in range(login_guard.REGISTER_ATTEMPTS):
        assert login_guard.allow_registration(address, now=0)
    assert not login_guard.allow_registration(address, now=1)
    assert login_guard.allow_registration(address, now=login_guard.REGISTER_WINDOW_SECONDS + 1)


def test_sign_up_and_login_limits_are_separate() -> None:
    address = "192.0.2.2"
    for _ in range(login_guard.REGISTER_ATTEMPTS):
        login_guard.allow_registration(address, now=0)
    assert login_guard.allow_attempt(address, now=0)
