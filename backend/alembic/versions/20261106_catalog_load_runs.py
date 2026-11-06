"""A lasting record of each catalog load, and what a rollback needs (spec 003 FR-031, decision 40).

Revision ID: 20261106_catalog_load_runs
Revises: 20261106_run_outcome_records
Create Date: 2026-11-06

Additive only. ``catalog_load_runs`` keeps each applied load's receipt, and
``catalog_load_changes`` the rows it inserted and the fields it changed. A rolled-back run's
archive rows stay in ``catalog_value_archive``, marked so the reverify guards stop reading them.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261106_catalog_load_runs"
down_revision = "20261106_run_outcome_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_load_runs",
        sa.Column("run_id", sa.String(80), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("rollback_of", sa.String(80), nullable=True),
        sa.Column("rolled_back_by", sa.String(80), nullable=True),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("inputs_hash", sa.String(64), nullable=True),
        sa.Column("receipt", sa.JSON(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('apply', 'rollback')", name="ck_catalog_load_runs_kind"),
    )
    op.create_table(
        "catalog_load_changes",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(80),
            sa.ForeignKey("catalog_load_runs.run_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("table_name", sa.String(40), nullable=False),
        sa.Column("row_id", sa.BigInteger(), nullable=False),
        sa.Column("row_key", sa.String(500), nullable=True),
        sa.Column("change", sa.String(8), nullable=False),
        sa.Column("field", sa.String(80), nullable=True),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.CheckConstraint("change IN ('insert', 'update')", name="ck_catalog_load_changes_change"),
    )
    with op.batch_alter_table("catalog_value_archive") as batch:
        batch.add_column(sa.Column("rolled_back_run_id", sa.String(80), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("catalog_value_archive") as batch:
        batch.drop_column("rolled_back_run_id")
    op.drop_table("catalog_load_changes")
    op.drop_table("catalog_load_runs")
