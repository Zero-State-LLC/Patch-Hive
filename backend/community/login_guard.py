"""
Brute-force protection for sign-in.

- Per account: after ``MAX_FAILURES`` wrong passwords the account is locked for
  ``LOCK_MINUTES``. While locked, sign-in answers exactly like a wrong password, so a
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

_lock = threading.Lock()
_attempts: dict[str, deque[float]] = {}


def client_address(request: Request) -> str:
    # The edge Worker sets X-Forwarded-For to CF-Connecting-IP, overwriting client values.
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def allow_attempt(address: str, *, now: float | None = None) -> bool:
    """Record one attempt from ``address``; False once it is over the per-minute limit."""
    now = time.monotonic() if now is None else now
    with _lock:
        window = _attempts.setdefault(address, deque())
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= IP_ATTEMPTS_PER_MINUTE:
            return False
        window.append(now)
        return True


def reset_attempts() -> None:
    """Forget every address (tests)."""
    with _lock:
        _attempts.clear()


def is_locked(user, *, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return user.locked_until is not None and user.locked_until > now


def record_failure(user, *, now: datetime | None = None) -> None:
    now = now or datetime.utcnow()
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= MAX_FAILURES:
        user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
        user.failed_login_count = 0


def record_success(user) -> None:
    user.failed_login_count = 0
    user.locked_until = None
