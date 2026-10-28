"""
SQLAlchemy models for monetization operations.
Tracks exports, credits ledger entries, licenses, and referrals.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship

from core.database import Base


class License(Base):
    """License record for paid exports."""

    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    license_key = Column(String(100), unique=True, nullable=False, index=True)
    terms_version = Column(String(50), nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)
    issued_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", backref="licenses")
    exports = relationship("Export", back_populates="license")


class Export(Base):
    """Export record for paid patch/rack outputs."""

    __tablename__ = "exports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patch_id = Column(
        Integer, ForeignKey("patches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rack_id = Column(
        Integer, ForeignKey("racks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True)
    export_type = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False, default="completed")
    credits_spent = Column(Integer, nullable=False, default=0)
    manifest_hash = Column(String(64), nullable=True, index=True)
    provenance = Column(JSON, nullable=True)
    license_id = Column(Integer, ForeignKey("licenses.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", backref="monetization_exports")
    license = relationship("License", back_populates="exports")
    patch = relationship("Patch", backref="exports")
    rack = relationship("Rack", backref="exports")


class Referral(Base):
    """Referral tracking record (append-only)."""

    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, index=True)
    referrer_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    referred_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(String(20), nullable=False, default="Pending")
    first_purchase_id = Column(
        Integer, ForeignKey("credits_ledger.id", ondelete="SET NULL"), nullable=True
    )
    rewarded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    referrer = relationship(
        "User", foreign_keys=[referrer_user_id], backref="monetization_referrals_sent"
    )
    referred = relationship(
        "User", foreign_keys=[referred_user_id], backref="monetization_referrals_received"
    )
    first_purchase = relationship("CreditsLedger", foreign_keys=[first_purchase_id])

    # At most one reward per referred user, even under concurrent purchases.
    __table_args__ = (
        Index(
            "uq_referrals_one_reward",
            "referred_user_id",
            unique=True,
            postgresql_where=text("status = 'Rewarded'"),
            sqlite_where=text("status = 'Rewarded'"),
        ),
    )


class CreditsLedger(Base):
    """Ledger of credit changes for users."""

    __tablename__ = "credits_ledger"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    change_type = Column(String(30), nullable=False, index=True)
    credits_delta = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    referral_id = Column(
        Integer, ForeignKey("referrals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    export_id = Column(
        Integer, ForeignKey("exports.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", backref="credits_ledger")
    export = relationship("Export", backref="credits_entries")
    referral = relationship("Referral", backref="ledger_entries", foreign_keys=[referral_id])
