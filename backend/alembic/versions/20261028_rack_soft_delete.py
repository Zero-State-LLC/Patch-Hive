"""Soft-delete racks; stop rack deletion from erasing runs and patches.

Revision ID: 20261028_rack_soft_delete
Revises: 20261027_catalog_lead_tags
Create Date: 2026-10-28

Spec 001 OQ-02. Runs, libraries and patches are append-only (ADR 0001), and
``rig_revisions.rig_id`` already RESTRICTs rack deletion, so deleting a rack that
ever generated failed on Postgres. Racks get ``deleted_at`` (the API hides a
deleted rack instead of deleting it), and ``runs.rack_id`` / ``patches.rack_id``
change from CASCADE to RESTRICT so nothing silently erases that history.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261028_rack_soft_delete"
down_revision = "20261027_catalog_lead_tags"
branch_labels = None
depends_on = None


def _rack_fk(table: str) -> str | None:
    for fk in inspect(op.get_bind()).get_foreign_keys(table):
        if fk.get("referred_table") == "racks" and fk.get("constrained_columns") == ["rack_id"]:
            return fk.get("name")
    return None


def _set_rack_fk(table: str, ondelete: str) -> None:
    name = _rack_fk(table)
    if name is None:
        return
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(name, type_="foreignkey")
        batch.create_foreign_key(name, "racks", ["rack_id"], ["id"], ondelete=ondelete)


def upgrade() -> None:
    columns = {c["name"] for c in inspect(op.get_bind()).get_columns("racks")}
    if "deleted_at" not in columns:
        op.add_column("racks", sa.Column("deleted_at", sa.DateTime(), nullable=True))
        op.create_index("ix_racks_deleted_at", "racks", ["deleted_at"], unique=False)
    _set_rack_fk("runs", "RESTRICT")
    _set_rack_fk("patches", "RESTRICT")


def downgrade() -> None:
    _set_rack_fk("patches", "CASCADE")
    _set_rack_fk("runs", "CASCADE")
    columns = {c["name"] for c in inspect(op.get_bind()).get_columns("racks")}
    if "deleted_at" in columns:
        op.drop_index("ix_racks_deleted_at", table_name="racks")
        op.drop_column("racks", "deleted_at")
