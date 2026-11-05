"""Authentication helpers for community routes."""

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from core import decode_access_token, get_db

from .models import User


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Get current user from JWT token."""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    if not payload:
        return None

    user_id = payload.get("user_id")
    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    # A token minted before the user's token_version was bumped (sign out everywhere,
    # role change) no longer counts. Tokens from before versions existed read as 0.
    if user is None or int(payload.get("tv", 0)) != int(user.token_version or 0):
        return None
    if user.deleted_at is not None:
        return None
    return user


def get_catalog_reader(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """The caller of a read whose answer depends on being signed in; None if no token was sent.

    A token that no longer counts is a 401, not an anonymous read. The web client renews on a
    401 and asks again; a quiet anonymous answer would never trigger that, so a signed-in person
    would lose rows once their short-lived access token expired.
    """
    user = get_current_user(authorization, db)
    if user is None and authorization and authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return user


def require_auth(current_user: Optional[User] = Depends(get_current_user)) -> User:
    """Require authentication."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return current_user


def require_admin(current_user: User = Depends(require_auth)) -> User:
    """Require admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user
