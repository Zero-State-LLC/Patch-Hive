"""Run outcome records: why a run failed, and every evidence decision.

Revision ID: 20261106_run_outcome_records
Revises: 20261102_export_fair_use
Create Date: 2026-11-06

Spec 001 T090:

- ``runs.failure_reason`` keeps why a run ended ``failed`` after the response is gone (D5).
- ``evidence_decisions`` records each decision on a photo candidate, including a reject and any
  later reversal (D8). A confirmation batch used to keep only what entered the inventory.

Additive. Existing runs have no reason, and earlier decisions weren't recorded.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261106_run_outcome_records"
down_revision = "20261102_export_fair_use"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("runs") as batch:
        batch.add_column(sa.Column("failure_reason", sa.String(200), nullable=True))
    op.create_table(
        "evidence_decisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("rack_id", sa.Integer(), sa.ForeignKey("racks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("candidate_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("module_revision_id", sa.String(128), nullable=True),
        sa.Column("replacement_candidate_id", sa.String(128), nullable=True),
        sa.Column(
            "inventory_revision_id",
            sa.String(64),
            sa.ForeignKey("system_inventory_revisions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reverses_decision_id",
            sa.String(64),
            sa.ForeignKey("evidence_decisions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("decided_by", sa.String(128), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evidence_decisions_rack_id", "evidence_decisions", ["rack_id"])
    op.create_index("ix_evidence_decisions_candidate_id", "evidence_decisions", ["candidate_id"])


def downgrade() -> None:
    op.drop_index("ix_evidence_decisions_candidate_id", table_name="evidence_decisions")
    op.drop_index("ix_evidence_decisions_rack_id", table_name="evidence_decisions")
    op.drop_table("evidence_decisions")
    with op.batch_alter_table("runs") as batch:
        batch.drop_column("failure_reason")
