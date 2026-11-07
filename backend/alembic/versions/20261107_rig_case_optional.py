"""Make a Rig's Case optional, so a Rig can start from a photo.

Revision ID: 20261107_rig_case_optional
Revises: 20261106_commerce_append_only
Create Date: 2026-11-07

Spec 009 T020 (ADR-007). A Rig started from a photo has no Case until its owner names one.
No data change: every existing Rig keeps its Case. The downgrade refuses while any Rig has
no Case, because putting the constraint back would need a Case nobody chose.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261107_rig_case_optional"
down_revision = "20261106_commerce_append_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("racks") as batch:
        batch.alter_column("case_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    caseless = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM racks WHERE case_id IS NULL")
    ).scalar()
    if caseless:
        raise RuntimeError(
            f"{caseless} Rig(s) have no Case; name a Case for each before downgrading"
        )
    with op.batch_alter_table("racks") as batch:
        batch.alter_column("case_id", existing_type=sa.Integer(), nullable=False)
