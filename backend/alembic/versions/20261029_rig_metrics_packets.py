"""Store one RigMetricsPacket per rig revision.

Revision ID: 20261029_rig_metrics_packets
Revises: 20261029_webhook_disposition
Create Date: 2026-10-29

Spec 001 FR-027, T031. The packet holds ``rig_id``, ``module_count`` and
``category_counts``; the six scores are ``NOT_COMPUTABLE`` until OQ-11 defines them.
Additive only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261029_rig_metrics_packets"
down_revision = "20261029_webhook_disposition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "rig_metrics_packets" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "rig_metrics_packets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "rig_revision_id",
            sa.String(64),
            sa.ForeignKey("rig_revisions.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("packet", sa.JSON(), nullable=False),
        sa.Column("canonical_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_rig_metrics_packets_canonical_hash", "rig_metrics_packets", ["canonical_hash"]
    )


def downgrade() -> None:
    op.drop_index("ix_rig_metrics_packets_canonical_hash", table_name="rig_metrics_packets")
    op.drop_table("rig_metrics_packets")
