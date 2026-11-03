"""Subscriptions: provider subscription records and per-period grants.

Revision ID: 20261102_subscriptions
Revises: 20261102_purchase_refunds
Create Date: 2026-11-02

Spec 004 Machine C (T049):

- ``provider_subscriptions`` holds one record per provider subscription id: the tier
  (from the provider price), the provider status, the current period, the
  cancel-at-period-end flag (FR-015), the newest applied event time and when the first
  paid invoice was recorded as a purchase (OQ-3 ``A_both``).
- ``subscription_period_grants`` holds exactly one grant per subscription billing
  period (FR-016, SC-005), unique on the grant key, on the invoice and on the
  (subscription, period start) pair. CORE and PRO rows point at their canonical
  ``grant`` entry; a STUDIO row carries the unlimited entitlement and its fair-use cap
  instead of credits (FR-004, OQ-8).
- ``subscription_checkouts`` reserves the user's outstanding subscription checkout
  (Machine C ``CheckoutOpen``), so a repeated request reuses it instead of opening a
  second subscription.

Additive only. Downgrade refuses while any of the tables has rows, because they back
canonical grants and the subscription state an operator reviews.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261102_subscriptions"
down_revision = "20261102_purchase_refunds"
branch_labels = None
depends_on = None

_TIER_CHECK = "tier IN ('core', 'pro', 'studio')"
_STATUS_CHECK = (
    "status IN ('incomplete', 'incomplete_expired', 'trialing', 'active', 'past_due', "
    "'canceled', 'unpaid', 'paused')"
)
_CHECKOUT_STATUS_CHECK = "status IN ('open', 'completed', 'expired')"
_GRANT_SHAPE = (
    "(unlimited AND credits = 0 AND fair_use_export_cap >= 1 AND ledger_entry_id IS NULL) "
    "OR (NOT unlimited AND credits > 0 AND fair_use_export_cap IS NULL "
    "AND ledger_entry_id IS NOT NULL)"
)


def upgrade() -> None:
    op.create_table(
        "provider_subscriptions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider_subscription_id", sa.String(255), nullable=False),
        sa.Column("provider_customer_id", sa.String(255), nullable=False),
        sa.Column("price_id", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_event_created", sa.BigInteger(), nullable=True),
        sa.Column("purchase_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "provider_subscription_id",
            name="uq_provider_subscriptions_provider_subscription_id",
        ),
        sa.CheckConstraint(_TIER_CHECK, name="ck_provider_subscriptions_tier"),
        sa.CheckConstraint(_STATUS_CHECK, name="ck_provider_subscriptions_status"),
        sa.CheckConstraint(
            "current_period_end > current_period_start",
            name="ck_provider_subscriptions_period",
        ),
    )
    op.create_index("ix_provider_subscriptions_user_id", "provider_subscriptions", ["user_id"])
    op.create_table(
        "subscription_period_grants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "subscription_record_id",
            sa.String(64),
            sa.ForeignKey("provider_subscriptions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("grant_key", sa.String(128), nullable=False),
        sa.Column("provider_invoice_id", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("unlimited", sa.Boolean(), nullable=False),
        sa.Column("fair_use_export_cap", sa.Integer(), nullable=True),
        sa.Column(
            "ledger_entry_id",
            sa.String(64),
            sa.ForeignKey("canonical_credit_ledger.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("grant_key", name="uq_subscription_period_grants_grant_key"),
        sa.UniqueConstraint(
            "provider_invoice_id", name="uq_subscription_period_grants_provider_invoice_id"
        ),
        sa.UniqueConstraint(
            "ledger_entry_id", name="uq_subscription_period_grants_ledger_entry_id"
        ),
        sa.UniqueConstraint(
            "subscription_record_id",
            "period_start",
            name="uq_subscription_period_grants_period",
        ),
        sa.CheckConstraint(_TIER_CHECK, name="ck_subscription_period_grants_tier"),
        sa.CheckConstraint(_GRANT_SHAPE, name="ck_subscription_period_grants_shape"),
        sa.CheckConstraint(
            "period_end > period_start", name="ck_subscription_period_grants_period"
        ),
    )
    op.create_index(
        "ix_subscription_period_grants_subscription_record_id",
        "subscription_period_grants",
        ["subscription_record_id"],
    )
    op.create_index(
        "ix_subscription_period_grants_user_id", "subscription_period_grants", ["user_id"]
    )
    op.create_table(
        "subscription_checkouts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("checkout_session_id", sa.String(255), nullable=False),
        sa.Column("checkout_url", sa.Text(), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider_subscription_id", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "checkout_session_id", name="uq_subscription_checkouts_checkout_session_id"
        ),
        sa.CheckConstraint(_TIER_CHECK, name="ck_subscription_checkouts_tier"),
        sa.CheckConstraint(_CHECKOUT_STATUS_CHECK, name="ck_subscription_checkouts_status"),
    )
    op.create_index("ix_subscription_checkouts_user_id", "subscription_checkouts", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("subscription_period_grants", "provider_subscriptions", "subscription_checkouts"):
        count = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
        if count:
            raise RuntimeError(
                f"refusing to downgrade 20261102_subscriptions: {table} has rows that back "
                "canonical subscription grants"
            )
    op.drop_index("ix_subscription_checkouts_user_id", table_name="subscription_checkouts")
    op.drop_table("subscription_checkouts")
    op.drop_index("ix_subscription_period_grants_user_id", table_name="subscription_period_grants")
    op.drop_index(
        "ix_subscription_period_grants_subscription_record_id",
        table_name="subscription_period_grants",
    )
    op.drop_table("subscription_period_grants")
    op.drop_index("ix_provider_subscriptions_user_id", table_name="provider_subscriptions")
    op.drop_table("provider_subscriptions")
