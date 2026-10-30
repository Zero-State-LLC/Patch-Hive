"""Add decision_receipt_keys: one accepted idempotency key per (request, key).

Revision ID: 20261029_decision_receipt_idempotency
Revises: 20261029_rig_metrics_packets
Create Date: 2026-10-29

Spec 005 T083, research R5: the evidence decision-resolution path looks a key up before
the provider call. ``decision_receipts`` is append-only and a receipt can answer several
keys (a provider decision id can recur), so keys are bound in their own table whose
primary key is ``(request_id, idempotency_key)``. ``evidence_hash`` on new receipts is a
SHA-256 of the retained evidence packet and image; old rows are not rewritten.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261029_decision_receipt_idempotency"
down_revision = "20261029_rig_metrics_packets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_receipt_keys",
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "receipt_id",
            sa.String(length=64),
            sa.ForeignKey("decision_receipts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("request_id", "idempotency_key"),
    )
    op.create_index(
        "ix_decision_receipt_keys_receipt_id", "decision_receipt_keys", ["receipt_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_decision_receipt_keys_receipt_id", table_name="decision_receipt_keys")
    op.drop_table("decision_receipt_keys")
