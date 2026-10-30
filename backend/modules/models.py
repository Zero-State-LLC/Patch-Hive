"""
SQLAlchemy models for Eurorack modules.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database import Base


class Module(Base):
    """Eurorack module model with full metadata."""

    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)

    # Basic info
    brand = Column(String(100), nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    hp = Column(Integer, nullable=False)  # Width in HP units

    # Module type/category
    module_type = Column(
        String(50), nullable=False, index=True
    )  # VCO, VCF, VCA, ENV, LFO, SEQ, UTIL, MIX, FX, etc.

    # Power specifications
    power_12v_ma = Column(Integer, nullable=True)  # +12V power draw in mA
    power_neg12v_ma = Column(Integer, nullable=True)  # -12V power draw in mA
    power_5v_ma = Column(Integer, nullable=True)  # +5V power draw in mA

    # Physical depth for case fit (null = unspecified; never invent)
    depth_mm = Column(Float, nullable=True, index=True)

    # I/O ports (stored as JSON array)
    # Format: [{"name": "CV In 1", "type": "cv_in"}, {"name": "Audio Out", "type": "audio_out"}, ...]
    io_ports = Column(JSON, nullable=False, default=list)

    # Metadata
    tags = Column(JSON, nullable=False, default=list)  # ["analog", "digital", "west-coast", etc.]
    description = Column(Text, nullable=True)
    manufacturer_url = Column(String(500), nullable=True)
    # Registry linkage (PDB wiring)
    registry_manufacturer_slug = Column(String(100), nullable=True, index=True)
    registry_device_slug = Column(String(200), nullable=True, index=True)

    status = Column(String(20), nullable=False, default="active", index=True)
    replacement_module_id = Column(Integer, ForeignKey("modules.id"), nullable=True)
    deprecated_at = Column(DateTime, nullable=True)
    tombstoned_at = Column(DateTime, nullable=True)

    # Data provenance (SEED principle)
    source = Column(String(50), nullable=False)  # "Manual", "CSV", "ModularGrid", etc.
    source_reference = Column(String(500), nullable=True)  # URL, filename, etc.

    # Brand check for catalog candidates. Unverified until a source page confirms it.
    verification_status = Column(String(20), nullable=False, default="unverified", server_default="unverified")
    verification_source_url = Column(String(500), nullable=True)
    # True when ModularGrid-derived values were removed and the row needs a maker-page check.
    needs_reverify = Column(Boolean, nullable=False, default=False, server_default="false")
    imported_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('verified', 'corrected', 'flagged', 'unverified')",
            name="ck_modules_verification_status",
        ),
    )

    # Relationships
    rack_modules = relationship("RackModule", back_populates="module", cascade="all, delete-orphan")
    power_configs = relationship("PowerConfig", back_populates="module", order_by="PowerConfig.id")


class PowerConfig(Base):
    """One jumper setting's draws for a module (spec 003 D8, T034).

    Filled by the catalog loader from a maker page; a rail the page gives no number
    for stays NULL (unknown), never 0. The loader inserts missing rows only.
    """

    __tablename__ = "power_configs"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False, index=True)
    brand = Column(String(100), nullable=False)
    name = Column(String(200), nullable=False)
    setting_key = Column(String(120), nullable=False)
    # The setting's label as printed on the maker page.
    label = Column(String(300), nullable=False)
    kind = Column(String(40), nullable=False)
    # True only where the page itself marks the setting recommended.
    is_recommended = Column(Boolean, nullable=False, default=False, server_default="false")
    power_12v_ma = Column(Integer, nullable=True)
    power_neg12v_ma = Column(Integer, nullable=True)
    power_5v_ma = Column(Integer, nullable=True)
    unit_stated = Column(Boolean, nullable=False)
    # Per rail: status (stated / not_used / not_stated), qualifier and the verbatim quote.
    rails = Column(JSON, nullable=False, default=dict)
    source_url = Column(String(500), nullable=False)
    # The page's power block, verbatim.
    quote = Column(Text, nullable=False)
    source_batch = Column(String(64), nullable=False)
    content_sha256 = Column(String(64), nullable=True)
    fetched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("module_id", "setting_key", name="uq_power_configs_module_setting"),
        CheckConstraint(
            "(power_12v_ma IS NULL OR power_12v_ma >= 0) AND "
            "(power_neg12v_ma IS NULL OR power_neg12v_ma >= 0) AND "
            "(power_5v_ma IS NULL OR power_5v_ma >= 0)",
            name="ck_power_configs_rails_non_negative",
        ),
    )

    module = relationship("Module", back_populates="power_configs")
