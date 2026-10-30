"""
SQLAlchemy models for user racks (case + module configurations).
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from core.database import Base


class Rack(Base):
    """User's rack configuration: a case filled with modules."""

    __tablename__ = "racks"

    id = Column(Integer, primary_key=True, index=True)

    # Ownership
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id = Column(
        Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Metadata
    name = Column(String(200), nullable=False)  # Auto-generated or user-specified
    name_suggested = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=False, default=list)

    # Sharing
    is_public = Column(Boolean, default=False, nullable=False)

    # Generation metadata (for deterministic naming)
    generation_seed = Column(Integer, nullable=True)

    # Soft delete (spec 001 OQ-02): a deleted rack disappears from the API, but its
    # runs, patches and canonical history stay, because they are append-only.
    deleted_at = Column(DateTime, nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="racks")
    case = relationship("Case", back_populates="racks")
    modules = relationship("RackModule", back_populates="rack", cascade="all, delete-orphan")
    # No delete cascade: runs and patches outlive their rack (append-only).
    patches = relationship("Patch", back_populates="rack")
    votes = relationship("Vote", back_populates="rack", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="rack", cascade="all, delete-orphan")


class RackModule(Base):
    """A module placed in a specific position within a rack."""

    __tablename__ = "rack_modules"

    id = Column(Integer, primary_key=True, index=True)

    rack_id = Column(
        Integer, ForeignKey("racks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    module_id = Column(
        Integer, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Position in rack
    row_index = Column(Integer, nullable=False)  # 0-indexed row number
    start_hp = Column(Integer, nullable=False)  # Starting HP position (0-indexed)
    # The jumper setting this placement's module is set to (spec 003 D8); NULL = not chosen.
    power_config_id = Column(
        Integer, ForeignKey("power_configs.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    rack = relationship("Rack", back_populates="modules")
    module = relationship("Module", back_populates="rack_modules")
