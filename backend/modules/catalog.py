"""
Module Catalog model - lightweight searchable/filterable module directory.

Two-tier architecture:
1. ModuleCatalog: Lightweight listing of ALL modules (searchable/filterable)
2. Module: Full specs, only populated when user adds to rack

This allows:
- Fast catalog browsing without loading heavy specs
- Scalability to 8,000+ modules
- On-demand spec fetching
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String

from core.database import Base


class ModuleCatalog(Base):
    """
    Lightweight module catalog for browsing/searching.

    Contains minimal info for fast queries. Full specs fetched on-demand
    when user adds module to rack.
    """

    __tablename__ = "module_catalog"

    id = Column(Integer, primary_key=True, index=True)

    # Basic identification
    modulargrid_id = Column(Integer, unique=True, nullable=True, index=True)  # MG ID if available
    slug = Column(String(200), unique=True, nullable=False, index=True)  # brand-name normalized
    brand = Column(String(100), nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)

    # Essential specs for filtering
    hp = Column(Integer, nullable=True, index=True)  # Width
    category = Column(String(50), nullable=True, index=True)  # VCO, VCF, VCA, etc.

    # Visual
    image_url = Column(String(500), nullable=True)  # Module image

    # Links
    modulargrid_url = Column(String(500), nullable=True)
    manufacturer_url = Column(String(500), nullable=True)

    # Registry linkage (PDB)
    registry_manufacturer_slug = Column(String(100), nullable=True, index=True)
    registry_device_slug = Column(String(200), nullable=True, index=True)

    # Status
    is_available = Column(
        String(20), default="available", index=True
    )  # available, discontinued, upcoming

    # Provenance (SEED): which pipeline admitted this lightweight row.
    # e.g. SynthCatalogResearch, ModularGrid, Manual — null only pre-migration.
    source = Column(String(50), nullable=True, index=True)
    # True when a ModularGrid-derived value (hp) was removed; see catalog_value_archive.
    needs_reverify = Column(Boolean, nullable=False, default=False, server_default="false")
    # External-source policy fields. ModularGrid-derived discovery leads carry
    # access_basis="unknown" and evidence_status="CATALOG_OBSERVED" (spec 003 D1, FR-033).
    access_basis = Column(String(40), nullable=True, index=True)
    evidence_status = Column(String(40), nullable=True)

    # Tombstone (never deleted): hidden from browse, search and counts; a slug lookup
    # still answers. Set only by the loader's retirement manifest.
    tombstoned_at = Column(DateTime, nullable=True, index=True)
    tombstone_reason = Column(String(200), nullable=True)

    # Metadata
    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(
        String(50),
        default=lambda: datetime.utcnow().isoformat(),
        onupdate=lambda: datetime.utcnow().isoformat(),
    )

    # Indexes for fast filtering
    __table_args__ = (
        Index("idx_catalog_brand_name", "brand", "name"),
        Index("idx_catalog_category_hp", "category", "hp"),
        Index("idx_catalog_available", "is_available"),
    )

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "modulargrid_id": self.modulargrid_id,
            "slug": self.slug,
            "brand": self.brand,
            "name": self.name,
            "hp": self.hp,
            "category": self.category,
            "image_url": self.image_url,
            "modulargrid_url": self.modulargrid_url,
            "manufacturer_url": self.manufacturer_url,
            "registry_manufacturer_slug": self.registry_manufacturer_slug,
            "registry_device_slug": self.registry_device_slug,
            "is_available": self.is_available,
            "source": self.source,
            "access_basis": self.access_basis,
            "evidence_status": self.evidence_status,
            "tombstoned_at": self.tombstoned_at.isoformat() if self.tombstoned_at else None,
            "tombstone_reason": self.tombstone_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def create_slug(brand: str, name: str) -> str:
        """Create URL-safe slug from brand and name."""
        import re

        combined = f"{brand}-{name}".lower()
        slug = re.sub(r"[^a-z0-9]+", "-", combined)
        return slug.strip("-")
