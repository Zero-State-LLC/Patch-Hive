"""
Brute-force protection for sign-in.

- Per account: after ``MAX_FAILURES`` wrong passwords the account is locked for
  ``LOCK_MINUTES``. The count is an atomic database update, so concurrent attempts
  cannot overwrite each other. While locked, sign-in answers exactly like a wrong password, so a
  lock reveals nothing about whether the account exists.
- Per client address: at most ``IP_ATTEMPTS_PER_MINUTE`` sign-in attempts a minute,
  answered with 429. Counted in this process, which is enough while the API runs as a
  single container; a Cloudflare rate-limiting rule is the edge-wide backstop.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timedelta

from fastapi import Request

MAX_FAILURES = 5
LOCK_MINUTES = 15
IP_ATTEMPTS_PER_MINUTE = 20
# Sign-up: a few accounts per address per window is plenty for a person, and slows a script.
REGISTER_ATTEMPTS = 5
REGISTER_WINDOW_SECONDS = 600

_lock = threading.Lock()
_attempts: dict[str, deque[float]] = {}


def client_address(request: Request) -> str:
    # The edge Worker sets X-Forwarded-For to CF-Connecting-IP, overwriting client values.
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def allow_attempt(
    address: str,
    *,
    now: float | None = None,
    bucket: str = "login",
    limit: int = IP_ATTEMPTS_PER_MINUTE,
    window_seconds: float = 60,
) -> bool:
    """Record one attempt from ``address`` in ``bucket``; False once it is over ``limit``
    within ``window_seconds``. Per container (in memory): a cold start resets it."""
    now = time.monotonic() if now is None else now
    key = address if bucket == "login" else f"{bucket}:{address}"
    with _lock:
        window = _attempts.setdefault(key, deque())
        while window and now - window[0] > window_seconds:
            window.popleft()
        if len(window) >= limit:
            return False
        window.append(now)
        return True


def allow_registration(address: str, *, now: float | None = None) -> bool:
    return allow_attempt(
        address,
        now=now,
        bucket="register",
        limit=REGISTER_ATTEMPTS,
        window_seconds=REGISTER_WINDOW_SECONDS,
    )


def reset_attempts() -> None:
    """Forget every address (tests)."""
    with _lock:
        _attempts.clear()


def is_locked(user, *, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return user.locked_until is not None and user.locked_until > now


def record_failure(db, user, *, now: datetime | None = None) -> None:
    """Count one failed password, atomically in the database, so concurrent wrong
    passwords each count; lock the account at ``MAX_FAILURES``."""
    from sqlalchemy import update

    from community.models import User

    now = now or datetime.utcnow()
    count = db.execute(
        update(User)
        .where(User.id == user.id)
        .values(failed_login_count=User.failed_login_count + 1)
        .returning(User.failed_login_count)
    ).scalar_one()
    if count >= MAX_FAILURES:
        # Only the request that crosses the threshold resets the counter and sets the lock.
        db.execute(
            update(User)
            .where(User.id == user.id, User.failed_login_count >= MAX_FAILURES)
            .values(locked_until=now + timedelta(minutes=LOCK_MINUTES), failed_login_count=0)
        )


def record_success(user) -> None:
    user.failed_login_count = 0
    user.locked_until = None
