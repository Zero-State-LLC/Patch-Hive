"""One-time credit checkout: provider customers, payment records, event object ids.

Revision ID: 20261102_credit_checkout
Revises: 20261101_user_deleted_at
Create Date: 2026-11-02

Spec 004 Machine B (T046):

- ``provider_customers`` maps each user to at most one provider customer (FR-020).
- ``provider_payments`` holds one record per one-time credit Checkout Session, unique on
  the session id and on the provider payment id once known (FR-012).
- ``stripe_event_records.object_id`` keeps the event's ``data.object.id`` so an operator
  resolve can retrieve the object later (T048b).

Additive only. Downgrade drops the two tables and the column; it refuses while any
payment record exists, because those rows are the provider-side evidence for canonical
``purchase`` entries.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261102_credit_checkout"
down_revision = "20261101_user_deleted_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stripe_event_records",
        sa.Column("object_id", sa.String(255), nullable=True),
    )
    op.create_index("ix_stripe_event_records_object_id", "stripe_event_records", ["object_id"])
    op.create_table(
        "provider_customers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider_customer_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_provider_customers_user_id"),
        sa.UniqueConstraint(
            "provider_customer_id", name="uq_provider_customers_provider_customer_id"
        ),
    )
    op.create_table(
        "provider_payments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("checkout_session_id", sa.String(255), nullable=False),
        sa.Column("provider_payment_id", sa.String(255), nullable=True),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("checkout_session_id", name="uq_provider_payments_checkout_session_id"),
        sa.UniqueConstraint("provider_payment_id", name="uq_provider_payments_provider_payment_id"),
        sa.CheckConstraint(
            "status IN ('open', 'pending', 'credited', 'failed', 'abandoned')",
            name="ck_provider_payments_status",
        ),
        sa.CheckConstraint("credits > 0", name="ck_provider_payments_credits_positive"),
        sa.CheckConstraint("amount_cents > 0", name="ck_provider_payments_amount_positive"),
    )
    op.create_index("ix_provider_payments_user_id", "provider_payments", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT COUNT(*) FROM provider_payments")).scalar() or 0
    if count:
        raise RuntimeError(
            "refusing to downgrade 20261102_credit_checkout: provider_payments has rows "
            "that back canonical purchase entries"
        )
    op.drop_index("ix_provider_payments_user_id", table_name="provider_payments")
    op.drop_table("provider_payments")
    op.drop_table("provider_customers")
    op.drop_index("ix_stripe_event_records_object_id", table_name="stripe_event_records")
    with op.batch_alter_table("stripe_event_records") as batch:
        batch.drop_column("object_id")
