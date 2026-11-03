"""Mark anonymized (deleted) accounts.

Revision ID: 20261101_user_deleted_at
Revises: 20261030_power_configs
Create Date: 2026-11-01

Spec 004 OQ-12 / EC-8, decided ``A_anonymize_keep``: deleting an account strips the
user's personal fields and keeps the row, because the append-only canonical ledger
references it with ``ON DELETE RESTRICT``. ``users.deleted_at`` records when that
happened, so a deleted account is told apart from a live one. Additive only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261101_user_deleted_at"
down_revision = "20261030_power_configs"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns("users")}


def upgrade() -> None:
    if "deleted_at" not in _columns():
        op.add_column("users", sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    if "deleted_at" in _columns():
        with op.batch_alter_table("users") as batch:
            batch.drop_column("deleted_at")
