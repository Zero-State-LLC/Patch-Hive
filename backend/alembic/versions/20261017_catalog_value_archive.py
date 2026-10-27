"""Catalog value archive and needs_reverify flags.

Revision ID: 20261017_catalog_value_archive
Revises: 20261017_module_verification
Create Date: 2026-10-17

Additive only. ``catalog_value_archive`` keeps every old spec value (with its
source tag) before the loader nulls or relabels it, so nothing is lost.
``needs_reverify`` marks rows whose ModularGrid-derived values were removed.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261017_catalog_value_archive"
down_revision = "20261017_module_verification"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "catalog_value_archive" not in _tables():
        op.create_table(
            "catalog_value_archive",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("batch", sa.String(64), nullable=False),
            sa.Column("table_name", sa.String(64), nullable=False),
            sa.Column("row_key", sa.String(400), nullable=False),
            sa.Column("brand", sa.String(100), nullable=True),
            sa.Column("name", sa.String(200), nullable=True),
            sa.Column("field", sa.String(64), nullable=False),
            sa.Column("old_value", sa.Text, nullable=True),
            sa.Column("source_tag", sa.String(200), nullable=False),
            sa.Column("maker_check", sa.String(40), nullable=True),
            sa.Column("action", sa.String(20), nullable=False),
            sa.Column("archived_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("batch", "table_name", "row_key", "field", name="uq_catalog_value_archive_key"),
        )
        op.create_index("ix_catalog_value_archive_row", "catalog_value_archive", ["table_name", "row_key"])
    for table in ("modules", "module_catalog"):
        columns = _columns(table)
        if columns and "needs_reverify" not in columns:
            op.add_column(
                table,
                sa.Column("needs_reverify", sa.Boolean, nullable=False, server_default=sa.false()),
            )


def downgrade() -> None:
    # Keep the archive on downgrade: it holds the only copy of removed values.
    for table in ("modules", "module_catalog"):
        if "needs_reverify" in _columns(table):
            op.drop_column(table, "needs_reverify")
