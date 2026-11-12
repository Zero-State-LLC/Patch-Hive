"""
SQLAlchemy models for credits, exports, and referrals.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from core.database import Base


class CreditLedgerEntry(Base):
    """A retired credit ledger. Nothing reads or writes it now; spending and the balance use
    the canonical ledger (spec 004 FR-009). The table stays so any old rows are kept."""

    __tablename__ = "credit_ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_type = Column(String(20), nullable=False)  # Purchase, Spend, Grant, Refund
    amount = Column(Integer, nullable=False)  # Positive or negative
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="credit_entries")


class ExportRecord(Base):
    """Record of an export action."""

    __tablename__ = "export_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    export_type = Column(String(20), nullable=False)  # patch | rack
    entity_id = Column(Integer, nullable=False)
    run_id = Column(String(64), nullable=False)
    unlocked = Column(Boolean, default=False, nullable=False)
    license_type = Column(String(50), nullable=True)  # Personal | Educational | Commercial
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="exports")


class AccountReferral(Base):
    """A retired account-dashboard referral projection. Nothing reads or writes it now; the
    summary comes from the append-only ``referrals`` rows owned by :mod:`monetization.models`
    (spec 004 FR-031). The table stays so any old rows are kept.
    """

    __tablename__ = "account_referrals"

    id = Column(Integer, primary_key=True, index=True)
    referrer_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    referred_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(String(20), nullable=False, default="pending")  # pending | earned
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    rewarded_at = Column(DateTime, nullable=True)

    referrer = relationship(
        "User", foreign_keys=[referrer_user_id], back_populates="referrals_sent"
    )
    referred = relationship(
        "User", foreign_keys=[referred_user_id], back_populates="referral_received"
    )

    __table_args__ = (
        UniqueConstraint("referred_user_id", name="unique_account_referral_referred_user"),
        UniqueConstraint(
            "referrer_user_id",
            "referred_user_id",
            name="unique_account_referrer_referred_pair",
        ),
    )


# Compatibility export for the historical account API. The mapped class keeps a
# distinct registry name, avoiding SQLAlchemy's ambiguous ``Referral`` lookup.
Referral = AccountReferral
