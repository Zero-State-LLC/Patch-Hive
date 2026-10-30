"""Tombstone catalog rows instead of deleting them.

Revision ID: 20261028_catalog_tombstones
Revises: 20261028_refresh_sessions
Create Date: 2026-10-28

``module_catalog`` gains ``tombstoned_at`` and ``tombstone_reason``, matching the
``modules.status = 'tombstoned'`` convention. The catalog loader never deletes; a
committed retirement manifest (data/synth-catalog/overlays/catalog-retirements-v*.json)
names each row it hides and why. Browse, search and counts skip tombstoned rows;
lookups by slug still answer. Additive only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261028_catalog_tombstones"
down_revision = "20261028_refresh_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in inspect(op.get_bind()).get_columns("module_catalog")}
    if "tombstoned_at" not in columns:
        op.add_column("module_catalog", sa.Column("tombstoned_at", sa.DateTime(), nullable=True))
        op.create_index("ix_module_catalog_tombstoned_at", "module_catalog", ["tombstoned_at"])
    if "tombstone_reason" not in columns:
        op.add_column("module_catalog", sa.Column("tombstone_reason", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_index("ix_module_catalog_tombstoned_at", table_name="module_catalog")
    op.drop_column("module_catalog", "tombstone_reason")
    op.drop_column("module_catalog", "tombstoned_at")
