"""Granting credits, shared by the admin console and beta invites."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy.orm import Session

from canon.models import CanonicalCreditLedgerEntryRecord
from monetization.models import CreditsLedger


def write_credit_grant(
    db: Session, *, user_id: int, credits: int, reason: str, grant_key: str, key_prefix: str
) -> str:
    """Grant credits to both the legacy and canonical ledgers, and return the canonical id.

    Dual-write keeps historical admin/referral paths working while MVP debit/balance surfaces
    read the canonical ledger only. The id comes from ``grant_key``, so a retry with the same
    key adds nothing to the canonical ledger.
    """
    db.add(
        CreditsLedger(user_id=user_id, change_type="Grant", credits_delta=credits, notes=reason)
    )
    grant_id = f"grant-{sha256(grant_key.encode('utf-8')).hexdigest()[:24]}"
    if db.get(CanonicalCreditLedgerEntryRecord, grant_id) is None:
        db.add(
            CanonicalCreditLedgerEntryRecord(
                id=grant_id,
                user_id=user_id,
                delta=int(credits),
                entry_type="grant",
                idempotency_key=f"{key_prefix}:{grant_id}",
                export_id=None,
                created_at=datetime.now(timezone.utc),
            )
        )
    return grant_id
