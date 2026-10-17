"""Add module verification status for catalog candidates.

Revision ID: 20261017_module_verification
Revises: 20260925_decision_receipts
Create Date: 2026-10-17

Additive only. Existing rows become ``unverified``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261017_module_verification"
down_revision = "20260925_decision_receipts"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    if table not in set(inspect(bind).get_table_names()):
        return set()
    return {column["name"] for column in inspect(bind).get_columns(table)}


def _indexes(table: str) -> set[str]:
    bind = op.get_bind()
    if table not in set(inspect(bind).get_table_names()):
        return set()
    return {index["name"] for index in inspect(bind).get_indexes(table)}


def upgrade() -> None:
    columns = _columns("modules")
    if not columns:
        return
    if "verification_status" not in columns:
        op.add_column(
            "modules",
            sa.Column(
                "verification_status",
                sa.String(length=20),
                nullable=False,
                server_default="unverified",
            ),
        )
    if "verification_source_url" not in columns:
        op.add_column(
            "modules",
            sa.Column("verification_source_url", sa.String(length=500), nullable=True),
        )
    bind = op.get_bind()
    constraint = "ck_modules_verification_status"
    existing = {item["name"] for item in inspect(bind).get_check_constraints("modules")}
    if constraint not in existing:
        op.create_check_constraint(
            constraint,
            "modules",
            "verification_status IN ('verified', 'corrected', 'flagged', 'unverified')",
        )
    if "ix_modules_verification_status" not in _indexes("modules"):
        op.create_index("ix_modules_verification_status", "modules", ["verification_status"])


def downgrade() -> None:
    columns = _columns("modules")
    if not columns:
        return
    indexes = _indexes("modules")
    if "ix_modules_verification_status" in indexes:
        op.drop_index("ix_modules_verification_status", table_name="modules")
    bind = op.get_bind()
    existing = {item["name"] for item in inspect(bind).get_check_constraints("modules")}
    if "ck_modules_verification_status" in existing:
        op.drop_constraint("ck_modules_verification_status", "modules", type_="check")
    if "verification_source_url" in columns:
        op.drop_column("modules", "verification_source_url")
    if "verification_status" in columns:
        op.drop_column("modules", "verification_status")
