"""Ed25519 approver signatures over evaluation receipt SHAs (Spec 007, T081).

An approver signs a receipt's ``receipt_sha256`` with a private key that never
leaves their machine. Public keys live in a committed allowlist
(``evaluation_approvers.json``) that changes only through a reviewed PR. Anyone
can verify; only the key holder can sign.

The signed message is ``SIGNING_DOMAIN + receipt_sha256`` (the 64 lowercase hex
characters as ASCII). The domain prefix stops a signature made for another
purpose from being replayed as a receipt approval.

Every check fails closed: an unknown key id, a key that is revoked or not yet
valid, a malformed or unreadable allowlist, a bad signature, or a SHA that does
not match all refuse. Failure codes are stable and never contain key material.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

APPROVER_ALLOWLIST_SCHEMA = "patchhive.eval-approver-allowlist.v1"
RECEIPT_SIGNATURE_SCHEMA = "patchhive.eval-receipt-signature.v1"
SIGNING_DOMAIN = b"patchhive.eval-enablement-receipt.v1\n"
APPROVER_ALLOWLIST_PATH = Path(__file__).with_name("evaluation_approvers.json")

_KEY_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ED25519_PUBLIC_KEY_BYTES = 32
_ED25519_SIGNATURE_BYTES = 64


class SignatureError(ValueError):
    """Fail-closed error. ``code`` is stable and never contains key material."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _b64_exact(value: str, length: int) -> bytes:
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as exc:
        raise ValueError("not base64") from exc
    if len(raw) != length:
        raise ValueError(f"expected {length} bytes")
    return raw


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp that must carry a timezone; return it in UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _same(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


class ApproverKey(BaseModel):
    """One approver public key in the committed allowlist."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key_id: str
    algorithm: Literal["ed25519"] = "ed25519"
    public_key: str
    valid_from: str
    revoked_at: str | None = None

    @field_validator("key_id")
    @classmethod
    def _key_id_shape(cls, value: str) -> str:
        if not _KEY_ID.match(value):
            raise ValueError("key_id must match ^[a-z0-9][a-z0-9._-]{0,63}$")
        return value

    @field_validator("public_key")
    @classmethod
    def _public_key_shape(cls, value: str) -> str:
        Ed25519PublicKey.from_public_bytes(_b64_exact(value, _ED25519_PUBLIC_KEY_BYTES))
        return value

    @field_validator("valid_from")
    @classmethod
    def _valid_from_shape(cls, value: str) -> str:
        parse_utc(value)
        return value

    @field_validator("revoked_at")
    @classmethod
    def _revoked_at_shape(cls, value: str | None) -> str | None:
        if value is not None:
            parse_utc(value)
        return value

    @model_validator(mode="after")
    def _revoked_after_valid(self) -> "ApproverKey":
        if self.revoked_at is not None and parse_utc(self.revoked_at) <= parse_utc(self.valid_from):
            raise ValueError("revoked_at must be after valid_from")
        return self

    def public_key_obj(self) -> Ed25519PublicKey:
        return Ed25519PublicKey.from_public_bytes(
            _b64_exact(self.public_key, _ED25519_PUBLIC_KEY_BYTES)
        )


class ApproverAllowlist(BaseModel):
    """The committed approver allowlist. Key ids and public keys are unique."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["patchhive.eval-approver-allowlist.v1"]
    description: str = ""
    approvers: tuple[ApproverKey, ...] = ()

    @model_validator(mode="after")
    def _unique(self) -> "ApproverAllowlist":
        ids = [key.key_id for key in self.approvers]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate key_id in approver allowlist")
        keys = [key.public_key for key in self.approvers]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate public_key in approver allowlist")
        return self

    def get(self, key_id: str) -> ApproverKey | None:
        for key in self.approvers:
            if _same(key.key_id, key_id):
                return key
        return None


def load_approver_allowlist(path: Path | None = None) -> ApproverAllowlist:
    """Load and validate the committed allowlist. Raises ``SignatureError`` on any defect."""
    target = path if path is not None else APPROVER_ALLOWLIST_PATH
    try:
        data = json.loads(Path(target).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SignatureError("APPROVER_ALLOWLIST_UNREADABLE") from exc
    try:
        return ApproverAllowlist.model_validate(data)
    except ValidationError as exc:
        raise SignatureError("APPROVER_ALLOWLIST_INVALID") from exc


class ReceiptSignature(BaseModel):
    """An approver's Ed25519 signature over one receipt SHA, kept beside the receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["patchhive.eval-receipt-signature.v1"] = RECEIPT_SIGNATURE_SCHEMA
    algorithm: Literal["ed25519"] = "ed25519"
    key_id: str
    receipt_sha256: str
    signature: str

    @field_validator("key_id")
    @classmethod
    def _key_id_shape(cls, value: str) -> str:
        if not _KEY_ID.match(value):
            raise ValueError("key_id must match ^[a-z0-9][a-z0-9._-]{0,63}$")
        return value

    @field_validator("receipt_sha256")
    @classmethod
    def _sha_shape(cls, value: str) -> str:
        if not _HEX64.match(value):
            raise ValueError("receipt_sha256 must be 64 lowercase hex characters")
        return value

    @field_validator("signature")
    @classmethod
    def _signature_shape(cls, value: str) -> str:
        _b64_exact(value, _ED25519_SIGNATURE_BYTES)
        return value


def signing_message(receipt_sha256: str) -> bytes:
    """The exact bytes an approver signs for ``receipt_sha256``."""
    if not isinstance(receipt_sha256, str) or not _HEX64.match(receipt_sha256):
        raise SignatureError("RECEIPT_SHA_INVALID")
    return SIGNING_DOMAIN + receipt_sha256.encode("ascii")


def sign_receipt_sha256(
    private_key: Ed25519PrivateKey, *, key_id: str, receipt_sha256: str
) -> ReceiptSignature:
    """Sign a receipt SHA. For the operator's offline machine and for tests."""
    signature = private_key.sign(signing_message(receipt_sha256))
    return ReceiptSignature(
        key_id=key_id,
        receipt_sha256=receipt_sha256,
        signature=base64.b64encode(signature).decode("ascii"),
    )


def signature_failures(
    signature: ReceiptSignature | None,
    *,
    receipt_sha256: str,
    approved_by: str,
    approved_at: str,
    allowlist: ApproverAllowlist | None,
    now: datetime | None = None,
) -> tuple[str, ...]:
    """Failure codes for a receipt signature; empty means the signature is valid.

    A key must be valid at both the receipt's ``approved_at`` and verification
    time. A revoked key refuses once ``revoked_at`` has passed, whatever the
    receipt's ``approved_at`` says, because ``approved_at`` is chosen by the
    signer: a lost key is revoked and its receipts are re-signed with a new key.
    """
    if signature is None:
        return ("RECEIPT_SIGNATURE_MISSING",)
    if not isinstance(signature, ReceiptSignature):
        return ("RECEIPT_SIGNATURE_INVALID_TYPE",)
    if allowlist is None:
        return ("APPROVER_ALLOWLIST_MISSING",)
    try:
        signature = ReceiptSignature.model_validate(signature.model_dump())
    except ValidationError:
        return ("RECEIPT_SIGNATURE_MALFORMED",)
    failed: list[str] = []
    if not isinstance(receipt_sha256, str) or not _HEX64.match(receipt_sha256):
        return ("RECEIPT_SHA_INVALID",)
    if not _same(signature.receipt_sha256, receipt_sha256):
        failed.append("SIGNATURE_RECEIPT_SHA_MISMATCH")
    if not isinstance(approved_by, str) or not _same(signature.key_id, approved_by):
        failed.append("SIGNATURE_KEY_NOT_APPROVER")
    key = allowlist.get(signature.key_id)
    if key is None:
        failed.append("APPROVER_KEY_UNKNOWN")
        return tuple(failed)
    try:
        approved = parse_utc(approved_at)
    except (TypeError, ValueError, AttributeError):
        failed.append("APPROVAL_TIMESTAMP_INVALID")
        return tuple(failed)
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        failed.append("VERIFICATION_TIME_INVALID")
        return tuple(failed)
    valid_from = parse_utc(key.valid_from)
    if moment < valid_from or approved < valid_from:
        failed.append("APPROVER_KEY_NOT_YET_VALID")
    if key.revoked_at is not None:
        revoked = parse_utc(key.revoked_at)
        if revoked <= moment or revoked <= approved:
            failed.append("APPROVER_KEY_REVOKED")
    try:
        key.public_key_obj().verify(
            _b64_exact(signature.signature, _ED25519_SIGNATURE_BYTES),
            signing_message(receipt_sha256),
        )
    except (InvalidSignature, ValueError, SignatureError):
        failed.append("SIGNATURE_INVALID")
    return tuple(failed)
