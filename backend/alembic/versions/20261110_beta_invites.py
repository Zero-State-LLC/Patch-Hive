"""One-use invites to the closed beta.

Revision ID: 20261110_beta_invites
Revises: 20261107_photo_readings
Create Date: 2026-11-10

Staging sign-up needs one of these while `ENABLE_INVITE_ONLY_SIGNUP` is on.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261110_beta_invites"
down_revision = "20261107_photo_readings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beta_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "redeemed_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            unique=True,
        ),
        sa.Column("redeemed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("beta_invites")
