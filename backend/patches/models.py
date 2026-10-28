"""
SQLAlchemy models for patches (connection graphs between modules).
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from core.database import Base


class Patch(Base):
    """
    A patch represents a specific configuration of cable connections between modules.
    Stores connections as a graph, along with metadata about generation and categorization.
    """

    __tablename__ = "patches"

    id = Column(Integer, primary_key=True, index=True)

    # Association with rack/run
    rack_id = Column(
        Integer, ForeignKey("racks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True)

    # Metadata
    name = Column(String(200), nullable=False)  # Auto-generated or user-specified
    suggested_name = Column(String(200), nullable=True)
    name_override = Column(String(200), nullable=True)
    category = Column(
        String(50), nullable=False, index=True
    )  # one of core.ir.PatchCategory; older rows may hold retired values such as "Study"
    description = Column(Text, nullable=True)

    # Connection graph
    # Format: [
    #   {
    #     "from_module_id": 1,
    #     "from_port": "Audio Out",
    #     "to_module_id": 2,
    #     "to_port": "Audio In",
    #     "cable_type": "audio"  # "audio", "cv", "gate", "clock"
    #   },
    #   ...
    # ]
    connections = Column(JSON, nullable=False, default=list)

    # Patch engine metadata (SEED principle - full traceability)
    generation_seed = Column(Integer, nullable=False)
    generation_version = Column(
        String(20), nullable=False
    )  # Patch engine version that generated this
    engine_config = Column(JSON, nullable=True)  # Config parameters used during generation

    # ABX-Core v1.3: Enhanced provenance
    provenance = Column(JSON, nullable=True)  # Full provenance record (Provenance.to_dict())
    generation_ir = Column(JSON, nullable=True)  # Complete IR that generated this patch
    generation_ir_hash = Column(String(32), nullable=True, index=True)  # Hash for deduplication

    # Waveform visualization
    waveform_svg_path = Column(String(500), nullable=True)  # Path to SVG file
    waveform_params = Column(JSON, nullable=True)  # Parameters used to generate waveform

    # Sharing
    is_public = Column(Boolean, default=False, nullable=False)
    tags = Column(JSON, nullable=False, default=list)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    rack = relationship("Rack", back_populates="patches")
    votes = relationship("Vote", back_populates="patch", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="patch", cascade="all, delete-orphan")
