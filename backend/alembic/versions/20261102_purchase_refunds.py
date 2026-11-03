"""Purchase refunds: refund totals and refund states on provider payment records.

Revision ID: 20261102_purchase_refunds
Revises: 20261102_credit_checkout
Create Date: 2026-11-02

Spec 004 OQ-2 ``A_reverse_unspent`` (T053):

- ``provider_payments.refunded_cents`` is the highest cumulative refunded amount applied
  from ``charge.refunded``; ``refund_reversed_credits`` and
  ``refund_unrecovered_credits`` split the credits that amount takes back into those
  reversed with a canonical ``refund`` entry and those already spent (operator review).
- ``ck_provider_payments_status`` gains ``partially_refunded`` and ``refunded``.

Additive: existing rows get zero refund totals. Downgrade refuses while any payment has
a refund recorded, because those totals back canonical ``refund`` entries.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261102_purchase_refunds"
down_revision = "20261102_credit_checkout"
branch_labels = None
depends_on = None

_OLD_STATUSES = "status IN ('open', 'pending', 'credited', 'failed', 'abandoned')"
_NEW_STATUSES = (
    "status IN ('open', 'pending', 'credited', 'failed', 'abandoned', "
    "'partially_refunded', 'refunded')"
)


def upgrade() -> None:
    with op.batch_alter_table("provider_payments") as batch:
        for name in ("refunded_cents", "refund_reversed_credits", "refund_unrecovered_credits"):
            batch.add_column(sa.Column(name, sa.Integer(), nullable=False, server_default="0"))
        batch.drop_constraint("ck_provider_payments_status", type_="check")
        batch.create_check_constraint("ck_provider_payments_status", _NEW_STATUSES)
        batch.create_check_constraint(
            "ck_provider_payments_refunded_cents",
            "refunded_cents >= 0 AND refunded_cents <= amount_cents",
        )
        batch.create_check_constraint(
            "ck_provider_payments_refund_credits",
            "refund_reversed_credits >= 0 AND refund_unrecovered_credits >= 0 "
            "AND refund_reversed_credits + refund_unrecovered_credits <= credits",
        )


def downgrade() -> None:
    bind = op.get_bind()
    count = (
        bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM provider_payments WHERE refunded_cents > 0 "
                "OR status IN ('partially_refunded', 'refunded')"
            )
        ).scalar()
        or 0
    )
    if count:
        raise RuntimeError(
            "refusing to downgrade 20261102_purchase_refunds: provider_payments has refunds "
            "that back canonical refund entries"
        )
    with op.batch_alter_table("provider_payments") as batch:
        batch.drop_constraint("ck_provider_payments_refund_credits", type_="check")
        batch.drop_constraint("ck_provider_payments_refunded_cents", type_="check")
        batch.drop_constraint("ck_provider_payments_status", type_="check")
        batch.create_check_constraint("ck_provider_payments_status", _OLD_STATUSES)
        for name in ("refund_unrecovered_credits", "refund_reversed_credits", "refunded_cents"):
            batch.drop_column(name)
