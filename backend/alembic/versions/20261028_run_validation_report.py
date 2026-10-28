"""Keep each run's validation report on the run.

Revision ID: 20261028_run_validation_report
Revises: 20261028_rack_soft_delete
Create Date: 2026-10-28

Spec 001 FR-016/FR-019. A run that ends ``validation_failed`` saves no patches, so the
report has to live on the run itself to say why after the response is gone.
Additive only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261028_run_validation_report"
down_revision = "20261028_rack_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in inspect(op.get_bind()).get_columns("runs")}
    if "validation_report" not in columns:
        op.add_column("runs", sa.Column("validation_report", sa.JSON(), nullable=True))


def downgrade() -> None:
    columns = {c["name"] for c in inspect(op.get_bind()).get_columns("runs")}
    if "validation_report" in columns:
        op.drop_column("runs", "validation_report")
