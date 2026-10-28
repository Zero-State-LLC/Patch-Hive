"""
Sessions: a short-lived access token held in memory by the SPA, renewed by a rotating
refresh token kept in an HttpOnly cookie on the API host.

- The refresh token is random, stored only as a SHA-256 hash, and lives
  ``settings.refresh_token_days``. Every use replaces it with a new one in the same
  family. Presenting a token that was already replaced is treated as theft: the whole
  family is revoked.
- The cookie is ``HttpOnly``, ``SameSite=Strict`` and, outside local development,
  ``Secure`` with the ``__Host-`` prefix (no Domain, Path=/). The SPA on patch-hive.com
  and the API on api.patch-hive.com are the same site, so it is sent on the SPA's
  credentialed requests and on nothing cross-site.
- The cookie authenticates only refresh and sign-out. Those require the
  ``X-PatchHive-Session`` header, which a cross-site form cannot set, and an allowed
  ``Origin`` when one is sent.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request, Response
from sqlalchemy import update
from sqlalchemy.orm import Session

from core import create_access_token, settings
from core.security import is_dev_environment

from .models import RefreshToken, User

CSRF_HEADER = "x-patchhive-session"


def cookie_name() -> str:
    return "ph_refresh" if is_dev_environment(settings.environment) else "__Host-ph_refresh"


def _cookie_secure() -> bool:
    return not is_dev_environment(settings.environment)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def access_token_for(user: User) -> str:
    return create_access_token(
        {"user_id": user.id, "username": user.username, "tv": int(user.token_version or 0)}
    )


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        cookie_name(),
        token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=_cookie_secure(),
        samesite="strict",
        path="/",
    )


def clear_cookie(response: Response) -> None:
    response.delete_cookie(
        cookie_name(), path="/", httponly=True, secure=_cookie_secure(), samesite="strict"
    )


def _mint(db: Session, user: User, family_id: str, *, now: datetime) -> tuple[RefreshToken, str]:
    token = secrets.token_urlsafe(48)
    row = RefreshToken(
        id=secrets.token_hex(16),
        user_id=user.id,
        family_id=family_id,
        token_hash=_hash(token),
        created_at=now,
        expires_at=now + timedelta(days=settings.refresh_token_days),
    )
    db.add(row)
    return row, token


def start_session(db: Session, user: User, response: Response) -> str:
    """Sign-in: open a new refresh family, set its cookie, return an access token."""
    _, token = _mint(db, user, secrets.token_hex(16), now=datetime.utcnow())
    _set_cookie(response, token)
    return access_token_for(user)


def require_same_site(request: Request) -> None:
    """The cookie is ambient, so cookie-authenticated calls must prove they come from
    the SPA: a custom header (forms cannot send one) and, if sent, an allowed Origin."""
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=403, detail="SESSION_HEADER_REQUIRED")
    origin = request.headers.get("origin")
    if origin and origin not in settings.cors_origins:
        raise HTTPException(status_code=403, detail="ORIGIN_NOT_ALLOWED")


def revoke_family(db: Session, family_id: str, *, now: Optional[datetime] = None) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now or datetime.utcnow())
    )


def revoke_user(db: Session, user: User) -> None:
    """Sign out everywhere: bump the token version and revoke every refresh token."""
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow())
    )
    user.token_version = int(user.token_version or 0) + 1


def rotate(db: Session, request: Request, response: Response) -> tuple[User, str]:
    """Exchange the refresh cookie for a new one and a new access token."""
    invalid = HTTPException(status_code=401, detail="SESSION_EXPIRED")
    presented = request.cookies.get(cookie_name())
    if not presented:
        raise invalid
    now = datetime.utcnow()
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == _hash(presented))
        .with_for_update()
        .first()
    )
    if row is None:
        clear_cookie(response)
        raise invalid
    if row.revoked_at is not None:
        # A replaced or revoked token came back: someone else may hold the family.
        revoke_family(db, row.family_id, now=now)
        db.commit()
        clear_cookie(response)
        raise invalid
    user = db.get(User, row.user_id)
    if row.expires_at <= now or user is None:
        row.revoked_at = now
        db.commit()
        clear_cookie(response)
        raise invalid
    new_row, token = _mint(db, user, row.family_id, now=now)
    row.revoked_at = now
    row.replaced_by = new_row.id
    db.commit()
    _set_cookie(response, token)
    return user, access_token_for(user)


def end_session(db: Session, request: Request, response: Response) -> None:
    presented = request.cookies.get(cookie_name())
    if presented:
        row = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash(presented)).first()
        if row is not None:
            revoke_family(db, row.family_id)
            db.commit()
    clear_cookie(response)
