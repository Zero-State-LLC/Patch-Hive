"""
SQLAlchemy models for community features (users, votes, comments).
"""

from datetime import datetime
import secrets

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database import Base


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=True)
    role = Column(String(20), nullable=False, default="User", index=True)
    avatar_url = Column(String(500), nullable=True)
    allow_public_avatar = Column(Boolean, default=True, nullable=False)
    bio = Column(Text, nullable=True)
    referral_code = Column(
        String(32), unique=True, nullable=False, index=True, default=lambda: secrets.token_hex(8)
    )
    referred_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # Sign-in brute-force protection (community/login_guard.py).
    failed_login_count = Column(Integer, nullable=False, default=0, server_default="0")
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    racks = relationship("Rack", back_populates="user", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="user", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    credit_entries = relationship(
        "CreditLedgerEntry", back_populates="user", cascade="all, delete-orphan"
    )
    exports = relationship("ExportRecord", back_populates="user", cascade="all, delete-orphan")
    referrals_sent = relationship(
        "AccountReferral",
        foreign_keys="AccountReferral.referrer_user_id",
        back_populates="referrer",
    )
    referral_received = relationship(
        "AccountReferral",
        foreign_keys="AccountReferral.referred_user_id",
        back_populates="referred",
    )
    referrer = relationship("User", remote_side=[id], backref="referrals")

    @property
    def is_admin(self) -> bool:
        """Compatibility view over the canonical role-based authorization field."""
        return self.role == "Admin"

    @is_admin.setter
    def is_admin(self, value: bool) -> None:
        self.role = "Admin" if value else "User"


class Vote(Base):
    """Vote/like on a rack or patch."""

    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rack_id = Column(Integer, ForeignKey("racks.id", ondelete="CASCADE"), nullable=True)
    patch_id = Column(Integer, ForeignKey("patches.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="votes")
    rack = relationship("Rack", back_populates="votes")
    patch = relationship("Patch", back_populates="votes")

    # Constraints: user can only vote once per item
    __table_args__ = (
        UniqueConstraint("user_id", "rack_id", name="unique_user_rack_vote"),
        UniqueConstraint("user_id", "patch_id", name="unique_user_patch_vote"),
    )


class Comment(Base):
    """Comment on a rack or patch."""

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rack_id = Column(Integer, ForeignKey("racks.id", ondelete="CASCADE"), nullable=True)
    patch_id = Column(Integer, ForeignKey("patches.id", ondelete="CASCADE"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="comments")
    rack = relationship("Rack", back_populates="comments")
    patch = relationship("Patch", back_populates="comments")
