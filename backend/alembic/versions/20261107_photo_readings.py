"""Readings and Sightings: what a Rig photo was read to show.

Revision ID: 20261107_photo_readings
Revises: 20261107_rig_case_optional
Create Date: 2026-11-07

Spec 009 T021. A Reading is evidence, never canon; its Sightings are append-only. The
downgrade refuses while any Reading exists, because dropping the tables would lose it.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261107_photo_readings"
down_revision = "20261107_rig_case_optional"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "photo_readings",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("rack_id", sa.Integer(), nullable=False),
        sa.Column("image_asset_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=True),
        sa.Column("photo_sha256", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("first_row", sa.Integer(), nullable=False),
        sa.Column("last_row", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["rack_id"], ["racks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_asset_id"], ["image_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    for column in ("rack_id", "image_asset_id", "user_id", "photo_sha256"):
        op.create_index(f"ix_photo_readings_{column}", "photo_readings", [column])

    op.create_table(
        "photo_sightings",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("reading_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("box", sa.JSON(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("start_hp", sa.Integer(), nullable=False),
        sa.Column("hp", sa.Integer(), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("disposition", sa.String(length=16), nullable=False),
        sa.Column("policy_reason", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["reading_id"], ["photo_readings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("reading_id", "position", name="uq_photo_sightings_position"),
    )
    op.create_index("ix_photo_sightings_reading_id", "photo_sightings", ["reading_id"])


def downgrade() -> None:
    readings = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM photo_readings")).scalar()
    if readings:
        raise RuntimeError(
            f"refusing to downgrade 20261107_photo_readings: {readings} Reading(s) would be lost"
        )
    op.drop_index("ix_photo_sightings_reading_id", table_name="photo_sightings")
    op.drop_table("photo_sightings")
    for column in ("photo_sha256", "user_id", "image_asset_id", "rack_id"):
        op.drop_index(f"ix_photo_readings_{column}", table_name="photo_readings")
    op.drop_table("photo_readings")
