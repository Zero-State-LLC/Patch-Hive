"""
Sessions: short access tokens plus a rotating refresh token in an HttpOnly cookie,
reuse detection, sign-out, sign-out everywhere, and revocation on role change.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

pytest.importorskip("httpx", reason="httpx is required for FastAPI TestClient")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from community import sessions
from community.models import RefreshToken, User
from core import settings
from core.security import get_password_hash
from main import app
from tests.conftest import bearer_headers, make_user

SAME_SITE = {"X-PatchHive-Session": "1"}


@pytest.fixture
def client(db_session: Session):
    from core import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def member(db_session: Session) -> User:
    user = make_user(db_session, "member")
    user.password_hash = get_password_hash("correct horse")
    db_session.commit()
    return user


def _login(client: TestClient):
    return client.post(
        "/api/community/auth/login", json={"username": "member", "password": "correct horse"}
    )


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_sign_in_sets_an_httponly_refresh_cookie_and_a_short_access_token(
    client: TestClient, member: User
) -> None:
    resp = _login(client)
    assert resp.status_code == 200
    cookie = resp.headers["set-cookie"]
    assert cookie.startswith(f"{sessions.cookie_name()}=")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    claims = jwt.decode(resp.json()["access_token"], options={"verify_signature": False})
    lifetime = datetime.fromtimestamp(claims["exp"], timezone.utc) - datetime.now(timezone.utc)
    assert lifetime <= timedelta(minutes=settings.access_token_expire_minutes)
    assert claims["tv"] == 0


def test_refresh_rotates_and_a_replayed_token_revokes_the_family(
    client: TestClient, db_session: Session, member: User
) -> None:
    _login(client)
    first = client.cookies.get(sessions.cookie_name())

    renewed = client.post("/api/community/auth/refresh", headers=SAME_SITE)
    assert renewed.status_code == 200
    assert client.get("/api/community/users/me", headers=_bearer(renewed.json()["access_token"])).status_code == 200
    second = client.cookies.get(sessions.cookie_name())
    assert second and second != first

    # The replaced token comes back (stolen copy): the whole family dies.
    client.cookies.set(sessions.cookie_name(), first)
    assert client.post("/api/community/auth/refresh", headers=SAME_SITE).status_code == 401
    client.cookies.set(sessions.cookie_name(), second)
    assert client.post("/api/community/auth/refresh", headers=SAME_SITE).status_code == 401
    assert db_session.query(RefreshToken).filter(RefreshToken.revoked_at.is_(None)).count() == 0


def test_cookie_routes_need_the_session_header_and_an_allowed_origin(
    client: TestClient, member: User
) -> None:
    _login(client)
    assert client.post("/api/community/auth/refresh").status_code == 403
    evil = {**SAME_SITE, "Origin": "https://evil.example"}
    assert client.post("/api/community/auth/refresh", headers=evil).status_code == 403
    assert client.post("/api/community/auth/logout").status_code == 403
    assert client.post("/api/community/auth/refresh", headers=SAME_SITE).status_code == 200


def test_sign_out_ends_the_session(client: TestClient, member: User) -> None:
    _login(client)
    cookie = client.cookies.get(sessions.cookie_name())
    assert client.post("/api/community/auth/logout", headers=SAME_SITE).status_code == 204
    client.cookies.set(sessions.cookie_name(), cookie)
    assert client.post("/api/community/auth/refresh", headers=SAME_SITE).status_code == 401


def test_sign_out_everywhere_kills_outstanding_access_tokens(
    client: TestClient, db_session: Session, member: User
) -> None:
    token = _login(client).json()["access_token"]
    assert client.get("/api/community/users/me", headers=_bearer(token)).status_code == 200
    assert client.post("/api/community/auth/logout-all", headers=_bearer(token)).status_code == 204
    assert client.get("/api/community/users/me", headers=_bearer(token)).status_code == 401
    db_session.refresh(member)
    assert member.token_version == 1


def test_a_role_change_revokes_the_users_tokens(
    client: TestClient, db_session: Session, member: User
) -> None:
    token = _login(client).json()["access_token"]
    admin = bearer_headers(make_user(db_session, "boss", "Admin"))
    resp = client.patch(
        f"/api/admin/users/{member.id}/role", json={"role": "Support", "reason": "t"}, headers=admin
    )
    assert resp.status_code == 200
    assert client.get("/api/community/users/me", headers=_bearer(token)).status_code == 401
    assert client.post("/api/community/auth/refresh", headers=SAME_SITE).status_code == 401


def test_an_expired_refresh_token_is_refused(
    client: TestClient, db_session: Session, member: User
) -> None:
    _login(client)
    row = db_session.query(RefreshToken).one()
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()
    assert client.post("/api/community/auth/refresh", headers=SAME_SITE).status_code == 401


def test_hosted_environments_use_a_secure_host_cookie(
    client: TestClient, member: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "environment", "staging")
    cookie = _login(client).headers["set-cookie"]
    assert cookie.startswith("__Host-ph_refresh=")
    assert "Secure" in cookie and "Domain" not in cookie and "Path=/" in cookie
