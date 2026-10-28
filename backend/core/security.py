"""
Security utilities for authentication and authorization.
"""

import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

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
# New hashes are Argon2id. bcrypt hashes from before verify and are upgraded on the next
# login. passlib (unmaintained, broken by bcrypt 4.1+) silently fell back to its own
# pbkdf2-sha256 format, so those hashes verify here too and are upgraded the same way.
_password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))

# Longest password accepted; also caps the work done hashing a hostile request.
MAX_PASSWORD_LENGTH = 128

# A real hash of a throwaway value, verified when no user matches so a login for an
# unknown name costs the same time as a wrong password.
_DUMMY_HASH = _password_hash.hash("not-a-real-password")


def _ab64_decode(value: str) -> bytes:
    """passlib's "adapted base64": '.' for '+', no padding."""
    value = value.replace(".", "+")
    return base64.b64decode(value + "=" * (-len(value) % 4))


def _verify_passlib_pbkdf2(password: str, stored: str) -> bool:
    try:
        _, _, rounds, salt, checksum = stored.split("$")
        expected = _ab64_decode(checksum)
        derived = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _ab64_decode(salt), int(rounds), len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived, expected)


def verify_and_update_password(plain_password: str, hashed_password: str) -> tuple[bool, Optional[str]]:
    """Check a password. Returns (valid, new_hash); new_hash is set when the stored hash
    should be replaced with a current Argon2id one."""
    if not hashed_password or len(plain_password) > MAX_PASSWORD_LENGTH:
        return False, None
    if hashed_password.startswith("$pbkdf2-sha256$"):
        valid = _verify_passlib_pbkdf2(plain_password, hashed_password)
        return valid, (_password_hash.hash(plain_password) if valid else None)
    try:
        return _password_hash.verify_and_update(plain_password, hashed_password)
    except Exception:
        # An unknown or malformed hash never verifies.
        return False, None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return verify_and_update_password(plain_password, hashed_password)[0]


def burn_password_check(plain_password: str) -> None:
    """Spend the time of a real check when there is nothing to check against."""
    verify_and_update_password(plain_password, _DUMMY_HASH)


def get_password_hash(password: str) -> str:
    """Hash a password with Argon2id."""
    return _password_hash.hash(password)


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
