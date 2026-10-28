"""
SQLAlchemy model for patch generation runs.
"""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
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
    # The validation report of the run (spec 001 FR-016/FR-019): kept on the run so a
    # validation_failed run still says why after the response is gone.
    validation_report = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    rack = relationship("Rack", backref="runs")
    patches = relationship("Patch", backref="run")
