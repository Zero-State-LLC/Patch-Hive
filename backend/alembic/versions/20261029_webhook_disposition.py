"""Record a final disposition for every provider webhook event.

Revision ID: 20261029_webhook_disposition
Revises: 20261029_ledger_append_only
Create Date: 2026-10-29

Spec 004 FR-014, T045, research R1: ``stripe_event_records`` gains ``reason_code``. The
webhook processor sets ``status`` to ``processed``, ``duplicate``, ``unresolved`` or
``ignored`` and sets ``processed_at``. Rows stored before the processor existed are still
``received``. Their payload was never stored, so they cannot be replayed; they become
``unresolved`` with reason ``RECEIVED_BEFORE_PROCESSOR`` for operator review. No event
stays ``received``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261029_webhook_disposition"
down_revision = "20261029_ledger_append_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stripe_event_records",
        sa.Column("reason_code", sa.String(64), nullable=True),
    )
    op.execute(
        """
        UPDATE stripe_event_records
        SET status = 'unresolved',
            reason_code = 'RECEIVED_BEFORE_PROCESSOR',
            processed_at = CURRENT_TIMESTAMP
        WHERE status = 'received'
        """
    )


def downgrade() -> None:
    # The backfilled rows keep their unresolved status: the processor's dispositions are
    # provenance and are not rewritten to "received".
    op.drop_column("stripe_event_records", "reason_code")
