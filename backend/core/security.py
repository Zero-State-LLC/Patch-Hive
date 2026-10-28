"""
Security utilities for authentication and authorization.
"""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext

from .config import settings

# Environments where the shipped placeholder secrets are tolerated.
DEV_ENVIRONMENTS = {"development", "dev", "local", "test", "testing", "ci"}

# Placeholder values that ship in config.py, start.sh and the compose files.
KNOWN_DEFAULT_SECRETS = {
    "dev-secret-key-change-in-production",
    "development-secret-key-change-in-production",
    "staging-secret-key-change-me-32chars-min",
}


def is_dev_environment(environment: str) -> bool:
    return str(environment or "").strip().lower() in DEV_ENVIRONMENTS


def validate_secret_policy(app_settings: Any = settings) -> None:
    """Refuse to start outside development with a placeholder or short SECRET_KEY.

    The key signs every login token, so a public default lets anyone mint one.
    """
    if is_dev_environment(app_settings.environment):
        return
    key = str(app_settings.secret_key or "")
    if key in KNOWN_DEFAULT_SECRETS or len(key.encode("utf-8")) < 32:
        raise RuntimeError(
            f"SECRET_KEY must be a private value of at least 32 bytes when "
            f"ENVIRONMENT={app_settings.environment}"
        )


def derived_key(purpose: str, app_settings: Any = settings) -> str:
    """A per-purpose key derived from SECRET_KEY (HMAC-SHA256 with a purpose label),
    so a key that leaks from one use cannot sign for another."""
    label = f"patchhive/{purpose}/v1".encode("utf-8")
    return hmac.new(str(app_settings.secret_key).encode("utf-8"), label, hashlib.sha256).hexdigest()


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    try:
        return pwd_context.hash(password)
    except Exception:
        fallback = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
        return fallback.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT access token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except InvalidTokenError:
        return None
