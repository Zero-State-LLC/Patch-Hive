"""
SQLAlchemy model for patch generation runs.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from core.database import Base


class Run(Base):
    """Run record for patch generation attempts."""

    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    rack_id = Column(
        Integer, ForeignKey("racks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status = Column(String(20), nullable=False, default="queued")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    rack = relationship("Rack", backref="runs")
    patches = relationship("Patch", backref="run")
