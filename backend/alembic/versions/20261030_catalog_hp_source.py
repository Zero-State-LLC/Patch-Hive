"""Mark catalog HP values that come only from the unsourced legacy overlay.

Revision ID: 20261030_catalog_hp_source
Revises: 20261029_decision_receipt_idempotency
Create Date: 2026-10-30

``module_catalog`` gains a nullable ``hp_source``. The catalog loader sets it to
``legacy_unsourced`` where the stored HP is a value from the unsourced v1 HP overlay
that no maker page in the dataset backs yet, and clears it once one does (spec 003
T039). NULL means not marked. Additive only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261030_catalog_hp_source"
down_revision = "20261029_decision_receipt_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in inspect(op.get_bind()).get_columns("module_catalog")}
    if "hp_source" not in columns:
        op.add_column("module_catalog", sa.Column("hp_source", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("module_catalog", "hp_source")
