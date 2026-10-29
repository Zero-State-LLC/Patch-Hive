"""Add idempotency_key to decision receipts with a unique (request_id, key) index.

Revision ID: 20261029_decision_receipt_idempotency
Revises: 20261029_ledger_append_only
Create Date: 2026-10-29

Spec 005 T083, research R5: the evidence decision-resolution path looks a receipt up by
``(request_id, idempotency_key)`` before the provider call. Existing receipts keep a NULL
key, which a unique index never treats as a duplicate. ``evidence_hash`` on new receipts is
a SHA-256 of the retained evidence packet and image; old rows are not rewritten (the table
is append-only).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261029_decision_receipt_idempotency"
down_revision = "20261029_ledger_append_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "decision_receipts",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "uq_decision_receipts_request_idempotency",
        "decision_receipts",
        ["request_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_decision_receipts_request_idempotency", table_name="decision_receipts")
    op.drop_column("decision_receipts", "idempotency_key")
