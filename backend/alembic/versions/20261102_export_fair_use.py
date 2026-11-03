"""Exports covered by a STUDIO period grant (fair use).

Revision ID: 20261102_export_fair_use
Revises: 20261102_subscriptions
Create Date: 2026-11-02

Spec 004 T050 (FR-004, OQ-8 ``A_flag_with_fair_use``): ``canonical_exports`` gains a
nullable ``subscription_grant_id`` that points at the STUDIO ``subscription_period_grants``
row that covered the export in place of a debit. Exports pointing at a grant are what
the grant's ``fair_use_export_cap`` counts. Such an export costs no credits and has no
ledger entry (``ck_canonical_exports_grant_shape``).

Additive only. Downgrade refuses while any export points at a grant, because the column
is the only record of which exports used the fair-use allowance.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261102_export_fair_use"
down_revision = "20261102_subscriptions"
branch_labels = None
depends_on = None

_GRANT_SHAPE = "subscription_grant_id IS NULL OR (credit_cost = 0 AND ledger_entry_id IS NULL)"


def upgrade() -> None:
    with op.batch_alter_table("canonical_exports") as batch:
        batch.add_column(sa.Column("subscription_grant_id", sa.String(64), nullable=True))
        batch.create_foreign_key(
            "fk_canonical_exports_subscription_grant_id",
            "subscription_period_grants",
            ["subscription_grant_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint("ck_canonical_exports_grant_shape", _GRANT_SHAPE)
    op.create_index(
        "ix_canonical_exports_subscription_grant_id",
        "canonical_exports",
        ["subscription_grant_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    count = (
        bind.execute(
            sa.text("SELECT COUNT(*) FROM canonical_exports WHERE subscription_grant_id IS NOT NULL")
        ).scalar()
        or 0
    )
    if count:
        raise RuntimeError(
            "refusing to downgrade 20261102_export_fair_use: canonical_exports has rows "
            "covered by a STUDIO period grant"
        )
    op.drop_index("ix_canonical_exports_subscription_grant_id", table_name="canonical_exports")
    with op.batch_alter_table("canonical_exports") as batch:
        batch.drop_constraint("ck_canonical_exports_grant_shape", type_="check")
        batch.drop_constraint("fk_canonical_exports_subscription_grant_id", type_="foreignkey")
        batch.drop_column("subscription_grant_id")
